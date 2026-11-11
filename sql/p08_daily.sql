-- Daily seule : la table existe deja mais vide, on la recree proprement.
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

CREATE OR REPLACE TEMPORARY VIEW mr1_raw (
  c1 STRING, c2 STRING, c3 STRING, c4 STRING
) USING csv OPTIONS (path 'hdfs://namenode:9000/p08/gold/mr1_daily', header 'false');

INSERT INTO lh.p08.daily
SELECT 'mr1-4cols-sample',
       concat('job1-', date_format(current_timestamp(), 'yyyyMMdd_HHmmss')),
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

-- Controles
SELECT dataset_version, count(*) AS n, count(DISTINCT lclid) AS n_lclid,
       min(day) AS d_min, max(day) AS d_max,
       round(sum(total_kwh), 3) AS kwh,
       count_if(quality_flag = 'ok') AS ok,
       count_if(quality_flag = 'partial_data') AS partial,
       count_if(quality_flag = 'no_data') AS no_data,
       count_if(quality_flag = 'duplicate_slots') AS duplicate,
       count_if(peak_kwh_hh IS NULL) AS peak_null,
       min(n_slots) AS slots_min, max(n_slots) AS slots_max,
       max(rows_in_run) AS rows_in_run
FROM lh.p08.daily GROUP BY 1;

SELECT count(*) AS hors_bornes FROM lh.p08.daily WHERE n_slots > 48 OR n_slots < 0;
SELECT count(*) AS pic_non_null FROM lh.p08.daily WHERE peak_kwh_hh IS NOT NULL;

SELECT * FROM lh.p08.daily ORDER BY lclid, day LIMIT 10;

SELECT snapshot_id, committed_at, operation,
       summary['added-records'] AS added_records,
       summary['total-records'] AS total_records
FROM lh.p08.daily.snapshots ORDER BY committed_at;