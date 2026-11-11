# P08 — État du projet

**Dernière mise à jour :** 2026-11-09
**Étudiante :** Rahma (Personne 2)
**Branche :** `solo-Rahma`
**Dépôt :** https://github.com/TaherDziri/Energy-Consumption
**Version du contrat / design :** v1.3 (décisions figées ; fuseau : tout en GMT)

## 1. Objectif

Analyser la consommation électrique demi-horaire de foyers londoniens
(Low Carbon London, 2011–2014) via une chaîne Lakehouse :

```
CSV -> HDFS raw -> silver (normalisé) -> MR1 (journalier)
    -> gold/mr1_daily -> MR2 (mensuel) -> gold/mr2_monthly
    -> Iceberg (Spark SQL) -> SQL -> dashboard
```

Le cahier des charges (`ideep08.pdf`) impose : HDFS, **deux jobs Hadoop
MapReduce Java**, de **vraies tables Iceberg**, une analyse SQL et un
dashboard. Le Deep Learning (GRU + Autoencoder) est une extension
ajoutée par l'équipe, après la partie obligatoire.

## 2. Périmètre de Rahma

- **MR2** : agrégat mensuel par foyer — `monthly_kwh`, pic demi-horaire,
  coût estimé en GBP, couverture tarifaire, jours valides, quality flag.
- **Pas MR1** : développé par le binôme (Taher). On fige seulement son
  format de sortie (voir `01_MR1_MR2_CONTRACT.md`).
- Plus tard : Iceberg, GRU, Autoencoder, dashboard, documentation.

## 3. Environnement vérifié

| Élément | Valeur vérifiée | Statut |
|---|---|---|
| Docker | conteneurs `Up ... (healthy)` | OK |
| `p08-namenode` | image **`apache/hadoop:3.3.6`**, Hadoop **3.3.6**, Java **8** | OK |
| `p08-datanode` | 1 DataNode **live** | OK |
| `p08-resourcemanager` | YARN **1 NodeManager RUNNING** | OK |
| `p08-nodemanager` | 4096 Mo / 4 vcores | OK |
| Maven (PC) | **3.9.12** | OK |
| Java (PC) | **21.0.9** (Oracle) | OK |
| Git | branche `solo-Rahma`, `Main` fusionnée en fast-forward (`dd0b030`) | OK |
| Données suivies par Git | aucune (`git ls-files data` vide) | OK |

**Conséquence technique :** le `pom.xml` doit cibler **Java 1.8** et
`hadoop-client 3.3.6` en `provided`, car les conteneurs tournent en Java 8.

### Étape 3 — vérification environnement + Maven (validée)

| Contrôle | Commande | Résultat |
|---|---|---|
| Hadoop conteneur | `docker exec p08-namenode hadoop version` | **Hadoop 3.3.6** ✅ (identique au pom) |
| Java conteneur | `docker exec p08-namenode java -version` | **openjdk 1.8.0_212** ✅ |
| Pom lisible | `mvn validate` | `BUILD SUCCESS` ✅ |
| Compilation | `mvn -q compile` | aucune sortie = succès (`No sources to compile`) ✅ |

Aucun mismatch de version : `hadoop-client 3.3.6` en `provided` +
`maven.compiler.release=8` est le bon réglage pour ce cluster.
Hadoop et Java n'ont pas besoin d'être installés sur le PC : la
compilation n'utilise que les JAR téléchargés par Maven.

## 4. HDFS (vérifié)

```
/p08/raw/meters/sample_5households.csv      7 681 883 B
/p08/raw/tariffs/tariffs_2013.csv             484 027 B
/p08/raw/tariffs/tariffs_2013_price.csv      17 520 lignes + 1 en-tête
/p08/silver/half_hourly/                     vide
/p08/quarantine/                             vide
/p08/gold/mr1_daily/                         vide (attente MR1 v1.1)
/p08/gold/mr2_monthly/                       vide
/p08/test/mr1_daily/mr1_test.tsv             3 lignes × 10 champs (jeu de test MR2)
```

Le dossier `/p08/test/mr1_daily` est séparé de `gold/` : il ne doit
jamais polluer les sorties de production.

**Vérifications HDFS du 2026-11-06 :**

| Contrôle | Commande | Résultat |
|---|---|---|
| En-tête tarifs | `hdfs dfs -cat ... \| sed -n '1,3p'` | `date,slot,tariff,price_pence` puis 2 lignes de données ✅ |
| 31/03/2013 | `grep -c '^2013-03-31,'` | **48** lignes ✅ |
| 27/10/2013 | `grep -c '^2013-10-27,'` | **48** lignes ✅ |
| Test MR2 (sans série) | `cut -f1-9` | 3 lignes correctes, totaux 25,5 / 20,8 / 25,5 ✅ |
| Nombre de champs | `awk -F'\t' '{print NF}'` | `10 10 10` ✅ |

