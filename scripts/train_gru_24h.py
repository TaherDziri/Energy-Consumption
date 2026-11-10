"""train_gru_24h.py
GRU 48 h -> 24 h (multi-step direct). CPU, seed fixe.
Entrainement + selection sur VAL uniquement. NE LIT JAMAIS le TEST.
Test : scripts/eval_gru_24h_test.py, a lancer UNE seule fois.

Usage :
  python scripts/train_gru_24h.py --tag runA_l1    --loss l1 --calendar 0
  python scripts/train_gru_24h.py --tag runB_l1cal --loss l1 --calendar 1
"""
import argparse
import json
import os
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

SEED = 42
os.environ["PYTHONHASHSEED"] = str(SEED)
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.use_deterministic_algorithms(True, warn_only=True)
torch.set_num_threads(4)

D = Path("data/processed/dl")
LOOKBACK, HORIZON = 48, 24
HIDDEN, LAYERS = 64, 1
BATCH, LR = 128, 1e-3
EPOCHS, PATIENCE = 40, 8


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--tag", required=True)
    p.add_argument("--loss", choices=["mse", "l1", "huber"], default="mse")
    p.add_argument("--calendar", type=int, choices=[0, 1], default=0)
    p.add_argument("--hidden", type=int, default=HIDDEN)
    p.add_argument("--layers", type=int, default=LAYERS)
    p.add_argument("--epochs", type=int, default=EPOCHS)
    p.add_argument("--patience", type=int, default=PATIENCE)
    return p.parse_args()


ARGS = parse_args()
TAG = ARGS.tag
LOSS = ARGS.loss
CALENDAR = bool(ARGS.calendar)
MONITOR = "mae" if LOSS in ("l1", "huber") else "mse"

MODEL_OUT = Path("models") / f"gru_24h_{TAG}.pt"
HIST_OUT = D / f"gru_24h_{TAG}_history.csv"
VAL_PRED_OUT = D / f"gru_24h_{TAG}_val_preds.parquet"
SUMMARY_OUT = D / f"gru_24h_{TAG}_summary.json"


def calendar_features(target_hour, lookback):
    base = pd.to_datetime(target_hour)
    offs = np.arange(-lookback, 0) * np.timedelta64(1, "h")
    ts = pd.DatetimeIndex((base.values[:, None] + offs).ravel())
    hod = ts.hour.to_numpy().reshape(len(target_hour), lookback)
    dow = ts.dayofweek.to_numpy().reshape(len(target_hour), lookback)
    return np.stack([
        np.sin(2.0 * np.pi * hod / 24.0),
        np.cos(2.0 * np.pi * hod / 24.0),
        np.sin(2.0 * np.pi * dow / 7.0),
        np.cos(2.0 * np.pi * dow / 7.0),
    ], axis=-1).astype("float32")


d = np.load(D / "windows_48to24.npz")
Xz = d["X"].astype("float32")           # (N,48) z-score
Yz = d["Y"].astype("float32")           # (N,24) z-score
tgt = d["target_hour"]
hid = d["LCLid"].astype(str)
split = d["split"].astype(str)

st = pd.read_csv(D / "scalers.csv").set_index("LCLid")
mu = np.array([st.loc[h, "mean"] for h in hid], dtype="float64")
sd = np.array([st.loc[h, "std"] for h in hid], dtype="float64")

if CALENDAR:
    cal = calendar_features(tgt, LOOKBACK)          # (N,48,4)
    X3np = np.concatenate([Xz[:, :, None], cal], axis=2)
else:
    X3np = Xz[:, :, None]
IN = X3np.shape[2]
print(f"run {TAG} | loss {LOSS} | calendar {CALENDAR} | input_size {IN}")

X3 = torch.from_numpy(X3np.astype("float32"))
Yt = torch.from_numpy(Yz)
tr = torch.from_numpy(split == "train")
va = torch.from_numpy(split == "val")
idx_va = np.flatnonzero(split == "val")

mu_va, sd_va = mu[idx_va], sd[idx_va]
Y_va_kwh = Yz[idx_va].astype("float64") * sd_va[:, None] + mu_va[:, None]
sais_va_kwh = Xz[idx_va, 24:48].astype("float64") * sd_va[:, None] + mu_va[:, None]
sais_mae = float(np.mean(np.abs(Y_va_kwh - sais_va_kwh)))
sais_rmse = float(np.sqrt(np.mean((Y_va_kwh - sais_va_kwh) ** 2)))
print(f"VAL saisonnier : MAE {sais_mae:.4f} | RMSE {sais_rmse:.4f}")


class GRU24(nn.Module):
    def __init__(self, inp, hidden, layers):
        super().__init__()
        self.gru = nn.GRU(inp, hidden, layers, batch_first=True)
        self.head = nn.Linear(hidden, HORIZON)

    def forward(self, x):
        out, _ = self.gru(x)
        return self.head(out[:, -1, :])


if LOSS == "mse":
    lossf = nn.MSELoss()
elif LOSS == "l1":
    lossf = nn.L1Loss()
