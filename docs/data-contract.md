# P08 - Data Contract (Big Data <-> Deep Learning <-> Dashboard)

Version 1.1 - 2026-11-06 (Job 1 output extended to the 10-field daily profile)
Owner: Person 1 (Big Data, Job 1). Audience: Person 2 (Job 2, GRU, Autoencoder), dashboard, report.

This document is the single source of truth for every dataset exchanged inside P08.
If an implementation disagrees with this document, the document wins (then we update it).

---

## 1. Source dataset

| Field                        | Value                                            |
| ---------------------------- | ------------------------------------------------ |
| Dataset                      | Smart meters in London - Low Carbon London (LCL) |
| File                         | `data/raw/CC_LCL-FullData.csv`                   |
| Size                         | 8,542,818,238 bytes                              |
| Data rows (excluding header) | 167,932,474                                      |
| Households (`LCLid`)         | 5,566                                            |
| Period                       | 2011-11-23 09:00:00 -> 2014-02-28 00:00:00       |
| Tariff split                 | `Std` 134,148,703 rows / `ToU` 33,783,771 rows   |
| Version control              | never committed (see `.gitignore`)               |

### Columns

| #   | Column                   | Example                       | Type                           |
| --- | ------------------------ | ----------------------------- | ------------------------------ |
| 1   | `LCLid`                  | `MAC000002`                   | string                         |
| 2   | `stdorToU`               | `Std` or `ToU`                | string                         |
| 3   | `DateTime`               | `2012-10-12 00:30:00.0000000` | timestamp, 7 fractional digits |
| 4   | `KWH/hh (per half hour)` | ` 0.132`                      | decimal with a leading space   |

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

## 3. Job 1 output - daily profile (v1.1, DELIVERED)

Replaces the v1.0 four-column output, as requested in
`docs/02_JOB1_EXTENSION_REQUEST.md` (Option A accepted).

| Field      | Value                                              |
| ---------- | -------------------------------------------------- |
| HDFS path  | `/p08/gold/mr1_daily/part-r-*`                     |
| Archive    | `/p08/processed/daily_consumption` (v1.0, 4 fields) |
| Local copy | `data/processed/` (not committed)                  |
| Format     | TSV, UTF-8, LF, **no header**, **tab separated**   |
| Encoding   | decimal `.`, no thousands separator                |

### Schema (fixed, 10 fields)

| #   | Column             | Type           | Rule                                                                |
| --- | ------------------ | -------------- | ------------------------------------------------------------------- |
| 1   | `household_id`     | string         | `LCLid`                                                             |
| 2   | `date`             | `yyyy-MM-dd`   | **local (Europe/London)** calendar day                              |
| 3   | `tariff_group`     | string         | `Std` or `ToU`, from the raw `stdorToU` column                      |
| 4   | `total_kwh`        | decimal (3 dp) | sum of the deduplicated values of the day                           |
| 5   | `n_valid_slots`    | integer        | number of observed half-hours (physical entries, not distinct slots) |
| 6   | `n_missing_slots`  | integer        | `expected_slots(day) - n_valid_slots`, expected in {46, 48, 50}      |
| 7   | `peak_kwh_hh`      | decimal        | max deduplicated slot value (kWh per 30 min)                        |
| 8   | `peak_slot`        | integer        | slot index 0-47 of the peak; on a tie the earliest slot wins        |
| 9   | `avg_valid_kwh_hh` | decimal        | `total_kwh / n_valid_slots`                                         |
| 10  | `series`           | string         | `slot:kwh;slot:kwh;...` - **observed slots only**, chronological     |

Example (real row, sample run):

```text
MAC000002	2012-10-12	Std	7.098	46	2	0.512	18	0.154304	0:0.11;1:0.13;...;47:0.09
```

### Missing versus zero

- A missing slot is **absent** from `series`. It is never written as `slot:0`.
- A measured zero is `slot:0.0`.
- Empty day: `total_kwh=0.000`, `peak_kwh_hh`, `peak_slot`, `avg_valid_kwh_hh`
  and `series` are empty (no such row exists in the current dataset).

### Day and slot definition (critical)

