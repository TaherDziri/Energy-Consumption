"""ae_val_scores.py
Compare 4 scores d'anomalie sur le MEME modele sauvegarde, sur VAL uniquement.
Ne lit JAMAIS le test. Aucun reentrainement.
"""
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from pathlib import Path

D = Path("data/processed/dl")
MODEL = Path("models/ae_day.pt")
H1, H2 = 16, 8
FA_CIBLES = (1, 5)          # % de fausses alertes acceptees, cote VAL


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


def residus(model, yk, mu_k, sd_k):
    zk = (yk - mu_k[:, None]) / sd_k[:, None]
    p = predict_z(model, zk).astype("float64") * sd_k[:, None] + mu_k[:, None]
    return np.abs(yk - p)


def quatre_scores(R, niveau):
    return {
        "mae_h": R.mean(axis=1),
        "max_h": R.max(axis=1),
        "top6_h": np.sort(R, axis=1)[:, -6:].mean(axis=1),
        "mae_rel": R.mean(axis=1) / np.maximum(niveau, 1e-6),
    }


ck = torch.load(MODEL, map_location="cpu", weights_only=False)
model = AE(ck["hparams"]["nin"])
model.load_state_dict(ck["state_dict"])
model.eval()
print("checkpoint :", ck["hparams"]["best_epoch"], "| val MSE(z)", ck["hparams"]["best_val_mse"])

Y, meta, mu, sd = load_days()
split = meta["split"].to_numpy()
va = np.flatnonzero(split == "val")
Yk, mu_k, sd_k = Y[va], mu[va], sd[va]
niveau = Yk.mean(axis=1)          # niveau attendu du foyer, kWh/h (jour sain)
print(f"VAL : {len(va)} jours | niveau moyen {niveau.mean():.3f} kWh/h "
      f"= {niveau.mean() * 24:.2f} kWh/jour")

R_clean = residus(model, Yk, mu_k, sd_k)
s_clean = quatre_scores(R_clean, niveau)

variantes = {"scale_x1.5": Yk * 1.5,
             "zeros_kwh": np.zeros_like(Yk),
             "shift_peak_+6h": np.roll(Yk, 6, axis=1)}
s_var = {k: quatre_scores(residus(model, yk, mu_k, sd_k), niveau)
         for k, yk in variantes.items()}

for fa in FA_CIBLES:
    print(f"\n--- cible {fa} % de fausses alertes sur VAL (seuil = P{100 - fa:g}) ---")
    print(f"  score   | seuil kWh/h | x1.5  | shift | zeros | lift x1.5")
    print("  --------+-------------+-------+-------+-------+----------")
    for nom in s_clean:
        thr = float(np.percentile(s_clean[nom], 100 - fa))
        det = {k: float((s_var[k][nom] > thr).mean()) for k in variantes}
        lift = det["scale_x1.5"] / (fa / 100.0)
        print(f"  {nom:7s} | {thr:11.4f} | {det['scale_x1.5'] * 100:5.1f} | "
              f"{det['shift_peak_+6h'] * 100:5.1f} | {det['zeros_kwh'] * 100:5.1f} | "
              f"{lift:9.1f}")

print("\nTEST non lu par ce script.")