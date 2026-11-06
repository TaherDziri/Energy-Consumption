# Job 1 extension request — MR1 output contract v1.1

**From:** Rahma (Person 2)
**To:** Taher (Person 1)
**Date:** 2026-11-06
**Status:** proposal — requires your agreement

## 1. Why

The official cahier des charges (`ideep08.pdf`, §8.1–8.2 and F05) requires
Job 2 to produce, per household and month:

- `monthly_kwh`
- `estimated_cost_gbp` (nullable)
- `price_coverage`
- `max_half_hour_kwh`
- `valid_days`
- `quality_flag`
- `run_id`

The current Job 1 output is:

```
household_id,date,total_kwh,reading_count
```

It is correct for monthly kWh, but it does **not** contain:

- `tariff_group` (Std / ToU), required by §8.1 ("ne jamais perdre tariff_group");
- the half-hour `series`, required to apply ToU prices per slot;
- `peak_kwh_hh` / `peak_slot`, required for `max_half_hour_kwh`;
- `n_missing_slots`, required to compute completeness and `price_coverage`.

Without these fields, Job 2 cannot satisfy F05. Computing a cost from the
daily total would silently assume a flat price for every slot, which is
wrong for ToU households and for 2013 dynamic pricing.

## 2. Proposed change (same Job 1, no new job)

Extend the reducer output to one **TSV** line per `(household_id, date)`,
no header, UTF-8, LF, decimal separator `.`:

| # | Field | Type | Rule |
|---|---|---|---|
| 1 | `household_id` | string | unchanged |
| 2 | `date` | `yyyy-MM-dd` | unchanged |
| 3 | `tariff_group` | string | `Std` or `ToU`, from the source column |
| 4 | `total_kwh` | decimal | unchanged (sum of deduplicated values) |
| 5 | `n_valid_slots` | integer | distinct timestamps that day (currently `reading_count`) |
| 6 | `n_missing_slots` | integer | `48 - n_valid_slots` on ordinary days; DST convention documented |
| 7 | `peak_kwh_hh` | decimal | max deduplicated slot value |
| 8 | `peak_slot` | integer | slot index 0–47 of the peak |
| 9 | `avg_valid_kwh_hh` | decimal | `total_kwh / n_valid_slots` |
| 10 | `series` | string | `slot:kwh;slot:kwh;...` — **only observed slots** |

Example:

```
MAC000002	2012-10-12	Std	7.098	46	2	0.512	18	0.154304	0:0.11;1:0.13;...;47:0.09
```

A missing slot is **absent** from `series`, never `slot:0`. A real measured
zero is `slot:0.0`.

## 3. Why it is cheap to add

The reducer already has `TimestampAccumulator`, which keeps the
deduplicated value per timestamp. To produce the new fields you only need:

1. `tariff_group`: add it to `Reading` and `LineParser` (the raw column
   `stdorToU` is already present).
2. `series`: iterate the accumulator's timestamps and emit `slot:value`.
3. `peak`: max over the deduplicated values; `peak_slot` = its slot index.
4. `n_missing_slots`: `48 - distinctReadings()` (with the DST note).

No change to the duplicate-averaging rule, no change to the daily total.

## 4. Impact

- **Re-run required** on the full dataset (≈ 250 min on the current
  single-node cluster), because `series` cannot be derived from the
  existing 4-column output.
- For development, we can run on the 5-household sample first (fast).
- `docs/data-contract.md` must move from **v1.0 to v1.1**, with a change-log
  entry.
- Existing consumers of the 4-column file would break. Two options:
  - **Option A (recommended):** replace the output with the 10-field TSV.
  - **Option B:** keep the current output and add a second output path
    `/p08/processed/daily_profile/`. More disk and two jobs to maintain.

## 5. Job 2 output alignment (v1.1)

Proposed Job 2 output, CSV, no header:

```
household_id,year_month,tariff_group,monthly_kwh,estimated_cost_gbp,
price_coverage,max_half_hour_kwh,valid_days,quality_flag,run_id
```

Rules:

- `estimated_cost_gbp` is **empty (NULL)** when no documented price covers
  the slots; never `0`.
- `price_coverage = priced_slots / valid_slots` (0.0–1.0).
- Tariffs are applied **only to 2013**; other years → NULL.
- `run_id` identifies the execution.

## 6. Acceptance tests for the extension

1. Sum of `total_kwh` is unchanged: **35,539,823.3 kWh**.
2. Sum of `n_valid_slots` is unchanged: **167,811,461**.
3. For any day, `sum(series values) == total_kwh` (tolerance 0.001).
4. `peak_kwh_hh == max(series values)` and `peak_slot` matches.
5. `n_valid_slots == count(series pairs)`.
6. A synthetic 47-slot day with one missing slot must show
   `n_missing_slots = 1` and **no** `12:0` in `series`.

## 7. Decision needed

Please confirm:

- [ ] Option A (replace output) or Option B (second output path)
- [ ] `tariff_group` source: `stdorToU` column
- [ ] DST convention for `n_missing_slots`
- [ ] Version bump of `docs/data-contract.md` to v1.1

Once confirmed, Job 2 can be developed against the frozen v1.1 contract.
