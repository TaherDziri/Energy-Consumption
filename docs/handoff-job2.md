# Handoff - Person 2 (Job 2, GRU, Autoencoder)

## What you get from this repository

- Job 1 implementation and its validated output contract.
- The cluster definition used to produce that output (`infra/docker-compose.yml`).
- The full data contract: `docs/data-contract.md`.

## Your first three actions

1. Clone the repository, then bring your branch up to date with the shared work:

```
git checkout solo-Rahma
git merge origin/Main
```

`Main` contains the validated Job 1 and every document listed here; `solo-Rahma` was created
before that work and does not, so merge before starting.
2. Read `docs/data-contract.md` sections 2, 3 and 4. They define the input you may rely on
   and the exact schema your Job 2 must produce.
3. Start the cluster (`docs/cluster-runbook.md`, section 3) and check that Job 1 output is present:

```
docker exec p08-namenode hdfs dfs -ls /p08/processed/daily_consumption
```

If the path is empty, the data is not in your local HDFS yet: either upload the CSV and run Job 1
(runbook, sections 5 and 6), or ask Person 1 for the 101 MB output file.

## Job 2 in one paragraph

Aggregate Job 1 daily rows into `household_id,year_month,total_kwh,day_count`, write to
`/p08/processed/monthly_consumption`, and satisfy the five acceptance tests in
`docs/data-contract.md`, section 4. Do not read the 8.5 GB raw file: it is 64x more I/O and you
would have to re-implement the duplicate-averaging rule.

## Input format (recap)

Job 1 output is CSV with **no header**:

```
household_id,date,total_kwh,reading_count
```

First lines (real data):

```
MAC000002,2012-10-12,7.098,46
MAC000002,2012-10-13,11.087,48
MAC000002,2012-10-14,13.223,48
```

Counters you can trust from Job 1, and which Job 2 must reproduce after aggregation:

| Quantity | Value |
|---|---|
| Input rows | 3,510,403 |
| Distinct households | 5,561 |
| Sum of `total_kwh` | 35,539,823.3 kWh |
| Sum of `reading_count` | 167,811,461 |
| Months | 28 (2011-11 -> 2014-02) |

## Suggested implementation shape (not prescriptive)

- Mapper: parse 4 fields, emit key `household_id|yyyy-MM` and value `total_kwh,1`.
- Combiner/Reducer: sum `total_kwh`, sum the `1`s into `day_count`.
- Guard against malformed lines with a counter; do not silently drop them.
- Emit `household_id,year_month,total_kwh,day_count` with `day_count` = number of daily rows,
  not the number of readings. `day_count` sums to 3,510,403 across all output rows.
- Use `TextOutputFormat` with `mapreduce.output.textoutputformat.separator=,` or write the comma
  explicitly in the value.
- Compile with `--release 8` like Job 1: the cluster JVM is Java 8.

## Acceptance tests (run these before declaring Job 2 done)

```powershell
# count rows, households, months and totals from the retrieved output
$f = "data/processed/monthly_consumption.csv"
$sumKwh = 0.0; $sumDays = 0L
$hh = @{}; $mm = @{}
foreach ($line in [System.IO.File]::ReadLines((Resolve-Path $f))) {
  if (-not $line) { continue }
  $p = $line.Split(',')
  if ($p.Length -ne 4) { continue }
  $sumKwh += [double]::Parse($p[2], [System.Globalization.CultureInfo]::InvariantCulture)
  $sumDays += [int]$p[3]
  $hh[$p[0]] = 1
  $mm[$p[1]] = 1
}
"rows        = $((Get-Content $f | Measure-Object -Line).Lines)"
"households  = $($hh.Count)   (expect 5561)"
"months      = $($mm.Count)   (expect 28)"
("sum total_kwh = {0:F1}   (expect 35539823.3)" -f $sumKwh)
"sum day_count = $sumDays   (expect 3510403)"
```

Per-household reconciliation is the stronger test: the sum of a household's monthly `total_kwh`
must equal the sum of its daily `total_kwh` from Job 1, to output rounding.

## Deep learning inputs

Daily totals are not suitable for LSTM/GRU (24 h = 48 half-hour steps). The half-hourly series
contract is in `docs/data-contract.md`, section 5. Its export (Phase 4, Person 1) is not produced yet:
agree with Person 1 on the missing-value policy before training.

## Ground rules

- Never commit raw data or job outputs.
- Do not change a schema or a rule in `docs/data-contract.md` without a version bump and a change-log entry.
- Keep Job 2 counters (rows in, rows out, malformed, missing) so the results can be audited.
