"""eval_gru_24h_test.py
Evaluation TEST, UNE SEULE FOIS, du run choisi sur VAL.
Journal : data/processed/dl/test_seen.json
Refuse de reevaluer le test sans --i-know.

Usage :
  python scripts/eval_gru_24h_test.py --tag runA_l1
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

D = Path("data/processed/dl")
LOOKBACK, HORIZON = 48, 24
LEDGER = D / "test_seen.json"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--tag", required=True)
    p.add_argument("--i-know", action="store_true")
    return p.parse_args()


ARGS = parse_args()
MODEL = Path("models") / f"gru_24h_{ARGS.tag}.pt"
SUMMARY = D / f"gru_24h_{ARGS.tag}_summary.json"
if not MODEL.exists():
    raise SystemExit(f"modele introuvable : {MODEL}")

summary = json.loads(SUMMARY.read_text(encoding="utf-8")) if SUMMARY.exists() else {}
if summary and not summary.get("beats_seasonal_val_mae", False) and not ARGS.i_know:
    raise SystemExit(
        f"STOP: {ARGS.tag} ne bat pas le saisonnier sur VAL "
        f"({summary.get('val_gru_mae'):.4f} vs {summary.get('val_saisonnier_mae'):.4f}). "
        "Le test ne doit pas etre lu. --i-know pour passer outre."
    )

used = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []
if used and not ARGS.i_know:
    print("TEST deja evalue :")
    print(json.dumps(used, indent=2))
    raise SystemExit("Refus : relance avec --i-know si tu assumes un second regard.")


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


class GRU24(nn.Module):
    def __init__(self, inp, hidden, layers):
        super().__init__()
        self.gru = nn.GRU(inp, hidden, layers, batch_first=True)
        self.head = nn.Linear(hidden, HORIZON)

    def forward(self, x):
        out, _ = self.gru(x)
        return self.head(out[:, -1, :])


ck = torch.load(MODEL, map_location="cpu", weights_only=False)
h = ck["hparams"]
model = GRU24(h["input_size"], h["hidden"], h["layers"])
model.load_state_dict(ck["state_dict"])
model.eval()

d = np.load(D / "windows_48to24.npz")
Xz = d["X"].astype("float32")
Yz = d["Y"].astype("float32")
tgt = d["target_hour"]
hid = d["LCLid"].astype(str)
split = d["split"].astype(str)
st = pd.read_csv(D / "scalers.csv").set_index("LCLid")
mu = np.array([st.loc[x, "mean"] for x in hid], dtype="float64")
sd = np.array([st.loc[x, "std"] for x in hid], dtype="float64")

if h["calendar"]:
    cal = calendar_features(tgt, LOOKBACK)
    X3np = np.concatenate([Xz[:, :, None], cal], axis=2)
else:
    X3np = Xz[:, :, None]

idx = np.flatnonzero(split == "test")
with torch.no_grad():
    pred_z = model(torch.from_numpy(X3np[idx].astype("float32"))).numpy()

mu_te, sd_te = mu[idx], sd[idx]
Y = Yz[idx].astype("float64") * sd_te[:, None] + mu_te[:, None]
P = pred_z.astype("float64") * sd_te[:, None] + mu_te[:, None]
S = Xz[idx, 24:48].astype("float64") * sd_te[:, None] + mu_te[:, None]
e, es = Y - P, Y - S
mae = np.mean(np.abs(e), axis=0)
rmse = np.sqrt(np.mean(e ** 2, axis=0))
mae_s = np.mean(np.abs(es), axis=0)
rmse_s = np.sqrt(np.mean(es ** 2, axis=0))

tab = pd.DataFrame({
    "horizon_h": np.arange(1, HORIZON + 1),
    "MAE_GRU": mae, "MAE_saisonnier": mae_s,
    "RMSE_GRU": rmse, "RMSE_saisonnier": rmse_s,
})
print(f"run {ARGS.tag} | val MAE {summary.get('val_gru_mae')} | loss {h['loss']} | calendar {h['calendar']}")
print(tab.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
print(f"\npoule GRU  : MAE {mae.mean():.4f} | RMSE {np.sqrt(np.mean(rmse ** 2)):.4f}")
print(f"poule sais : MAE {mae_s.mean():.4f} | RMSE {np.sqrt(np.mean(rmse_s ** 2)):.4f}")
print(f"GRU bat le saisonnier (MAE) : {bool(mae.mean() < mae_s.mean())}")

pred_out = D / f"gru_test_{ARGS.tag}_preds.parquet"
tab_out = D / f"gru_test_{ARGS.tag}_metrics.csv"
tab.to_csv(tab_out, index=False)
pd.DataFrame({
    "LCLid": np.repeat(hid[idx], HORIZON),
    "target_hour": np.repeat(pd.to_datetime(tgt[idx]), HORIZON),
    "horizon_h": np.tile(np.arange(1, HORIZON + 1), len(idx)),
    "y_true_kwh": Y.ravel(),
    "y_pred_kwh": P.ravel(),
    "y_seasonal_kwh": S.ravel(),
}).to_parquet(pred_out, index=False)

try:
    commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
except Exception:
    commit = None

entry = {
    "tag": ARGS.tag,
    "utc": datetime.now(timezone.utc).isoformat(),
    "n_test": int(len(idx)),
    "test_hash": hashlib.sha256(np.ascontiguousarray(Y).tobytes()).hexdigest()[:16],
    "loss": h["loss"], "calendar": h["calendar"],
    "pooled_mae_gru": float(mae.mean()),
    "pooled_mae_saisonnier": float(mae_s.mean()),
    "pooled_rmse_gru": float(np.sqrt(np.mean(rmse ** 2))),
    "git_commit": commit,
}
used.append(entry)
LEDGER.write_text(json.dumps(used, indent=2), encoding="utf-8")

print("\necrit :", pred_out, "|", tab_out)
print("journal test :", LEDGER, "| test vu", len(used), "fois")