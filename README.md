# P08 - Intelligent Analysis of Energy Consumption with Big Data and Deep Learning

End-to-end pipeline over the Low Carbon London dataset (half-hourly readings,
5,566 households, 2011-11-23 -> 2014-02-28), plus a separate Deep Learning
workload on a 5-household hourly sample.

- **Big Data chain:** HDFS -> MapReduce job 1 (day) -> MapReduce job 2 (month + cost)
  -> Iceberg -> Spark SQL -> Parquet export -> Streamlit.
- **Deep Learning (separate, small volume):** GRU 24 h forecast and a daily
  autoencoder for anomaly detection.

## Team and branches

| Person | Branch | Scope |
|---|---|---|
| Taher (Person 1) | `solo-Taher` | Job 1, half-hourly export, LSTM, LSTM vs GRU |
| Rahma (Person 2) | `solo-Rahma` | Job 2, Iceberg, dashboard, GRU, Autoencoder |
| Integration | `Main` | merged, always runnable |

## Status (branch `solo-Rahma`, 2026-11-20)

| Phase | Scope | State |
|---|---|---|
| 0-3 | Environment, profiling, Job 1, cluster, validation | done |
| 4 | Job 2 (monthly + cost) with 29 JUnit tests | done |
| 5 | Iceberg `lh.p08.daily`, `lh.p08.monthly`, `lh.test.monthly` | done |
| 6 | Parquet exports + Streamlit dashboard (10 pages) | done |
| 7 | GRU 24 h (single test read) + daily autoencoder | done (AE negative) |
| 8 | MR1 v1.1 (10 columns) integrated from Person 1 | **done** on the real 5-household sample; full 8.5 GB run belongs to Person 1 and was not reproduced here |
| 9 | Real 50-household run (40 Std + 10 ToU), own Iceberg version + dashboard page | **done**, MR1↔MR2 écart 0,0 |

Job 1 v1.1 uses **local `Europe/London` days/slots with DST (46/48/50 half-hours)**.
This supersedes the earlier GMT working hypothesis; the start-vs-end-of-period
timestamp convention remains an **unverified assumption**.

## Stack

Hadoop 3.3.6 (HDFS + YARN), Java 8 bytecode, Maven, Docker Compose,
Spark 3.5.1 + Iceberg 1.5.2, PyTorch CPU, Streamlit + Plotly.

## Repository layout

```
big-data/
  mapreduce/job1-daily/          Job 1 v1.1 - daily profile, 10 columns, local DST
  mapreduce/job2-monthly/        Job 2 - monthly kWh + cost, 29 JUnit tests, DST-aware
  spark/ iceberg/                notes on the Iceberg loading (see sql/)
sql/
  p08_load.sql                   DDL + first loads (daily, monthly)
  p08_move_test.sql              moves validation rows to lh.test.monthly
  p08_fixture_monthly.sql        loads the sample-fixture-v11 run
  p08_dashboard_export.sql       Iceberg -> data/dashboard/*.parquet
  p08_dashboard_export_fixture.sql
  p08_v11_real.sql               loads the real MR1 v1.1 run into lh.p08
  p08_dashboard_export_v11.sql   exports that run to data/dashboard/{monthly,daily}_v11
   p08_50mix.sql                  loads the real 50-household Std+ToU run (mr1-v11-50mix)
   p08_dashboard_export_50mix.sql exports it to data/dashboard/{monthly,daily}_50mix
  f06_quality.sql                quality metrics + chain reconciliation
scripts/
  make_mr1_v11_fixture.py        sample CSV -> MR1 v1.1 TSV (test fixture)
  check_fixture_vs_mr2.py        independent pandas check, tolerance 1e-6
  check_v11_vs_mr2.py            independent raw CSV -> local DST -> monthly check
  hdfs/make620k.awk              builds the 620k synthetic volume
  hdfs/run_f11.sh                timed MR2 run (F11 measurements)
  *.py                           DL: sample prep, GRU, baselines, autoencoder
dashboard/app.py                 Streamlit, read-only, 10 pages
docs/                            design, contract, runbook, proofs
```

