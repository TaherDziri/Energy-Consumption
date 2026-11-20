-- sql/p08_dashboard_export_v11.sql
-- Exports Parquet du run REEL v1.1 (echantillon 5 foyers) vers le dashboard.
INSERT OVERWRITE DIRECTORY 'file:///work/data/dashboard/monthly_v11' USING parquet
SELECT * FROM lh.p08.monthly WHERE dataset_version = 'mr1-v11-real-sample';

INSERT OVERWRITE DIRECTORY 'file:///work/data/dashboard/daily_v11' USING parquet
SELECT * FROM lh.p08.daily_v11 WHERE dataset_version = 'mr1-v11-real-sample';

SELECT 'monthly_v11' AS export, count(*) AS n FROM lh.p08.monthly
WHERE dataset_version = 'mr1-v11-real-sample'
UNION ALL
SELECT 'daily_v11', count(*) FROM lh.p08.daily_v11
WHERE dataset_version = 'mr1-v11-real-sample';
