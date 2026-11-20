#!/usr/bin/env python3
"""
Phase 4.3 - Train an LSTM or GRU forecaster.

Input : data/processed/tensors/{train,val,test}.npz
        data/processed/tensors/summary.json  (per-household scalers)
Output: data/processed/models/{model}/best.pt, history.json, metrics.json

Task: X (336, 2) -> y (48).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class RNNForecaster(nn.Module):
    def __init__(
        self,
        cell: str,
        input_size: int = 2,
        hidden_size: int = 64,
        num_layers: int = 1,
        output_size: int = 48,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        rnn_cls = nn.LSTM if cell == "lstm" else nn.GRU
        self.rnn = rnn_cls(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Linear(hidden_size, output_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.rnn(x)
        return self.head(out[:, -1, :])


def make_loader(
    path: Path,
    batch_size: int,
    shuffle: bool,
    generator: torch.Generator | None,
    num_workers: int,
) -> tuple[DataLoader, np.ndarray]:
    data = np.load(path, allow_pickle=False)
    X = torch.from_numpy(data["X"]).float()
    y = torch.from_numpy(data["y"]).float()
    households = data["household"]
    dataset = TensorDataset(X, y, torch.arange(len(X)))
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        generator=generator,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
        drop_last=False,
    )
    return loader, households


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    households: np.ndarray,
    scalers: dict[str, dict[str, float]],
    device: torch.device,
) -> dict[str, float]:
    model.eval()
    loss_sum = 0.0
    abs_sum = 0.0
    sq_sum = 0.0
    y_sum = 0.0
    count = 0
    for xb, yb, idx in loader:
        xb = xb.to(device, non_blocking=True)
        yb = yb.to(device, non_blocking=True)
        pred = model(xb)
        loss_sum += nn.functional.mse_loss(pred, yb, reduction="sum").item()

        names = [str(households[i]) for i in idx.tolist()]
        mean = torch.tensor(
            [scalers[name]["mean"] for name in names],
            device=device,
            dtype=torch.float32,
        ).unsqueeze(1)
        std = torch.tensor(
            [scalers[name]["std"] for name in names],
            device=device,
            dtype=torch.float32,
        ).unsqueeze(1)
        pred_kwh = pred * std + mean
        true_kwh = yb * std + mean
        abs_sum += (pred_kwh - true_kwh).abs().sum().item()
        sq_sum += ((pred_kwh - true_kwh) ** 2).sum().item()
        y_sum += true_kwh.sum().item()
        count += true_kwh.numel()

    mse = loss_sum / count
    mae = abs_sum / count
    rmse = math.sqrt(sq_sum / count)
    mean_y = y_sum / count
    return {
        "mse_scaled": mse,
        "mae_kwh": mae,
        "rmse_kwh": rmse,
        "nrmse": rmse / mean_y if mean_y > 0 else float("nan"),
        "mean_kwh": mean_y,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tensors-dir", type=Path, default=Path("data/processed/tensors"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/processed/models"))
    parser.add_argument("--model", choices=["lstm", "gru"], default="lstm")
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=1)
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--max-epochs", type=int, default=80)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--min-delta", type=float, default=1e-5)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-workers", type=int, default=0)
    args = parser.parse_args()

    started = time.time()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = True

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out_dir = args.out_dir / args.model
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] loading tensors from {args.tensors_dir} ...", flush=True)
    generator = torch.Generator()
    generator.manual_seed(args.seed)
    train_loader, train_households = make_loader(
        args.tensors_dir / "train.npz",
        args.batch_size,
        True,
        generator,
        args.num_workers,
    )
    val_loader, val_households = make_loader(
        args.tensors_dir / "val.npz",
        args.batch_size,
        False,
        None,
        args.num_workers,
    )
    test_loader, test_households = make_loader(
        args.tensors_dir / "test.npz",
        args.batch_size,
        False,
        None,
        args.num_workers,
    )
    scalers = json.loads(
        (args.tensors_dir / "summary.json").read_text(encoding="utf-8")
    )["scalers"]
    print(
        f"      train={len(train_loader.dataset):,} "
        f"val={len(val_loader.dataset):,} "
        f"test={len(test_loader.dataset):,} "
        f"| device={device}",
        flush=True,
    )

    model_config = {
        "cell": args.model,
        "input_size": 2,
        "hidden_size": args.hidden_size,
        "num_layers": args.num_layers,
        "output_size": 48,
        "dropout": args.dropout,
    }
    model = RNNForecaster(**model_config).to(device)
    parameters = sum(p.numel() for p in model.parameters())
    print(f"[2/4] model {args.model.upper()} | parameters={parameters:,}", flush=True)

    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=4
    )

    print("[3/4] training ...", flush=True)
    history: list[dict] = []
    best_val = float("inf")
    best_epoch = 0
    stale = 0

    for epoch in range(1, args.max_epochs + 1):
        model.train()
        loss_sum = 0.0
        count = 0
        for xb, yb, _ in train_loader:
            xb = xb.to(device, non_blocking=True)
            yb = yb.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optimizer.step()
            loss_sum += loss.item() * yb.numel()
            count += yb.numel()
        train_mse = loss_sum / count

        val = evaluate(model, val_loader, val_households, scalers, device)
        scheduler.step(val["mse_scaled"])
        lr = optimizer.param_groups[0]["lr"]
        history.append(
            {
                "epoch": epoch,
                "train_mse_scaled": train_mse,
                **val,
                "lr": lr,
            }
        )
        print(
            f"      epoch {epoch:03d} | train {train_mse:.5f} | "
            f"val {val['mse_scaled']:.5f} | mae {val['mae_kwh']:.4f} | "
            f"rmse {val['rmse_kwh']:.4f} | lr {lr:.2e}",
            flush=True,
        )

        if val["mse_scaled"] < best_val - args.min_delta:
            best_val = val["mse_scaled"]
            best_epoch = epoch
            stale = 0
            torch.save(
                {
                    "model": model.state_dict(),
                    "config": model_config,
                    "epoch": epoch,
                    "val": val,
                },
                out_dir / "best.pt",
            )
        else:
            stale += 1
            if stale >= args.patience:
                print(f"      early stopping at epoch {epoch}", flush=True)
                break

    print("[4/4] evaluating the best checkpoint ...", flush=True)
    checkpoint = torch.load(
        out_dir / "best.pt", map_location=device, weights_only=True
    )
    model.load_state_dict(checkpoint["model"])
    train_metrics = evaluate(model, train_loader, train_households, scalers, device)
    val_metrics = evaluate(model, val_loader, val_households, scalers, device)
    test_metrics = evaluate(model, test_loader, test_households, scalers, device)

    metrics = {
        "model": args.model,
        "config": model_config,
        "training": {
            "batch_size": args.batch_size,
            "max_epochs": args.max_epochs,
            "patience": args.patience,
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "grad_clip": args.grad_clip,
            "seed": args.seed,
            "best_epoch": best_epoch,
            "epochs_run": len(history),
            "parameters": parameters,
            "device": str(device),
        },
        "train": train_metrics,
        "val": val_metrics,
        "test": test_metrics,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    (out_dir / "history.json").write_text(
        json.dumps(history, indent=2), encoding="utf-8"
    )
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )

    print(f"\nDONE in {metrics['elapsed_seconds'] / 60:.1f} min", flush=True)
    print(f"  model       : {args.model.upper()}", flush=True)
    print(f"  best epoch  : {best_epoch} / {len(history)}", flush=True)
    print(
        f"  val  MAE    : {val_metrics['mae_kwh']:.4f} kWh | "
        f"RMSE {val_metrics['rmse_kwh']:.4f} kWh | "
        f"nRMSE {val_metrics['nrmse']:.3f}",
        flush=True,
    )
    print(
        f"  test MAE    : {test_metrics['mae_kwh']:.4f} kWh | "
        f"RMSE {test_metrics['rmse_kwh']:.4f} kWh | "
        f"nRMSE {test_metrics['nrmse']:.3f}",
        flush=True,
    )
    print(f"  output      : {out_dir}", flush=True)


if __name__ == "__main__":
    main()