The raw `DateTime` is **UTC**. The contract uses the **local** date and slot:

- `date` = `DateTime` converted to `Europe/London`, then the calendar date;
- `slot = hour * 2 + minute / 30` on the converted local clock;
- `expected_slots(day)` is computed from the timezone rules, never hardcoded:

| Day type                          | expected slots | Slots            |
| --------------------------------- | -------------- | ---------------- |
| ordinary                          | 48             | 0..47            |
| spring forward (last Sunday March) | 46             | 2 and 3 absent   |
| fall back (last Sunday October)    | 50             | 2 and 3 **twice** |

On a fall-back day the two physical half-hours that share a slot index are
kept as **two entries** in `series` (same `slot`, different values). They are
two distinct half-hours and must be summed by consumers, never merged.

### Invariants (must hold on the full run)

| Invariant                    | Value                                                  |
| ---------------------------- | ------------------------------------------------------ |
| Sum of `total_kwh`           | 35,539,823.3 kWh (regrouping does not change the energy) |
| Sum of `n_valid_slots`       | 167,811,461 (= 167,926,914 valid - 115,453 duplicates) |
| Per row: `n_valid_slots`     | equals the number of pairs in `series`                 |
| Per row: sum of `series`     | equals `total_kwh` (tolerance 0.001)                   |
| Per row: `peak_kwh_hh`       | equals `max(series values)`                            |
| Households present           | 5,561                                                  |
| Date range                   | 2011-11-23 -> 2014-02-28 (local)                       |

### Known anomalies (unchanged)

- 5 households have no output row: `MAC001150`, `MAC005556`, `MAC005559`,
  `MAC005560`, `MAC005563` (each has one source row and it is `Null`).
- `MAC004067` is present but always `0.000`: a real zero-consumption meter.
- `total_kwh` is below the raw source sum (35,560,708.7) by 20,885.4 kWh
  (0.0587%): the duplicate-averaging rule.

### Job 1 counters (MapReduce group `P08`)

| Counter                   | Meaning                                          |
| ------------------------- | ------------------------------------------------ |
| `readings_valid`          | parseable, non-null rows                         |
| `missing_null`            | `Null` rows, skipped                             |
| `malformed`               | wrong column count / bad timestamp               |
| `negative`                | negative kWh values                              |
| `unknown_tariff`          | tariff outside {Std, ToU} (0 expected)           |
| `value_parse_error`       | non-numeric value                                |
| `header_skipped`          | header line                                      |
| `readings_off_grid`       | readings not on the :00/:30 grid                 |
| `duplicate_rows_averaged` | rows collapsed by the averaging rule             |
| `tariff_conflict`         | one day with two different tariffs (0 expected)  |
| `dst_days`                | output rows whose local day is 46 or 50 slots    |
| `days_more_than_expected` | more readings than the local day can hold        |
| `days_dropped_empty`      | days that produced no reading                    |

Validator: `big-data/mapreduce/job1-daily/tools/validate_mr1.py`.

---

## 4. Job 2 output - monthly consumption (TO BE DELIVERED BY PERSON 2)

| Field     | Value                                         |
| --------- | --------------------------------------------- |
| HDFS path | `/p08/processed/monthly_consumption/part-r-*` |
| Format    | CSV, UTF-8, LF, no header, comma separated    |
| Schema    | `household_id,year_month,total_kwh,day_count` |

| #   | Column         | Type      | Meaning                                                         |
| --- | -------------- | --------- | --------------------------------------------------------------- |
| 1   | `household_id` | string    | same key as Job 1                                               |
| 2   | `year_month`   | `yyyy-MM` | e.g. `2012-10`                                                  |
| 3   | `total_kwh`    | decimal   | sum of the month's daily `total_kwh`                            |
| 4   | `day_count`    | integer   | number of daily rows summed (days with data), not calendar days |

### Recommended input

Use Job 1 v1.1 output (`/p08/gold/mr1_daily`), not the 8.5 GB raw file:

- ~60x less data than the raw file and the only file that carries `series`;
- duplicate-averaging, `Null` rules, DST slots and `tariff_group` are already
  applied, so Job 2 cannot diverge from Job 1.

