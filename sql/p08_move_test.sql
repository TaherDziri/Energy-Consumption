-- 1. Namespace de validation
CREATE DATABASE IF NOT EXISTS lh.test;

-- 2. Copie des seules partitions de validation
CREATE TABLE IF NOT EXISTS lh.test.monthly
USING iceberg
PARTITIONED BY (dataset_version)
AS
SELECT * FROM lh.p08.monthly
WHERE dataset_version IN ('test-contract-mr2', 'tou-test-mr2');

-- 3. Controle avant suppression
SELECT 'p08.monthly' AS t, dataset_version, count(*) AS n
FROM lh.p08.monthly GROUP BY dataset_version
UNION ALL
SELECT 'test.monthly', dataset_version, count(*) AS n
FROM lh.test.monthly GROUP BY dataset_version
ORDER BY t, dataset_version;

-- 4. Suppression dans la table de production
DELETE FROM lh.p08.monthly
WHERE dataset_version IN ('test-contract-mr2', 'tou-test-mr2');

-- 5. Controle apres suppression
SELECT count(*) AS reste_dans_p08_monthly FROM lh.p08.monthly;

-- 6. Historique (montre l'operation delete)
SELECT snapshot_id, committed_at, operation
FROM lh.p08.monthly.snapshots ORDER BY committed_at;