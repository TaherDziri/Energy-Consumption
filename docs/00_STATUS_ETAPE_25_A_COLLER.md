> **Texte à coller dans `docs/00_PROJECT_STATUS.md`**, juste après la dernière
> étape existante (ne pas remplacer le fichier). Fichier préparé le
> 2026-11-20 ; le document d'origine n'a pas été modifié.

---

### Étape 25 — Contrat v1.1 livré par Taher : MR2 local DST, run réel 5 foyers, dashboard 10 pages (2026-11-20)

- **Intégration `origin/Main`** dans `solo-Rahma` (commit `903df24`,
  `b97610e` côté Taher). Job 1 v1.1 = 10 colonnes, jour et créneaux
  **locaux `Europe/London`**, 46/48/50 demi-heures selon la DST. Seul conflit :
  `docs/02_JOB1_EXTENSION_REQUEST.md` → décision Taher §8 conservée, notre
  hypothèse GMT initiale gardée en §9 comme historique (citation du PDF
  toujours **non vérifiée**).
- **Jars reconstruits** : job 1 `38bf1070ac121a95580e68d521424f7931ff1e581b7505dd4ad9d48ed258fa64`
  (20 543 B, 37 tests), job 2 `ad01db8e4653fbca59aa3f995fe4406b35ee4a2f16d7f10cc664db5f4aab40f9`
  (19 906 B, 29 tests). `mvn clean test` = `BUILD SUCCESS` pour les deux modules.
  SHA-256 poste = SHA-256 conteneur (`/job/` et `/tmp/`) dans les deux cas.
- **MR2 adapté au contrat v1.1** : `TariffCalendar.expectedSlots(date)` calcule
  46 (printemps) / 48 / 50 (automne) depuis les règles de `Europe/London`, jamais
  en dur. `dst_days` ajouté aux compteurs ; les slots 2 et 3 répétés le 27/10
  sont **additionnés** et comptés dans `duplicate_slots`, jamais écrasés. Pas de
  Combiner, arrondi uniquement à la sortie (`%.6f`, `Locale.ROOT`).
- **Run réel** (echantillon 5 foyers, **pas** le run 8,5 Go) :
  - MR1 sur `/p08/raw/meters/sample_5households.csv` → `/p08/gold/mr1_daily_v11` :
    **3 191** lignes, `readings_valid=152 806`, `duplicate_rows_averaged=105`,
    `dst_days=17`, `elapsed_ms=34 443`, toutes les incohérences à 0.
  - MR2 → `/p08/gold/mr2_monthly_v11`, `run_id=mr2-v11-real-sample` :
    **108** lignes, `flag_ok=55`, `flag_partial_data=5`, `flag_no_tariff=48`,
    `priced_slots=87 594`, `unpriced_slots=65 107`, `missing_slots_total=473`,
    `duplicate_slots=20`, `dst_days=17`, `missing_slots_mismatch=0`,
    `elapsed_ms=22 116`.
  - **28 416,517 kWh**, **2 321,437776 GBP**, 60 coûts calculés et **48 NULL**
    (hors calendrier 2013), **aucun coût à 0**.
- **Trois contrôles indépendants** : MR1→MR2 par `(foyer, mois)` écart max
  **0,0** ; `scripts/check_v11_vs_mr2.py` recalcule depuis le CSV brut en local
  DST sans lire MR2 (kwh `2,8e-6`, coût `5,2e-7`, pic `1,0e-7`, couverture `0`,
  **0** écart de flag, **48** NULL des deux côtés) ; `sql/p08_v11_real.sql`
  charge `lh.p08.monthly` (108 lignes) et la nouvelle table `lh.p08.daily_v11`
  (3 191 lignes, 17 jours DST, 0 pic NULL) avec écart journalier/mensuel **0,0**.
- **Dashboard** : `sql/p08_dashboard_export_v11.sql` exporte
  `data/dashboard/monthly_v11` (108) et `daily_v11` (3 191). Nouvelle page
  **« Run reel v1.1 »** avec profil demi-heure moyen depuis la `series` MR1.
  Les 10 pages ont été ouvertes dans le navigateur : **0 erreur console**.
  Les pages « Couts », « Qualite », « Std vs ToU » et « Limites » ont été
  corrigées : elles ne disent plus que MR1 v1.1 manque.
- **Honnêteté des volumes** : `sample-fixture-v11` reste une **fixture** dans
  `lh.test.monthly` ; `synthetic_155k` / `synthetic_620k` restent des **volumes
  synthétiques**. Les temps F11 (2026-11-11) ont été mesurés avec les **anciens**
  jars et ne sont pas attribués au jar v1.1 ; avec le nouveau jar, seule la
  mesure ci-dessus (`elapsed_ms=22 116` sur 3 191 lignes) est rapportée.
- **Matrice T01–T10 complétée** : les définitions exactes étaient dans
  `ideep08.pdf` §17 « Plan de tests et critères d'acceptation » (page 16), pas
  en §8.2 comme supposé. Elles ont été recopiées telles quelles dans
  `docs/04_PREUVES_F01_F11.md`. T08 (reproductibilité) est prouvé par un
  relancement de MR2 avec le même jar et le même `run_id` : sortie octet pour
  octet identique, SHA-256 `2284eff2cd1e7cfe107607d636a56559ba8de35e769b2677317c7f96daab9d02`.
  Le test ToU du 19/01/2013 reste une preuve supplémentaire, pas T07 (T07 =
  Iceberg dans le PDF).
- **Toujours non vérifié** : la convention début/fin de période, la citation du
  guide officiel dans `ideep08.pdf`, la provenance de `tariffs_2013_price.csv`.
  Le run 8,5 Go du binôme n'a pas été reproduit localement : identifiant de job,
  compteurs `P08_MR2` complets, chemin/taille/lignes d'entrée, mappers/reducers,
  phases, configuration, Combiner, commit du jar, lignes de sortie et
  réconciliation MR1/MR2 restent à demander.
