"""scripts/check_v11_vs_mr2.py

Recalcule independamment depuis data/sample/sample_5households.csv les
metriques mensuelles du contrat v1.1 (jour local Europe/London, DST 46/48/50,
prix Std plat 2013) et les compare a une sortie MR2.

La sortie MR2 n'entre dans AUCUN calcul : elle n'est que comparee.

Usage : .venv\\Scripts\\python scripts\\check_v11_vs_mr2.py tmp\\mr2_v11_real.csv
"""
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

RAW = "data/sample/sample_5households.csv"
CAL = "data/tariffs_2013_price.csv"
STD_PENCE = 14.228
ZONE = ZoneInfo("Europe/London")
# MR1 ecrit total_kwh avec 3 decimales et series avec 6 decimales :
# la tolerance doit couvrir ces arrondis, pas seulement le %.6f de MR2.
TOL_KWH = 0.01
TOL_COST = 0.001


def expected_slots(day: str) -> int:
    d = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=ZONE)
    nxt = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=ZONE) + timedelta(days=1)
    # Soustraire en UTC : avec le meme tzinfo, Python fait une soustraction
    # d'horloge murale et renvoie 24 h meme le jour de 25 h.
    return int((nxt.astimezone(timezone.utc) - d.astimezone(timezone.utc))
               .total_seconds() // 1800)


def expected_table():
    raw = pd.read_csv(RAW, dtype=str)
    raw.columns = ["lclid", "tariff", "ts", "kwh"]
    raw["kwh"] = pd.to_numeric(raw["kwh"].str.strip(), errors="coerce")
    raw = raw.dropna(subset=["kwh"])
    raw["ts"] = pd.to_datetime(raw["ts"].str.strip().str.slice(0, 19),
                               format="%Y-%m-%d %H:%M:%S")

    # Regle 3 du data contract : doublons (foyer, timestamp UTC) moyennes.
    slots = raw.groupby(["lclid", "ts"], as_index=False)["kwh"].mean()
    local = slots["ts"].dt.tz_localize("UTC").dt.tz_convert("Europe/London")
    slots["date"] = local.dt.strftime("%Y-%m-%d")
    # slot local ; le 27/10, 01:00 et 01:30 ont le MEME slot mais restent
    # deux lignes distinctes (deux demi-heures physiques).
    slots["slot"] = local.dt.hour * 2 + local.dt.minute // 30

    cal = pd.read_csv(CAL)
    d_min, d_max = cal["date"].min(), cal["date"].max()
    covered = (slots["date"] >= d_min) & (slots["date"] <= d_max)
    # L'echantillon est exclusivement Std. Pour un jeu ToU il faudrait
    # rejoindre cal par (date, slot) au lieu du prix plat.
    slots["cost"] = np.where(covered, slots["kwh"] * STD_PENCE / 100.0, np.nan)

    day = slots.groupby(["lclid", "date"]).agg(
        total=("kwh", "sum"), n=("kwh", "size"), peak=("kwh", "max"),
        cost=("cost", "sum"), priced=("cost", "count"),
    ).reset_index()
    day["expected"] = day["date"].map(expected_slots)
    day["missing"] = day["expected"] - day["n"]
    assert (day["missing"] >= 0).all()
    day["month"] = day["date"].str.slice(0, 7)

    exp = day.groupby(["lclid", "month"]).agg(
        kwh=("total", "sum"), peak=("peak", "max"),
        valid_days=("date", "nunique"), priced=("priced", "sum"),
        observed=("n", "sum"), missing=("missing", "sum"), cost=("cost", "sum"),
    ).reset_index()
    exp["cost"] = np.where(exp["priced"] == 0, np.nan, exp["cost"])
    exp["coverage"] = exp["priced"] / exp["observed"]
    exp["flag"] = np.select(
        [exp["priced"] == 0, exp["priced"] < exp["observed"], exp["missing"] > 0],
        ["no_tariff", "partial_tariff", "partial_data"], default="ok")
    return exp


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tmp/mr2_v11_real.csv"
    exp = expected_table()
    cols = ["lclid", "month", "tariff", "kwh", "cost", "coverage",
            "peak", "valid_days", "flag", "run_id"]
    got = pd.read_csv(path, names=cols, header=None, dtype=str,
                      keep_default_na=False)
    for c in ["kwh", "cost", "coverage", "peak"]:
        got[c] = pd.to_numeric(got[c].replace("", np.nan), errors="coerce")
    got["valid_days"] = got["valid_days"].astype(int)

    m = exp.merge(got, on=["lclid", "month"], how="outer",
                  suffixes=("_exp", "_mr2"), indicator=True)
    fails = []
    if len(m) != 108 or (m["_merge"] != "both").any():
        fails.append("cles (foyer, mois) non appariees")

    for c, tol in [("kwh", TOL_KWH), ("cost", TOL_COST),
                   ("peak", TOL_COST), ("coverage", 1e-6)]:
        d = (m[f"{c}_exp"] - m[f"{c}_mr2"]).abs()
        print(f"ecart max {c:9s} = {d.max():.3e}  (tol {tol:g}, "
              f"lignes hors tol {int((d > tol).sum())})")
        if d.max() > tol:
            fails.append(f"{c} : ecart {d.max():.3e} > {tol:g}")

    print("flags differents :", int((m["flag_exp"] != m["flag_mr2"]).sum()))
    if (m["flag_exp"] != m["flag_mr2"]).any():
        fails.append("flags differs")
    print("couts NULL : attendu", int(m["cost_exp"].isna().sum()),
          "MR2", int(m["cost_mr2"].isna().sum()))
    if int((m["cost_exp"].isna() != m["cost_mr2"].isna()).sum()):
        fails.append("NULL costs differs")
    if int((m["cost_mr2"] == 0).sum()):
        fails.append("un cout vaut 0")

    print("total kWh  :", round(m["kwh_exp"].sum(), 6),
          "/", round(m["kwh_mr2"].sum(), 6))
    print("total cout :", round(m["cost_exp"].sum(), 6),
          "/", round(m["cost_mr2"].sum(), 6))
    print("flags MR2  :", got["flag"].value_counts().to_dict())

    if fails:
        print("ECHEC :", *fails, sep="\n  - ")
        return 1
    print("OK : reconciliation v1.1 (jour local + DST) dans la tolerance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
