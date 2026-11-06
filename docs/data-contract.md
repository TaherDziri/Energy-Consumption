# P08 - Data Contract (Big Data <-> Deep Learning <-> Dashboard)

Version 1.0 - 2026-11-06
Owner: Person 1 (Big Data, Job 1). Audience: Person 2 (Job 2, GRU, Autoencoder), dashboard, report.

This document is the single source of truth for every dataset exchanged inside P08.
If an implementation disagrees with this document, the document wins (then we update it).

---

## 1. Source dataset

| Field | Value |
|---|---|
| Dataset | Smart meters in London - Low Carbon London (LCL) |
| File | `data/raw/CC_LCL-FullData.csv` |
| Size | 8,542,818,238 bytes |
| Data rows (excluding header) | 167,932,474 |
| Households (`LCLid`) | 5,566 |
| Period | 2011-11-23 09:00:00 -> 2014-02-28 00:00:00 |
| Tariff split | `Std` 134,148,703 rows / `ToU` 33,783,771 rows |
| Version control | never committed (see `.gitignore`) |

### Columns

| # | Column | Example | Type |
|---|---|---|---|
| 1 | `LCLid` | `MAC000002` | string |
| 2 | `stdorToU` | `Std` or `ToU` | string |
| 3 | `DateTime` | `2012-10-12 00:30:00.0000000` | timestamp, 7 fractional digits |
| 4 | `KWH/hh (per half hour)` | ` 0.132` | decimal with a leading space |

Exactly one header line, at the top of the file.

---

## 2. Mandatory parsing rules

1. `Null` (literal string) means missing. Never convert it to `0`.
   5,560 rows are `Null` (off-grid / disconnected periods).
2. The numeric value may start with a space: trim before parsing.
3. Duplicate `(LCLid, DateTime)` keys: 115,453 rows. They are averaged, never double-summed:
   for a key with values `v1..vn`, its contribution is `mean(v1..vn)`.
4. Daily attribution (Option A): a reading belongs to the calendar date of its own `DateTime`.
   Known boundary effect: a reading stamped `00:00:00` is attributed to day D even though it may
   represent consumption from the previous evening. Accepted and documented.
5. `0.0` is a valid reading (zero consumption), not a missing value.
6. The file is grouped by household, but rows are not guaranteed sorted by timestamp.
7. No malformed, negative or non-numeric values exist (0 of each).

---

## 3. Job 1 output - daily consumption (DELIVERED)

| Field | Value |
|---|---|
| HDFS path | `/p08/processed/daily_consumption/part-r-00000` |
| Local copy | `data/processed/daily_consumption.csv` (not committed) |
| Format | CSV, UTF-8, LF, no header, comma separated |
| Rows | 3,510,403 |
| Size | 106,583,320 bytes |

### Schema (fixed)

| # | Column | Type | Meaning |
|---|---|---|---|
| 1 | `household_id` | string | `LCLid`, e.g. `MAC000002` |
| 2 | `date` | `yyyy-MM-dd` | calendar day |
| 3 | `total_kwh` | decimal (3 dp) | sum of deduplicated half-hourly values of that day |
| 4 | `reading_count` | integer | number of distinct half-hour timestamps used that day (0 < n <= 48) |

First rows (full sample: `docs/samples/daily_consumption_head20.csv`):

```
MAC000002,2012-10-12,7.098,46
MAC000002,2012-10-13,11.087,48
MAC000002,2012-10-14,13.223,48
```

### Invariants (verified on the real run)

| Invariant | Value |
|---|---|
| Sum of `total_kwh` | 35,539,823.3 kWh |
| Sum of `reading_count` | 167,811,461 (= 167,926,914 valid - 115,453 duplicates) |
| Households present | 5,561 |
| Date range | 2011-11-23 -> 2014-02-28 |
| Days with more than 48 readings | 0 |

### Known anomalies

