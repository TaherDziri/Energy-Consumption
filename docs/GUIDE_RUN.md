# Guide de run P08

Toutes les commandes se lancent **depuis la racine du dépôt**.

## 1. Prérequis

- Docker Desktop démarré (backend WSL2).
- Environnement Python : `.venv\Scripts\python.exe`.
- Vérifier : `docker ps`.

## 2. Run rapide — dashboard seul

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dashboard.txt
.venv\Scripts\streamlit.exe run dashboard\app.py --server.headless true --server.port 8502
```

Ouvrir **http://localhost:8502**.  
10 pages, **50 foyers par défaut**. Arrêt : `Ctrl+C`.

## 3. Run complet de démo — HDFS → MR1 → MR2 → Iceberg → dashboard

### 3.1 Démarrer le cluster

```powershell
docker compose -f "infra/docker-compose.yml" up -d
docker compose -f "infra/docker-compose.yml" ps
docker exec p08-namenode hdfs dfsadmin -report
docker exec p08-resourcemanager yarn node -list
```

Attendre : `Live datanodes (1)` et `Total Nodes:1`.

### 3.2 Voir les données HDFS

```powershell
docker exec p08-namenode hdfs dfs -ls -h /p08/raw/meters /p08/raw/tariffs
```

### 3.3 Copier le jar Job 2 (une seule fois)

```powershell
docker cp big-data\mapreduce\job2-monthly\target\job2-monthly-aggregation.jar p08-namenode:/tmp/job2-monthly-aggregation.jar
```

Le jar Job 1 est déjà monté en lecture seule dans `/job`.

### 3.4 Rejouer MR1 v1.1 — échantillon 5 foyers

```powershell
docker exec p08-namenode hdfs dfs -rm -r -f /p08/gold/mr1_daily_v11_demo
docker exec p08-namenode hadoop jar /job/job1-daily-consumption.jar /p08/raw/meters/sample_5households.csv /p08/gold/mr1_daily_v11_demo
```

Contrôle : `JOB1 STATUS = SUCCESS`, `readings_valid = 152806`, `dst_days = 17`.

### 3.5 Rejouer MR2 v1.1

```powershell
docker exec p08-namenode hdfs dfs -rm -r -f /p08/gold/mr2_monthly_v11_demo
docker exec p08-namenode hadoop jar /tmp/job2-monthly-aggregation.jar -D p08.run_id=demo-f12 /p08/gold/mr1_daily_v11_demo /p08/gold/mr2_monthly_v11_demo /p08/raw/tariffs/tariffs_2013_price.csv
```

**Piège :** `-D` et `p08.run_id=demo-f12` sont deux tokens séparés.  
Contrôle : `JOB2 STATUS = SUCCESS`, `months_written=108`, `flag_no_tariff=48`.

### 3.6 Run réel 50 foyers — optionnel

```powershell
docker exec p08-namenode hdfs dfs -rm -r -f /p08/gold/mr1_daily_50mix /p08/gold/mr2_monthly_50mix
docker exec p08-namenode hadoop jar /job/job1-daily-consumption.jar /p08/raw/meters/sample_50_mix.csv /p08/gold/mr1_daily_50mix
docker exec p08-namenode hadoop jar /tmp/job2-monthly-aggregation.jar -D p08.run_id=mr2-v11-50mix /p08/gold/mr1_daily_50mix /p08/gold/mr2_monthly_50mix /p08/raw/tariffs/tariffs_2013_price.csv
```

Contrôle : 37 145 jours-foyers, 1 237 lignes mensuelles, 40 Std + 10 ToU.  
Ne pas appliquer `scripts/check_v11_vs_mr2.py` à ce run mixte.

### 3.7 Iceberg + Spark SQL

La commande complète de contrôle est dans `docs/12_DEMO_F12.md`, §4.  
Résultat attendu pour le run 5 foyers : `108 | 60 | 48 | 28416.517 | 2321.437776`.

### 3.8 Ouvrir le tableau de bord

```powershell
.venv\Scripts\streamlit.exe run dashboard\app.py --server.headless true --server.port 8502
```

### 3.9 Arrêter

```powershell
docker compose -f "infra/docker-compose.yml" stop
```

## 4. Livrables

- Rapport PDF : `report/main.pdf`
- Démo détaillée : `docs/12_DEMO_F12.md`
- Preuves : `docs/04_PREUVES_F01_F11.md`
- État du projet : `docs/00_PROJECT_STATUS.md`

## 5. À ne pas faire

- Ne pas lancer le run complet 8,5 Go : c'est une mesure du binôme, non reproduite localement.
- Ne pas présenter `sample-fixture-v11`, `synthetic_155k` ou `synthetic_620k` comme des mesures de production.
- Ne pas écrire un coût inconnu à 0 : il reste `NULL`.
