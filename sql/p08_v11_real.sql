-- sql/p08_v11_real.sql
-- Charge le run REEL issue de MR1 v1.1 (30 colonnes TSV -> MR2).
-- Ce n'est PAS la fixture : la source est /p08/gold/mr1_daily_v11, produit
-- par le job 1 v1.1 de Taher depuis sample_5households.csv (5 foyers reels).
-- dataset_version = mr1-v11-real-sample : echantillon reel, PAS le run 8,5 Go.

CREATE DATABASE IF NOT EXISTS lh.p08;

-- ------------------------------------------------------------------ mensuel
CREATE OR REPLACE TEMPORARY VIEW mr2_v11 (
  c1 STRING, c2 STRING, c3 STRING, c4 STRING, c5 STRING,
  c6 STRING, c7 STRING, c8 STRING, c9 STRING, c10 STRING
) USING csv OPTIONS (
  path 'hdfs://namenode:9000/p08/gold/mr2_monthly_v11', header 'false');

DELETE FROM lh.p08.monthly WHERE dataset_version = 'mr1-v11-real-sample';

INSERT INTO lh.p08.monthly
SELECT 'mr1-v11-real-sample', c10, to_date(concat(c2, '-01')), c1, c3,
       CAST(c4 AS DOUBLE),
       CASE WHEN c5 = '' THEN NULL ELSE CAST(c5 AS DOUBLE) END,
       CAST(c6 AS DOUBLE), CAST(c7 AS DOUBLE), CAST(c8 AS INT), c9,
       COUNT(*) OVER (),
       COUNT(*) OVER (PARTITION BY c10, c2),
       'hdfs://namenode:9000/p08/gold/mr2_monthly_v11 (MR1 v1.1 REEL)',
       current_timestamp()
FROM mr2_v11;

-- ------------------------------------------------------------------ journalier
-- Table dediee : le schema de lh.p08.daily (v1.0) n'a ni series ni peak_slot.
CREATE TABLE IF NOT EXISTS lh.p08.daily_v11 (
  dataset_version    STRING,
  run_id             STRING,
  day                DATE,
  lclid              STRING,
  tariff_group       STRING,
  total_kwh          DOUBLE,
  n_valid_slots      INT,
  n_missing_slots    INT,
  expected_slots     INT,
  peak_kwh_hh        DOUBLE,
  peak_slot          INT,
  avg_valid_kwh_hh   DOUBLE,
  series             STRING,
  quality_flag       STRING,
  rows_in_run        BIGINT,
  source_path        STRING,
  loaded_at          TIMESTAMP
) USING iceberg PARTITIONED BY (dataset_version);

CREATE OR REPLACE TEMPORARY VIEW mr1_v11 (
  c1 STRING, c2 STRING, c3 STRING, c4 STRING, c5 STRING,
  c6 STRING, c7 STRING, c8 STRING, c9 STRING, c10 STRING
) USING csv OPTIONS (
  path 'hdfs://namenode:9000/p08/gold/mr1_daily_v11',
  header 'false', sep '\t');

DELETE FROM lh.p08.daily_v11 WHERE dataset_version = 'mr1-v11-real-sample';

INSERT INTO lh.p08.daily_v11
SELECT 'mr1-v11-real-sample', 'job1-v11-sample', to_date(c2), c1, c3,
       CAST(c4 AS DOUBLE), CAST(c5 AS INT), CAST(c6 AS INT),
       CAST(c5 AS INT) + CAST(c6 AS INT),
       CASE WHEN c7 = '' THEN NULL ELSE CAST(c7 AS DOUBLE) END,
       CASE WHEN c8 = '' THEN NULL ELSE CAST(c8 AS INT) END,
       CASE WHEN c9 = '' THEN NULL ELSE CAST(c9 AS DOUBLE) END,
       c10,
       CASE WHEN CAST(c5 AS INT) = 0 THEN 'no_data'
            WHEN CAST(c6 AS INT) > 0 THEN 'partial_data'
            ELSE 'ok' END,
       COUNT(*) OVER (),
       'hdfs://namenode:9000/p08/gold/mr1_daily_v11 (MR1 v1.1 REEL)',
       current_timestamp()
FROM mr1_v11;

-- ------------------------------------------------------------------ controles
SELECT dataset_version, count(*) AS n, count(DISTINCT lclid) AS foyers,
       count(estimated_cost_gbp) AS n_cost,
       count(*) - count(estimated_cost_gbp) AS n_null,
       round(sum(monthly_kwh), 6) AS kwh,
       round(sum(estimated_cost_gbp), 6) AS cout,
       count_if(quality_flag = 'ok') AS ok,
       count_if(quality_flag = 'partial_data') AS partial_data,
       count_if(quality_flag = 'no_tariff') AS no_tariff,
       max(rows_in_run) AS rows_in_run
FROM lh.p08.monthly
WHERE dataset_version = 'mr1-v11-real-sample'
GROUP BY dataset_version;

SELECT count(*) AS p08_monthly_rows FROM lh.p08.monthly;

SELECT dataset_version, count(*) AS n,
       count(DISTINCT lclid) AS foyers,
       CAST(min(day) AS STRING) AS debut, CAST(max(day) AS STRING) AS fin,
       round(sum(total_kwh), 6) AS kwh,
       count_if(expected_slots <> 48) AS dst_days,
       count_if(n_missing_slots > 0) AS jours_incomplets,
       count_if(peak_kwh_hh IS NULL) AS pics_null,
       count_if(tariff_group IS NULL) AS tarifs_null
FROM lh.p08.daily_v11
GROUP BY dataset_version;

-- Reconciliation des deux niveaux : doit etre 0.
SELECT
  (SELECT round(sum(total_kwh), 6) FROM lh.p08.daily_v11
    WHERE dataset_version = 'mr1-v11-real-sample')
  - (SELECT round(sum(monthly_kwh), 6) FROM lh.p08.monthly
    WHERE dataset_version = 'mr1-v11-real-sample') AS ecart_kwh;
