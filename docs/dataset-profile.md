# Dataset Profile - CC_LCL-FullData.csv

Phase 1 deliverable. All numbers below were measured on the full 8.5 GB file, not on a sample.

## 1. Identity

| Field | Value |
|---|---|
| Dataset | Smart meters in London - Low Carbon London (LCL) |
| Archive | `CC_LCL-FullData.zip` (Deflate64 / Zip64, method 9) |
| Extraction | 7-Zip 26.05 (Windows built-in ZipFile and bsdtar fail on Deflate64) |
| Extracted file | `data/raw/CC_LCL-FullData.csv` |
| Bytes | 8,542,818,238 |
| Data rows | 167,932,474 (plus 1 header) |

## 2. Measured facts

| Metric | Value |
|---|---|
| Households | 5,566 |
| First timestamp | 2011-11-23 09:00:00 |
| Last timestamp | 2014-02-28 00:00:00 |
| Tariff `Std` rows | 134,148,703 |
| Tariff `ToU` rows | 33,783,771 |
| `Null` values | 5,560 (all off-grid periods) |
| Duplicate `(LCLid, DateTime)` rows | 115,453 |
| Distinct `(LCLid, DateTime)` keys | 167,811,461 |
| Total energy (raw sum of valid values) | 35,560,708.7 kWh |
| Malformed rows | 0 |
| Empty values | 0 |
| Non-numeric values | 0 |
| Negative values | 0 |

The file is grouped by household; rows inside a household are not guaranteed to be sorted by time.

## 3. Per-household profile

`docs/dataset-profile/household_profile.csv` (copy of the Phase 1 artifact) contains one row per household:

| Column | Meaning |
|---|---|
| `household_id` | `LCLid` |
| `rows` | source rows for that household |
| `missing` | rows whose value is `Null` |
| `first_timestamp` | earliest timestamp |
| `last_timestamp` | latest timestamp |
| `total_kwh` | raw sum of valid values (duplicates included once) |

Producer script: `deep-learning/preprocessing/profile_dataset.py` (streaming, constant memory,
optional row LIMIT argument for smoke tests).

## 4. Cross-validation against Job 1

| Check | Result |
|---|---|
| Sum of Job 1 daily `total_kwh` | 35,539,823.3 kWh |
| Raw profile total | 35,560,708.7 kWh |
| Difference | 20,885.4 kWh (0.0587%) - explained by duplicate averaging |
| Per-household comparison | 5,566 households, 0 negative differences, mean 3.752 kWh, max 83.467 kWh |
| Exact duplicate proof (`MAC005198`) | recomputed 31,415.959010 = Job 1 31,415.959; correction 83.467000 = observed gap |
| Households in Job 1 output | 5,561 (5 have a single `Null` row only) |

## 5. Caveats

- A reading is attributed to the calendar date of its own timestamp (Option A). A `00:00:00`
  reading counts in the new day although it may describe the previous evening (30-minute boundary effect).
- `MAC004067` has 31,186 non-null source rows, all `0.0` (31,165 distinct half-hours after
  deduplication): valid data, not a parsing error.
- Very high per-household totals (e.g. `MAC005198` at 31,499 kWh over ~2.3 years) reflect the
  source data, not an aggregation error: they were reproduced independently from the raw file.