If Job 2 is computed from the raw file, it must re-implement sections 2.1-2.4
and the DST rules of section 3 exactly, otherwise the monthly totals will not
reconcile with Job 1.

### Acceptance tests for Job 2

| Test                               | Expected                                     |
| ---------------------------------- | -------------------------------------------- |
| Sum of `total_kwh` over all months | 35,539,823.3 kWh (float tolerance)           |
| Sum of `valid_days`                | number of Job 1 rows (3.5 M, one per day)     |
| Distinct households                | 5,561                                        |
| Distinct months                    | 28 (2011-11 -> 2014-02)                      |
| Reconciliation per household       | sum(Job 2 total_kwh) == sum(Job 1 total_kwh) |
| Cost coverage                      | `price_coverage = priced_slots / valid_slots` |

Months without any daily row do not appear (no zero-filled rows).

---

## 5. Half-hourly series - input for the deep learning models (PROPOSED, Phase 4)

LSTM/GRU/Autoencoder need the 48-steps-per-day series; daily totals are not usable for them.

| Field              | Value                                                  |
| ------------------ | ------------------------------------------------------ |
| HDFS path          | `/p08/processed/halfhourly_series/`                    |
| Format             | CSV, UTF-8, LF, no header                              |
| Schema             | `household_id,timestamp,kwh`                           |
| `timestamp`        | `yyyy-MM-dd HH:mm:ss` (fraction dropped)               |
| `kwh`              | deduplicated value (mean of duplicates), `0.0` allowed |
| Missing half-hours | absent rows by default; imputation policy to be agreed |
| Expected rows      | 167,811,461                                            |

Open point to settle with Person 2 before Phase 4: whether missing half-hours are
dropped (ragged sequences) or imputed (fixed 48-step windows).

---

## 6. Conventions

- UTF-8 without BOM, LF line endings, comma separator, no header on outputs.
- Decimal separator `.`, no thousands separators.
- Never commit raw data or outputs (see `.gitignore`).
- Any schema or rule change requires a version bump and an entry in the change log.

## 7. Change log

| Version | Date       | Change                                                      |
| ------- | ---------- | ----------------------------------------------------------- |
| 1.0     | 2026-11-06 | Initial contract after Job 1 validation on the full dataset |
| 1.1     | 2026-11-06 | Job 1 output replaced by the 10-field daily profile (Option A of `02_JOB1_EXTENSION_REQUEST.md`): local Europe/London day, `tariff_group` from `stdorToU`, `series`, peak, missing slots. v1.0 output archived at `/p08/processed/daily_consumption`. |

## MR2 slot / DST contract (Job 2 input)

Since Job 1 v1.1, the same convention is also produced directly by MapReduce
(`/p08/gold/mr1_daily`), with `series` serialized as `slot:kwh;...`.
Both representations describe the same 50-household validation set; the
Parquet version below is what the deep-learning pipeline uses.

- Source timestamps in the raw CSV are UTC/GMT. Convert to Europe/London
  before computing the local date and the slot.
- `series` is a **list** of `[slot, kwh]` pairs. It is never a dictionary.
- `slot = hour * 2 + minute // 30` using the converted Europe/London time.
- `expected_slots` per local date:
  - normal day: 48
  - spring forward (last Sunday of March): 46 (slots 2 and 3 absent)
  - fall back (last Sunday of October): 50 (slots 2 and 3 present twice)
- `valid_slots` = number of entries in `series`
  (physical half-hours, not distinct slots).
- `n_missing_slots = expected_slots - valid_slots`.
- On fall back, slots 2 (01:00) and 3 (01:30) may appear twice.
  Those are two distinct physical half-hours and must be summed, not merged.
- One row per `(household_id, date)`.

Example (fall back, local date 2012-10-28):

```json
{
  "household_id": "MAC000145",
  "date": "2012-10-28",
  "series": [
    [0, 0.262],
    [1, 0.157],
    [2, 0.138],
    [2, 0.082],
    [3, 0.086],
    [3, 0.138],
    [4, 0.145]
  ],
  "expected_slots": 50,
  "valid_slots": 50,
  "n_missing_slots": 0
}
```
