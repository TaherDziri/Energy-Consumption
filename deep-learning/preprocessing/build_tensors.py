#!/usr/bin/env python3
"""
Phase 4.2 - Build supervised tensors for the LSTM.

Input : data/processed/halfhourly_series/halfhourly_series.parquet (UTC)
Output: data/processed/tensors/{train,val,test}.npz + summary.json

Task: 336 half-hours in (7 days) -> 48 half-hours out (next day).

Rules:
  - parquet timestamps are UTC; convert to Europe/London
  - local calendar grid at 00:00, 48 steps per day
  - DST transition days are excluded from input/target windows
  - gaps of 1-2 consecutive steps are linearly interpolated (time-based)
  - channel 0 = scaled kWh, channel 1 = observed mask (1 = real reading)
  - long gaps stay missing (value 0 after scaling, mask 0)
  - target day must be 100% observed
  - input window must be >= 80% observed
  - per-household z-score fitted on the training period only
  - chronological split by target date
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "Europe/London"
DST_DATES = {
    pd.Timestamp("2012-03-25").date(),
    pd.Timestamp("2012-10-28").date(),
    pd.Timestamp("2013-03-31").date(),
    pd.Timestamp("2013-10-27").date(),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--series",
        type=Path,
        default=Path("data/processed/halfhourly_series/halfhourly_series.parquet"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed/tensors"),
    )
    parser.add_argument("--train-end", default="2013-06-30")
    parser.add_argument("--val-end", default="2013-10-31")
    parser.add_argument("--input-days", type=int, default=7)
    parser.add_argument("--min-input-observed", type=float, default=0.8)
    args = parser.parse_args()

    started = time.time()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    input_steps = args.input_days * 48
    train_end = pd.Timestamp(args.train_end)
    val_end = pd.Timestamp(args.val_end)

    # ------------------------------------------------------------------ read
    print(f"[1/5] reading {args.series} ...", flush=True)
    frame = pd.read_parquet(
        args.series, columns=["household_id", "timestamp", "kwh"]
    )
    frame["timestamp"] = (
        pd.to_datetime(frame["timestamp"])
        .dt.tz_localize("UTC")
        .dt.tz_convert(TZ)
        .dt.tz_localize(None)
    )
    frame = frame.sort_values(
        ["household_id", "timestamp"], kind="mergesort"
    ).reset_index(drop=True)
    print(
        f"      {len(frame):,} rows, "
        f"{frame['household_id'].nunique()} households "
        f"(UTC -> {TZ})",
        flush=True,
    )

    # ------------------------------------------------------- daily matrices
    print("[2/5] building 48-step local daily matrices ...", flush=True)
    days: dict[str, dict] = {}
    for household, group in frame.groupby("household_id", sort=True):
        stamps = pd.DatetimeIndex(group["timestamp"])
        first = stamps.min().normalize()
        last = stamps.max().normalize()
        grid = pd.date_range(
            first,
            last + pd.Timedelta(hours=23, minutes=30),
            freq="30min",
        )
        series = pd.Series(group["kwh"].to_numpy(), index=stamps)
        # fall-back day maps two UTC half-hours to one local timestamp
        series = series.groupby(level=0).mean()
        series = series.reindex(grid)

        observed = series.notna().to_numpy()
        filled = series.interpolate(
            method="time", limit=2, limit_area="inside"
        )

        n_days = (last - first).days + 1
        values = filled.to_numpy(dtype="float64")
        if values.size != n_days * 48:
            raise RuntimeError(
                f"{household}: grid has {values.size} steps, "
                f"expected {n_days * 48}"
            )

        dates = pd.date_range(first, last, freq="D")
        is_dst = np.array(
            [day.date() in DST_DATES for day in dates], dtype=bool
        )
        days[household] = {
            "values": values.reshape(n_days, 48),
            "mask": observed.astype("float32").reshape(n_days, 48),
            "dates": dates,
            "is_dst": is_dst,
        }
    print(f"      {len(days)} households on a local calendar grid", flush=True)

    # ------------------------------------------------------------- scaling
    print("[3/5] fitting per-household scalers on the training period ...", flush=True)
    scalers: dict[str, dict[str, float]] = {}
    for household, block in days.items():
        in_train = block["dates"] <= train_end
        observed = block["mask"][in_train].astype(bool)
        values = block["values"][in_train][observed]
        values = values[np.isfinite(values)]
        if values.size == 0:
            raise RuntimeError(
                f"{household}: no observed value in the training period"
            )
        mean = float(values.mean())
        std = float(values.std())
        if not np.isfinite(std) or std < 1e-6:
            std = 1.0
        scalers[household] = {"mean": mean, "std": std}
        scaled = (block["values"] - mean) / std
        block["values"] = np.nan_to_num(
            scaled, nan=0.0, posinf=0.0, neginf=0.0
        )

    # ------------------------------------------------------------- windows
    print("[4/5] building sliding windows ...", flush=True)
    x_rows: list[np.ndarray] = []
    y_rows: list[np.ndarray] = []
    households: list[str] = []
    target_dates: list[pd.Timestamp] = []
    skipped_target = 0
    skipped_input = 0
    skipped_dst = 0

    for household, block in days.items():
        values = block["values"]
        mask = block["mask"]
        dates = block["dates"]
        is_dst = block["is_dst"]
        for i in range(args.input_days, len(dates)):
            if bool(is_dst[i - args.input_days : i + 1].any()):
                skipped_dst += 1
                continue
            if int(mask[i].sum()) != 48:
                skipped_target += 1
                continue
            window = slice(i - args.input_days, i)
            if float(mask[window].sum()) < args.min_input_observed * input_steps:
                skipped_input += 1
                continue

            x_rows.append(
                np.stack(
                    [
                        values[window].reshape(-1),
                        mask[window].reshape(-1),
                    ],
                    axis=1,
                ).astype("float32")
            )
            y_rows.append(values[i].astype("float32"))
            households.append(str(household))
            target_dates.append(dates[i])

    if not x_rows:
        raise SystemExit("no samples built: relax the filters")

    X = np.stack(x_rows)
    y = np.stack(y_rows)
    household = np.array(households)
    target_date = np.array(target_dates, dtype="datetime64[D]")
    del x_rows, y_rows

    print(
        f"      {len(X):,} samples "
        f"(skipped: {skipped_target:,} incomplete target days, "
        f"{skipped_input:,} sparse input windows, "
        f"{skipped_dst:,} DST windows)",
        flush=True,
    )

    # --------------------------------------------------------------- split
    train_end_np = np.datetime64(args.train_end)
    val_end_np = np.datetime64(args.val_end)
    train_idx = np.where(target_date <= train_end_np)[0]
    val_idx = np.where(
        (target_date > train_end_np) & (target_date <= val_end_np)
    )[0]
    test_idx = np.where(target_date > val_end_np)[0]

    if len(train_idx) == 0 or len(val_idx) == 0 or len(test_idx) == 0:
        raise SystemExit(
            f"empty split: train={len(train_idx)}, "
            f"val={len(val_idx)}, test={len(test_idx)}"
        )

    # ---------------------------------------------------------------- save
    print("[5/5] saving arrays and summary ...", flush=True)
    splits = {"train": train_idx, "val": val_idx, "test": test_idx}
    for name, index in splits.items():
        np.savez_compressed(
            args.out_dir / f"{name}.npz",
            X=X[index],
            y=y[index],
            household=household[index],
            target_date=target_date[index],
        )

    def split_info(index: np.ndarray) -> dict:
        if index.size == 0:
            return {"samples": 0}
        return {
            "samples": int(index.size),
            "households": int(np.unique(household[index]).size),
            "first_target_date": str(target_date[index].min()),
            "last_target_date": str(target_date[index].max()),
        }

    index = int(test_idx[0])
    key = str(household[index])
    mean = scalers[key]["mean"]
    std = scalers[key]["std"]
    kwh = y[index].astype("float64") * std + mean
    example = {
        "household": key,
        "target_date": str(target_date[index]),
        "min_kwh": round(float(kwh.min()), 4),
        "max_kwh": round(float(kwh.max()), 4),
        "mean_kwh": round(float(kwh.mean()), 4),
    }

    summary = {
        "config": {
            "series": str(args.series),
            "source_timezone": "UTC",
            "timezone": TZ,
            "input_days": args.input_days,
            "input_steps": input_steps,
            "output_steps": 48,
            "channels": ["kwh_scaled", "observed_mask"],
            "train_end": args.train_end,
            "val_end": args.val_end,
            "min_input_observed": args.min_input_observed,
            "interpolation": "time-based, limit=2 steps, inside only",
            "target_rule": "48/48 observed",
            "dst_days_excluded": [str(day) for day in sorted(DST_DATES)],
            "scaling": "per-household z-score fitted on the training period",
            "split": "chronological by target date",
        },
        "skipped": {
            "incomplete_target_days": skipped_target,
            "sparse_input_windows": skipped_input,
            "dst_windows": skipped_dst,
        },
        "splits": {name: split_info(index) for name, index in splits.items()},
        "shapes": {"X": list(X.shape[1:]), "y": list(y.shape[1:])},
        "example_test_target_kwh": example,
        "scalers": scalers,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(f"\nDONE in {summary['elapsed_seconds'] / 60:.1f} min", flush=True)
    print(
        f"  samples : train={len(train_idx):,} "
        f"val={len(val_idx):,} test={len(test_idx):,}",
        flush=True,
    )
    print(f"  X shape : {X.shape}  ({X.nbytes / 1e6:.0f} MB float32)", flush=True)
    print(f"  y shape : {y.shape}", flush=True)
    print(f"  example : {example}", flush=True)
    print(f"  output  : {args.out_dir}", flush=True)


if __name__ == "__main__":
    main()