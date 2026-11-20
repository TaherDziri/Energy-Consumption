# Job 1 - Daily half-hourly profile per household

## 1. Goal

Transform 167.9 million half-hourly readings into one row per
(household, **local** day), contract **v1.1**:

```
household_id  date  tariff_group  total_kwh  n_valid_slots
n_missing_slots  peak_kwh_hh  peak_slot  avg_valid_kwh_hh  series
```

Output: `hdfs:///p08/gold/mr1_daily` (TSV, no header).
Contract: `docs/data-contract.md`, section 3.
The v1.0 four-column output is archived at `/p08/processed/daily_consumption`.

## 2. Location

```
big-data/mapreduce/job1-daily/
  pom.xml
  src/main/java/tn/isima/energy/job1/
    Reading.java                 one validated reading (+ local date, slot, tariff)
    LineParser.java              CSV line -> Reading, statuses, counters
    LocalSlot.java               UTC -> Europe/London date + slot, expected slots
    TimestampAccumulator.java    per-timestamp {sum, count, slot}, duplicates averaged
    DailyRecord.java             formats the 10-field TSV line (peak, series, ...)
    DailyConsumptionMapper.java
    DailyConsumptionCombiner.java
    DailyConsumptionReducer.java
    DailyConsumptionDriver.java
  src/test/java/tn/isima/energy/job1/
    LineParserTest.java
    LocalSlotTest.java
    TimestampAccumulatorTest.java
    DailyRecordTest.java
  tools/validate_mr1.py          full-file validator of the contract
```

## 3. Pipeline

| Stage | Key | Value | Role |
|---|---|---|---|
| Mapper | `household|localDate` | `tariff;slot;timestamp;kwh` | parse a line, skip `Null`/header, convert UTC -> London |
| Combiner | same | `tariff;slot;timestamp;sum;count` | pre-aggregate duplicates per split |
| Reducer | same | 10-field TSV row | average duplicates, build series/peak/missing |

The reducer accepts both value formats, so it works with or without the combiner.

### Why averaging, not summing

115,453 rows repeat an existing `(LCLid, DateTime)`. Summing them would inflate
energy. The accumulator keeps, per UTC timestamp, `{sum, count}` and contributes
`sum / count` to the day.

### Why the UTC timestamp stays the key

On a fall-back day two distinct UTC timestamps map to the same local slot.
Keeping the raw timestamp as the map key keeps both physical half-hours, which
is exactly what `series` must contain. Merging by slot would silently lose
~30 minutes of energy per household per year.

## 4. Design decisions

- **Local day**: the raw `DateTime` is UTC; the contract day and slot are
  `Europe/London`. In summer the 23:30 UTC reading belongs to the next local day.
- **Expected slots from the timezone rules**, not from a hardcoded list:
  `Duration(startOfDay, startOfNextDay) / 30 min` gives 46 / 48 / 50.
- `n_missing_slots = expected - n_valid`, clamped at 0; a counter reports any
  day with more readings than the local day can hold.
- **Tariff** comes from the raw `stdorToU` column (`Std` / `ToU`); any other
  value is dropped and counted (`unknown_tariff`), never guessed.
- **Peak tie** keeps the earliest slot (strict `>` while scanning in order).
- Numeric formatting is locale independent (`Locale.ROOT`), totals keep 3 dp,
  series/peak/avg use at most 6 dp with trailing zeros stripped
  (`0.0` for a measured zero).
- Reducer key is `NullWritable`; the output separator is set to `\t`.

## 5. Tests

37 JUnit 4 tests, all passing:

- `LineParserTest` (12): header, valid line, `Std`/`ToU`, `Null`, malformed,
  non-numeric, negative, unknown tariff, BOM, off-grid helper.
- `LocalSlotTest` (7): 46/48/50 expected slots, spring skip of slots 2-3,
  fall-back repetition of slots 2-3, summer/winter midnight boundary.
- `TimestampAccumulatorTest` (9): distinct timestamps, duplicates averaged,
  combiner format, both fall-back half-hours kept, chronological sort,
  tariff conflict, malformed/range rejection.