else:
    lossf = nn.HuberLoss(delta=1.0)

g = torch.Generator().manual_seed(SEED)
ds_tr = TensorDataset(X3[tr], Yt[tr])
ds_va = TensorDataset(X3[va], Yt[va])
dl_tr = DataLoader(ds_tr, batch_size=BATCH, shuffle=True, generator=g, num_workers=0)
dl_va = DataLoader(ds_va, batch_size=512, shuffle=False, num_workers=0)


def val_metrics(model):
    model.eval()
    out = []
    with torch.no_grad():
        for xb, _ in dl_va:
            out.append(model(xb).numpy())
    pred_z = np.concatenate(out, axis=0)
    p = pred_z.astype("float64") * sd_va[:, None] + mu_va[:, None]
    e = Y_va_kwh - p
    return (float(np.mean(np.abs(e))), float(np.sqrt(np.mean(e ** 2))),
            float(np.mean(e ** 2)), pred_z)


model = GRU24(IN, ARGS.hidden, ARGS.layers)
opt = torch.optim.Adam(model.parameters(), lr=LR)

best, best_state, best_ep, bad = float("inf"), None, 0, 0
hist = []
for ep in range(1, ARGS.epochs + 1):
    model.train()
    tot = 0.0
    for xb, yb in dl_tr:
        opt.zero_grad()
        loss = lossf(model(xb), yb)
        loss.backward()
        opt.step()
        tot += loss.item() * len(xb)
    train_loss = tot / len(ds_tr)
    v_mae, v_rmse, v_mse, _ = val_metrics(model)
    score = v_mae if MONITOR == "mae" else v_mse
    hist.append((ep, train_loss, v_mae, v_rmse, v_mse))
    print(f"epoch {ep:02d} | train {train_loss:.5f} | val MAE {v_mae:.4f} | val RMSE {v_rmse:.4f}")
    if score < best - 1e-5:
        best, best_ep, bad = score, ep, 0
        best_state = {k: t.clone() for k, t in model.state_dict().items()}
    else:
        bad += 1
        if bad >= ARGS.patience:
            print(f"early stopping a l'epoque {ep} (meilleur {MONITOR} {best:.5f}, ep {best_ep})")
            break

assert best_state is not None
model.load_state_dict(best_state)
v_mae, v_rmse, v_mse, val_pred_z = val_metrics(model)
print(f"\nmeilleur modele : epoque {best_ep} | val MAE {v_mae:.4f} | val RMSE {v_rmse:.4f}")
print(f"VAL GRU        : MAE {v_mae:.4f} | RMSE {v_rmse:.4f}")
print(f"VAL saisonnier : MAE {sais_mae:.4f} | RMSE {sais_rmse:.4f}")
print(f"bat le saisonnier sur VAL (MAE) : {bool(v_mae < sais_mae)}")

MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
torch.save({
    "state_dict": model.state_dict(),
    "hparams": {
        "tag": TAG, "loss": LOSS, "calendar": CALENDAR,
        "input_size": IN, "lookback": LOOKBACK, "horizon": HORIZON,
        "hidden": ARGS.hidden, "layers": ARGS.layers, "seed": SEED,
        "monitor": MONITOR, "best_epoch": best_ep,
        "val_mae": v_mae, "val_rmse": v_rmse, "val_mse": v_mse,
    },
}, MODEL_OUT)

pd.DataFrame(hist, columns=["epoch", "train_loss", "val_mae", "val_rmse", "val_mse"]).to_csv(HIST_OUT, index=False)

val_pred_kwh = val_pred_z.astype("float64") * sd_va[:, None] + mu_va[:, None]
pd.DataFrame({
    "LCLid": np.repeat(hid[idx_va], HORIZON),
    "target_hour": np.repeat(pd.to_datetime(tgt[idx_va]), HORIZON),
    "horizon_h": np.tile(np.arange(1, HORIZON + 1), len(idx_va)),
    "y_true_kwh": Y_va_kwh.ravel(),
    "y_pred_kwh": val_pred_kwh.ravel(),
    "y_seasonal_kwh": sais_va_kwh.ravel(),
}).to_parquet(VAL_PRED_OUT, index=False)

summary = {
    "tag": TAG, "loss": LOSS, "calendar": CALENDAR, "input_size": IN,
    "best_epoch": best_ep, "monitor": MONITOR, "best_score": best,
    "val_gru_mae": v_mae, "val_gru_rmse": v_rmse, "val_gru_mse": v_mse,
    "val_saisonnier_mae": sais_mae, "val_saisonnier_rmse": sais_rmse,
    "beats_seasonal_val_mae": bool(v_mae < sais_mae),
    "seed": SEED, "hidden": ARGS.hidden, "layers": ARGS.layers,
    "n_train": int(tr.sum()), "n_val": int(len(idx_va)),
}
SUMMARY_OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")

print("\necrit :", MODEL_OUT)
print("        ", HIST_OUT)
print("        ", VAL_PRED_OUT)
print("        ", SUMMARY_OUT)
print("TEST non lu par ce script.")