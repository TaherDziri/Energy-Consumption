-- sql/p08_dl_predictions.sql
-- Charge en Iceberg les predictions du modele DL retenu (GRU 24 h, runA_l1).
-- Branche parallele a Job 2 : la source est MR1 v1.1 (serie 30 min -> 1 h),
-- PAS le mensuel. Ce script ne modifie ni MR1 ni MR2 ni leurs tables.
-- Le CSV est produit par scripts/export_dl_predictions.py.
-- Test lum une seule fois : test_seen.json (hash + commit) est recopie dans la table.

CREATE DATABASE IF NOT EXISTS lh.p08;

DROP TABLE IF EXISTS lh.p08.dl_predictions;

CREATE TABLE lh.p08.dl_predictions (
  model_tag         STRING,
  split_name        STRING,
  lclid             STRING,
  target_hour       TIMESTAMP,
  horizon_h         INT,
  y_true_kwh        DOUBLE,
  y_pred_kwh        DOUBLE,
  y_seasonal_kwh    DOUBLE,
  abs_err_gru       DOUBLE,
  abs_err_seasonal  DOUBLE,
  test_hash         STRING,
  git_commit        STRING,
  source_path       STRING,
  loaded_at         TIMESTAMP
) USING iceberg PARTITIONED BY (model_tag);

CREATE OR REPLACE TEMPORARY VIEW dl_preds_csv (
  model_tag STRING, split_name STRING, lclid STRING, target_hour STRING,
  horizon_h INT, y_true_kwh DOUBLE, y_pred_kwh DOUBLE, y_seasonal_kwh DOUBLE,
  abs_err_gru DOUBLE, abs_err_seasonal DOUBLE, test_hash STRING,
  git_commit STRING, source_path STRING
) USING csv OPTIONS (
  path 'file:///work/data/dashboard/dl_predictions.csv',
  header 'true', sep ',', inferSchema 'false');

INSERT INTO lh.p08.dl_predictions
SELECT model_tag, split_name, lclid, to_timestamp(target_hour), horizon_h,
       y_true_kwh, y_pred_kwh, y_seasonal_kwh,
       abs_err_gru, abs_err_seasonal, test_hash, git_commit, source_path,
       current_timestamp()
FROM dl_preds_csv;

-- Controle : 310920 | 5 | 24 | 0.198047 | 0.201439 | 151184 | eb401abb29f4a656 | a35e723
SELECT model_tag, split_name,
       count(*) AS n,
       count(DISTINCT lclid) AS foyers,
       count(DISTINCT horizon_h) AS horizons,
       CAST(min(target_hour) AS STRING) AS debut,
       CAST(max(target_hour) AS STRING) AS fin,
       round(avg(abs_err_gru), 6) AS mae_gru,
       round(avg(abs_err_seasonal), 6) AS mae_saisonnier,
       count_if(abs_err_gru < abs_err_seasonal) AS gru_meilleur,
       max(test_hash) AS test_hash,
       max(git_commit) AS git_commit
FROM lh.p08.dl_predictions
GROUP BY model_tag, split_name;
