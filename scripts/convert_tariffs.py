#!/usr/bin/env python3
"""Enrichit le calendrier tarifaire officiel avec un prix par créneau.

Entrée  : data/Tariffs.xlsx   (colonnes TariffDateTime, Tariff)
Sortie  : data/tariffs_2013_price.csv   (date,slot,tariff,price_pence)

Le fichier de sortie est celui distribué à MR2 via DistributedCache.
Il ne contient que des faits observés dans le tableur officiel :

    date          date locale du signal          2013-01-01
    slot          indice du créneau (0-47)       0
    tariff        niveau du signal               Normal
    price_pence   prix du signal en p/kWh        11.76

Le tarif plat du groupe Std (14.228 p/kWh) n'est PAS écrit ici : il ne
provient pas du tableur dynamique. C'est MR2 qui l'applique aux foyers
Std lorsque la date existe dans le calendrier.

Aucun créneau n'est inventé : le script échoue si un jour ne contient
pas exactement 48 lignes.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

# Prix officiels des signaux dynamiques (p/kWh), voir phase1_summary.md.
PRICE_PENCE = {
    "High": 67.20,
    "Normal": 11.76,
    "Low": 3.99,
}

EXPECTED_SLOTS_PER_DAY = 48


def read_source(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        frame = pd.read_excel(path)
    else:
        frame = pd.read_csv(path, encoding="utf-8-sig")

    required = {"TariffDateTime", "Tariff"}
    missing = required - set(frame.columns)
    if missing:
        raise SystemExit(f"Colonnes manquantes dans {path} : {sorted(missing)}")

    frame = frame[["TariffDateTime", "Tariff"]].copy()
    frame["TariffDateTime"] = pd.to_datetime(frame["TariffDateTime"], errors="raise")
    frame["Tariff"] = frame["Tariff"].astype(str).str.strip()
    frame = frame.sort_values("TariffDateTime", kind="mergesort").reset_index(drop=True)
    return frame


def build_price_table(frame: pd.DataFrame) -> pd.DataFrame:
    unknown = sorted(set(frame["Tariff"]) - set(PRICE_PENCE))
    if unknown:
        raise SystemExit(f"Niveaux tarifaires inconnus : {unknown}")

    frame["date"] = frame["TariffDateTime"].dt.strftime("%Y-%m-%d")
    # slot = position du créneau dans la journée, dans l'ordre chronologique.
    frame["slot"] = frame.groupby("date", sort=False).cumcount()

    counts = frame.groupby("date", sort=False).size()
    bad = counts[counts != EXPECTED_SLOTS_PER_DAY]
    if not bad.empty:
        details = ", ".join(f"{day}={n}" for day, n in bad.items())
        raise SystemExit(f"Jours incomplets (attendu 48 créneaux) : {details}")

    frame["price_pence"] = frame["Tariff"].map(PRICE_PENCE)
    frame["price_pence"] = frame["price_pence"].map(lambda value: f"{value:.2f}")
    return frame[["date", "slot", "Tariff", "price_pence"]].rename(
        columns={"Tariff": "tariff"}
    )


def write_csv(table: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["date", "slot", "tariff", "price_pence"])
        writer.writerows(table.itertuples(index=False, name=None))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/Tariffs.xlsx"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/tariffs_2013_price.csv")
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Fichier introuvable : {args.input}")

    frame = read_source(args.input)
    table = build_price_table(frame)
    write_csv(table, args.output)

    levels = table["tariff"].value_counts().to_dict()
    print(f"Source      : {args.input}")
    print(f"Sortie      : {args.output}")
    print(f"Lignes      : {len(table)}")
    print(f"Jours       : {table['date'].nunique()}")
    print(f"Période     : {table['date'].min()} -> {table['date'].max()}")
    print(f"Niveaux     : {levels}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