- 5 households have no output row: `MAC001150`, `MAC005556`, `MAC005559`, `MAC005560`, `MAC005563`.
  Each has exactly one source row and it is `Null`.
- `MAC004067` is present but always `0.000` (31,165 readings): a real zero-consumption meter.
- `total_kwh` is below the raw source sum (35,560,708.7) by 20,885.4 kWh (0.0587%):
  exactly the effect of averaging duplicate rows instead of summing them.

### Job 1 counters (MapReduce group `P08`)

| Counter | Value | Meaning |
|---|---|---|
| `readings_valid` | 167,926,914 | parseable, non-null rows |
| `missing_null` | 5,560 | `Null` rows, skipped |
| `malformed` | 0 | wrong column count |
| `negative` | 0 | negative kWh values |
| `value_parse_error` | 0 | non-numeric value |
| `header_skipped` | 1 | header line |
| `duplicate_rows_averaged` | 115,453 | rows collapsed by the averaging rule |
| `days_more_than_48` | 0 | days with more than 48 distinct timestamps |
| `days_dropped_empty` | 0 | days that produced no reading |

---

## 4. Job 2 output - monthly consumption (TO BE DELIVERED BY PERSON 2)

| Field | Value |
|---|---|
| HDFS path | `/p08/processed/monthly_consumption/part-r-*` |
| Format | CSV, UTF-8, LF, no header, comma separated |
| Schema | `household_id,year_month,total_kwh,day_count` |

| # | Column | Type | Meaning |
|---|---|---|---|
| 1 | `household_id` | string | same key as Job 1 |
| 2 | `year_month` | `yyyy-MM` | e.g. `2012-10` |
| 3 | `total_kwh` | decimal | sum of the month's daily `total_kwh` |
| 4 | `day_count` | integer | number of daily rows summed (days with data), not calendar days |

### Recommended input

Use Job 1 output (`/p08/processed/daily_consumption`), not the 8.5 GB raw file:

- 64x less data (101 MB vs 8,558 MB);
- duplicate-averaging and `Null` rules are already applied, so Job 2 cannot diverge from Job 1.

If Job 2 is computed from the raw file, it must re-implement sections 2.1-2.4 exactly,
otherwise the monthly totals will not reconcile with Job 1.

### Acceptance tests for Job 2

| Test | Expected |
|---|---|
| Sum of `total_kwh` over all months | 35,539,823.3 kWh (float tolerance) |
| Sum of `day_count` | 3,510,403 |
| Distinct households | 5,561 |
| Distinct months | 28 (2011-11 -> 2014-02) |
| Reconciliation per household | sum(Job 2 total_kwh) == sum(Job 1 total_kwh) |

Months without any daily row do not appear (no zero-filled rows).

---

## 5. Half-hourly series - input for the deep learning models (PROPOSED, Phase 4)

LSTM/GRU/Autoencoder need the 48-steps-per-day series; daily totals are not usable for them.

| Field | Value |
|---|---|
| HDFS path | `/p08/processed/halfhourly_series/` |
| Format | CSV, UTF-8, LF, no header |
| Schema | `household_id,timestamp,kwh` |
| `timestamp` | `yyyy-MM-dd HH:mm:ss` (fraction dropped) |
| `kwh` | deduplicated value (mean of duplicates), `0.0` allowed |
| Missing half-hours | absent rows by default; imputation policy to be agreed |
| Expected rows | 167,811,461 |

Open point to settle with Person 2 before Phase 4: whether missing half-hours are
dropped (ragged sequences) or imputed (fixed 48-step windows).

---

## 6. Conventions

- UTF-8 without BOM, LF line endings, comma separator, no header on outputs.
- Decimal separator `.`, no thousands separators.
- Never commit raw data or outputs (see `.gitignore`).
- Any schema or rule change requires a version bump and an entry in the change log.

## 7. Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-11-06 | Initial contract after Job 1 validation on the full dataset |
