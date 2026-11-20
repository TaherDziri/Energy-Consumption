"""Export the selected DL test predictions to a CSV loadable by Spark/Iceberg.

The GRU is trained and selected on validation only; the test split is read once.
This script only reformats the retained run A (L1) predictions. It does not
touch MR1, MR2 or any monthly aggregation.

Run from the repository root:
    .venv\\Scripts\\python scripts\\export_dl_predictions.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
D_DL = ROOT / "data" / "processed" / "dl"
D_DASH = ROOT / "data" / "dashboard"

P_PREDS = D_DL / "gru_test_runA_l1_preds.parquet"
P_SEEN = D_DL / "test_seen.json"
P_OUT = D_DASH / "dl_predictions.csv"

COLUMNS = [
    "model_tag", "split_name", "lclid", "target_hour", "horizon_h",
    "y_true_kwh", "y_pred_kwh", "y_seasonal_kwh",
    "abs_err_gru", "abs_err_seasonal", "test_hash", "git_commit",
    "source_path",
]


def main() -> None:
    seen = json.loads(P_SEEN.read_text(encoding="utf-8"))
    run = next((r for r in seen if r.get("tag") == "runA_l1"), None)
    if run is None:
        raise SystemExit("test_seen.json : runA_l1 absent")

    df = pd.read_parquet(P_PREDS)
    expected = {"LCLid", "target_hour", "horizon_h", "y_true_kwh",
                "y_pred_kwh", "y_seasonal_kwh"}
    if set(df.columns) != expected:
        raise SystemExit(f"colonnes inattendues : {sorted(df.columns)}")
    if df.isna().any().any():
        raise SystemExit("valeurs nulles dans les predictions")

    mae_gru = float((df["y_true_kwh"] - df["y_pred_kwh"]).abs().mean())
    mae_sais = float((df["y_true_kwh"] - df["y_seasonal_kwh"]).abs().mean())
    if abs(mae_gru - float(run["pooled_mae_gru"])) > 1e-6:
        raise SystemExit("MAE GRU different de test_seen.json")
    if abs(mae_sais - float(run["pooled_mae_saisonnier"])) > 1e-6:
        raise SystemExit("MAE saisonnier different de test_seen.json")

    out = pd.DataFrame({
        "model_tag": f"gru_24h_{run['tag']}",
        "split_name": "test",
        "lclid": df["LCLid"],
        "target_hour": pd.to_datetime(df["target_hour"]).dt.strftime("%Y-%m-%d %H:%M:%S"),
        "horizon_h": df["horizon_h"].astype(int),
        "y_true_kwh": df["y_true_kwh"].astype(float),
        "y_pred_kwh": df["y_pred_kwh"].astype(float),
        "y_seasonal_kwh": df["y_seasonal_kwh"].astype(float),
        "abs_err_gru": (df["y_true_kwh"] - df["y_pred_kwh"]).abs().astype(float),
        "abs_err_seasonal": (df["y_true_kwh"] - df["y_seasonal_kwh"]).abs().astype(float),
        "test_hash": run["test_hash"],
        "git_commit": run["git_commit"],
        "source_path": P_PREDS.relative_to(ROOT).as_posix(),
    })[COLUMNS]

    D_DASH.mkdir(parents=True, exist_ok=True)
    out.to_csv(P_OUT, index=False, lineterminator="\n")

    print(f"rows={len(out)} foyers={out['lclid'].nunique()} horizons={out['horizon_h'].nunique()}")
    print(f"mae_gru={mae_gru:.6f} mae_saisonnier={mae_sais:.6f}")
    print(f"test_hash={run['test_hash']} git_commit={run['git_commit']}")
    print(f"out={P_OUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