- `DailyRecordTest` (9): the three reference rows of
  `docs/01_MR1_MR2_CONTRACT.md`, empty day shape, measured zero, peak tie,
  fall-back 50 slots with repeated indexes, spring 46 slots, number formatting.

## 6. Build

```
mvn -f big-data/mapreduce/job1-daily/pom.xml clean package
```

- Maven compiler `--release 8` (cluster JVM is Java 8; class file major 52).
- Hadoop 3.3.6 dependencies are `provided`; the jar is thin (~20 KB).
- Artifact: `target/job1-daily-consumption.jar`, mounted read-only in the
  namenode at `/job/job1-daily-consumption.jar` by `infra/docker-compose.yml`.

## 7. Run

```
docker exec p08-namenode hadoop jar /job/job1-daily-consumption.jar \
    /p08/raw/CC_LCL-FullData.csv /p08/gold/mr1_daily
```

Note: no class name, the manifest provides `Main-Class`.

### Measured full run (2026-11-06)

| Metric | Value |
|---|---|
| Input | 8,551,075,774 bytes, 64 map splits |
| Runtime | 683,471 ms (11 min 24 s): ~6.5 min map, ~4.8 min reduce |
| Output | 1,643,062,284 bytes, one `part-r-00000` |
| `readings_valid` | 167,926,914 |
| `missing_null` | 5,560 |
| `duplicate_rows_averaged` | 115,453 |
| `malformed` / `negative` / `unknown_tariff` / `readings_off_grid` | 0 |
| `tariff_conflict` / `days_more_than_expected` / `days_dropped_empty` | 0 |
| `dst_days` (rows on a 46/50-slot local day) | 17,313 |

### Validation on the full run

`validate_mr1.py` on all 3,510,463 rows, baseline = the v1.0 output:

| Check | Result |
|---|---|
| `errors` | **0** |
| Rows | 3,510,463 (v1.0: 3,510,403; **+60** from regrouping UTC days into local days) |
| Households | 5,561 (identical set) |
| `sum(total_kwh)` | **35,539,823.307 kWh** (v1.0: 35,539,823.307, diff **0.000**) |
| `sum(n_valid_slots)` | **167,811,461** (identical per household, no mismatch) |
| `max_abs_household_total_diff` | **0.0 kWh** |
| Max series length | 50 (fall-back day) |
| Rows with a repeated slot index | 10,705 (fall-back days, both physical half-hours kept) |
| DST distribution | 2012-03-25: 1,185 rows with 46 slots; 2012-10-28: 5,502 with 50; 2013-03-31: 5,399 with 46; 2013-10-27: 5,176 with 50 |

Energy and valid slots are **exactly conserved**: the only difference with v1.0
is the day attribution (UTC -> Europe/London), which moves 60 household-day
boundaries. No row violates the contract.

The single reducer shuffles the whole map output (the `series` column makes it
~2 GB). On this 4 GB nodemanager the **first reduce attempt died in the shuffle
with `OutOfMemoryError: Java heap space`**; Hadoop retried the reduce task and
the second attempt succeeded. To avoid the retry, run with a larger reducer heap:

```
-D mapreduce.reduce.memory.mb=3072 \
-D mapreduce.reduce.java.opts=-Xmx2560m \
-D mapreduce.reduce.shuffle.input.buffer.percent=0.5
```

### Validation (contract v1.1)

```
python big-data/mapreduce/job1-daily/tools/validate_mr1.py \
    --input <local copy of part-r-*> [--baseline <local copy of the v1.0 CSV>]
```

The validator checks every row (10 fields, slots, missing, sum(series)==total,
peak, repeated fall-back slots) and the aggregates, then prints a JSON summary.

## 8. Limitations

- One-node cluster: at most ~3 concurrent mappers (4 GB YARN memory); the full
  run measured 11 min 24 s (see above), the map phase dominates.
- Output is not globally sorted (single reducer, no secondary sort).
- Days with zero readings do not appear in the output; consumers must handle
  gaps (`n_missing_slots > 0` is the in-row signal).
- `series` is a text column: the full output is 1.64 GB, ~15x the 106 MB v1.0
  CSV. Consumers that only need daily totals can read columns 1-9 only.