## 5. Données

### Dataset complet

- `data/CC_LCL-FullData.csv` : 8,54 Go, ~167 M lignes, 5 567 foyers.
- Période : 2011-11 → 2014-02, mesures toutes les 30 min.
- SHA-256 : non calculé (fichier trop volumineux pour l'instant).

### Échantillon local

- `data/sample/sample_5households.csv` : 152 811 lignes, **5 foyers Std**.
- Période : 2012-01-30 → 2014-02-28.
- SHA-256 : `62A4675CD50764ED4EA6882F2C17D035FEAE365A91347DA04FAC1AEE912ACEA5`.

### Tarifs

- `data/Tariffs.xlsx` → `data/tariffs_2013.csv`.
- 17 520 lignes, **2013 uniquement**, 48 créneaux/jour, 365 jours.
- Niveaux : Normal 15 072 (86,0 %), Low 1 660 (9,5 %), High 788 (4,5 %).
- Prix : High 67,20 p/kWh, Normal 11,76, Low 3,99 ; Std plat 14,228.
  **À vérifier** : ces pences ne figurent pas dans `Tariffs.xlsx`, elles
  sont codées dans `scripts/convert_tariffs.py`. Le guide (§2.2) donne
  Low = £0,0390 ; seul `tariff_d.csv` (colonne `Price`) peut trancher.
- SHA-256 : `323C00C043BB8334477B38B3D6CA69230A7F82C7DABCC6C55EC2BB810B179804`.
- **Table enrichie générée** par `scripts/convert_tariffs.py` :
  `data/tariffs_2013_price.csv` = `date,slot,tariff,price_pence`,
  **avec en-tête**, 17 520 lignes de données + 1 en-tête, LF, sans BOM.
  Uploadée dans `/p08/raw/tariffs/tariffs_2013_price.csv` (HDFS).
- Le fichier d'origine `tariffs_2013.csv` (sans prix) reste la référence
  brute ; c'est la table enrichie que MR2 charge via `DistributedCache`.

### Règles données

- Unité : **kWh par demi-heure** (pas kW).
- Un créneau manquant n'est **jamais** un 0 ; un 0 mesuré est valide.
- Coût : `kWh × pence / 100` → livres.
- Coût inconnu = **NULL** (jamais 0, jamais inventé).
- Tarifs dynamiques : **2013 uniquement**.
- Aucune réidentification des foyers.

## 6. Ce qui est fait

### Phase 1 — terminée

- Java/Maven/Python/PyTorch vérifiés.
- Dataset complet téléchargé, structure inspectée.
- Échantillon 5 foyers créé.
- Tarifs inspectés et convertis en CSV.

### Phase 2A — terminée

- Cluster Hadoop Docker 4 conteneurs.
- Zones HDFS `raw/silver/quarantine/gold` créées.
- Échantillon + tarifs uploadés dans HDFS.
- Commit `29911c7` poussé sur `origin/solo-Rahma`.

### Phase 2B — migration vers le cluster du binôme (terminée)

- `Main` fusionnée dans `solo-Rahma` en fast-forward (`dd0b030`).
- Ancien cluster bde2020 (Hadoop 3.2.1) arrêté ; conteneurs supprimés,
  **volumes conservés** (`energy-consumption_hadoop_*`).
- Nouveau cluster `apache/hadoop:3.3.6` (`infra/docker-compose.yml`),
  chemins de bind adaptés au dossier de Rahma.
- Vérifié : 1 DataNode live, YARN 1 NodeManager RUNNING.
- Zones HDFS recréées, échantillon + tarifs ré-uploadés.

### Étape 2 — contrat MR1 → MR2 (vérifiée)

- Contrat TSV défini (10 champs) — voir `01_MR1_MR2_CONTRACT.md`.
- Jeu de test 3 lignes conçu (2 jours 2013 + 1 jour 2012).
- Calculs manuels effectués.
- Fichier vérifié dans HDFS : 3 lignes, 10 champs, 47/48/48 créneaux,
  totaux 25,5 / 20,8 / 25,5, pics 2,5@18, 2,0@19, 2,0@20.

### Étape 3 — environnement + Maven (validée)

- Voir le tableau détaillé au §3 : Hadoop **3.3.6**, Java **1.8.0_212**,
  `mvn validate` = `BUILD SUCCESS`, `mvn -q compile` silencieux.
- Compréhension validée : Mapper → Shuffle/Sort → Reducer, `Writable`
  (sérialisation) et `WritableComparable` (tri + regroupement).

### Étape 4 — décisions MR2 figées v1.2 (validée)

Les 10 décisions sont écrites dans `01_MR1_MR2_CONTRACT.md` §9 et
`03_MR2_DESIGN.md` §12. Résumé :

| # | Décision |
|---|---|
| 1 | Table tarifaire **avec en-tête** ; le Mapper ignore **exactement** `date,slot,tariff,price_pence` |
| 2 | `price_coverage = créneaux tarifés / créneaux observés` (pas la complétude) |
| 3 | Coût écrit dès `pricedSlots > 0` ; `partial_tariff` si couverture < 1 ; couverture toujours écrite |
| 4 | Std `14.228` p/kWh **seulement** sur les dates du calendrier 2013 ; source unique = intersection avec la plage min/max du calendrier |
| 5 | `DateTime` bruts **et** calendrier tarifaire en **GMT** ; aucune conversion (MR1 ni MR2) ; 48 créneaux tous les jours |
| 6 | Lignes `n_valid_slots = 0` ignorées (compteur) et hors `valid_days` ; `n_missing = attendu(date) − n_valid` |
| 7 | **Pas de Combiner en v1** ; arrondi `%.6f` en sortie seulement ; tolérance `1e-6` |
| 8 | Prix Std = constante Java `14.228` (jamais relu d'un CSV arrondi) |
| 9 | Flag : `no_data` > `no_tariff` > `partial_tariff` > `partial_data` > `ok` + compteurs ; `no_data` défensif |
| 10 | `total_kwh`/`peak` = champs MR1 ; coût calculé depuis `series` ; écart > 0,001 → compteur |

Points de vigilance retenus : `series` est une **liste de paires**
(jamais une `Map<slot,kwh>`, sinon un doublon écrase une mesure) ;
`no_data` reste défensif ; les 20 compteurs du groupe `P08_MR2` sont
listés dans `03_MR2_DESIGN.md` §10.

### Étape 5 — fuseau horaire : hypothèse GMT (2026-11-06, révisé le 2026-11-09)

Commandes exécutées sur `/p08/raw/meters/sample_5households.csv`,
foyer `MAC000002` :

| Contrôle | Résultat | Conclusion |
|---|---|---|
| `grep -c '2013-03-31 01:00:00'` | **5** lignes (les 5 foyers) | pas de trou DST → compatible avec GMT, ne prouve pas le fuseau |
| 31/03/2013, journée | 48 timestamps uniques | journée de 24 h complète |
| 27/10/2013 `00:00` | 2 lignes, `0.181` identique | doublon exact du dataset, moyenné par MR1 |
| Calendrier 31/03 et 27/10 | 48 et 48 | cohérent, **non probant** : grille naïve 00:00–23:30 |

> **Hypothèses non vérifiées.** Le guide officiel (SN 7857, §3.3) est
> cité de seconde main : la phrase exacte sur le fuseau et la fin de
> période doit être recopiée depuis le PDF. La provenance GMT du
> calendrier réel (`Tariffs.xlsx` → `tariffs_2013_price.csv`) et sa
> convention début/fin de période ne sont pas documentées. Voir
> `01_MR1_MR2_CONTRACT.md` §10 et `03_MR2_DESIGN.md`.

**Conséquence :** sous cette hypothèse, MR1 moyenne les doublons et
écrit `date`/`series` **en GMT**, sans conversion. MR2 ne convertit rien
non plus. Détail dans `02_JOB1_EXTENSION_REQUEST.md` §8.

### MR1 (binôme) — état au 2026-11-06

- MR1 tourne sur le dataset complet : **3 510 403 lignes**, 5 561 foyers,
  28 mois, **35 539 823,3 kWh**, 167 811 461 lectures, ~250 min.
- **Bloquant :** la sortie réelle ne contient encore que **4 colonnes**
  (`household_id, date, total_kwh, reading_count`), pas les 10 champs du
  contrat v1.1. MR2 ne peut donc pas tourner sur les données réelles.
- Demande formelle envoyée à Taher : `02_JOB1_EXTENSION_REQUEST.md`
  (option A : remplacer la sortie ; option B : second chemin de sortie).
- **Obligation ajoutée (fuseau) :** moyenner les doublons
  `(foyer, DateTime)`, puis calculer `date`/`slot` **en GMT**, sans
  conversion. Voir `02_JOB1_EXTENSION_REQUEST.md` §8.
- En attendant : MR2 se développe et se teste sur
  `/p08/test/mr1_daily/mr1_test.tsv` (3 lignes, 10 champs).

### MR2 — classes écrites et testées (v1.3)

| Classe | Rôle |
|---|---|
| `HouseholdMonthKey` | `WritableComparable` : foyer + `YYYY-MM` + groupe tarifaire |
| `DailyMetrics` | `Writable` : kWh, pic, coût, créneaux observés/tarifés, manquants |
| `TariffCalendar` | charge `tariffs_2013_price.csv` (DistributedCache), jointure `(date, slot)`, `SLOTS_PER_DAY = 48` |
| `MonthlyMapper` | parse 10 champs, ignore l'en-tête, calcule le coût du jour |
| `MonthlyReducer` | somme, max, couverture, `valid_days`, quality flag |
| `MonthlyAggregationDriver` | configure le job, **sans Combiner**, écrit `mr2_monthly` |

### Étape 6 — MR2 codé, testé, exécuté (2026-11-09)

- **Tests JUnit :** 27 tests / 6 classes, `mvn clean test` = `BUILD SUCCESS`.
- **Exécution cluster** sur `/p08/test/mr1_daily/mr1_test.tsv` :
  `JOB2 STATUS = SUCCESS`, 2 lignes écrites.
- **Résultats identiques aux calculs manuels :**

  ```
  MAC000002,2012-03,Std,25.500000,,0.000000,2.000000,1,no_tariff,...
  MAC000002,2013-03,Std,46.300000,6.587564,1.000000,2.500000,2,partial_data,...
  ```

- **Compteurs clés :** `lines_read=3`, `lines_ok=3`, `priced_slots=95`,
  `unpriced_slots=48`, `missing_slots_total=1`, `tariff_lines_loaded=17520`,
  `tariff_header_skipped=1`, `months_written=2`, `duplicate_slots=0`,
  `flag_no_tariff=1`, `flag_partial_data=1`, `Combine input records=0`
  (confirme l'absence de Combiner).
- **Réalignement GMT :** sortie identique après refactor (aucun décalage
  de prix sur ce jeu de test).
- **Reste à faire :** exercer réellement le calendrier ToU — fait à
  l'étape 13 ci-dessous.

### Étape 13 — test ToU 19/01/2013 (2026-11-09)

- Fixture HDFS `/p08/test/mr1_daily/toU_test.tsv` : 1 jour, 48 paires,
  60 kWh (12 créneaux à 2,0 kWh, 36 à 1,0 kWh), sans fichier local dans
  le dépôt.
- Prix du 19/01 vérifiés dans HDFS : **10 Normal (11,76)**, **26 Low
  (3,99)**, **12 High (67,20)**, 48 lignes au total.
- Calcul manuel : `117,60 + 103,74 + 1612,80 = 1834,14 p` =
  **18,341400 £**.
- Sortie réelle :

  ```
  MAC000002,2013-01,ToU,60.000000,18.341400,1.000000,2.000000,1,ok,mr2-20261109T003444Z
  ```

- Compteurs : `priced_slots=48`, `unpriced_slots=0`,
  `missing_slots_total=0`, `duplicate_slots=0`, `flag_ok=1`,
  `tariff_lines_loaded=17520`, `tariff_header_skipped=1`,
  `Combine input records=0`.
- **Validé :** jointure `(date, slot)` et calcul ToU sur le cluster.
  **Non validé :** fuseau et convention début/fin de période (étape 5).
- **Option A ajoutée après ce run :** compteur non bloquant
  `missing_slots_mismatch`, confirmé `0` au rerun de contrôle
  (`mr2-20261109T004004Z`, sortie identique, 20 compteurs).

### Étape 14 — montée en charge synthétique (2026-11-09)

Objectif : mesurer MR2 sur un volume supérieur aux fixtures, sans
attendre MR1 v1.1. **Jeu fabriqué, pas des mesures réelles.**

- Entrée : `/p08/test/mr1_daily/synthetic_155k.tsv`, **55,1 Mo**,
  **155 000 lignes** = 5 000 foyers (`SYN000001`…`SYN005000`) × 31 jours
  de janvier 2013, 48 paires/jour, 60 kWh/jour.
- Découpage forcé à 16 Mo → **4 mappers**, **1 reducer**.
- Sortie : **5 000 lignes**, 439,5 Ko, `mr2-20261109T004516Z`.
- **Temps driver : `elapsed_ms = 49 541`** (≈ 49,5 s).
- Compteurs : `lines_read=155000`, `lines_ok=155000`,
  `priced_slots=7 440 000` (= 155 000 × 48), `unpriced_slots=0`,
  `missing_slots_total=0`, `missing_slots_mismatch=0`,
  `duplicate_slots=0`, `flag_ok=5 000`, `months_written=5 000`,
  `Combine input records=0`.
- `tariff_lines_loaded=70 080` = 4 × 17 520 et
  `tariff_header_skipped=4` : le calendrier est rechargé **une fois par
  mapper** (DistributedCache), comportement attendu.
- **Vérification indépendante :** toutes les lignes ont
  `monthly_kwh=1860.000000` (31 × 60), `estimated_cost_gbp=250.853400`,
  `price_coverage=1.000000`, `peak=2.000000`, `valid_days=31`, `ok`.
  Le coût a été recalculé depuis le CSV tarifaire local, dont le MD5 est
  identique à celui de HDFS (`09a0e546…`).
- **Limites :** jeu synthétique et cluster Docker mono-nœud à 4 mappers ;
  ces temps ne préjugent pas du dataset complet. La mesure réelle reste
  bloquée par MR1 v1.1 (10 colonnes).


### Étape 15 — smoke test Iceberg (2026-11-09)

- Compatibilité vérifiée : Java 1.8.0_212, Hadoop 3.3.6, réseau Docker `p08_default`.
- Spark 3.5.1 (Scala 2.12) + `iceberg-spark-runtime-3.5_2.12:1.5.2`, catalogue
  `local` (type `hadoop`), warehouse `hdfs://namenode:9000/p08/warehouse`.
- Table `local.db.t1 (id INT, label STRING) USING iceberg` créée via `spark-sql`.
- `INSERT` de 3 lignes, `SELECT` = `1 a`, `2 b`, `3 c`.
- **1 snapshot** `append`, `snapshot_id = 1496640063262222205`.
- Méta HDFS : `v1.metadata.json` (CREATE), `v2.metadata.json` (après INSERT),
  `version-hint.text = 2` ; données = 3 fichiers Parquet (~600 o chacun).
- Incidents sans effet : cache Ivy `/home/spark/.ivy2` non inscriptible →
  corrigé par `--conf spark.jars.ivy=/tmp/.ivy2` ; `findstr` inexistant
  dans le conteneur (commande Windows).
- Limite : 3 petits fichiers Parquet (1 par tâche). Un ingestion réel devra
  viser des fichiers ≈128 Mo.
- Ce que Spark/Iceberg apportent : table, ACID, snapshots, évolution de
  schéma sur HDFS. MapReduce (MR1/MR2) écrit des CSV bruts, sans transaction
  ni snapshot.

### Étape 16 — MR2 → Iceberg → SQL (2026-11-09)

- Chargement de la sortie MR2 **synthétique**
  (`/p08/gold/mr2_monthly_synth`, 5 000 lignes) dans
  `local.db.mr2_monthly` (Iceberg, catalogue `hadoop`, warehouse
  `hdfs://namenode:9000/p08/warehouse`) via vue CSV temporaire (10 champs).
- Requêtes :
  - `count(*) = 5000`
  - `sum(monthly_kwh) = 9 300 000.0` (= 5 000 × 1 860)
  - `sum(estimated_cost_gbp) = 1 254 266.9999999888` → **≈ 1 254 267,00 £**
    (dérive d'arrondi flottant sur 5 000 doubles, pas un bug)
  - `quality_flag` : `ok = 5000`
  - 3 lignes témoins : `SYN000001…`, `1860.0`, `250.8534`,
    `mr2-20261109T004516Z`
- **1 snapshot** `append` (`6569157221866874837`).
- Chaîne complète démontrée : HDFS → MR2 (CSV) → Iceberg (table ACID) →
  SQL. **Volume synthétique** : ne représente pas le dataset réel.
- Limite : table non partitionnée (`partition-specs: []`) → scan complet.
  Candidat : `PARTITIONED BY (month)`.

### Étape 17 — préparation DL sur échantillon (2026-11-09)

- Source : `data/sample/sample_5households.csv`, **5 foyers Std**,
  152 811 lignes, 2012-01-30 → 2014-02-28, 4 colonnes.
- Nettoyage : **105 doublons** `(LCLid, DateTime)` **moyennés** →
  152 706 demi-heures ; **5** valeurs `kwh` NaN à l'origine ;
  **26 229** valeurs `kwh == 0` **conservées** (mesures réelles, pas des trous).
- Passage horaire : convention **timestamp = fin de période** (1re ligne 00:30),
  `resample('1h', closed='right', label='right')` ; une heure n'est retenue
  que si **2 demi-heures valides**, sinon **NaN** (jamais un demi-total).
- Résultat : **76 418 heures**, **76 NaN**, `kwh_total = 28 411,222 kWh`.
- Split **temporel** sur les dates : `train` 2012-01-30 → 2013-07-15
  (49 078), `val` → 2013-11-06 (13 670), `test` → 2014-02-28 (13 670).
  Volumes non 70/15/15 exactement : couverture historique inégale des foyers.
- Sortie : `data/processed/dl/sample_hourly.parquet` (~415 Ko), **hors Git**.
- **Aucun entraînement** effectué. Risque identifié : PyTorch sous
  Python 3.14 (non vérifié) → prévoir un venv Python 3.11/3.12.
- Vérification indépendante de la convention horaire : le 2013-01-01,
  `kwh(hour_end 01:00) = 0,432 = kwh(00:30) 0,241 + kwh(01:00) 0,191` ;
  idem 02:00 (0,417) et 03:00 (0,423). Le créneau brut 00:00 appartient
  à l'heure 00:00, donc à la veille.
- `.gitignore` complété (`data/**/*.parquet`) : le Parquet est bien hors
  Git (`git check-ignore` renvoie `.gitignore:7`).
- Script reproductible versionné : `scripts/prepare_dl_sample.py`.

### Étape 18 — fenêtres 48 h → 1 h et baselines naïves (2026-11-09)

- Construction : fenêtre gardée seulement si les **48 entrées + la cible**
  sont présentes et les **49 heures consécutives** ; aucune imputation.
- Sortie : **75 257 fenêtres** (`X (75 257, 48)`), `train 48 162`,
  `val 13 670`, `test 13 425`, **0 NaN** — MAC000002 11 818,
  MAC000003 17 528, MAC000004 15 682, MAC000006 18 006, MAC000007 12 223.
- Normalisation **z-score par foyer**, `mean`/`std` **fittés sur `train`
  seulement** (`scalers.csv`), appliqués tels quels à `val`/`test` (aucune
  fuite). Dénormalisation vérifiée à la main : `X[-1] = 0,205 kWh` et
  `y = 0,897 kWh` = valeurs réelles.
- Artefacts **hors Git** : `windows_48to1.npz` (884 Ko),
  `windows_48to1_meta.parquet` (276 Ko), `scalers.csv`.
- Bogue corrigé : `np.savez_compressed` stockait `LCLid`/`split`/
  `target_hour` en tableaux *object* (pickle) → rechargement impossible
  avec `allow_pickle=False`. Converti en `str` / `datetime64[ns]`.

**Baselines naïves (kWh réels, aucun entraînement)**

| Modèle | Split | n | MAE | RMSE |
|---|---|---|---|---|
| persistance (t-1) | test | 13 425 | 0,2160 | 0,4872 |
| saisonnier (t-24) | test | 13 425 | **0,2021** | **0,4697** |
| moyenne train | test | 13 425 | 0,3396 | 0,6235 |

- Sur `train` : persistance 0,2138 / saisonnier 0,1695 / moyenne 0,3144.
- Le **saisonnier 24 h** est la meilleure référence sur les 3 splits :
  c'est le plancher que le GRU doit battre.
- `test` = novembre 2013 → février 2014 (**hiver**) : la baseline
  « moyenne train » est structurellement pessimiste, ce n'est pas un bug.


### Étape 19 — GRU 48 h → 24 h (2026-11-09 / 11-10)

- Tâche : prédire **24 h** à partir de **48 h** (72 h consécutives, 0 NaN,
  un seul split temporel). Sorties : `X (74 041, 48)`, `Y (74 041, 24)`,
  `train 47 771` / `val 13 315` / `test 12 955`.
- Baselines 24 h, test (kWh) : persistance 0,3960 / 0,8419 —
  **saisonnier 0,2014 / 0,4710** — moyenne train 0,3413 / 0,6286.
- Deux runs **val-only** : `runA_l1` (L1, sans calendrier) val MAE
  **0,1206** ; `runB_l1cal` val MAE 0,1231 → `runA_l1` retenu.
- Test lu **une seule fois** : MAE **0,1980** vs 0,2014, RMSE **0,4425**
  vs 0,4710. GRU meilleur sur **15 / 24** horizons (h = 1–5 et 15–24).
- Limites déclarées : les deux runs s'arrêtent à l'epoch 40 (budget), donc
  VAL est optimiste ; dégradation val→test **1,64×** contre **1,47×** pour
  le saisonnier → le gain de 12 % sur VAL ne se transfère qu'à 1,7 %.
  Un premier run MSE avait déjà vu le test avant la création du journal :
  c'est déclaré comme un **second regard global**, pas comme un protocole
  vierge.
- Journal : `data/processed/dl/test_seen.json` (n_test 12 955,
  hash `eb401abb29f4a656`, commit `a35e723`).

### Étape 20 — MR2 → Iceberg `lh.p08.monthly` (2026-11-10)

- Catalog `lh` type `hadoop`, warehouse `hdfs://namenode:9000/p08/warehouse`,
  table `PARTITIONED BY (dataset_version)`.
- 2 INSERT : `test-contract-mr2` (2 lignes — 2012-03 `cost` **NULL**,
  2013-03 `6,587564`) et `tou-test-mr2` (1 ligne, 60,0 kWh, `18,3414`).
- **2 snapshots `append`** (`5432148918239810490` +2,
  `3866664282499896418` +1), `version-hint.text = 3`,
  `v1/v2/v3.metadata.json`, **2 partitions physiques** `dataset_version=…`.
- Coût inconnu relu comme **NULL**, jamais 0.

### Étape 21 — MR1 (4 colonnes) → Iceberg `lh.p08.daily` (2026-11-10)

- Job 1 rejoué sur l'échantillon 5 foyers : `SUCCESS`,
  `Reduce output records = 3 191` ; compteurs `readings_valid 152 806`,
  `duplicate_rows_averaged 105`, `missing_null 5`, `header_skipped 1`,
  `days_more_than_48 0`, `elapsed_ms 21 782`.
- `lh.p08.daily` : **3 191 lignes**, 5 foyers, 2012-01-30 → 2014-02-28,
  total **28 416,517 kWh**, `3 161 ok` + `30 partial_data`, `n_slots 1..48`,
  `peak_kwh_hh / peak_slot / tariff_group` **NULL par construction**
  (MR1 v1 = 4 colonnes).
- 1 snapshot `append` (`1262258339771469827`), `version-hint.text = 2`.
- **Réconciliation exacte** avec le CSV brut :
  `28 448,701 − 32,184 = 28 416,517`, soit **−0,113 %**. Les 105 groupes de
  doublons ont des valeurs identiques des deux côtés : c'est la règle
  anti-double-comptage, pas un bug d'agrégation.
- Bogue corrigé : `date_format(..., 'yyyyMMddTHHmmss')` →
  `Unknown pattern letter: T` sous Spark 3.5 → `'yyyyMMdd_HHmmss'`.

### Étape 22 — Autoencodeur jour 24 h : résultat négatif (2026-11-10)

- `scripts/autoencoder_day.py` : AE 24→16→8→16→24, z-score par foyer,
  seed 42, CPU. Jours retenus **3 153** (`train 2 028` / `val 565` /
  `test 560`) : les 38 jours écartés sont incomplets (< 24 h valides) ou à
  cheval sur deux splits.
- Meilleur modèle : epoch **129**, val MSE(z) **0,20324**. Erreurs VAL en
  kWh/h : P50 0,0728 — P90 0,2049 — **P95 0,2338** (= 5,61 kWh/jour) —
  P99 0,3158 — max 0,4156. Seuil enregistré = **P95 des erreurs VAL**.
- Sensibilité du seuil (VAL seulement) et comparaison de 4 scores : la
  détection d'une hausse de +50 % **baisse** quand le percentile monte
  (29,2 % à P90 → 8,1 % à P99,5) ; à 1 % de fausses alertes le meilleur
  score (`top6_h`) atteint **12,4 %**.
- **Règle pré-enregistrée** : lire le test une seule fois seulement si la
  détection à 1 % FA est ≥ 40 %. **12,4 % < 40 % → test non lu**,
  `test_seen.json` ne contient aucune entrée `autoencoder_day`.
- Explication : +50 % d'une journée moyenne vaut **0,142 kWh/h**, soit
  **moins** que l'erreur d'un jour sain à P90 (0,205). Le score **classe**
  les anomalies (lift ≈ 10×) mais ne les **sépare** pas.
- **Angle mort** : `zeros_kwh` détecté à **0 %** quel que soit le score.
  Une coupure produit une ligne plate, donc facile à reconstruire. Un score
  de reconstruction détecte « ce que je ne sais pas redessiner », pas « une
  consommation anormalement basse » → règle de niveau (`total_kwh ≈ 0`) à
  ajouter, et **anomalie ≠ fraude**.


## 7. Ce qui reste

- [x] Vérifier le jeu de test dans `/p08/test/mr1_daily`
- [x] Enrichir le fichier tarifaire (`price_pence`) et l'uploader dans HDFS
- [x] Vérifier versions Hadoop/Java + build Maven (`validate`, `compile`)
- [x] Figer les décisions MR2 v1.2 (contrat + design)
- [x] Fuseau des données brutes : **hypothèse GMT** (aucun trou DST
  observé, fuseau tarifaire non prouvé)
- [x] Écrire `HouseholdMonthKey` + `DailyMetrics` (Writable / WritableComparable)
- [x] Écrire `TariffCalendar`, Mapper, Reducer, Driver (sans Combiner)
- [x] Tests JUnit (27/27) + exécution sur `/p08/test/mr1_daily` (T05–T07)
- [x] Test ToU réel 19/01/2013 (60 kWh, 18,341400 £) + option A
- [x] Étape 14 : montée en charge synthétique (155 k lignes, 4 mappers, 49,5 s)
- [x] Étapes 15–16 : Iceberg sur HDFS + SQL sur volume synthétique
- [x] Étape 17 : préparation DL échantillon (horaire + split temporel, sans entraînement)
- [ ] Normalisation raw → `silver/half_hourly` (F02)
- [ ] MR1 Java v1.1 (binôme) + tests T02–T04
- [ ] **MR2 Java + tests T05–T06 sur données réelles** (bloqué : MR1 v1.1 10 colonnes)
- [x] Tables Iceberg + Spark SQL (volume synthétique)
- [x] Fenêtres 48 h → 1 h (échantillon) + baselines naïves (`scripts/baseline.py`)
- [x] GRU 48 h → 24 h : MAE test **0,1980** vs saisonnier 0,2014
- [ ] GRU 48 h → 1 h (plancher toujours à battre : saisonnier MAE test 0,2021)
- [x] MR2 → Iceberg `monthly` (2 snapshots) + MR1 → Iceberg `daily` (3 191 lignes)
- [x] Autoencoder jour 24 h : résultat 
- [ ] Dashboard + rapport + soutenance

## 8. Décisions

| Sujet | Décision |
|---|---|
| Deep Learning | Exigé par l'équipe, mais après le socle PDF |
| Branche | `solo-Rahma` |
| MR1 | codé par Taher ; contrat figé par Rahma |
| Contrat / design MR2 | version **1.3**, 10 décisions figées le 2026-11-06, révisées le 2026-11-09 |
| Fuseau horaire | **hypothèse de travail** : tout en GMT ; aucune conversion (non vérifiée, voir étape 5) |
| Coût Std | appliqué seulement si la date est dans le calendrier 2013 |
| 2012 | coût **NULL** (hors calendrier), jamais 0 |
| Combiner | absent en v1 ; ajout seulement après T05/T06 |
| `series` | liste de paires `slot:kwh`, doublons conservés (jamais écrasés) |
| `/p08/ref` | non utilisé ; tarifs dans `/p08/raw/tariffs` |

## 9. Commandes utiles

```bash
docker ps --filter "name=p08-"
docker exec p08-namenode hadoop version
docker exec p08-namenode java -version
docker exec p08-namenode hdfs dfs -ls -R /p08
docker exec p08-namenode hdfs dfs -cat /p08/test/mr1_daily/mr1_test.tsv
```

```bat
cd "C:\Users\rahma\Desktop\Premiere  master\big data\PROJET\Energy-Consumption\big-data\mapreduce\job2-monthly"
mvn validate
mvn -q compile
```

## 10. Checklist globale

- [x] Cluster Hadoop 3.3.6 healthy
- [x] HDFS zones
- [x] Données dans HDFS (échantillon + tarifs + tarifs avec prix)
- [x] `Main` fusionnée dans `solo-Rahma`
- [x] Contrat MR1 → MR2 défini
- [x] Jeu de test vérifié dans HDFS
- [x] Versions Hadoop/Java + build Maven vérifiés
- [x] Décisions MR2 v1.3 figées (docs à jour)
- [x] Fuseau horaire vérifié (tout GMT : consommation et tarifs, aucune conversion)
- [x] MR2 codé, compilé, exécuté (sur jeu de test)
- [x] Résultats validés à la main (jeu de test)
- [x] Iceberg opérationnel (`lh.p08.monthly`, `lh.p08.daily`)
- [x] Deep Learning : GRU 24 h (test lu une fois) + AE jour (test non lu)
