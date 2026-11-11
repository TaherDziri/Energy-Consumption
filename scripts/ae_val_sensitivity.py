"""ae_val_sensitivity.py
Sensibilite du seuil sur VAL UNIQUEMENT. Ne lit JAMAIS le test.
Charge models/ae_day.pt et compare P90 / P95 / P99 / P99.5 :
seuil en kWh/h et kWh/jour, fausses alertes, detection des 3 synthetiques.
"""
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from pathlib import Path

D = Path("data/processed/dl")
MODEL = Path("models/ae_day.pt")
H1, H2 = 16, 8


class AE(nn.Module):
    def __init__(self, nin=24):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(nin, H1), nn.ReLU(),
                                 nn.Linear(H1, H2), nn.ReLU())
        self.dec = nn.Sequential(nn.Linear(H2, H1), nn.ReLU(),
                                 nn.Linear(H1, nin))

    def forward(self, x):
        return self.dec(self.enc(x))


def load_days():
    h = pd.read_parquet(D / "sample_hourly.parquet")
    h["period_start"] = h["hour_end"] - pd.Timedelta(hours=1)
    h["day"] = h["period_start"].dt.floor("D")
    h["hod"] = h["period_start"].dt.hour
    assert not h.duplicated(["LCLid", "period_start"]).any(), "heure en double"
    piv = h.pivot_table(index=["LCLid", "day"], columns="hod",
                        values="kwh", aggfunc="first").reindex(columns=range(24))
    info = h.groupby(["LCLid", "day"])["split"].agg(["nunique", "first"])
    Y = piv.to_numpy(dtype="float64")
    keep = (~np.isnan(Y).any(axis=1)) & \
           (info["nunique"].reindex(piv.index).to_numpy() == 1)
    meta = piv.index.to_frame(index=False)[keep].reset_index(drop=True)
    meta["split"] = info["first"].reindex(piv.index).to_numpy()[keep]
    Y = Y[keep]
    st = pd.read_csv(D / "scalers.csv").set_index("LCLid")
    mu = np.array([st.loc[x, "mean"] for x in meta["LCLid"]], dtype="float64")
    sd = np.array([st.loc[x, "std"] for x in meta["LCLid"]], dtype="float64")
    return Y, meta, mu, sd


def predict_z(model, Z):
    model.eval()
    with torch.no_grad():
        return model(torch.from_numpy(Z.astype("float32"))).numpy()


def err_kwh(pred_z, yk, mu_k, sd_k):
    p = pred_z.astype("float64") * sd_k[:, None] + mu_k[:, None]
    return np.abs(yk - p).mean(axis=1)


ck = torch.load(MODEL, map_location="cpu", weights_only=False)
model = AE(ck["hparams"]["nin"])
model.load_state_dict(ck["state_dict"])
model.eval()
print("checkpoint :", ck["hparams"]["best_epoch"], "| val MSE(z)", ck["hparams"]["best_val_mse"])

Y, meta, mu, sd = load_days()
Z = (Y - mu[:, None]) / sd[:, None]
split = meta["split"].to_numpy()
va = np.flatnonzero(split == "val")

Yk, mu_k, sd_k = Y[va], mu[va], sd[va]
e_va = err_kwh(predict_z(model, Z[va]), Yk, mu_k, sd_k)
niveau = float(Yk.mean())
print(f"VAL : {len(va)} jours | niveau moyen {niveau:.3f} kWh/h = {niveau * 24:.2f} kWh/jour")
print(f"erreur : P50 {np.percentile(e_va, 50):.4f} | P90 {np.percentile(e_va, 90):.4f} "
      f"| P95 {np.percentile(e_va, 95):.4f} | P99 {np.percentile(e_va, 99):.4f}")

variantes = {
    "scale_x1.5": Yk * 1.5,
    "zeros_kwh": np.zeros_like(Yk),
    "shift_peak_+6h": np.roll(Yk, 6, axis=1),
}
err = {}
for k, yk in variantes.items():
    zk = (yk - mu_k[:, None]) / sd_k[:, None]
    err[k] = err_kwh(predict_z(model, zk), yk, mu_k, sd_k)

print("\n  P     | seuil kWh/h | seuil kWh/j | fausses alertes | x1.5  | zeros | shift")
print("  ------+-------------+-------------+-----------------+-------+-------+------")
for p in (90, 95, 99, 99.5):
    thr = float(np.percentile(e_va, p))
    fa = (e_va > thr).mean()
    det = [f"{(err[k] > thr).mean() * 100:5.1f}" for k in variantes]
    print(f"  P{p:<4} | {thr:11.4f} | {thr * 24:11.3f} | {fa * 100:14.2f} % | "
          + " | ".join(det))

# Seuil qui rendrait le seuil egal a une hausse de +50 % du niveau moyen
print(f"\nrepere : +50 % du niveau moyen = {0.5 * niveau:.4f} kWh/h "
      f"(= {0.5 * niveau * 24:.2f} kWh/jour)")
print("TEST non lu par ce script.")