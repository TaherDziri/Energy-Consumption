-- 1. Namespace p08 (= /p08/warehouse/p08)
CREATE DATABASE IF NOT EXISTS lh.p08;

-- 2. Tables (repartitions par dataset_version : une valeur par jeu charge)
DROP TABLE IF EXISTS lh.p08.monthly PURGE;
CREATE TABLE lh.p08.monthly (
  dataset_version    STRING   COMMENT 'jeu source',
  run_id             STRING   COMMENT 'run_id emis par MR2',
  period             DATE     COMMENT '1er du mois (GMT, hypothese)',
  lclid              STRING,
  tariff_group       STRING,
  monthly_kwh        DOUBLE,
  estimated_cost_gbp DOUBLE   COMMENT 'NULL si aucun tarif : jamais 0',
  price_coverage     DOUBLE,
  peak_kwh_hh        DOUBLE,
  valid_days         INT,
  quality_flag       STRING   COMMENT 'ok|partial_data|partial_tariff|no_tariff|no_data',
  rows_in_run        BIGINT   COMMENT 'nb de lignes de la sortie MR2 du run',
  rows_in_period     BIGINT   COMMENT 'nb de lignes du run pour ce mois',
  source_path        STRING,
  loaded_at          TIMESTAMP
) USING iceberg
PARTITIONED BY (dataset_version);

DROP TABLE IF EXISTS lh.p08.daily PURGE;
CREATE TABLE lh.p08.daily (
  dataset_version  STRING,
  run_id           STRING,
  day              DATE     COMMENT 'jour civil GMT',
  lclid            STRING,
  total_kwh        DOUBLE,
  n_slots          INT      COMMENT 'reading_count MR1 = creneaux reellement sommes',
  n_missing_slots  INT      COMMENT 'DERIVE 48 - n_slots (MR1 v1 le fournira)',
  avg_slot_kwh     DOUBLE   COMMENT 'DERIVE total / n_slots',
  peak_kwh_hh      DOUBLE   COMMENT 'NULL en v1 (MR1 4 colonnes)',
  peak_slot        INT      COMMENT 'NULL en v1',
  tariff_group     STRING   COMMENT 'NULL en v1',
  quality_flag     STRING   COMMENT 'ok|partial_data|no_data|duplicate_slots',
  rows_in_run      BIGINT,
  source_path      STRING,
  loaded_at        TIMESTAMP
) USING iceberg
PARTITIONED BY (dataset_version);

-- 3. Vue CSV brute (tout en STRING : un champ vide devient NULL, jamais 0)
CREATE OR REPLACE TEMPORARY VIEW mr2_contract (
  c1 STRING, c2 STRING, c3 STRING, c4 STRING, c5 STRING,
  c6 STRING, c7 STRING, c8 STRING, c9 STRING, c10 STRING
) USING csv OPTIONS (path 'hdfs://namenode:9000/p08/gold/mr2_monthly_test', header 'false');

CREATE OR REPLACE TEMPORARY VIEW mr2_tou (
  c1 STRING, c2 STRING, c3 STRING, c4 STRING, c5 STRING,
  c6 STRING, c7 STRING, c8 STRING, c9 STRING, c10 STRING
) USING csv OPTIONS (path 'hdfs://namenode:9000/p08/gold/mr2_monthly_tou', header 'false');

-- 4. Chargement 1 : test de contrat MR2 (contient un cout vide -> NULL)
INSERT INTO lh.p08.monthly
SELECT 'test-contract-mr2', c10, to_date(concat(c2, '-01')), c1, c3,
       CAST(c4 AS DOUBLE), CAST(c5 AS DOUBLE), CAST(c6 AS DOUBLE),
       CAST(c7 AS DOUBLE), CAST(c8 AS INT), c9,
       COUNT(*) OVER (),
       COUNT(*) OVER (PARTITION BY c10, c2),
       'hdfs://namenode:9000/p08/gold/mr2_monthly_test',
       current_timestamp()
