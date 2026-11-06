# P08 — État du projet

**Dernière mise à jour :** 2026-11-06
**Étudiante :** Rahma (Personne 2)
**Branche :** `solo-Rahma`
**Dépôt :** https://github.com/TaherDziri/Energy-Consumption

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

## 3. Environnement vérifié (étape 1 — validée)

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

## 4. HDFS (vérifié)

```
/p08/raw/meters/sample_5households.csv   7 681 883 B
/p08/raw/tariffs/tariffs_2013.csv          484 027 B
/p08/silver/half_hourly/                   vide
/p08/quarantine/                           vide
/p08/gold/mr1_daily/                       vide
/p08/gold/mr2_monthly/                     vide
/p08/test/mr1_daily/mr1_test.tsv           3 lignes (jeu de test MR2)
```

Le dossier `/p08/test/mr1_daily` est séparé de `gold/` : il ne doit
jamais polluer les sorties de production.

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
- **Le CSV actuel ne contient que `TariffDateTime,Tariff` — pas de
  colonne prix.** Il devra être enrichi (`price_pence`) avant MR2.

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

## 7. Ce qui reste

- [x] Vérifier le jeu de test dans `/p08/test/mr1_daily`
- [ ] Enrichir le fichier tarifaire (`price_pence`)
- [ ] Normalisation raw → `silver/half_hourly` (F02)
- [ ] MR1 Java (binôme) + tests T02–T04
- [ ] **MR2 Java + tests T05–T06**
- [ ] Tables Iceberg + Spark SQL
- [ ] GRU + Autoencoder
- [ ] Dashboard + rapport + soutenance

## 8. Décisions

| Sujet | Décision |
|---|---|
| Deep Learning | Exigé par l'équipe, mais après le socle PDF |
| Branche | `solo-Rahma` |
| MR1 | codé par Taher ; contrat figé par Rahma |
| Coût Std | appliqué seulement si la date est dans le calendrier 2013 |
| 2012 | coût **NULL** (hors calendrier) |
| `/p08/ref` | non utilisé ; tarifs dans `/p08/raw/tariffs` |

## 9. Commandes utiles

```bash
docker ps --filter "name=p08-"
docker exec p08-namenode hdfs dfs -ls -R /p08
docker exec p08-namenode hdfs dfs -cat /p08/test/mr1_daily/mr1_test.tsv
```

## 10. Checklist globale

- [x] Cluster Hadoop 3.3.6 healthy
- [x] HDFS zones
- [x] Données dans HDFS
- [x] `Main` fusionnée dans `solo-Rahma`
- [x] Contrat MR1 → MR2 défini
- [x] Jeu de test vérifié dans HDFS
- [ ] MR2 codé, compilé, exécuté
- [ ] Résultats validés à la main
- [ ] Iceberg opérationnel
- [ ] Deep Learning
