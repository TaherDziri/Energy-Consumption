-- sql/f06_quality.sql
-- F06 : qualite des donnees + reconciliation des deux chaines independantes
-- (MR1 4 colonnes -> lh.p08.daily) et (fixture 10 colonnes -> MR2 -> lh.test.monthly).

SELECT 'lh.p08.daily' AS tbl, dataset_version AS ver, count(*) AS lignes,
       count(DISTINCT lclid) AS foyers,
       CAST(min(day) AS STRING) AS debut, CAST(max(day) AS STRING) AS fin,
       round(sum(total_kwh), 6) AS kwh,
       count_if(quality_flag = 'ok') AS n_ok,
       count_if(quality_flag <> 'ok') AS n_ko,
       sum(n_missing_slots) AS manquants,
       count_if(peak_kwh_hh IS NULL) AS pics_null
FROM lh.p08.daily GROUP BY dataset_version
UNION ALL
SELECT 'lh.test.monthly', dataset_version, count(*), count(DISTINCT lclid),
       CAST(min(period) AS STRING), CAST(max(period) AS STRING),
       round(sum(monthly_kwh), 6),
       count_if(quality_flag = 'ok'), count_if(quality_flag <> 'ok'),
       CAST(NULL AS BIGINT), CAST(NULL AS BIGINT)
FROM lh.test.monthly GROUP BY dataset_version
ORDER BY tbl, ver;

-- Reconciliation : la moyenne des doublons ne change pas la somme, donc
-- les deux chaines doivent donner exactement la meme energie.
SELECT
  (SELECT round(sum(total_kwh), 6)   FROM lh.p08.daily)                     AS daily_kwh,
  (SELECT round(sum(monthly_kwh), 6) FROM lh.test.monthly
    WHERE dataset_version = 'sample-fixture-v11')                           AS fixture_kwh,
  (SELECT round(sum(monthly_kwh), 6) FROM lh.test.monthly
    WHERE dataset_version = 'sample-fixture-v11')
  - (SELECT round(sum(total_kwh), 6) FROM lh.p08.daily)                     AS ecart;

SELECT d.lclid, round(d.kwh, 6) AS daily, round(m.kwh, 6) AS fixture,
       round(d.kwh - m.kwh, 6) AS ecart
FROM (SELECT lclid, sum(total_kwh) AS kwh FROM lh.p08.daily GROUP BY lclid) d
JOIN (SELECT lclid, sum(monthly_kwh) AS kwh FROM lh.test.monthly
      WHERE dataset_version = 'sample-fixture-v11' GROUP BY lclid) m
  ON d.lclid = m.lclid
ORDER BY d.lclid;
