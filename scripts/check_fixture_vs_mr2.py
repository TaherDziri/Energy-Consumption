"""scripts/check_fixture_vs_mr2.py

Recalcule avec pandas, depuis le CSV source uniquement, monthly_kwh,
pic demi-heure, couverture et cout par (foyer, mois), puis compare a la
sortie MR2 de la fixture. Tolerance 1e-6. La sortie MR2 n'entre dans
aucun calcul : elle n'est que comparee.

Usage : .venv\\Scripts\\python scripts\\check_fixture_vs_mr2.py tmp\\mr2_fixture.csv
"""
import sys

import numpy as np
import pandas as pd

RAW = "data/sample/sample_5households.csv"
CAL = "data/tariffs_2013_price.csv"
TOL = 1e-6
STD_PENCE = 14.228


def expected_table():
    """Attendu, recalcule depuis la source (aucune lecture de la sortie MR2)."""
    raw = pd.read_csv(RAW, dtype=str)
    raw.columns = ["lclid", "tariff", "ts", "kwh"]
    raw["kwh"] = pd.to_numeric(raw["kwh"].str.strip(), errors="coerce")
    raw = raw.dropna(subset=["kwh"])
    raw["ts"] = pd.to_datetime(raw["ts"].str.strip().str.slice(0, 19),
                               format="%Y-%m-%d %H:%M:%S")
    raw["date"] = raw["ts"].dt.strftime("%Y-%m-%d")
    raw["slot"] = (raw["ts"].dt.hour * 2 + raw["ts"].dt.minute // 30).astype(int)

    slots = raw.groupby(["lclid", "date", "slot"], as_index=False)["kwh"].mean()

    cal = pd.read_csv(CAL)
    d_min, d_max = cal["date"].min(), cal["date"].max()
    covered = (slots["date"] >= d_min) & (slots["date"] <= d_max)
    slots["cost"] = np.where(covered, slots["kwh"] * STD_PENCE / 100.0, np.nan)

    day = slots.groupby(["lclid", "date"]).agg(
        total=("kwh", "sum"), n=("kwh", "size"), peak=("kwh", "max"),
        cost=("cost", "sum"), priced=("cost", "count"),
    ).reset_index()
    day["missing"] = 48 - day["n"]
    day["month"] = day["date"].str.slice(0, 7)

    exp = day.groupby(["lclid", "month"]).agg(
        monthly_kwh=("total", "sum"), peak=("peak", "max"),
        valid_days=("date", "nunique"), priced=("priced", "sum"),
        observed=("n", "sum"), missing=("missing", "sum"), cost=("cost", "sum"),
    ).reset_index()
    exp["cost"] = np.where(exp["priced"] == 0, np.nan, exp["cost"])
    exp["coverage"] = exp["priced"] / exp["observed"]
    exp["flag"] = np.select(
        [exp["priced"] == 0, exp["priced"] < exp["observed"], exp["missing"] > 0],
        ["no_tariff", "partial_tariff", "partial_data"], default="ok")
    return exp


def mr2_table(path):
    cols = ["lclid", "month", "tariff", "monthly_kwh", "cost", "coverage",
            "peak", "valid_days", "flag", "run_id"]
    got = pd.read_csv(path, names=cols, header=None, dtype=str,
                      keep_default_na=False)
    for c in ["monthly_kwh", "cost", "coverage", "peak"]:
        got[c] = pd.to_numeric(got[c].replace("", np.nan), errors="coerce")
    got["valid_days"] = got["valid_days"].astype(int)
    return got


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tmp/mr2_fixture.csv"
    exp = expected_table()
    got = mr2_table(path)

    fails = []
    m = exp.merge(got, on=["lclid", "month"], how="outer",
                  suffixes=("_exp", "_mr2"), indicator=True)
    if len(m) != 108:
        fails.append(f"lignes attendues 108, obtenu {len(m)}")
    if (m["_merge"] != "both").any():
        fails.append("cles (foyer, mois) non appariees : "
                     + str(m.loc[m["_merge"] != "both", ["lclid", "month", "_merge"]]
                           .head(10).to_dict("records")))

    for c in ["monthly_kwh", "peak", "coverage"]:
        d = (m[f"{c}_exp"] - m[f"{c}_mr2"]).abs()
        print(f"ecart max {c:12s} = {d.max():.3e}   (lignes > 1e-6 : {int((d > TOL).sum())})")
        if d.max() > TOL:
            fails.append(f"{c} : ecart max {d.max():.3e} > 1e-6")

    both = m.dropna(subset=["cost_exp", "cost_mr2"])
    d = (both["cost_exp"] - both["cost_mr2"]).abs()
    print(f"ecart max cost         = {d.max():.3e}   (couples avec cout : {len(both)})")
    if d.max() > TOL:
        fails.append(f"cost : ecart max {d.max():.3e} > 1e-6")

    n_null_exp = int(m["cost_exp"].isna().sum())
    n_null_mr2 = int(m["cost_mr2"].isna().sum())
    print(f"couts NULL : attendu {n_null_exp}  MR2 {n_null_mr2}")
    if n_null_exp != n_null_mr2 or n_null_exp != 48:
        fails.append(f"couts NULL : {n_null_exp} vs {n_null_mr2}")
    if int((m["cost_mr2"] == 0).sum()):
        fails.append("un cout vaut 0 : interdit")

    bad_flag = m[m["flag_exp"] != m["flag_mr2"]]
    print(f"flags differents : {len(bad_flag)}")
    if len(bad_flag):
        fails.append("flags : " + str(bad_flag[["lclid", "month", "flag_exp", "flag_mr2"]]
                                         .head(10).to_dict("records")))
    print(f"flags : {got['flag'].value_counts().to_dict()}")

    print(f"total kWh  : attendu {m['monthly_kwh_exp'].sum():.6f}  "
          f"MR2 {m['monthly_kwh_mr2'].sum():.6f}")
    print(f"total cout : attendu {m['cost_exp'].sum():.6f}  "
          f"MR2 {m['cost_mr2'].sum():.6f}")

    print("\ncout 2013 par foyer (attendu / MR2)")
    a = exp[exp["cost"].notna()].groupby("lclid")["cost"].sum().round(6)
    b = got[got["cost"].notna()].groupby("lclid")["cost"].sum().round(6)
    print(pd.DataFrame({"attendu": a, "mr2": b, "ecart": (a - b).abs()}).to_string())

    print("\n5 premieres lignes MR2")
    print(got.head(5).to_string(index=False))

    if fails:
        print("\nECHEC :")
        for f in fails:
            print("  -", f)
        return 1
    print("\nOK : toutes les comparaisons sont dans 1e-6.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
