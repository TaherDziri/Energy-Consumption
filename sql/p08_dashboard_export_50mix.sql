-- sql/p08_dashboard_export_50mix.sql
-- Exports Parquet du run REEL 50 foyers (Std+ToU) vers le dashboard.
INSERT OVERWRITE DIRECTORY 'file:///work/data/dashboard/monthly_50mix' USING parquet
SELECT * FROM lh.p08.monthly WHERE dataset_version = 'mr1-v11-50mix';

INSERT OVERWRITE DIRECTORY 'file:///work/data/dashboard/daily_50mix' USING parquet
SELECT * FROM lh.p08.daily_v11 WHERE dataset_version = 'mr1-v11-50mix';

SELECT 'monthly_50mix' AS export, count(*) AS n FROM lh.p08.monthly
WHERE dataset_version = 'mr1-v11-50mix'
UNION ALL
SELECT 'daily_50mix', count(*) FROM lh.p08.daily_v11
WHERE dataset_version = 'mr1-v11-50mix';
