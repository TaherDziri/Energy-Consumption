# P08 - Intelligent Analysis of Energy Consumption with Big Data and Deep Learning

End-to-end pipeline over the Low Carbon London dataset (167.9 M half-hourly readings,
5,566 households, 2011-11-23 -> 2014-02-28).

Person 1: Hadoop / MapReduce (Job 1, half-hourly export) and deep learning (LSTM, LSTM vs GRU).
Person 2: MapReduce (Job 2, monthly) and deep learning (GRU, Autoencoder). Dashboard shared.

## Team and branches

| Person | Branch | Scope |
|---|---|---|
| Taher (Person 1) | `solo-Taher` | Job 1, half-hourly export, LSTM, LSTM vs GRU |
| Rahma (Person 2) | `solo-Rahma` | Job 2, GRU, Autoencoder |
| Integration | `Main` | merged, always runnable |

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Environment | done |
| 1 | Dataset profiling | done |
| 2 | Job 1 code + 15 unit tests + jar | done |
| 3 | Hadoop 3.3.6 cluster, HDFS ingest, Job 1 on full data, validation | done |
| 4 | Half-hourly export + LSTM | next |
| 5 | LSTM vs GRU comparison | pending |
| 6 | Dashboard | pending |
| 7 | Documentation + git | done (initial push) |

## Stack

Hadoop 3.3.6 (HDFS + YARN), Java 8 bytecode, Maven, Docker Compose, Spark/Iceberg (later phases),
PyTorch CPU, Streamlit (dashboard).

## Repository layout

```
big-data/
  mapreduce/job1-daily/     Job 1 - daily kWh per household (delivered)
  mapreduce/job2-monthly/   Job 2 - monthly kWh per household (Person 2)
  spark/                    Spark jobs (later)
  iceberg/                  Iceberg table definitions (later)
data/
  raw/                      source CSV (never committed)
  processed/                local copies of job outputs (never committed)
deep-learning/
  preprocessing/            streaming profiler, half-hourly export
  lstm/ gru/ autoencoder/   models
docs/
  data-contract.md          single source of truth for shared datasets
  dataset-profile.md        Phase 1 measurements
  job1-design.md            Job 1 design, tests, run metrics
  cluster-runbook.md        start/stop, health checks, troubleshooting
  handoff-job2.md           checklist for Person 2
  samples/                  small committed extracts
  dataset-profile/          per-household profile artifact
infra/
  docker-compose.yml        Hadoop cluster (4 daemons)
dashboard/                  Streamlit app (later)
```

## Quick start

```
docker compose -f "infra/docker-compose.yml" up -d
docker exec p08-namenode hdfs dfsadmin -report
docker exec p08-namenode hdfs dfs -ls -h /p08/raw
```

Full instructions: `docs/cluster-runbook.md`.

## Documentation

- Data contract (read this first): `docs/data-contract.md`
- Dataset profile: `docs/dataset-profile.md`
- Job 1 design and results: `docs/job1-design.md`
- Cluster runbook: `docs/cluster-runbook.md`
- Person 2 handoff: `docs/handoff-job2.md`

## Data policy

Raw data (8.5 GB) and job outputs (101 MB and growing) are never committed.
`.gitignore` excludes `data/raw/`, `data/processed/*.csv`, `target/`, model artifacts and logs.
Only small extracts under `docs/samples/` are versioned.

## Branches

- `Main` - integration, always runnable
- `solo-Taher` - Person 1 work
- `solo-Rahma` - Person 2 work
