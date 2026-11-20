#!/usr/bin/env python3
"""
Phase 4 / MR2 - export the Job 2 contract.

One row per household-day:
  household_id, date, series, expected_slots, valid_slots, n_missing_slots

series = list of (slot, kwh) pairs, slot = hour*2 + minute//30 (displayed time).
expected_slots is computed from Europe/London: 46 (spring), 48 (normal), 50 (fall).
n_missing_slots = expected_slots - valid_slots.

Read-only on data/raw. Writes only under data/processed/job2_contract/.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

TZ = ZoneInfo("Europe/London")
DST_DATES = ("2012-03-25", "2012-10-28", "2013-03-31", "2013-10-27")
_exp_cache: dict[date, int] = {}


def expected_slots(day: date) -> int:
    cached = _exp_cache.get(day)
    if cached is not None:
        return cached
    start = datetime(day.year, day.month, day.day, tzinfo=TZ)
    end = start + timedelta(days=1)
    delta = end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    slots = int(delta.total_seconds() // 1800)
    _exp_cache[day] = slots
    return slots


def split_occurrences(values: list[float], occurrences: int) -> list[float]:
    """Collapse duplicate readings into the expected number of half-hours."""
    if len(values) <= occurrences:
        return values
    n = len(values)
    out: list[float] = []
    previous = 0
    for index in range(1, occurrences + 1):
        end = round(index * n / occurrences)
        chunk = values[previous:end]
        if chunk:
            out.append(sum(chunk) / len(chunk))
        previous = end
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("data/raw/CC_LCL-FullData.csv"))
    parser.add_argument("--cohort", type=Path, default=Path("data/processed/cohort_top50.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/processed/job2_contract"))
    parser.add_argument("--chunksize", type=int, default=1_000_000)
    args = parser.parse_args()

    started = time.time()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    cohort = set(
        pd.read_csv(args.cohort, usecols=["household_id"])["household_id"]
        .astype(str)
        .tolist()
    )
    print(f"[1/5] cohort: {len(cohort)} households", flush=True)

    print(f"[2/5] streaming {args.raw} ...", flush=True)
    parts: list[pd.DataFrame] = []
    scanned = 0
    reader = pd.read_csv(

        args.raw,
        usecols=[0, 2, 3],
        header=0,
        dtype="string",
        chunksize=args.chunksize,
    )
    for chunk in reader:
        chunk.columns = ["LCLid", "DateTime", "kwh_raw"]
        scanned += len(chunk)
        selected = chunk[chunk["LCLid"].isin(cohort)]
        if not selected.empty:
            parts.append(selected.copy())
        if scanned % 20_000_000 < args.chunksize:
            print(f"      ... {scanned:,} lines", flush=True)

    if not parts:
        raise SystemExit("no rows for the cohort")

    frame = pd.concat(parts, ignore_index=True)
    frame["timestamp_utc"] = pd.to_datetime(
        frame["DateTime"].str.slice(0, 19),
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce",
        utc=True,
    )
    frame["timestamp"] = frame["timestamp_utc"].dt.tz_convert(TZ)
    frame["kwh"] = pd.to_numeric(frame["kwh_raw"], errors="coerce")
    frame["slot"] = (
        frame["timestamp"].dt.hour * 2 + frame["timestamp"].dt.minute // 30
    )
    frame = frame[["LCLid", "timestamp", "kwh", "slot"]].sort_values(
        ["LCLid", "timestamp"], kind="mergesort"
    )
    frame = frame.reset_index(drop=True)

    null_dropped = int(frame["kwh"].isna().sum())
    print(
        f"      lines scanned       : {scanned:,}\n"
        f"      cohort rows         : {len(frame):,}\n"
        f"      Null/NaN dropped    : {null_dropped:,}",
        flush=True,
    )

    first_household = sorted(cohort)[0]
    print(f"[3/5] DST debug for {first_household}:", flush=True)
    for text in DST_DATES:
        day = date.fromisoformat(text)
        subset = frame[
            (frame["LCLid"] == first_household)
            & (frame["timestamp"].dt.date == day)
        ]
        stamps = sorted(subset["timestamp"].dt.strftime("%H:%M").tolist())
        print(
            f"      {text}: expected={expected_slots(day)} "
            f"rows={len(subset)} early={stamps[:8]}",
            flush=True,
        )

    print("[4/5] building household-day series ...", flush=True)
    rows: list[dict] = []
    dst_valid: dict[str, Counter] = {text: Counter() for text in DST_DATES}
    overflow_days = 0
    total_entries = 0

    for household, group in frame.groupby("LCLid", sort=True):
        for day, day_group in group.groupby(group["timestamp"].dt.date, sort=True):
            observed = day_group[day_group["kwh"].notna()]
            if observed.empty:
                continue

            expected = expected_slots(day)
            series: list[tuple[int, float]] = []
            for slot, slot_group in observed.groupby("slot", sort=True):
                values = slot_group["kwh"].astype(float).tolist()
                occurrences = 2 if expected == 50 and int(slot) in (2, 3) else 1
                for value in split_occurrences(values, occurrences):
                    series.append((int(slot), float(value)))
            series.sort(key=lambda pair: pair[0])

            valid = len(series)
            missing = expected - valid
            if missing < 0:
                overflow_days += 1
                missing = 0

            rows.append(
                {
                    "household_id": str(household),
                    "date": day,
                    "series": [
                        {"slot": slot, "kwh": round(value, 6)}
                        for slot, value in series
                    ],
                    "expected_slots": expected,
                    "valid_slots": valid,
                    "n_missing_slots": missing,
                }
            )
            total_entries += valid
            if day.isoformat() in dst_valid:
                dst_valid[day.isoformat()][valid] += 1

    if not rows:
        raise SystemExit("no household-day rows built")

    print(f"      household-days : {len(rows):,}", flush=True)
    print(f"      entries        : {total_entries:,}", flush=True)

    print("[5/5] writing Parquet + JSONL + manifest ...", flush=True)
    table = pa.table(
        {
            "household_id": pa.array(
                [row["household_id"] for row in rows], type=pa.string()
            ),
            "date": pa.array([row["date"] for row in rows], type=pa.date32()),
            "series": pa.array(
                [row["series"] for row in rows],
                type=pa.list_(
                    pa.struct([("slot", pa.int16()), ("kwh", pa.float64())])
                ),
            ),
            "expected_slots": pa.array(
                [row["expected_slots"] for row in rows], type=pa.int16()
            ),
            "valid_slots": pa.array(
                [row["valid_slots"] for row in rows], type=pa.int16()
            ),
            "n_missing_slots": pa.array(
                [row["n_missing_slots"] for row in rows], type=pa.int16()
            ),
        }
    )
    pq.write_table(table, args.out_dir / "job2_contract.parquet")

    with (args.out_dir / "job2_contract.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    {
                        "household_id": row["household_id"],
                        "date": row["date"].isoformat(),
                        "series": [
                            [pair["slot"], pair["kwh"]] for pair in row["series"]
                        ],
                        "expected_slots": row["expected_slots"],
                        "valid_slots": row["valid_slots"],
                        "n_missing_slots": row["n_missing_slots"],
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )

    by_expected = Counter(row["expected_slots"] for row in rows)
    manifest = {
        "config": {
            "raw": str(args.raw),
            "cohort": str(args.cohort),
            "timezone": "Europe/London",
            "slot_formula": "hour*2 + minute//30 (displayed time)",
            "expected_slots_rule": "java.time/Europe/London equivalent (zoneinfo)",
            "missing_rule": "n_missing_slots = expected_slots - valid_slots",
            "fallback_hour_slots": [2, 3],
            "source_kind": "raw CSV, one pass",
            "source_timestamp_interpretation": "UTC, converted to Europe/London",
        },
        "counters": {
            "lines_scanned": scanned,
            "cohort_rows": len(frame),
            "null_or_nan_dropped": null_dropped,
            "households": len({row["household_id"] for row in rows}),
            "household_days": len(rows),
            "total_entries": total_entries,
            "overflow_days": overflow_days,
        },
        "by_expected_slots": {str(k): v for k, v in sorted(by_expected.items())},
        "dst_days": {
            text: {
                "expected_slots": expected_slots(date.fromisoformat(text)),
                "valid_slots_distribution": {
                    str(k): v for k, v in sorted(counter.items())
                },
            }
            for text, counter in dst_valid.items()
        },
        "schema": {
            "household_id": "string",
            "date": "date32",
            "series": "list<struct<slot:int16,kwh:float64>>",
            "expected_slots": "int16",
            "valid_slots": "int16",
            "n_missing_slots": "int16",
        },
        "elapsed_seconds": round(time.time() - started, 1),
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(
        f"\nDONE in {manifest['elapsed_seconds'] / 60:.1f} min\n"
        f"  household-days : {len(rows):,}\n"
        f"  entries        : {total_entries:,}\n"
        f"  by expected    : {dict(sorted(by_expected.items()))}\n"
        f"  overflow days  : {overflow_days}\n"
        f"  output         : {args.out_dir}",
        flush=True,
    )
    if overflow_days:
        print(
            "  WARNING: valid_slots > expected_slots on some days "
            "(source timezone or DST encoding is not Europe/London).",
            flush=True,
        )


if __name__ == "__main__":
    main()