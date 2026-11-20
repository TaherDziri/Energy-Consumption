# F12 — Démonstration de la chaîne complète

**Critère exact (PDF §10) :** « Chaîne HDFS, MR1, MR2, Iceberg et tableau de
bord démontrée. »

**Périmètre affiché pendant la démo :** échantillon réel de **5 foyers**, jamais
le run complet 8,5 Go. Le run du binôme est une mesure externe, à citer comme
telle. Volumes synthétiques (`synthetic_155k`, `synthetic_620k`) et fixture
(`sample-fixture-v11`) toujours étiquetés.

Durée estimée de la démo : 3–5 min (hors redémarrage des conteneurs).

---

## 1. HDFS — montrer les zones (30 s)

```powershell
docker ps --filter "name=p08-"
docker exec p08-namenode hdfs dfs -ls -h /p08/raw/meters /p08/raw/tariffs
docker exec p08-namenode hdfs dfs -ls -h /p08/gold/mr1_daily_v11 /p08/gold/mr2_monthly_v11
```

**À dire :** `raw` = CSV brut + tarifs, `gold` = sorties MR1/MR2. Les chemins
`part-r-*` sont vérifiables. Le jar Job 1 est monté en lecture seule dans
`/job` ; le jar Job 2 est copié dans `/tmp` du namenode.

## 2. MR1 v1.1 — rejouer le job (1 min)

```powershell
docker exec p08-namenode hdfs dfs -rm -r -f /p08/gold/mr1_daily_v11_demo
docker exec p08-namenode hadoop jar /job/job1-daily-consumption.jar `
  /p08/raw/meters/sample_5households.csv /p08/gold/mr1_daily_v11_demo
```

Montrer dans la console :
`readings_valid = 152806`, `duplicate_rows_averaged = 105`, `missing_null = 5`,
`dst_days = 17`, `JOB1 STATUS = SUCCESS`.

```powershell
docker exec p08-namenode hdfs dfs -cat /p08/gold/mr1_daily_v11_demo/part-r-00000 | Select-Object -First 2
```

**À dire :** 10 colonnes TSV ; `date` et `slot` sont **locaux Europe/London**,
46/48/50 créneaux selon la DST. Un créneau manquant est **absent** de la `series`,
jamais écrit `slot:0`. Un zéro mesuré reste `slot:0.0`.

## 3. MR2 v1.1 — rejouer le job (1 min)

```powershell
docker exec p08-namenode hdfs dfs -rm -r -f /p08/gold/mr2_monthly_v11_demo
docker exec p08-namenode hadoop jar /tmp/job2-monthly-aggregation.jar `
  -D p08.run_id=demo-f12 `
  /p08/gold/mr1_daily_v11_demo /p08/gold/mr2_monthly_v11_demo `
  /p08/raw/tariffs/tariffs_2013_price.csv
```