## Quick start

```powershell
docker compose -f "infra/docker-compose.yml" up -d
docker exec p08-namenode hdfs dfsadmin -report
docker exec p08-namenode hdfs dfs -ls -h /p08/raw
```

Job 1 is mounted read-only in the namenode at `/job` (source
`big-data/mapreduce/job1-daily/target`). Job 2 has no mount, so copy its jar
once per container:

```powershell
docker cp big-data\mapreduce\job2-monthly\target\job2-monthly-aggregation.jar p08-namenode:/tmp/job2-monthly-aggregation.jar
docker exec p08-namenode hadoop jar /tmp/job2-monthly-aggregation.jar -D p08.run_id=my-run /p08/gold/mr1_daily /p08/gold/mr2_monthly /p08/raw/tariffs/tariffs_2013_price.csv
```

Note: `-D` and `p08.run_id=...` must be **two separate tokens**, otherwise
`GenericOptionsParser` leaves the option in the positional arguments and the
driver stops with `Usage: MonthlyAggregationDriver ...`.

## Results (measured on this branch)

### Job 1 - daily, 4 columns, 5-household sample

3,191 household-days, 2012-01-30 -> 2014-02-28, **28,416.517 kWh**,
152,806 valid readings, 105 duplicate slots averaged, 5 unparseable kWh,
3,161 `ok` + 30 `partial_data`. `peak_kwh_hh`, `peak_slot` and `tariff_group`
are NULL by construction.

### Job 2 - monthly + cost, on the v1.1 test fixture

Fixture `sample-fixture-v11` (10 columns, built from the same 5 households,
152,701 slot pairs, 467 missing slots, all `Std`):

| Metric | Value |
|---|---|
| output rows | **108** (household x month) |
| quality flags | 55 `ok`, 5 `partial_data`, 48 `no_tariff` |
| NULL costs | **48** (months outside the 2013 calendar; never 0) |
| total energy | 28,416.517005 kWh |
| total cost (2013 only) | **2,321.437773 GBP** |
| priced / unpriced slots | 87,594 / 65,107 |
| inconsistency counters | `series_slot_mismatch`, `series_mismatch`, `peak_mismatch`, `missing_slots_mismatch`, `duplicate_slots` = **0** |
| independent pandas check | every row within **1e-6** |

### Job 2 on the **real** v1.1 run (`mr1-v11-real-sample`)

Not the fixture: Job 1 v1.1 was rerun on `sample_5households.csv` (5 real
households, local `Europe/London` days/slots), then Job 2 v1.1 aggregated its
output. `run_id=mr2-v11-real-sample`.

| Metric | Value |
|---|---|
| MR1 output / MR2 output | 3,191 daily rows / **108** monthly rows |
| MR1 → MR2 reconciliation | **0.0 kWh** per household-month |
| Independent check from raw CSV | max diff 2.8e-6 kWh, 5.2e-7 GBP, **0** flag differences, **48** NULL costs on both sides |
| Quality flags | 55 `ok`, 5 `partial_data`, 48 `no_tariff` |
| NULL costs | **48** (outside the 2013 calendar; never 0) |
| Total energy | 28,416.517 kWh |
| Total cost (2013 only) | **2,321.437776 GBP** |
| DST days / duplicate slots | 17 / 20 (slots 2 and 3 repeated on 27 Oct, summed, not overwritten) |
| `missing_slots_mismatch` | 0 |

The full 8.5 GB run remains Person 1's; only his recorded counters exist, and
they are labelled as such, not presented as a local measurement.

### F11 - three volumes, same job, same host

| Volume | Nature | Lines | `elapsed_ms` | mappers | reducers | map time | reduce time |
|---|---|---|---|---|---|---|---|
| V1 `mr1_v11_sample` | real sample (fixture) | 3,191 | 30,304 | 1 | 1 | 10,428 ms | 2,816 ms |
| V2 `synthetic_155k` | **synthetic** | 155,000 | 25,377 | 1 | 1 | 5,961 ms | 3,639 ms |
| V3 `synthetic_620k` | **synthetic** | 620,000 | 30,420 | 2 | 1 | 18,194 ms | 4,043 ms |

