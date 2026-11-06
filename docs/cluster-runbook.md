# Cluster Runbook - Hadoop 3.3.6 on Docker (Windows)

## 1. Prerequisites

- Docker Desktop for Windows, engine running (WSL2 backend).
- Image `apache/hadoop:3.3.6` (ships Hadoop 3.3.6 and Java 8 - do not use it with Java 11 bytecode).
- The compose file: `infra/docker-compose.yml`.

## 2. Topology

| Service | Container | Hostname | Ports (host -> container) |
|---|---|---|---|
| NameNode | `p08-namenode` | `namenode` | 9870 (UI), 9000 (RPC) |
| DataNode | `p08-datanode` | `datanode` | 9864 (UI) |
| ResourceManager | `p08-resourcemanager` | `resourcemanager` | 8088 (UI) |
| NodeManager | `p08-nodemanager` | `nodemanager` | - |

- YARN capacity: 4096 MB, 4 vcores.
- Volumes: `p08_p08-nn`, `p08_p08-dn`, `p08_p08-rm`, `p08_p08-nm` (one per daemon, mounted at `/data`).
- Bind mounts on the NameNode: the project `data/` folder (read-only, `/p08-data`)
  and the Job 1 `target/` folder (read-only, `/job`).

## 3. Start / stop

```
docker compose -f "infra/docker-compose.yml" up -d
docker compose -f "infra/docker-compose.yml" ps
docker compose -f "infra/docker-compose.yml" stop
```

Destroy containers but keep HDFS data:

```
docker compose -f "infra/docker-compose.yml" down
```

Destroy everything, including HDFS data (requires re-upload of the CSV):

```
docker compose -f "infra/docker-compose.yml" down -v
```

## 4. Health checks

```
docker exec p08-namenode hdfs dfsadmin -report
docker exec p08-resourcemanager yarn node -list
```

Pass conditions: `Live datanodes (1)` and `Total Nodes:1` with state `RUNNING`.

Web UIs: HDFS http://localhost:9870 - YARN http://localhost:8088 - DataNode http://localhost:9864

## 5. HDFS layout

```
/p08/raw/CC_LCL-FullData.csv              input dataset (8,542,818,238 bytes, 64 blocks)
/p08/processed/daily_consumption/         Job 1 output
/p08/processed/monthly_consumption/       Job 2 output (Person 2)
```

Create directories:

```
docker exec p08-namenode hdfs dfs -mkdir -p /p08/raw /p08/processed
```

Upload the dataset (already done once, ~1m25s on this machine):

```
docker exec p08-namenode hdfs dfs -put -f /p08-data/raw/CC_LCL-FullData.csv /p08/raw/
```

## 6. Run Job 1

```
docker exec p08-namenode bash -lc 'hadoop jar /job/job1-daily-consumption.jar /p08/raw/CC_LCL-FullData.csv /p08/processed/daily_consumption'
```

The output directory must not exist. To re-run, remove it first:

```
docker exec p08-namenode hdfs dfs -rm -r -f /p08/processed/daily_consumption
```

Retrieve the result to the host:

```
docker exec p08-namenode bash -lc 'rm -rf /tmp/p08out && mkdir -p /tmp/p08out && hdfs dfs -get /p08/processed/daily_consumption/part-r-00000 /tmp/p08out/'
docker cp p08-namenode:/tmp/p08out/part-r-00000 data/processed/daily_consumption.csv
```

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No such file` inside container | host bind path wrong or empty | compare `docker inspect <c> --format '{{json .Mounts}}'` with the real path |
| `Usage: DailyConsumptionDriver ...` | class name passed after the jar | do not repeat the class name; the manifest provides it |
| `UnsupportedClassVersionError` | jar compiled for Java 11+ | rebuild with `--release 8` |
| `Total Nodes:0` | NodeManager still starting | wait, then `yarn node -list` again |
| Container restarts in a loop | `/data` volume missing (`chmod /data` fails) | keep one volume mounted at `/data` per service |
| Job stuck in `ACCEPTED` | not enough YARN memory | lower `mapreduce.map.memory.mb` or raise `yarn.nodemanager.resource.memory-mb` |
| `FileAlreadyExistsException` on output | output directory exists | remove it with `hdfs dfs -rm -r` |

## 8. Evidence checklist for the report

- `hdfs dfsadmin -report` (1 live DataNode)
- `yarn node -list` (1 RUNNING node)
- `hdfs dfs -ls -h /p08/raw` (8.0 G) and `hdfs fsck ... -files -blocks` (64 blocks, HEALTHY)
- Job counters block (`P08` group) and `JOB1 STATUS = SUCCESS`
- Screenshots: http://localhost:9870 (NameNode), http://localhost:8088 (ResourceManager)
- Output listing and `docs/samples/daily_consumption_head20.csv`

## 9. Resource notes

- Docker Desktop memory on this machine: ~9.6 GB. Container caps: 1.5 GB per daemon, 6 GB NodeManager.
- Increasing YARN memory (`yarn.nodemanager.resource.memory-mb`) shortens Job 1 but needs more Docker memory.
- Job 1 wall time on this machine: 250m41s with ~3 concurrent mappers.
