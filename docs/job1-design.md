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

### Validation (contract v1.1)

```
python big-data/mapreduce/job1-daily/tools/validate_mr1.py \
    --input <local copy of part-r-*> [--baseline data/processed/daily_consumption_v1.csv]
```

The validator checks every row (10 fields, slots, missing, sum(series)==total,
peak, repeated fall-back slots) and the aggregates, then prints a JSON summary.

## 8. Limitations

- One-node cluster: at most ~3 concurrent mappers (4 GB YARN memory), so the
  full run takes hours, dominated by the map phase.
- Output is not globally sorted (single reducer, no secondary sort).
- Days with zero readings do not appear in the output; consumers must handle
  gaps (`n_missing_slots > 0` is the in-row signal).
- `series` is a text column: the full output is ~10x bigger than the v1.0 CSV.
  Consumers that only need daily totals can read columns 1-9 only.
