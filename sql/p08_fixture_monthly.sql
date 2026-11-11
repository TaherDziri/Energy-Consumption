-- sql/p08_fixture_monthly.sql
-- Chargement de la FIXTURE de validation (sample-fixture-v11) dans
-- lh.test.monthly. lh.p08.monthly reste reservee aux runs de production.
-- Source : sortie MR2 de /p08/test/mr1_v11_sample.

CREATE DATABASE IF NOT EXISTS lh.test;

CREATE TABLE IF NOT EXISTS lh.test.monthly (
  dataset_version    STRING,
  run_id             STRING,
  period             DATE,
  lclid              STRING,
  tariff_group       STRING,
  monthly_kwh        DOUBLE,
  estimated_cost_gbp DOUBLE,
  price_coverage     DOUBLE,
  peak_kwh_hh        DOUBLE,
  valid_days         INT,
  quality_flag       STRING,
  rows_in_run        BIGINT,
  rows_in_period     BIGINT,
  source_path        STRING,
  loaded_at          TIMESTAMP
) USING iceberg PARTITIONED BY (dataset_version);

-- Vue CSV brute : tout en STRING, un champ vide devient NULL (jamais 0)
CREATE OR REPLACE TEMPORARY VIEW mr2_fixture (
  c1 STRING, c2 STRING, c3 STRING, c4 STRING, c5 STRING,
  c6 STRING, c7 STRING, c8 STRING, c9 STRING, c10 STRING
) USING csv OPTIONS (
  path 'hdfs://namenode:9000/p08/gold/mr2_monthly_fixture', header 'false');

-- Idempotent : on remplace la partition de la fixture
DELETE FROM lh.test.monthly WHERE dataset_version = 'sample-fixture-v11';

INSERT INTO lh.test.monthly
SELECT 'sample-fixture-v11', c10, to_date(concat(c2, '-01')), c1, c3,
       CAST(c4 AS DOUBLE), CAST(c5 AS DOUBLE), CAST(c6 AS DOUBLE),
       CAST(c7 AS DOUBLE), CAST(c8 AS INT), c9,
       COUNT(*) OVER (),
       COUNT(*) OVER (PARTITION BY c10, c2),
       'hdfs://namenode:9000/p08/gold/mr2_monthly_fixture (FIXTURE DE TEST)',
       current_timestamp()
FROM mr2_fixture;

-- Controles attendus : 108 lignes, 60 couts, 48 NULL, 28416.517003 kWh,
-- 2321.437777 GBP, 60 ok, 48 no_tariff.
SELECT dataset_version, count(*) AS n,
       count(estimated_cost_gbp) AS n_cost,
       count(*) - count(estimated_cost_gbp) AS n_null,
       round(sum(monthly_kwh), 6) AS kwh,
       round(sum(estimated_cost_gbp), 6) AS cost,
       count_if(quality_flag = 'ok') AS ok,
       count_if(quality_flag = 'no_tariff') AS no_tariff,
       max(rows_in_run) AS rows_in_run
FROM lh.test.monthly
WHERE dataset_version = 'sample-fixture-v11'
GROUP BY dataset_version;

SELECT lclid, period, monthly_kwh, estimated_cost_gbp, price_coverage,
       peak_kwh_hh, valid_days, quality_flag
FROM lh.test.monthly
WHERE dataset_version = 'sample-fixture-v11'
ORDER BY lclid, period LIMIT 6;

-- La table de production doit rester vide (runs reels uniquement)
SELECT count(*) AS p08_monthly_rows FROM lh.p08.monthly;

SELECT snapshot_id, committed_at, operation
FROM lh.test.monthly.snapshots ORDER BY committed_at;
