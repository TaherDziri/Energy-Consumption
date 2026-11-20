# P08 - Preuves F01, F06, F10, F11 et matrice de tests

Mesures faites le 2026-11-11 sur la branche `solo-Rahma`, cluster Docker
`p08-namenode | datanode | resourcemanager | nodemanager` (Hadoop 3.3.6,
un seul hote). Tout chiffre ci-dessous a ete produit par une commande
reproductible ; rien n'est estime.

**Mise a jour 2026-11-20 :** integration du contrat v1.1 livre par Taher
(jour et creneaux **locaux Europe/London**, DST 46/48/50). Les jars ont ete
reconstruits (§1) et un **run reel sur l'echantillon 5 foyers** a ete produit
et charge (§2). Les mesures F11 ci-dessous restent celles du 2026-11-11 avec
les **anciens** jars : elles ne sont pas presentees comme des mesures du jar
v1.1.

---

## 1. F01 - integrite des artefacts (SHA-256)

`hdfs dfs -checksum` renvoie du **CRC32C**, pas du SHA-256 : il ne convient
pas pour F01. Les valeurs ci-dessous viennent de `Get-FileHash -Algorithm
SHA256` (poste) et de `sha256sum` (conteneur).

| Artefact | Taille | SHA-256 poste | SHA-256 conteneur / HDFS | Identique |
|---|---|---|---|---|
| `job1-daily-consumption.jar` (v1.1) | 20 543 B | `38bf1070ac121a95580e68d521424f7931ff1e581b7505dd4ad9d48ed258fa64` | `38bf1070...8fa64` (`/job/`) | **oui** |
| `job2-monthly-aggregation.jar` (v1.1) | 19 906 B | `ad01db8e4653fbca59aa3f995fe4406b35ee4a2f16d7f10cc664db5f4aab40f9` | `ad01db8e...40f9` (`/tmp/`) | **oui** |
| `data/tariffs_2013_price.csv` | 461 203 B | `b70543c61d52e66d1a039adbfd6bb51d729b50f23f65fd8331186363ca837d46` | `b70543c6...7d46` (`/p08/raw/tariffs/`) | **oui** |
| `mr1_v11_sample.tsv` (fixture) | 1 472 260 B | `a9e1f1faade949e555d9d9cfba6e165d4591bb1f42eda71861a7b03d4a86e354` | `a9e1f1fa...e354` (`/p08/test/mr1_v11_sample/part-mr1v11.tsv`) | **oui** |
| `synthetic_155k.tsv` | 55,1 Mo | - (pas de copie locale) | `61379bd000eb45bd69a3fec50bfc0e913bc20f3e5f34dd8697cca0fb004e2197` | HDFS seul |
| `synthetic_620k.tsv` | 223,5 Mo | - | voir `sha256sum` au besoin | HDFS seul |

Le jar Job 2 n'a pas de copie dans `/job` : ce point de montage est
**read-only** et pointe sur `big-data/mapreduce/job1-daily/target`. Il est
donc copie dans `/tmp` du namenode (voir §6).

---

## 2. F06 - qualite des donnees et reconciliation

Requete : `sql/f06_quality.sql`.

| Table | Version | Lignes | Foyers | Debut | Fin | kWh | ok | non ok | creneaux manquants | pics NULL |
|---|---|---|---|---|---|---|---|---|---|---|
| `lh.p08.daily` | `mr1-4cols-sample` | 3 191 | 5 | 2012-01-30 | 2014-02-28 | 28 416,517 | 3 161 | 30 | 467 | 3 191 |
| `lh.p08.monthly` | `mr1-v11-real-sample` | 108 | 5 | 2012-01-01 | 2014-02-01 | 28 416,517 | 55 | 53 | - | - |
| `lh.p08.daily_v11` | `mr1-v11-real-sample` | 3 191 | 5 | 2012-01-30 | 2014-02-28 | 28 416,517 | - | 30 | 473 | 0 |
| `lh.test.monthly` | `sample-fixture-v11` | 108 | 5 | 2012-01-01 | 2014-02-01 | 28 416,517005 | 55 | 53 | - | - |
| `lh.test.monthly` | `test-contract-mr2` | 2 | 1 | 2012-03-01 | 2013-03-01 | 71,8 | 0 | 2 | - | - |
| `lh.test.monthly` | `tou-test-mr2` | 1 | 1 | 2013-01-01 | 2013-01-01 | 60,0 | 1 | 0 | - | - |

