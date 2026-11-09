"""baseline.py
References naives sur les fenetres 48 h -> 1 h (aucun entrainement).
  persistance      : y_hat(t) = y(t-1)   = X[:, -1]
  saisonnier 24 h  : y_hat(t) = y(t-24)  = X[:, 24]
  moyenne foyer    : y_hat(t) = moyenne train du foyer (z = 0)
Metriques en kWh reels (denormalisation via scalers.csv).
"""
import numpy as np
import pandas as pd
from pathlib import Path

D = Path("data/processed/dl")
d = np.load(D / "windows_48to1.npz")
X, y, split, hid = d["X"], d["y"], d["split"], d["LCLid"]

st = pd.read_csv(D / "scalers.csv").set_index("LCLid")
mu = np.array([st.loc[h, "mean"] for h in hid], dtype="float64")
sd = np.array([st.loc[h, "std"] for h in hid], dtype="float64")

def to_kwh(z):
    return np.asarray(z, dtype="float64") * sd + mu

y_true = to_kwh(y)
preds = {
    "persistance (t-1)": to_kwh(X[:, -1]),
    "saisonnier (t-24)": to_kwh(X[:, 24]),
    "moyenne train": mu,
}

rows = []
for name, p in preds.items():
    for sp in ("train", "val", "test"):
        k = split == sp
        e = y_true[k] - p[k]
        rows.append((name, sp, int(k.sum()),
                     float(np.mean(np.abs(e))),
                     float(np.sqrt(np.mean(e ** 2)))))
r = pd.DataFrame(rows, columns=["modele", "split", "n", "MAE_kWh", "RMSE_kWh"])
print(r.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

print("\nDetail persistance par foyer (test) :")
rows = []
for h in sorted(set(hid)):
    k = (split == "test") & (hid == h)
    e = y_true[k] - preds["persistance (t-1)"][k]
    rows.append((h, int(k.sum()), float(np.mean(np.abs(y_true[k]))),
                 float(np.mean(np.abs(e)))))
print(pd.DataFrame(rows, columns=["LCLid", "n_test", "kwh_moyen_reel", "MAE_persistance"])
      .to_string(index=False, float_format=lambda v: f"{v:.4f}"))

r.to_csv(D / "baseline_metrics.csv", index=False)
print("\nEcrit :", D / "baseline_metrics.csv")