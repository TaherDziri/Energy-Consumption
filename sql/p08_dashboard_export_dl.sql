-- sql/p08_dashboard_export_dl.sql
-- Export Parquet de la table Iceberg des predictions DL vers le dashboard.
INSERT OVERWRITE DIRECTORY 'file:///work/data/dashboard/dl_predictions' USING parquet
SELECT * FROM lh.p08.dl_predictions WHERE model_tag = 'gru_24h_runA_l1';

SELECT 'dl_predictions' AS export, count(*) AS n
FROM lh.p08.dl_predictions WHERE model_tag = 'gru_24h_runA_l1';