Reconciliation des deux chaines independantes (meme source, deux formats) :

| Foyer | `lh.p08.daily` (MR1 4 col.) | fixture (MR1 v1.1 -> MR2) | ecart |
|---|---|---|---|
| MAC000002 | 6 095,672 | 6 095,672 | 0,0 |
| MAC000003 | 14 080,862 | 14 080,862005 | -5,0e-6 |
| MAC000004 | 1 119,839 | 1 119,839 | 0,0 |
| MAC000006 | 2 167,448 | 2 167,448 | 0,0 |
| MAC000007 | 4 952,696 | 4 952,696 | 0,0 |
| **Total** | **28 416,517** | **28 416,517005** | **5,0e-6** |

Lecture : l'ecart residuel (<= 5e-6) vient de l'**arrondi a 3 decimales** des
totaux journaliers ecrits par MR1 v1, pas d'une perte d'energie (moyenner les
105 doublons ne change pas la somme). Le nombre de creneaux manquants declare
par `lh.p08.daily` (467, derive `48 - n_slots`) est **identique** a celui
calcule par la fixture (467) : deux chemins, meme diagnostic.

### Run reel v1.1 (`mr1-v11-real-sample`, 2026-11-20)

Ce run n'est **pas** la fixture : MR1 v1.1 a ete relance sur
`/p08/raw/meters/sample_5households.csv` (5 foyers reels) puis MR2 v1.1 sur sa
sortie. Compteurs MR1 : `readings_valid=152806`, `duplicate_rows_averaged=105`,
`dst_days=17`, toutes les incoherences a 0, `elapsed_ms=34443`. Compteurs MR2 :
`lines_ok=3191`, `flag_ok=55`, `flag_partial_data=5`, `flag_no_tariff=48`,
`priced_slots=87594`, `unpriced_slots=65107`, `missing_slots_total=473`,
`duplicate_slots=20`, `dst_days=17`, `missing_slots_mismatch=0`,
`run_id=mr2-v11-real-sample`, `elapsed_ms=22116`.

Trois controles independants :

| Controle | Resultat |
|---|---|
| MR1 -> MR2 par `(foyer, mois)` | ecart max **0,0** (28 416,517 kWh des deux cotes) |
| `scripts/check_v11_vs_mr2.py` (CSV brut -> local DST -> mois, sans lire MR2) | kwh `2,8e-6`, cout `5,2e-7`, pic `1,0e-7`, couverture `0` ; **0** ecart de flag ; **48** couts NULL des deux cotes ; **0** cout a 0 |
| `sql/p08_v11_real.sql` (Iceberg) | 108 lignes, 60 couts, 48 NULL, **2 321,437776 GBP**, ecart journalier/mensuel **0,0** |

Les 20 `duplicate_slots` sont les slots 2 et 3 repetes le 27/10 (50
demi-heures) : deux lectures physiques **additionnees**, jamais ecrasees.

---

## 3. F10 - justification d'architecture

La chaine est separee en quatre etages independants et rejouables :

1. **HDFS** conserve les donnees brutes et les sorties intermediaires ; chaque
   etape peut etre rejouee sans relire la source.
2. **Deux jobs MapReduce** font les transformations : job 1 (demi-heure ->
   jour) et job 2 (jour -> mois + cout). Ces agregations sont deterministes,
   idempotentes et verifiables par compteurs, sans etat en memoire, et elles
   tiennent sur un cluster de quatre conteneurs. C'est aussi le perimetre
   demande par le cahier des charges (deux jobs).
3. **Iceberg** apporte l'ACID, le partitionnement par `dataset_version` (une
   fixture de test ne peut pas contaminer la table de production) et
   l'historique de snapshots qui rend le deplacement des runs de validation
   vers `lh.test.monthly` auditable (snapshot `delete`).
4. **Spark SQL** sert uniquement de lecture et d'export, pas de moteur de
   transformation : un seul moteur de calcul a valider.

Le **dashboard ne lit pas Iceberg en direct** mais des exports Parquet : la
demo reste reproductible sans garder une session Spark ouverte, et l'export
est la seule chose a regenerer. Le volet **Deep Learning** est traite a part,
sur un echantillon horaire de 5 foyers : il ne pretend pas etre du volume Big
Data et ses metriques sont des mesures locales, distinctes des compteurs du
cluster.

