"""build_windows.py
Fenetres 48 h -> 1 h depuis data/processed/dl/sample_hourly.parquet.
Aucune valeur inventee : fenetre gardee seulement si 48 entrees + cible
presentes et heures consecutives. z-score PAR FOYER fitte sur TRAIN seul.
Sorties hors Git : windows_48to1.npz, windows_48to1_meta.parquet, scalers.csv
"""
import numpy as np
import pandas as pd
from pathlib import Path

SRC = Path("data/processed/dl/sample_hourly.parquet")
OUT = Path("data/processed/dl")
LOOKBACK, HORIZON = 48, 1

t = pd.read_parquet(SRC).sort_values(["LCLid", "hour_end"]).reset_index(drop=True)
meta, X, y = [], [], []

for hid, g in t.groupby("LCLid", sort=True):
    g = g.sort_values("hour_end").reset_index(drop=True)
    ts = g["hour_end"].to_numpy()
    v = g["kwh"].to_numpy(dtype="float64")
    sp = g["split"].to_numpy()
    n = len(g)
    consec = np.ones(n, dtype=bool)
    consec[1:] = np.diff(ts) == np.timedelta64(1, "h")
    csum = np.concatenate([[0], np.cumsum(consec)])
    kept = 0
    for i in range(0, n - (LOOKBACK + HORIZON) + 1):
        if csum[i + LOOKBACK + HORIZON] - csum[i + 1] != LOOKBACK + HORIZON - 1:
            continue
        w = v[i:i + LOOKBACK + HORIZON]
        if np.isnan(w).any():
            continue
        X.append(w[:LOOKBACK])
        y.append(w[LOOKBACK])
        meta.append((hid, ts[i + LOOKBACK], sp[i + LOOKBACK]))
        kept += 1
    print(f"{hid}: {kept} fenetres valides / {n} heures")

X = np.asarray(X, dtype="float32")
y = np.asarray(y, dtype="float64")
meta = pd.DataFrame(meta, columns=["LCLid", "target_hour", "split"])

# z-score par foyer, fitte sur TRAIN seulement (pas de fuite)
stats = []
for hid, g in t.groupby("LCLid", sort=True):
    tr = g.loc[(g["split"] == "train") & g["kwh"].notna(), "kwh"].to_numpy(dtype="float64")
    mu, sd = float(np.mean(tr)), float(np.std(tr))
    stats.append((hid, mu, sd if sd > 1e-9 else 1.0, len(tr)))
st = pd.DataFrame(stats, columns=["LCLid", "mean", "std", "n_train_hours"])
print(st.to_string(index=False))

m = meta.merge(st, on="LCLid", how="left", validate="many_to_one")
mu = m["mean"].to_numpy(dtype="float32")
sd = m["std"].to_numpy(dtype="float32")
Xz = (X - mu[:, None]) / sd[:, None]
yz = ((y - mu) / sd).astype("float32")

OUT.mkdir(parents=True, exist_ok=True)
np.savez_compressed(OUT / "windows_48to1.npz", X=Xz, y=yz,
                    LCLid=m["LCLid"].to_numpy(dtype="str"),
                    target_hour=m["target_hour"].to_numpy(dtype="datetime64[ns]"),
                    split=m["split"].to_numpy(dtype="str"))
st.to_csv(OUT / "scalers.csv", index=False)
meta.to_parquet(OUT / "windows_48to1_meta.parquet", index=False)

print("X", Xz.shape, "| y", yz.shape)
print(meta.groupby("split").size().to_string())
print("NaN X:", int(np.isnan(Xz).sum()), "| NaN y:", int(np.isnan(yz).sum()))
print("bornes Xz:", float(Xz.min()), float(Xz.max()))