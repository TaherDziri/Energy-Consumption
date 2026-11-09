"""build_windows_24h.py
Fenetres 48 h -> 24 h. Memes scalers et memes splits que le one-step.
72 h consecutives, sans NaN, entierement dans un seul split.
Sorties hors Git : windows_48to24.npz, windows_48to24_meta.parquet,
                   baseline_24h_metrics.csv
"""
import numpy as np
import pandas as pd
from pathlib import Path

D = Path("data/processed/dl")
LOOKBACK, HORIZON = 48, 24
STEP = LOOKBACK + HORIZON

t = pd.read_parquet(D / "sample_hourly.parquet").sort_values(["LCLid", "hour_end"]).reset_index(drop=True)
st = pd.read_csv(D / "scalers.csv").set_index("LCLid")

Xs, Ys, mids, tgts, spls = [], [], [], [], []
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
    for i in range(n - STEP + 1):
        if csum[i + STEP] - csum[i + 1] != STEP - 1:
            continue
        w = v[i:i + STEP]
        if np.isnan(w).any():
            continue
        s = sp[i:i + STEP]
        if s.min() != s.max():          # fenetre a cheval sur deux splits
            continue
        Xs.append(w[:LOOKBACK])
        Ys.append(w[LOOKBACK:])
        mids.append(hid)
        tgts.append(ts[i + LOOKBACK])
        spls.append(s[0])
        kept += 1
    print(f"{hid}: {kept} fenetres 48->24")

X = np.asarray(Xs, dtype="float32")
Y = np.asarray(Ys, dtype="float32")
mid = np.asarray(mids, dtype="str")
tgt = np.asarray(tgts, dtype="datetime64[ns]")
spl = np.asarray(spls, dtype="str")

mu = np.array([st.loc[h, "mean"] for h in mid], dtype="float32")
sd = np.array([st.loc[h, "std"] for h in mid], dtype="float32")
Xz = (X - mu[:, None]) / sd[:, None]
Yz = (Y - mu[:, None]) / sd[:, None]

np.savez_compressed(D / "windows_48to24.npz", X=Xz, Y=Yz,
                    LCLid=mid, target_hour=tgt, split=spl)
pd.DataFrame({"LCLid": mid, "target_hour": tgt, "split": spl}).to_parquet(
    D / "windows_48to24_meta.parquet", index=False)

print("X", Xz.shape, "| Y", Yz.shape)
print(pd.Series(spl).value_counts().to_string())
print("NaN X", int(np.isnan(Xz).sum()), "| NaN Y", int(np.isnan(Yz).sum()))

# --- baselines adaptees a 24 sorties, en kWh reels ---
Yk = Y.astype("float64") * sd[:, None] + mu[:, None]
last = X[:, [-1]].astype("float64") * sd[:, None] + mu[:, None]
preds = {
    "persistance (t-1)": np.repeat(last, HORIZON, axis=1),
    "saisonnier (t-24)": X[:, 24:48].astype("float64") * sd[:, None] + mu[:, None],
    "moyenne train": np.repeat(mu[:, None].astype("float64"), HORIZON, axis=1),
}

rows = []
for name, P in preds.items():
    for s in ("train", "val", "test"):
        k = spl == s
        e = Yk[k] - P[k]
        rows.append((name, s, int(k.sum()),
                     float(np.mean(np.abs(e))), float(np.sqrt(np.mean(e ** 2)))))
r = pd.DataFrame(rows, columns=["modele", "split", "n_fenetres", "MAE_kWh", "RMSE_kWh"])
print(r.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

kt = spl == "test"
out = pd.DataFrame({"horizon_h": np.arange(1, HORIZON + 1)})
for name in ("persistance (t-1)", "saisonnier (t-24)"):
    out[name] = np.mean(np.abs(Yk[kt] - preds[name][kt]), axis=0)
print("\nMAE par horizon (test) :")
print(out.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
r.to_csv(D / "baseline_24h_metrics.csv", index=False)