FROM mr2_contract;

-- 5. Chargement 2 : sortie ToU reelle (meme table, autre dataset_version)
INSERT INTO lh.p08.monthly
SELECT 'tou-test-mr2', c10, to_date(concat(c2, '-01')), c1, c3,
       CAST(c4 AS DOUBLE), CAST(c5 AS DOUBLE), CAST(c6 AS DOUBLE),
       CAST(c7 AS DOUBLE), CAST(c8 AS INT), c9,
       COUNT(*) OVER (),
       COUNT(*) OVER (PARTITION BY c10, c2),
       'hdfs://namenode:9000/p08/gold/mr2_monthly_tou',
       current_timestamp()
FROM mr2_tou;

-- 6. Controles monthly
SELECT dataset_version, run_id, period, count(*) AS n,
       count(estimated_cost_gbp) AS n_cost_not_null,
       count(*) - count(estimated_cost_gbp) AS n_cost_null,
       sum(monthly_kwh) AS kwh,
       sum(estimated_cost_gbp) AS cost,
       count_if(quality_flag <> 'ok') AS n_not_ok,
       max(rows_in_run) AS rows_in_run
FROM lh.p08.monthly
GROUP BY 1, 2, 3
ORDER BY 3;

SELECT * FROM lh.p08.monthly ORDER BY period;

-- 7. Snapshots / fichiers
SELECT snapshot_id, committed_at, operation,
       summary['added-records'] AS added_records,
       summary['total-records'] AS total_records
FROM lh.p08.monthly.snapshots ORDER BY committed_at;

SELECT file_path, record_count, file_size_in_bytes, partition
FROM lh.p08.monthly.files;

-- 8. Chargement daily : MR1 4 colonnes
CREATE OR REPLACE TEMPORARY VIEW mr1_raw (
  c1 STRING, c2 STRING, c3 STRING, c4 STRING
) USING csv OPTIONS (path 'hdfs://namenode:9000/p08/gold/mr1_daily', header 'false');

INSERT INTO lh.p08.daily
SELECT 'mr1-4cols-sample',
       concat('job1-', date_format(current_timestamp(), 'yyyyMMddTHHmmss')),
       to_date(c2), c1, CAST(c3 AS DOUBLE), CAST(c4 AS INT),
       GREATEST(48 - CAST(c4 AS INT), 0),
       CASE WHEN CAST(c4 AS INT) = 0 THEN NULL
            ELSE CAST(c3 AS DOUBLE) / CAST(c4 AS INT) END,
       CAST(NULL AS DOUBLE), CAST(NULL AS INT), CAST(NULL AS STRING),
       CASE WHEN CAST(c4 AS INT) = 48 THEN 'ok'
            WHEN CAST(c4 AS INT) = 0  THEN 'no_data'
            WHEN CAST(c4 AS INT) > 48 THEN 'duplicate_slots'
            ELSE 'partial_data' END,
       COUNT(*) OVER (),
       'hdfs://namenode:9000/p08/gold/mr1_daily',
       current_timestamp()
FROM mr1_raw;

-- 9. Controles daily
SELECT dataset_version, count(*) AS n, count(DISTINCT lclid) AS n_lclid,
       min(day) AS d_min, max(day) AS d_max, sum(total_kwh) AS kwh,
       count_if(quality_flag = 'ok') AS ok,
       count_if(quality_flag = 'partial_data') AS partial,
       count_if(quality_flag = 'no_data') AS no_data,
       count_if(quality_flag = 'duplicate_slots') AS duplicate,
       count_if(peak_kwh_hh IS NULL) AS peak_null
FROM lh.p08.daily GROUP BY 1;

SELECT * FROM lh.p08.daily ORDER BY lclid, day LIMIT 10;

SELECT snapshot_id, committed_at, operation,
       summary['added-records'] AS added_records,
       summary['total-records'] AS total_records
FROM lh.p08.daily.snapshots ORDER BY committed_at;