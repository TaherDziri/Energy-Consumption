-- sql/p08_dashboard_export_fixture.sql
-- Export Parquet de la fixture vers le disque de l'hote (volume /work).
INSERT OVERWRITE DIRECTORY 'file:///work/data/dashboard/monthly_fixture' USING parquet
SELECT * FROM lh.test.monthly WHERE dataset_version = 'sample-fixture-v11';

SELECT dataset_version, count(*) AS n, round(sum(monthly_kwh), 6) AS kwh
FROM lh.test.monthly GROUP BY dataset_version;

SELECT count(*) AS p08_monthly_rows FROM lh.p08.monthly;