**Piège :** `-D` et `p08.run_id=...` sont **deux tokens séparés** (sinon
`GenericOptionsParser` laisse l'option dans les arguments positionnels).

Compteurs attendus : `lines_ok=3191`, `flag_ok=55`, `flag_partial_data=5`,
`flag_no_tariff=48`, `priced_slots=87594`, `unpriced_slots=65107`,
`duplicate_slots=20`, `dst_days=17`, `missing_slots_mismatch=0`,
`months_written=108`, `JOB2 STATUS = SUCCESS`.

**À dire :** les 20 `duplicate_slots` sont les slots 2 et 3 répétés le 27/10 :
deux lectures physiques **additionnées**, pas écrasées. Aucun Combiner. Arrondi
uniquement à la sortie (`%.6f`, `Locale.ROOT`). 48 coûts sont **NULL** (hors
calendrier 2013), jamais 0.

**Reproductibilité (T08) :** relancer la même commande sur une autre sortie donne
un fichier octet pour octet identique (SHA-256
`2284eff2cd1e7cfe107607d636a56559ba8de35e769b2677317c7f96daab9d02` avec
`run_id=mr2-v11-real-sample`).

## 4. Iceberg + Spark SQL (1 min)

Les tables sont déjà chargées par `sql/p08_v11_real.sql`. Montrer le contrôle :

```powershell
docker run --rm --network p08_default -e HOME=/tmp -v "${PWD}:/work" -w /work `
  apache/spark:3.5.1 /opt/spark/bin/spark-sql `
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2 `
  --conf spark.jars.ivy=/tmp/.ivy2 `
  --conf spark.hadoop.fs.defaultFS=hdfs://namenode:9000 `
  --conf spark.sql.catalog.lh=org.apache.iceberg.spark.SparkCatalog `
  --conf spark.sql.catalog.lh.type=hadoop `
  --conf spark.sql.catalog.lh.warehouse=hdfs://namenode:9000/p08/warehouse `
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions `
  --conf spark.driver.extraJavaOptions=-Dderby.system.home=/tmp/derby `
  -e "SELECT dataset_version, count(*) n, count(estimated_cost_gbp) n_cost, count(*)-count(estimated_cost_gbp) n_null, round(sum(monthly_kwh),3) kwh, round(sum(estimated_cost_gbp),6) cout FROM lh.p08.monthly WHERE dataset_version='mr1-v11-real-sample' GROUP BY dataset_version;"
```

Résultat attendu : `108 | 60 | 48 | 28416.517 | 2321.437776`.

**À dire :** `lh.p08.monthly` contient le run réel ; la fixture reste isolée dans
`lh.test.monthly`. `lh.p08.daily_v11` (3 191 lignes) donne l'écart
journalier/mensuel **0,0**.

## 5. Tableau de bord — les 10 pages (1 min)

```powershell
.venv\Scripts\streamlit run dashboard\app.py --server.headless true --server.port 8501
```

Ouvrir `http://localhost:8501`, puis parcourir dans l'ordre :

| # | Page | Point à montrer |
|---|---|---|
| 1 | Vue d'ensemble | 5 foyers, 3 191 jours, 28 416,517 kWh ; préciser que c'est l'ancien export 4 colonnes |
| 2 | Profil horaire | **pas** un profil 30 min : échantillon horaire, libellé explicite |
| 3 | Journees et pics | pics `NULL` en MR1 v1 (4 colonnes) |
| 4 | Couts (GBP) | lignes de validation ; coût `non calculable` en 2012 |
| 5 | **Run reel v1.1** | 108 lignes, 2 321,44 GBP, 48 NULL, 17 jours DST, profil demi-heure réel depuis `series` |
| 6 | Validation (fixture) | **`sample-fixture-v11` est une fixture**, pas de la production |
| 7 | Qualite | `n_missing_slots` dérivé en v1 (48 − n_slots) |
| 8 | Std vs ToU | échantillon réel **100 % Std** ; seule une preuve synthétique existe |
| 9 | Modeles (documentation) | GRU test lu une fois ; AE = résultat négatif, test non lu |
| 10 | Limites | volumes synthétiques étiquetés, convention début/fin de période non vérifiée |

Les 10 pages ont été vérifiées dans le navigateur le 2026-11-20 : **0 erreur
console**.

---

## 6. Deep Learning — livrable exigé oralement (2 min)

Le Deep Learning (GRU + autoencodeur) est un livrable exigé oralement par l'enseignante. Le sujet écrit (ideep08.pdf §12) le classe hors périmètre ; cette exigence orale n'est pas confirmée par écrit à ce jour.

**À dire (4 phrases) :**

1. « Les données sont l'échantillon réel de 5 foyers, converti en base horaire, avec des fenêtres de 48 h en entrée et 24 h en sortie, et un split temporel 70/15/15 en train/validation/test. »
2. « Le GRU `runA_l1` a été choisi sur la validation seule (MAE 0,1206 contre 0,1231 pour `runB_l1cal`) ; le test n'a été lu qu'une seule fois : MAE 0,1980 contre 0,2014 pour la base saisonnière, soit un écart de 0,0034 kWh — je ne le présente pas comme un gain important. »
3. « L'autoencodeur est un résultat négatif documenté : la règle (40 % de détection à 1 % de fausses alertes) a été fixée avant de lire le test, elle donne 12,4 % sur la validation, donc le test n'a jamais été lu. C'est une conclusion valable, pas un résultat masqué. »
4. « Je montre la page **Modeles (documentation)** du dashboard, puis la page **Limites** où la formulation orale/écrite est affichée. »

**Questions probables du jury :**

- **Q : Pourquoi faire du DL si le PDF le met hors périmètre ?** R : Livrable exigé oralement par l'enseignante ; le sujet écrit (§12) le classe hors périmètre et il n'y a pas de confirmation écrite à ce jour. On le dit explicitement.
- **Q : Le gain du GRU est-il convaincant ?** R : Non : 0,1980 contre 0,2014, écart 0,0034 kWh ; test lu une seule fois. On ne revendique pas d'amélioration majeure.
- **Q : L'autoencodeur a-t-il échoué ?** R : Il n'a pas atteint le seuil pré-enregistré (12,4 % au lieu de 40 % à 1 % de fausses alertes) ; le test n'a pas été lu. C'est un résultat négatif documenté, donc une conclusion honnête.
- **Q : Est-ce du Big Data ?** R : Non : c'est un échantillon horaire de 5 foyers, distinct des compteurs HDFS/MR2 ; il n'est pas présenté comme un volume Big Data.

---
## Ce qui reste à demander au binôme (run 8,5 Go)

1. identifiant de job (`job_...` / `application_...`) ;
2. dump complet des compteurs `P08_MR2` ;
3. chemin d'entrée + taille + nombre de lignes ;
4. nombre de mappers / reducers lancés ;
5. `elapsed_ms` + temps par phase ;
6. configuration du cluster (noeuds, conteneurs, vCores, disques) ;
7. présence ou absence d'un Combiner ;
8. commit exact du jar MR2 ;
9. nombre de lignes de sortie et réconciliation MR1 ↔ MR2.

Tant que ces 9 éléments ne sont pas fournis, le run 8,5 Go est cité comme
**« mesure du binôme »**, jamais comme une mesure locale ni une preuve de
montée en charge linéaire.
