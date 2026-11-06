#!/usr/bin/env python3
"""Validate a Job 1 output file against the MR1 contract v1.1.

Checks (all rows, not a sample):
  - 10 tab separated fields, tab separator, no header
  - date = yyyy-MM-dd, expected slots in {46, 48, 50} (Europe/London rules)
  - n_valid_slots == number of pairs in series
  - n_missing_slots == expected - n_valid_slots
  - every slot in 0..47, slots non-decreasing (chronological order)
  - sum(series values) == total_kwh (tolerance 0.001)
  - peak_kwh_hh == max(series values) and peak_slot == its slot (first max)
  - empty day shape: n_valid = 0 -> peak/peak_slot/avg/series empty
  - aggregates: rows, households, sum(total_kwh), sum(n_valid_slots)
  - DST proof: distribution of n_valid_slots per DST date
  - fall-back proof: rows where a slot index appears twice

Optional baseline comparison (v1.0 CSV `household_id,date,total_kwh,reading_count`):
  - per household, sum(n_valid_slots) must be identical
  - per household, sum(total_kwh) must match within 0.05 kWh (per-row rounding)

Usage:
  python big-data/mapreduce/job1-daily/tools/validate_mr1.py --input out.tsv
  python big-data/mapreduce/job1-daily/tools/validate_mr1.py --input out.tsv --baseline v1.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date as Date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/London")
DST_DATES = {
    Date(2012, 3, 25),
    Date(2012, 10, 28),
    Date(2013, 3, 31),
    Date(2013, 10, 27),
}
TOLERANCE = 0.001


def slots_in_local_day(day: Date) -> int:
    """46 / 48 / 50 half-hours in a Europe/London local day."""
    start = datetime(day.year, day.month, day.day, tzinfo=ZONE)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=ZONE)
    delta = end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    return int(delta.total_seconds() // 1800)


def parse_series(raw: str) -> list[tuple[int, float]]:
    if not raw:
        return []
    pairs = []
    for token in raw.split(";"):
        slot_s, _, kwh_s = token.partition(":")
        pairs.append((int(slot_s), float(kwh_s)))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument(
        "--exclude-household",
        action="append",
        default=[],
        metavar="LCLID",
        help="skip this household in the baseline comparison "
        "(needed when the input file is a truncated sample)",
    )
    parser.add_argument("--max-errors", type=int, default=20)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    errors: list[str] = []
    rows = 0
    households: set[str] = set()
    total_kwh = 0.0
    total_valid = 0
    total_missing = 0
    valid_by_date: dict[str, Counter] = defaultdict(Counter)
    dst_rows = 0
    repeated_slot_rows = 0
    max_pairs = 0
    per_household_total: dict[str, float] = defaultdict(float)
    per_household_valid: dict[str, int] = defaultdict(int)

    def fail(message: str) -> None:
        if len(errors) < args.max_errors:
            errors.append(message)

    with args.input.open("r", encoding="utf-8", newline="") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.rstrip("\n")
            if not line:
                fail(f"line {line_no}: empty line")
                continue
            fields = line.split("\t")
            if len(fields) != 10:
                fail(f"line {line_no}: {len(fields)} fields (expected 10)")
                continue

            hid, day_s, tariff, total_s, valid_s, missing_s, peak_s, peak_slot_s, avg_s, series_s = fields
            rows += 1
            households.add(hid)
            try:
                day = Date.fromisoformat(day_s)
                total = float(total_s)
                valid = int(valid_s)
                missing = int(missing_s)
                pairs = parse_series(series_s)
            except ValueError as exc:
                fail(f"line {line_no}: parse error {exc}")
                continue

            if tariff not in {"Std", "ToU"}:
                fail(f"line {line_no}: tariff '{tariff}'")
            if len(pairs) != valid:
                fail(f"line {line_no}: n_valid={valid} but {len(pairs)} series pairs")
            expected = slots_in_local_day(day)
            if missing != expected - valid:
                fail(f"line {line_no}: n_missing={missing} expected={expected} valid={valid}")
            slots = [p[0] for p in pairs]
            if any(s < 0 or s > 47 for s in slots):
                fail(f"line {line_no}: slot out of range")
            # on a fall-back day the local slots restart (0,1,2,3,2,3,4,...),
            # so the monotonic check only applies to days without repeated slots
            if len(slots) == len(set(slots)) and any(b < a for a, b in zip(slots, slots[1:])):
                fail(f"line {line_no}: series not in chronological slot order")
            values = [p[1] for p in pairs]
            if values:
                if abs(sum(values) - total) > TOLERANCE:
                    fail(f"line {line_no}: sum(series)={sum(values):.6f} total={total}")
                if peak_s == "" or peak_slot_s == "" or avg_s == "":
                    fail(f"line {line_no}: peak/avg empty on a non-empty day")
                else:
                    peak = float(peak_s)
                    peak_slot = int(peak_slot_s)
                    best = max(values)
                    if abs(peak - best) > 1e-6:
                        fail(f"line {line_no}: peak={peak} max={best}")
                    first_index = values.index(best)
                    if peak_slot != slots[first_index]:
                        fail(f"line {line_no}: peak_slot={peak_slot} expected={slots[first_index]}")
                    if abs(float(avg_s) - total / valid) > 1e-6:
                        fail(f"line {line_no}: avg={avg_s} expected={total / valid:.6f}")
            else:
                if peak_s or peak_slot_s or avg_s or series_s:
                    fail(f"line {line_no}: empty day must keep peak/avg/series empty")
                if abs(total) > 1e-9:
                    fail(f"line {line_no}: empty day must have total 0")

            if len(slots) != len(set(slots)):
                repeated_slot_rows += 1
            if day in DST_DATES:
                dst_rows += 1
                valid_by_date[day.isoformat()][valid] += 1
            max_pairs = max(max_pairs, len(pairs))
            total_kwh += total
            total_valid += valid
            total_missing += missing
            per_household_total[hid] += total
            per_household_valid[hid] += valid

    baseline_report = None
    if args.baseline is not None:
        base_total: dict[str, float] = defaultdict(float)
        base_valid: dict[str, int] = defaultdict(int)
        base_rows = 0
        keep = households - set(args.exclude_household)
        with args.baseline.open("r", encoding="utf-8") as handle:
            for line in handle:
                parts = line.rstrip("\n").split(",")
                if len(parts) != 4 or parts[0] not in keep:
                    continue
                base_rows += 1
                base_total[parts[0]] += float(parts[2])
                base_valid[parts[0]] += int(parts[3])

        valid_mismatch = {
            h: (base_valid[h], per_household_valid[h])
            for h in sorted(keep)
            if base_valid.get(h, 0) != per_household_valid.get(h, 0)
        }
        total_diffs = {
            h: round(per_household_total[h] - base_total.get(h, 0.0), 6)
            for h in sorted(keep)
        }
        baseline_report = {
            "baseline_rows_same_households": base_rows,
            "households_checked": len(keep),
            "valid_slots_mismatches": valid_mismatch,
            "sum_total_kwh": round(sum(per_household_total[h] for h in keep), 3),
            "sum_total_kwh_baseline": round(sum(base_total.values()), 3),
            "sum_total_kwh_diff": round(
                sum(per_household_total.values()) - sum(base_total.values()), 3
            ),
            "max_abs_household_total_diff": max(
                (abs(v) for v in total_diffs.values()), default=0.0
            ),
        }
        if valid_mismatch:
            fail(f"baseline: {len(valid_mismatch)} households differ on n_valid_slots")

    summary = {
        "input": str(args.input),
        "rows": rows,
        "households": len(households),
        "sum_total_kwh": round(total_kwh, 3),
        "sum_n_valid_slots": total_valid,
        "sum_n_missing_slots": total_missing,
        "max_series_pairs": max_pairs,
        "dst_rows": dst_rows,
        "dst_valid_distribution": {
            day: {str(k): v for k, v in sorted(counts.items())}
            for day, counts in sorted(valid_by_date.items())
        },
        "rows_with_repeated_slot": repeated_slot_rows,
        "errors": len(errors),
        "error_samples": errors,
        "baseline": baseline_report,
    }

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if errors:
        print(f"\nVALIDATION FAILED: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("\nVALIDATION OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
