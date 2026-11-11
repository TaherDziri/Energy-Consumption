"""scripts/make_mr1_v11_fixture.py

Fabrique une FIXTURE DE TEST au format MR1 v1.1 (TSV, 10 colonnes)
depuis data/sample/sample_5households.csv.

Ce n'est PAS une sortie de MR1 : dataset_version = 'sample-fixture-v11'.
Aucun zero n'est invente : seuls les creneaux OBSERVES sont ecrits.
Un zero reellement mesure s'ecrit 0.0 ; un creneau absent n'apparait pas.

Regles appliquees :
  - une ligne par (foyer, date), sans en-tete
  - slot = heure*2 + minute//30 du timestamp, SANS aucun decalage
  - doublons (foyer, date, slot) moyennes (comme MR1 v1 : 105 cas)
  - kWh illisibles supprimes (5 cas)
  - total_kwh = somme des valeurs ECRITES dans series
  - peak_kwh_hh / peak_slot = max et indice de cette meme serie

Sorties : tmp/mr1_v11_sample.tsv
          tmp/_FIXTURE_sample-fixture-v11.txt
"""
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SRC = Path("data/sample/sample_5households.csv")
OUT = Path("tmp/mr1_v11_sample.tsv")
MARKER = Path("tmp/_FIXTURE_sample-fixture-v11.txt")
VERSION = "sample-fixture-v11"
SLOTS_PER_DAY = 48

CAVEAT = """HYPOTHESE NON VERIFIEE (convention de timestamp)
Le fichier source est horodate a la FIN de chaque demi-heure
(00:30 = premiere demi-heure du jour). Le slot est calcule ici par
slot = heure*2 + minute//30 sur l'horodatage tel qu'il est ecrit.
Consequence : une lecture a 00:00 est rangee dans le slot 0 du jour
affiche, alors qu'en convention fin-de-periode elle appartient au
slot 47 de la veille (~3 100 lectures concernees).
Cette convention n'est tranchee ni par le PDF ni par le depot.
Impact : aucun sur un cout Std a prix plat, SAUF aux bornes du
calendrier 2013 (une lecture du 2013-01-01 00:00 pourrait basculer
au 2012-12-31, donc devenir non tarifee). A verifier avec le
tariff_d.csv et le PDF avant tout chiffre definitif.
"""


def num(v: float) -> str:
    """Decimal avec point, 12 decimales max, jamais d'exposant."""
    if v == 0.0:
        return "0.0"
    s = f"{v:.12f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def main() -> int:
    rows = 0
    bad_fields = 0
    bad_kwh = 0
    negative = 0
    acc = defaultdict(lambda: [0.0, 0])   # (foyer, date, slot) -> [somme, n]
    tariff_of = {}                        # (foyer, date) -> groupe

    with SRC.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        next(reader)                      # en-tete
        for raw in reader:
            rows += 1
            if len(raw) != 4:
                bad_fields += 1
                continue
            lclid = raw[0].strip()
            group = raw[1].strip()
            ts = datetime.strptime(raw[2].strip()[:19], "%Y-%m-%d %H:%M:%S")
            try:
                kwh = float(raw[3].strip())
            except ValueError:
                bad_kwh += 1
                continue
            if kwh != kwh or kwh < 0.0:    # NaN ou negatif
                negative += 1
                continue
            date = ts.strftime("%Y-%m-%d")
            slot = ts.hour * 2 + ts.minute // 30
            cell = acc[(lclid, date, slot)]
            cell[0] += kwh
            cell[1] += 1
            prev = tariff_of.setdefault((lclid, date), group)
            if prev != group:
                raise SystemExit(f"groupe tarifaire incoherent : {lclid} {date}")

    pairs_total = len(acc)
    duplicates = sum(n - 1 for _, n in acc.values())
    by_day = defaultdict(list)
    for (lclid, date, slot), (total, n) in acc.items():
        by_day[(lclid, date)].append((slot, total / n))

    lines = []
    kwh_sum = 0.0
    missing_total = 0
    zeros = 0
    for key in sorted(by_day):
        lclid, date = key
        pairs = sorted(by_day[key])
        vals = [(slot, num(v)) for slot, v in pairs]
        n_valid = len(vals)
        n_missing = SLOTS_PER_DAY - n_valid
        if n_missing < 0:
            raise SystemExit(f"plus de 48 creneaux : {lclid} {date}")
        total = 0.0
        for _, s in vals:                  # meme ordre, memes doubles que Java
            total += float(s)
        peak_slot, peak_txt = max(vals, key=lambda p: (float(p[1]), -p[0]))
        zeros += sum(1 for _, s in vals if float(s) == 0.0)
        series = ";".join(f"{slot}:{s}" for slot, s in vals)
        kwh_sum += total
        missing_total += n_missing
        lines.append("\t".join([
            lclid, date, tariff_of[key], num(total), str(n_valid),
            str(n_missing), num(float(peak_txt)), str(peak_slot),
            num(total / n_valid), series,
        ]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        for line in lines:
            fh.write(line + "\n")

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text("\n".join([
        f"dataset_version: {VERSION}",
        "NATURE: FIXTURE DE TEST -- PAS une sortie de MR1",
        f"source: {SRC.as_posix()}",
        f"lignes source (hors en-tete): {rows}",
        f"kWh illisibles supprimes: {bad_kwh}",
        f"doublons (foyer, date, slot) moyennes: {duplicates}",
        f"paires (foyer, date, slot): {pairs_total}",
        f"foyers-jours: {len(lines)}",
        f"creneaux manquants: {missing_total}",
        f"somme kWh: {num(kwh_sum)}",
        f"zeros reellement mesures: {zeros}",
        "fichier de donnees associe: part-mr1v11.tsv",
        "",
        CAVEAT,
    ]) + "\n", encoding="utf-8")

    print(f"lignes lues            : {rows}")
    print(f"champs != 4            : {bad_fields}")
    print(f"kWh illisibles         : {bad_kwh}   (attendu 5)")
    print(f"kWh negatifs / NaN     : {negative}")
    print(f"paires uniques         : {pairs_total}   (attendu 152701)")
    print(f"doublons moyennes      : {duplicates}   (attendu 105)")
    print(f"foyers-jours           : {len(lines)}   (attendu 3191)")
    print(f"creneaux manquants     : {missing_total}   (attendu 467)")
    print(f"zeros mesures          : {zeros}   (attendu 26212)")
    print(f"somme kWh              : {num(kwh_sum)}   (attendu 28416.517003)")
    print(f"pic global             : {max(float(l.split(chr(9))[6]) for l in lines)}")
    print(f"ecrit                  : {OUT}  et  {MARKER}")

    assert rows == 152811, rows
    assert bad_kwh == 5, bad_kwh
    assert pairs_total == 152701, pairs_total
    assert duplicates == 105, duplicates
    assert len(lines) == 3191, len(lines)
    assert missing_total == 467, missing_total
    assert abs(kwh_sum - 28416.517003) < 1e-5, kwh_sum
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