Limites assumees : cluster Docker mono-hote, aucun run a l'echelle des 8,5 Go
du binome, jours/creneaux locaux `Europe/London` depuis le contrat v1.1 (mais
la **convention debut/fin de periode reste non verifiee** et la citation du
guide officiel n'a pas ete relue dans le PDF), cout `Std` a prix plat 2013
uniquement.

---

## 4. F11 - trois volumes mesures

Protocole : meme jar, meme cluster, meme calendrier tarifaire, sortie
supprimee avant chaque run. `elapsed_ms` est imprime par le driver ;
`WALL_MS` est mesure autour de `hadoop jar` (soumission comprise). Les temps
par phase viennent du dump Hadoop (`Total time spent by all map/reduce tasks`).

| # | Volume | Nature | Lignes | Foyers | `elapsed_ms` | `WALL_MS` | mappers | reducers | map (ms) | reduce (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| V1 | `/p08/test/mr1_v11_sample` | echantillon reel (fixture) | 3 191 | 5 | 30 304 | 35 317 | 1 | 1 | 10 428 | 2 816 |
| V2 | `synthetic_155k.tsv` | **volume synthetique** | 155 000 | 5 000 | 25 377 | 27 089 | 1 | 1 | 5 961 | 3 639 |
| V3 | `synthetic_620k.tsv` | **volume synthetique** | 620 000 | 20 000 | 30 420 | 32 330 | 2 | 1 | 18 194 | 4 043 |

Compteurs verifies :

| Volume | `lines_ok` | `months_written` | `priced_slots` | `unpriced_slots` | incoherences |
|---|---|---|---|---|---|
| V1 | 3 191 | 108 | 87 594 | 65 107 | toutes a 0 |
| V2 | 155 000 | 5 000 | 7 440 000 | 0 | toutes a 0 |
| V3 | 620 000 | 20 000 | 29 760 000 | 0 | toutes a 0 |

**Conclusion honnete.** 194 fois plus de lignes, mais un temps quasi identique
(30,3 s -> 30,4 s) et meme un volume intermediaire plus rapide que le petit
(25,4 s). Le cout fixe (demarrage JVM, soumission YARN, chargement du
calendrier de 17 520 lignes par mapper via le DistributedCache) domine a ces
echelles, et le cluster est un seul hote Docker. **Aucune acceleration
lineaire n'est revendiquee** : on rapporte le volume traite, les compteurs et
le temps observe, pas un debit normalise.

**Important — version du jar.** Ce tableau a ete mesure le 2026-11-11 avec les
jars `6df1def5...` (job 1) et `0d8eaeb0...` (job 2), soit l'hypothese GMT. Les
jars ont ensuite ete reconstruits le 2026-11-20 pour le contrat v1.1 local DST
(`38bf1070...` et `ad01db8e...`, voir §1). Avec le **nouveau** jar, une seule
mesure a ete faite : MR2 v1.1 sur 3 191 lignes reelles, `elapsed_ms=22 116`
(§2). Les volumes synthetiques V2/V3 **n'ont pas ete re-mesures** avec le jar
v1.1 : les temps du tableau ne doivent donc **pas** etre attribues au jar
v1.1. La conclusion qualitative (cout fixe dominant, aucune acceleration
lineaire revendiquee) reste intacte, mais elle n'est pas une nouvelle mesure.

### Run 8,5 Go du binome

Non reproduit ici. A demander, et a etiqueter « mesure du binome » :
identifiant de job (`job_...` / `application_...`), dump complet des compteurs
`P08_MR2`, chemin d'entree + taille + nombre de lignes, nombre de
mappers/reducers lances, `elapsed_ms` et temps par phase, configuration du
cluster (noeuds, conteneurs, vCores, disques), presence d'un Combiner, commit
du jar MR2, nombre de lignes de sortie, et s'il s'agit de MR1 ou MR2.

---

## 5. Matrice de tests

> **Source exacte :** `ideep08.pdf` §17 « Plan de tests et critères
> d'acceptation » (page 16), et non §8.2 comme supposé auparavant. Libellés et
> résultats attendus recopiés du PDF, sans invention. Le PDF demande aussi
> « un petit CSV artificiel avec calculs manuels documentés » et « au moins une
> date proche d'un changement d'heure, avec convention annoncée » : le run réel
> contient 17 jours DST et la convention locale est annoncée en §1.

| ID | Scénario / résultat attendu (PDF §17) | Statut | Preuve |
|---|---|---|---|
| T01 — Parsing | « Ligne valide, en-tête répété, date illisible » → « Ligne valide admise ; cas problématiques comptés/quarantinés » | **fait** | MR1 v1.1 : `header_skipped=1`, `malformed=0`, `value_parse_error=0`, `missing_null=5`, `negative=0` |
| T02 — MR1 | « Journée de 48 mesures connues » → « Somme kWh, pic et créneau exacts » | **fait** | run réel 5 foyers + `check_v11_vs_mr2.py` : kwh écart ≤ 2,8e-6, pic ≤ 1,0e-7 |
| T03 — Doublons | « Deux copies identiques et un conflit de créneau » → « Déduplication conforme, conflit explicite » | **fait** | `duplicate_rows_averaged=105`, `tariff_conflict=0` ; les 20 slots répétés du 27/10 sont conservés et comptés |
| T04 — Lacune | « Journée avec mesures manquantes » → « Complétude inférieure à 100 %, aucune invention de zéro » | **fait** | `n_missing_slots` issu de l'attendu local 46/48/50, créneau absent de la série (jamais `slot:0`), `partial_data=5`, `missing_slots_mismatch=0` |
| T05 — MR2 | « Deux jours, calendrier de prix connu » → « Coût £ et total kWh corrects à la main » | **fait** | `docs/03` §9 : 46,3 kWh, 6,587564 GBP, `partial_data` |
| T06 — Hors tarif | « Signal 2013 absent ou année non couverte » → « Coût null/partiel et taux de couverture indiqué » | **fait** | `2012-03` : coût vide, couverture 0, `no_tariff` |
| T07 — Iceberg | « Charger les deux tables + requête SQL » → « Métadonnées et lignes disponibles, résultats cohérents » | **fait** | `sql/p08_v11_real.sql` : `lh.p08.monthly` 108 lignes + `lh.p08.daily_v11` 3 191, écart 0,0 |
| T08 — Reproductibilité | « Relancer jobs avec même lot/version » → « Même agrégation numérique et même schéma » | **fait** (2026-11-20) | MR2 relancé avec le même jar, la même entrée et le même `run_id` : sortie **octet pour octet identique**, SHA-256 `2284eff2cd1e7cfe107607d636a56559ba8de35e769b2677317c7f96daab9d02` (108 lignes, `elapsed_ms=22 629`) |
| T09 — Volumétrie | « Exécuter avec lot réduit puis élargi » → « Temps et compteurs consignés, limites analysées » | **fait (volumes synthétiques)** | F11 §4 : 3 191 / 155 000 / 620 000 lignes, temps et compteurs consignés ; aucune accélération linéaire revendiquée |
| T10 — Visualisation | « Consommation et coût pour un foyer/mois » → « Unités et dates correctes, couverture affichée » | **fait** | dashboard page « Run reel v1.1 » : kWh, GBP (£), `price_coverage`, mois ; 10 pages vérifiées, 0 erreur console |

Le test ToU du 19/01/2013 (48 créneaux, 18,341400 GBP, `ok`) est une **preuve
supplémentaire**, pas T07 : T07 est le test Iceberg dans le PDF.

Tests unitaires (2026-11-20) : job 1 **37 tests / 4 classes**, job 2 **29 tests
/ 6 classes**, `mvn clean test` = `BUILD SUCCESS` pour les deux modules. Les
nouveaux tests couvrent `expectedSlots` 46/48/50 (`Europe/London`) et le
doublon de slots 2/3 le 27/10.

---

## 6. Deux pieges operationnels rencontres (a garder)

1. `/job` est un montage **read-only** de `big-data/mapreduce/job1-daily/target`.
   Le jar Job 2 doit etre copie dans le conteneur :
   `docker cp big-data\mapreduce\job2-monthly\target\job2-monthly-aggregation.jar p08-namenode:/tmp/`
2. `-Dp08.run_id=...` (un seul token) n'est pas consomme par
   `GenericOptionsParser` et le driver s'arrete sur
   `Usage: MonthlyAggregationDriver ...`. Ecrire **`-D p08.run_id=...`**
   (deux tokens).
