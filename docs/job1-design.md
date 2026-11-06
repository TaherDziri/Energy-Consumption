# Job 1 - Daily Electricity Consumption per Household

## 1. Goal

Transform 167.9 million half-hourly readings into one row per (household, day):

```
household_id,date,total_kwh,reading_count
```

Output: `hdfs:///p08/processed/daily_consumption` (CSV, no header).
Contract: `docs/data-contract.md`, section 3.

## 2. Location

```
big-data/mapreduce/job1-daily/
  pom.xml
  src/main/java/tn/isima/energy/job1/
    Reading.java
    LineParser.java
    TimestampAccumulator.java
    DailyConsumptionMapper.java
    DailyConsumptionCombiner.java
    DailyConsumptionReducer.java
    DailyConsumptionDriver.java
  src/test/java/tn/isima/energy/job1/
    LineParserTest.java
    TimestampAccumulatorTest.java
```

## 3. Pipeline

| Stage | Key | Value | Role |
|---|---|---|---|
| Mapper | `household|yyyy-MM-dd` | `timestamp;kwh` | parse a line, skip `Null`/header |
| Combiner | same | `timestamp;sum;count` | pre-aggregate duplicates per split |
| Reducer | same | output row | average duplicates, sum the day |

The reducer accepts both value formats, so it works with or without the combiner.

### Why averaging, not summing

115,453 rows repeat an existing `(LCLid, DateTime)`. Summing them would inflate energy.
The reducer keeps, per timestamp, `{sum, count}` and contributes `sum / count` to the day.

## 4. Design decisions

- Day = calendar date of the reading's own timestamp (Option A), documented boundary effect.
- Reducer key is `NullWritable`, so `mapreduce.output.textoutputformat.separator` is set to `""`
  to avoid a leading tab.
- All quality signals are counters, never silent drops.
- Numeric formatting is locale-independent (`Locale.ROOT`).

## 5. Tests

15 JUnit 5 tests, all passing:

- `LineParserTest` (10): header, valid line with leading space, `Null`, malformed, non-numeric,
  negative, extra columns, timestamp with 7 fractional digits.
- `TimestampAccumulatorTest` (5): single values, duplicates averaged, combiner format,
  mixed formats, empty state.

A real bug was caught by these tests: the accumulator originally multiplied the combiner's sum
by its count, doubling duplicate values. Fixed and locked by `readsCombinerFormat`.

## 6. Build

```
mvn -f big-data/mapreduce/job1-daily/pom.xml clean package
```

- Maven compiler `--release 8` (cluster JVM is Java 8; class file major version 52).
- Hadoop 3.3.6 dependencies are `provided`; the jar is thin.
- Artifact: `target/job1-daily-consumption.jar` (~16 KB), `Main-Class` in the manifest.

## 7. Run (full dataset, measured)

| Metric | Value |
|---|---|
| Input | 8,542,818,238 bytes, 64 HDFS blocks (128 MB, replication 1) |
| Map attempts | 67 launched (64 splits + 3 failed retries), 1 speculative copy killed |
| Reducers | 1 |
| Map input records | 167,932,475 |
| Combine output records | 167,811,461 |
| Reduce output records | 3,510,403 |
| Shuffle bytes | 9,883,184,059 |
| Peak map memory | 696,872,960 bytes |
| Peak reduce memory | 1,820,549,120 bytes |
| Wall time | 250m41s |
| Result | `JOB1 STATUS = SUCCESS` |

Command (note: no class name, the manifest provides it):

```
hadoop jar /job/job1-daily-consumption.jar /p08/raw/CC_LCL-FullData.csv /p08/processed/daily_consumption
```

## 8. Limitations

- One-node cluster: at most ~3 concurrent mappers (4 GB YARN memory), hence the long runtime.
- Output is not globally sorted (single reducer, but no secondary sort).
- Days with zero readings do not appear in the output; consumers must handle gaps.
- The `00:00:00` boundary effect described in the data contract applies.

## 9. Validation summary

See `docs/dataset-profile.md`, section 4. Independent recomputation of one household matched
Job 1 to the third decimal, and the aggregate difference against the raw sum equals the
duplicate correction (20,885.4 kWh, 0.0587%).
