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
`no_data` reste défensif ; les 19 compteurs du groupe `P08_MR2` sont
listés dans `03_MR2_DESIGN.md` §10.

### Étape 5 — fuseau horaire vérifié (2026-11-06)

Commandes exécutées sur `/p08/raw/meters/sample_5households.csv`,
foyer `MAC000002` :

| Contrôle | Résultat | Conclusion |
|---|---|---|
| `grep -c '2013-03-31 01:00:00'` | **5** lignes (les 5 foyers) | données en **GMT** (pas en heure locale) |
| 31/03/2013, journée | 48 timestamps uniques | journée de 24 h complète |
| 27/10/2013 `00:00` | 2 lignes, `0.181` identique | doublon exact du dataset, moyenné par MR1 |
| Calendrier 31/03 et 27/10 | 48 et 48 | calendrier indexé en GMT |

**Conséquence :** MR1 moyenne les doublons et écrit `date`/`series`
**en GMT**, sans conversion. MR2 ne convertit rien non plus. Détail dans
`02_JOB1_EXTENSION_REQUEST.md` §8.

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

- **Tests JUnit :** 26 tests / 6 classes, `mvn clean test` = `BUILD SUCCESS`.
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
- **Reste à faire :** exercer réellement le calendrier ToU — le jeu de
  test est `Std`, donc `pricePence` n'a jamais été appelé sur le cluster.

## 7. Ce qui reste

- [x] Vérifier le jeu de test dans `/p08/test/mr1_daily`
- [x] Enrichir le fichier tarifaire (`price_pence`) et l'uploader dans HDFS
- [x] Vérifier versions Hadoop/Java + build Maven (`validate`, `compile`)
- [x] Figer les décisions MR2 v1.2 (contrat + design)
- [x] Vérifier le fuseau horaire des données brutes (GMT confirmé)
- [x] Écrire `HouseholdMonthKey` + `DailyMetrics` (Writable / WritableComparable)
- [x] Écrire `TariffCalendar`, Mapper, Reducer, Driver (sans Combiner)
- [x] Tests JUnit (26/26) + exécution sur `/p08/test/mr1_daily` (T05/T06)
- [ ] Normalisation raw → `silver/half_hourly` (F02)
- [ ] MR1 Java v1.1 (binôme) + tests T02–T04
- [ ] **MR2 Java + tests T05–T06 sur données réelles** (bloqué : MR1 v1.1 10 colonnes)
- [ ] Tables Iceberg + Spark SQL
- [ ] GRU + Autoencoder
- [ ] Dashboard + rapport + soutenance

## 8. Décisions

| Sujet | Décision |
|---|---|
| Deep Learning | Exigé par l'équipe, mais après le socle PDF |
| Branche | `solo-Rahma` |
| MR1 | codé par Taher ; contrat figé par Rahma |
| Contrat / design MR2 | version **1.3**, 10 décisions figées le 2026-11-06, révisées le 2026-11-09 |
| Fuseau horaire | tout en **GMT** (consommation et tarifs) ; aucune conversion |
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
- [ ] Iceberg opérationnel
- [ ] Deep Learning
