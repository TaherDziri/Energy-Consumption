#!/usr/bin/env python3
"""
Phase 4.1 - Export half-hourly series for the selected household cohort.

Reads data/raw/CC_LCL-FullData.csv in a single streaming pass, keeps only the
households selected from the Phase 1 profile, drops Null values, averages
duplicate (household_id, timestamp) keys, and writes one Parquet file.

Outputs (default):
  data/processed/cohort_top50.csv
  data/processed/halfhourly_series/halfhourly_series.parquet
  data/processed/halfhourly_series/manifest.json

Example (PowerShell, from the project root):
  python deep-learning/preprocessing/export_halfhourly.py --raw data/raw/CC_LCL-FullData.csv --profile data/processed/household_profile.csv --out-dir data/processed/halfhourly_series --cohort-size 50
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def select_cohort(profile_path: Path, size: int, min_span_days: int) -> pd.DataFrame:
    """Rank households by completeness and return the best `size` ones."""
    prof = pd.read_csv(profile_path)

    required = {
        "household_id", "rows", "missing",
        "first_timestamp", "last_timestamp", "total_kwh",
    }
    missing = required - set(prof.columns)
    if missing:
        raise SystemExit(f"profile is missing columns: {sorted(missing)}")

    for col in ("first_timestamp", "last_timestamp"):
        prof[col] = pd.to_datetime(
            prof[col].astype(str).str.slice(0, 19),
            format="%Y-%m-%d %H:%M:%S",
            errors="coerce",
        )

    prof = prof.dropna(subset=["first_timestamp", "last_timestamp"]).copy()

    span_seconds = (prof["last_timestamp"] - prof["first_timestamp"]).dt.total_seconds()
    prof["expected_slots"] = (span_seconds // 1800 + 1).astype("int64")
    prof["valid"] = prof["rows"] - prof["missing"]
    prof["span_days"] = span_seconds / 86400.0
    prof["completeness"] = (prof["valid"] / prof["expected_slots"]).clip(upper=1.0)

    eligible = prof[
        (prof["total_kwh"] > 0)
        & (prof["valid"] > 0)
        & (prof["span_days"] >= min_span_days)
    ].copy()

    cohort = (
        eligible.sort_values(["completeness", "valid"], ascending=False)
        .head(size)
        .reset_index(drop=True)
    )
    cohort.insert(0, "rank", range(1, len(cohort) + 1))
    return cohort


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--cohort-size", type=int, default=50)
    parser.add_argument("--min-span-days", type=int, default=365)
    parser.add_argument(
        "--max-lines", type=int, default=0,
        help="debug only: stop after N data lines (0 = read the whole file)",
    )
    args = parser.parse_args()

    started = time.time()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/4] selecting the cohort from the profile ...", flush=True)
    cohort = select_cohort(args.profile, args.cohort_size, args.min_span_days)
    if len(cohort) < args.cohort_size:
        print(f"      WARNING: only {len(cohort)} households passed the filters", flush=True)
    cohort_path = args.out_dir.parent / f"cohort_top{len(cohort)}.csv"
    cohort.to_csv(cohort_path, index=False)
    ids = set(cohort["household_id"])
    print(f"      {len(ids)} households -> {cohort_path}", flush=True)
    print(
        cohort[["rank", "household_id", "completeness", "span_days", "total_kwh"]]
        .head(10)
        .to_string(index=False),
        flush=True,
    )

    print("[2/4] streaming the raw CSV (single pass) ...", flush=True)
    counters = Counter()
    households: list[str] = []
    stamps: list[str] = []
    values: list[float] = []
    next_report = 10_000_000

    with args.raw.open("r", encoding="utf-8", newline="") as handle:
        header = handle.readline()
        if "LCLid" not in header:
            raise SystemExit(f"unexpected header: {header[:120]!r}")
        counters["header_skipped"] += 1

        for line in handle:
            if args.max_lines and counters["rows_read"] >= args.max_lines:
                break
            counters["rows_read"] += 1

            if counters["rows_read"] >= next_report:
                print(f"      ... {counters['rows_read']:,} lines read", flush=True)
                next_report += 10_000_000

            household, _, rest = line.partition(",")
            if household not in ids:
                continue
            counters["rows_kept"] += 1

            fields = rest.split(",")
            if len(fields) < 3:
                counters["malformed"] += 1
                continue

            raw_value = fields[2].strip()
            if raw_value == "Null":
                counters["missing_null"] += 1
                continue
            try:
                value = float(raw_value)
            except ValueError:
                counters["value_parse_error"] += 1
                continue
            if value < 0:
                counters["negative"] += 1
                continue

            households.append(sys.intern(household))
            stamps.append(sys.intern(fields[1][:19]))
            values.append(value)

    print(f"      lines read       : {counters['rows_read']:,}", flush=True)
    print(f"      lines for cohort : {counters['rows_kept']:,}", flush=True)
    print(f"      Null dropped     : {counters['missing_null']:,}", flush=True)
    print(f"      non-null kept    : {len(values):,}", flush=True)

    if not values:
        raise SystemExit("no rows kept: check --raw and the cohort selection")

    print("[3/4] deduplicating (household_id, timestamp) with mean ...", flush=True)
    frame = pd.DataFrame(
        {
            "household_id": households,
            "timestamp": pd.to_datetime(stamps, format="%Y-%m-%d %H:%M:%S"),
            "kwh": values,
        }
    )
    del households, stamps, values

    raw_rows = len(frame)
    frame = (
        frame.groupby(["household_id", "timestamp"], as_index=False)["kwh"]
        .mean()
        .sort_values(["household_id", "timestamp"])
        .reset_index(drop=True)
    )
    counters["duplicate_rows_averaged"] = raw_rows - len(frame)

    per_day = frame.groupby(
        [frame["household_id"], frame["timestamp"].dt.date]
    ).size()
    counters["days_more_than_48"] = int((per_day > 48).sum())

    print(f"      duplicate rows averaged : {counters['duplicate_rows_averaged']:,}", flush=True)
    print(f"      output rows             : {len(frame):,}", flush=True)
    print(f"      households in output    : {frame['household_id'].nunique():,}", flush=True)
    print(f"      days with >48 readings  : {counters['days_more_than_48']:,}", flush=True)
    print(f"      time range              : {frame['timestamp'].min()} -> {frame['timestamp'].max()}", flush=True)

    print("[4/4] writing Parquet + manifest ...", flush=True)
    series_path = args.out_dir / "halfhourly_series.parquet"
    frame.to_parquet(series_path, index=False, compression="snappy")

    summary = (
        frame.groupby("household_id")
        .agg(
            rows=("kwh", "size"),
            first_timestamp=("timestamp", "min"),
            last_timestamp=("timestamp", "max"),
            total_kwh=("kwh", "sum"),
        )
        .reset_index()
    )

    elapsed = time.time() - started
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw_file": str(args.raw),
        "profile_file": str(args.profile),
        "cohort_file": str(cohort_path),
        "cohort_size": len(ids),
        "series_file": str(series_path),
        "schema": ["household_id", "timestamp", "kwh"],
        "dedup_rule": "mean of duplicate (household_id, timestamp)",
        "null_rule": "Null rows dropped, never zero-filled",
        "counters": dict(counters),
        "output_rows": len(frame),
        "elapsed_seconds": round(elapsed, 1),
        "per_household": {
            row.household_id: {
                "rows": int(row.rows),
                "first_timestamp": row.first_timestamp.isoformat(),
                "last_timestamp": row.last_timestamp.isoformat(),
                "total_kwh": round(float(row.total_kwh), 6),
            }
            for row in summary.itertuples(index=False)
        },
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nDONE in {elapsed / 60:.1f} min", flush=True)
    print(f"  series   : {series_path} ({series_path.stat().st_size / 1e6:.1f} MB)", flush=True)
    print(f"  manifest : {args.out_dir / 'manifest.json'}", flush=True)
    print(f"  cohort   : {cohort_path}", flush=True)


if __name__ == "__main__":
    main()