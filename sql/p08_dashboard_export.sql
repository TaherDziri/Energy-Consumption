-- Ecrit sur le disque de l'hote via le volume /work (file:// explicite).
INSERT OVERWRITE DIRECTORY 'file:///work/data/dashboard/daily' USING parquet
SELECT * FROM lh.p08.daily;

INSERT OVERWRITE DIRECTORY 'file:///work/data/dashboard/monthly' USING parquet
SELECT * FROM lh.p08.monthly;

INSERT OVERWRITE DIRECTORY 'file:///work/data/dashboard/monthly_test' USING parquet
SELECT * FROM lh.test.monthly;

SELECT dataset_version, count(*) AS n, round(sum(total_kwh), 3) AS kwh
FROM lh.p08.daily GROUP BY dataset_version;
SELECT dataset_version, count(*) AS n FROM lh.test.monthly GROUP BY dataset_version;