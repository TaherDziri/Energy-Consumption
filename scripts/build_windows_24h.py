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

# --- invariants de structure (on ne verifie pas un nombre de fenetres) ---
print("\ninvariants :")
print("  shapes :", X.shape, Y.shape, "| Yz", Yz.shape)
print("  dtypes :", X.dtype, Y.dtype, mid.dtype, tgt.dtype, spl.dtype)
print("  NaN X/Y:", int(np.isnan(X).sum()), int(np.isnan(Yz).sum()))
assert X.shape[1] == LOOKBACK and Y.shape[1] == HORIZON
assert len(X) == len(Y) == len(mid) == len(tgt) == len(spl)
assert not np.isnan(X).any() and not np.isnan(Yz).any()

for hid in sorted(set(mid)):
    k = np.flatnonzero(mid == hid)
    th = tgt[k]
    assert np.all(np.diff(th) > np.timedelta64(0, "h")), f"{hid}: cible non croissante"
    cont = np.flatnonzero(np.diff(th) == np.timedelta64(1, "h"))
    assert np.allclose(Yz[k][cont + 1][:, :-1], Yz[k][cont][:, 1:]), f"{hid}: recouvrement Y"
    pos = pd.Series(np.arange(len(k)), index=pd.DatetimeIndex(th))
    j = pos.reindex(pd.DatetimeIndex(th) + pd.Timedelta(hours=HORIZON)).to_numpy()
    ok = ~pd.isna(j)
    jj = j[ok].astype(int)
    assert np.allclose(Xz[k][jj][:, -HORIZON:], Yz[k][ok]), f"{hid}: X(i+24) != Y(i)"
    print(f"  {hid}: {len(k)} fenetres | {th.min()} -> {th.max()}")

for a, b in (("train", "val"), ("val", "test")):
    fin = tgt[spl == a].max() + np.timedelta64(HORIZON - 1, "h")
    assert fin < tgt[spl == b].min(), f"chevauchement {a}/{b}"
print("  frontieres de split : ok")

# --- baselines 24 sorties, en kWh REELS (X et Y sont deja en kWh) ---
Yk = Y.astype("float64")
preds = {
    "persistance (t-1)": np.repeat(X[:, [-1]].astype("float64"), HORIZON, axis=1),
    "saisonnier (t-24)": X[:, 24:48].astype("float64"),
    "moyenne train": np.repeat(mu[:, None].astype("float64"), HORIZON, axis=1),
}

rows = []
for name, P in preds.items():
    for s in ("train", "val", "test"):
        kk = spl == s
        e = Yk[kk] - P[kk]
        rows.append((name, s, int(kk.sum()),
                     float(np.mean(np.abs(e))), float(np.sqrt(np.mean(e ** 2)))))
r = pd.DataFrame(rows, columns=["modele", "split", "n_fenetres", "MAE_kWh", "RMSE_kWh"])
print("\n" + r.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

kt = spl == "test"
out = pd.DataFrame({"horizon_h": np.arange(1, HORIZON + 1)})
for name in ("persistance (t-1)", "saisonnier (t-24)"):
    out[name] = np.mean(np.abs(Yk[kt] - preds[name][kt]), axis=0)
print("\nMAE par horizon (test) :")
print(out.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

# --- garde-fou : saisonnier test doit retrouver le one-step (~0.2021) ---
mae_pool = float(r.loc[(r.modele == "saisonnier (t-24)") & (r.split == "test"), "MAE_kWh"].iloc[0])
mae_h1 = float(np.mean(np.abs(Yk[kt, 0] - preds["saisonnier (t-24)"][kt, 0])))
print(f"\nsaisonnier test : pool {mae_pool:.4f} | h=1 {mae_h1:.4f} | ref one-step 0.2021")
assert abs(mae_pool - 0.2021) <= 0.02, (
    f"saisonnier test {mae_pool:.4f} hors 0.2021 +/- 0.02 : verifier l'echelle kWh")
print("garde-fou saisonnier : ok")

r.to_csv(D / "baseline_24h_metrics.csv", index=False)