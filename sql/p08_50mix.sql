-- sql/p08_50mix.sql
-- Charge le run REEL de 50 foyers (40 Std + 10 ToU) issu de MR1 v1.1.
-- Source : /p08/gold/mr1_daily_50mix et /p08/gold/mr2_monthly_50mix,
-- produits depuis sample_50_mix.csv (50 foyers reels du jeu complet).
-- dataset_version = mr1-v11-50mix : echantillon reel, PAS le run 8,5 Go.
-- Le run de reference 5 foyers (mr1-v11-real-sample) n'est pas touche.

CREATE DATABASE IF NOT EXISTS lh.p08;

-- ------------------------------------------------------------------ mensuel
CREATE OR REPLACE TEMPORARY VIEW mr2_50mix (
  c1 STRING, c2 STRING, c3 STRING, c4 STRING, c5 STRING,
  c6 STRING, c7 STRING, c8 STRING, c9 STRING, c10 STRING
) USING csv OPTIONS (
  path 'hdfs://namenode:9000/p08/gold/mr2_monthly_50mix', header 'false');

DELETE FROM lh.p08.monthly WHERE dataset_version = 'mr1-v11-50mix';

INSERT INTO lh.p08.monthly
SELECT 'mr1-v11-50mix', c10, to_date(concat(c2, '-01')), c1, c3,
       CAST(c4 AS DOUBLE),
       CASE WHEN c5 = '' THEN NULL ELSE CAST(c5 AS DOUBLE) END,
       CAST(c6 AS DOUBLE), CAST(c7 AS DOUBLE), CAST(c8 AS INT), c9,
       COUNT(*) OVER (),
       COUNT(*) OVER (PARTITION BY c10, c2),
       'hdfs://namenode:9000/p08/gold/mr2_monthly_50mix (MR1 v1.1 REEL, 50 foyers Std+ToU)',
       current_timestamp()
FROM mr2_50mix;

-- ------------------------------------------------------------------ journalier
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

CREATE OR REPLACE TEMPORARY VIEW mr1_50mix (
  c1 STRING, c2 STRING, c3 STRING, c4 STRING, c5 STRING,
  c6 STRING, c7 STRING, c8 STRING, c9 STRING, c10 STRING
) USING csv OPTIONS (
  path 'hdfs://namenode:9000/p08/gold/mr1_daily_50mix',
  header 'false', sep '\t');

DELETE FROM lh.p08.daily_v11 WHERE dataset_version = 'mr1-v11-50mix';

INSERT INTO lh.p08.daily_v11
SELECT 'mr1-v11-50mix', 'job1-v11-50mix', to_date(c2), c1, c3,
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
       'hdfs://namenode:9000/p08/gold/mr1_daily_50mix (MR1 v1.1 REEL, 50 foyers Std+ToU)',
       current_timestamp()
FROM mr1_50mix;

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
WHERE dataset_version = 'mr1-v11-50mix'
GROUP BY dataset_version;

SELECT tariff_group, count(*) AS n, count(DISTINCT lclid) AS foyers,
       round(sum(monthly_kwh), 6) AS kwh,
       round(sum(estimated_cost_gbp), 6) AS cout
FROM lh.p08.monthly
WHERE dataset_version = 'mr1-v11-50mix'
GROUP BY tariff_group;

SELECT dataset_version, count(*) AS n,
       count(DISTINCT lclid) AS foyers,
       CAST(min(day) AS STRING) AS debut, CAST(max(day) AS STRING) AS fin,
       round(sum(total_kwh), 6) AS kwh,
       count_if(expected_slots <> 48) AS dst_days,
       count_if(n_missing_slots > 0) AS jours_incomplets,
       count_if(peak_kwh_hh IS NULL) AS pics_null,
       count_if(tariff_group IS NULL) AS tarifs_null
FROM lh.p08.daily_v11
WHERE dataset_version = 'mr1-v11-50mix'
GROUP BY dataset_version;

-- Reconciliation des deux niveaux : doit etre 0.
SELECT
  (SELECT round(sum(total_kwh), 6) FROM lh.p08.daily_v11
    WHERE dataset_version = 'mr1-v11-50mix')
  - (SELECT round(sum(monthly_kwh), 6) FROM lh.p08.monthly
    WHERE dataset_version = 'mr1-v11-50mix') AS ecart_kwh;
