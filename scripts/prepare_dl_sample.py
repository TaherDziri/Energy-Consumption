"""prepare_dl_sample.py
Nettoie data/sample/sample_5households.csv -> base HORAIRE propre.
Convention : timestamp = FIN de periode (1re ligne = 00:30).
Un creneau absent reste absent (NaN). Un 0 mesure reste 0.
Sortie : data/processed/dl/sample_hourly.parquet
"""
import numpy as np
import pandas as pd
from pathlib import Path

SRC = Path("data/sample/sample_5households.csv")
OUT = Path("data/processed/dl/sample_hourly.parquet")

df = pd.read_csv(SRC).rename(columns={"KWH/hh (per half hour)": "kwh"})
df["kwh"] = pd.to_numeric(df["kwh"], errors="coerce")
df["ts"] = pd.to_datetime(df["DateTime"], errors="coerce")

print("1) brut          :", df.shape,
      "| ts illisibles :", int(df["ts"].isna().sum()))
print("2) kwh NaN       :", int(df["kwh"].isna().sum()),
      "| kwh < 0 :", int((df["kwh"] < 0).sum()),
      "| kwh == 0 :", int((df["kwh"] == 0).sum()))
print("3) doublons      :", int(df.duplicated(["LCLid", "ts"]).sum()))

# Doublons (foyer, timestamp) -> moyenne, comme MR1.
df = df.groupby(["LCLid", "ts"], as_index=False).agg(kwh=("kwh", "mean"))
print("4) apres moyenne :", df.shape)

rows = []
for hid, g in df.groupby("LCLid", sort=True):
    s = g.set_index("ts")["kwh"].sort_index()
    # Heure (00:00, 01:00] = creneaux 00:30 + 01:00 -> label = 01:00
    r = s.resample("1h", closed="right", label="right")
    kwh_sum, n = r.sum(), r.count()
    h = pd.DataFrame({"kwh": kwh_sum.where(n == 2)})   # heure incomplete -> NaN
    out = h.reset_index().rename(columns={"ts": "hour_end"})
    out.insert(0, "LCLid", hid)
    rows.append(out)

t = pd.concat(rows, ignore_index=True)

# Split TEMPOREL global 70 / 15 / 15 sur les heures distinctes.
hours = np.sort(t["hour_end"].unique())
lim1, lim2 = hours[int(len(hours) * 0.70)], hours[int(len(hours) * 0.85)]
t["split"] = np.where(t["hour_end"] <= lim1, "train",
             np.where(t["hour_end"] <= lim2, "val", "test"))

print("5) horaire       :", t.shape,
      "| NaN:", int(t["kwh"].isna().sum()))
print(t.groupby("LCLid").agg(
    lignes=("kwh", "size"),
    heures_manquantes=("kwh", lambda x: int(x.isna().sum())),
    debut=("hour_end", "min"),
    fin=("hour_end", "max"),
    kwh_total=("kwh", "sum")).to_string())

print("6) split :")
for name, g in t.groupby("split"):
    print("   ", name, "|", g["hour_end"].min(), "->", g["hour_end"].max(),
          "| NaN", int(g["kwh"].isna().sum()), "/", len(g))

OUT.parent.mkdir(parents=True, exist_ok=True)
t.to_parquet(OUT, index=False)
print("7) ecrit         :", OUT, "|", OUT.stat().st_size, "octets")
print("8) kWh total (NaN exclus) :", round(float(t["kwh"].sum()), 3))