194x more lines, 1.0x elapsed time. Fixed costs (JVM start, YARN submission,
one 17,520-line tariff load per mapper through the DistributedCache) dominate
at these sizes and the cluster is a single Docker host. **No linear speed-up is
claimed.**

These timings were measured on 2026-11-11 with the **pre-DST jars**. The v1.1
jars were rebuilt on 2026-11-20; with the new Job 2 jar the only measurement so
far is `elapsed_ms=22,116` on 3,191 real rows. The synthetic volumes were **not**
re-measured, so the table above must not be attributed to the v1.1 jar.

### Deep Learning (5-household hourly sample, not a Big Data volume)

- GRU 48 -> 24 h, selected on validation only: `runA_l1` (val MAE 0.1206) kept,
  `runB_l1cal` (0.1231) dropped. Single test read: MAE **0.1980** vs seasonal
  **0.2014**, RMSE 0.4425 vs 0.4710, better on 15/24 horizons.
- Daily autoencoder: threshold = P95 of validation errors (0.2338 kWh/h),
  pre-registered rule = 40 % detection at 1 % false alerts. Observed 12.4 %,
  so the test set was **never read**: documented **negative result**.

## Limitations (declared, not hidden)

- The old 4-column MR1 v1 output (no slots, no peaks, no `tariff_group`) is kept
  in `lh.p08.daily` for comparison. The 10-column v1.1 profile is available in
  `lh.p08.daily_v11` / the dashboard page **Run reel v1.1**.
- `lh.p08.monthly` now holds the **real 5-household sample** (`mr1-v11-real-sample`);
  the fixture and contract runs remain isolated in `lh.test.monthly`. No
  synthetic volume is ever presented as a measurement.
- Days and slots are **local `Europe/London`** (DST 46/48/50) since v1.1. The
  **start-vs-end-of-period timestamp convention is still unverified**; the cited
  guide sentence has not been re-read in `ideep08.pdf`.
- Cost is an exercise estimate (flat 14.228 p/kWh for `Std`, 2013 only,
  excluding taxes and standing charges).
- Single Docker host; the 8.5 GB full run belongs to Person 1 and is not
  reproduced here.
- Le Deep Learning (GRU + autoencodeur) est un livrable exigé oralement par l'enseignante. Le sujet écrit (ideep08.pdf §12) le classe hors périmètre ; cette exigence orale n'est pas confirmée par écrit à ce jour. `ideep08.pdf` §9.2 limite le ML optionnel aux méthodes classiques (pas de LSTM/Transformer/autoencodeur). Résultats inchangés : GRU sélectionné sur validation, test lu une seule fois, MAE 0,1980 contre 0,2014 pour la base saisonnière (gain faible) ; autoencodeur = résultat négatif documenté, test jamais lu.

## Data policy

Raw data (8.5 GB) and job outputs are never committed: `.gitignore` excludes
`data/**/*.csv|parquet|npz`, `models/`, `data/dashboard/`, `target/`, `tmp/`,
`metastore_db/` and `derby.log`.

## Documentation

- `docs/01_MR1_MR2_CONTRACT.md` - 10-column schema, slot rule, invariants
- `docs/03_MR2_DESIGN.md` - Job 2 design, decisions, tests T05-T08
- `docs/04_PREUVES_F01_F11.md` - F01 hashes, F06 quality, F10 rationale,
  F11 volumes, T01-T10 matrix (exact wording from `ideep08.pdf` §17)
- `docs/00_STATUS_ETAPE_25_A_COLLER.md` - ready-to-paste text for the
  user-owned status log (that file is deliberately not edited)
- `docs/00_PROJECT_STATUS.md` - chronological log of every step
- `docs/cluster-runbook.md` - cluster start/stop and troubleshooting
