# MR2 — Conception détaillée

**Version :** 1.0 — 2026-11-06
**Auteure :** Rahma (Personne 2)
**Référence :** `ideep08.pdf` §8.2, tests T05 et T06

## 1. Rôle de MR2

MR2 ne relit **jamais** le CSV brut. Il consomme uniquement la sortie
vérifiée de MR1, la rapproche du calendrier tarifaire, puis agrège par
`(household_id, year_month, tariff_group)`.

```
/p08/gold/mr1_daily/  (TSV 10 champs)
        +
/p08/raw/tariffs/tariffs_2013_price.csv  (DistributedCache)
        |
        v
   Mapper  -> clé (foyer, mois, groupe) / valeur (métriques du jour)
        v
   Combiner (sommes + max, associatif)
        v
   Reducer -> une ligne par foyer / mois / groupe
        v
/p08/gold/mr2_monthly/  (CSV 10 champs)
```

## 2. Entrée 1 — sortie MR1 (contrat v1.1)

TSV, sans en-tête, 10 champs :

| # | Champ | Exemple |
|---|---|---|
| 1 | `household_id` | `MAC000002` |
| 2 | `date` | `2013-03-01` |
| 3 | `tariff_group` | `Std` / `ToU` |
| 4 | `total_kwh` | `25.5` |
| 5 | `n_valid_slots` | `47` |
| 6 | `n_missing_slots` | `1` |
| 7 | `peak_kwh_hh` | `2.5` |
| 8 | `peak_slot` | `18` |
| 9 | `avg_valid_kwh_hh` | `0.542553` |
| 10 | `series` | `0:0.5;1:0.5;...;47:0.5` |

Un créneau absent n'apparaît **pas** dans `series`.

## 3. Entrée 2 — calendrier tarifaire enrichi

Fichier `tariffs_2013_price.csv`, sans en-tête, séparé par virgules :

```
date,slot,tariff,price_pence
2013-01-01,0,Normal,11.76
2013-01-01,1,Normal,11.76
...
```

- 17 520 lignes = 365 jours × 48 créneaux, **2013 uniquement**.
- `slot` est l'indice du créneau dans la journée locale (0–47), dans
  l'ordre du tableur officiel.
- Table de prix (documentation officielle, `phase1_summary.md`) :

| Groupe | Signal | Prix (p/kWh) |
|---|---|---|
| ToU | High | 67.20 |
| ToU | Normal | 11.76 |
| ToU | Low | 3.99 |
| Std | tarif plat | 14.228 |

### Règle d'application

Un prix n'est appliqué que si **la date existe dans le calendrier**
(c'est-à-dire 2013). Hors calendrier :

- `priced_slots = 0` ;
- `estimated_cost_gbp = NULL` ;
- `price_coverage = 0.0`.

On ne projette **jamais** les tarifs 2013 sur 2012 ou 2014.

Pour un foyer `Std`, le prix plat 14,228 s'applique lui aussi uniquement
aux dates présentes dans le calendrier. C'est une décision d'équipe
conservatrice, conforme au T06.

## 4. Mapper

**Clé :** `HouseholdMonthKey` (`WritableComparable`) =
`household_id` + `year_month` (`yyyy-MM`) + `tariff_group`.

**Valeur :** `DailyMetrics` (`Writable`) :

| Champ | Type | Sens |
|---|---|---|
| `totalKwh` | `double` | kWh du jour (champ 4 de MR1) |
| `peakKwhHh` | `double` | pic du jour (champ 7) |
| `costGbp` | `double` | coût des créneaux couverts, en £ |
| `observedSlots` | `long` | créneaux observés (nb de paires de `series`) |
| `pricedSlots` | `long` | créneaux observés avec un prix |
| `missingSlots` | `long` | champ 6 de MR1 |
| `validDays` | `long` | `1` (un jour = une ligne MR1) |

Traitement d'une ligne :

1. découper sur `\t` ; exiger exactement 10 champs ;
2. lire `date`, `tariff_group`, `total_kwh`, `peak_kwh_hh`,
   `n_missing_slots`, `series` ;
3. pour chaque paire `slot:kwh` de `series` :
   - `observedSlots++` ;
   - vérifier que la date existe dans le calendrier ;
   - si oui, choisir le prix :
     - `ToU` → `price_pence` du signal `(date, slot)` ;
     - `Std` → **14.228** p/kWh (tarif plat), quel que soit le signal ;
   - si un prix existe : `costGbp += kwh * price / 100`, `pricedSlots++` ;
4. contrôles (compteurs, pas d'échec bloquant) :
   - `observedSlots == n_valid_slots` ;
   - `sum(series) ≈ total_kwh` (tolérance 0,001) ;
   - `max(series) == peak_kwh_hh`.

Une ligne mal formée est **comptée** et ignorée : elle ne fabrique
jamais de valeurs.

## 5. Combiner

Autorisé car toutes les opérations sont associatives :

- somme : `totalKwh`, `costGbp`, `observedSlots`, `pricedSlots`,
  `missingSlots`, `validDays` ;
- max : `peakKwhHh`.

Aucune moyenne ni ratio n'est calculé dans le combiner.

## 6. Reducer

Pour chaque clé :

| Sortie | Formule |
|---|---|
| `monthly_kwh` | `Σ totalKwh` |
| `estimated_cost_gbp` | `Σ costGbp` si `pricedSlots > 0`, sinon **NULL** |
| `price_coverage` | `pricedSlots / observedSlots` (0 si `observedSlots = 0`) |
| `max_half_hour_kwh` | `max(peakKwhHh)` |
| `valid_days` | `Σ validDays` |
| `quality_flag` | voir §8 |

Le coût est donc un **coût des créneaux couverts**, pas une facture.
La couverture dit quelle part du mois est couverte.

## 7. Sortie — `/p08/gold/mr2_monthly/`

CSV, sans en-tête, séparateur `,`, décimales avec `.` :

```
household_id,month,tariff_group,monthly_kwh,estimated_cost_gbp,price_coverage,max_half_hour_kwh,valid_days,quality_flag,run_id
```

Exemple :

```
MAC000002,2013-03,Std,46.300000,6.587564,1.000000,2.500000,2,partial_data,mr2-20261106T120000Z
MAC000002,2012-03,Std,25.500000,,0.000000,2.000000,1,no_tariff,mr2-20261106T120000Z
```

**NULL = champ vide** (deux virgules consécutives). Aucun `0` de
remplacement, aucune chaîne `NaN`.

### `run_id`

- lu dans la configuration Hadoop : `-Dp08.run_id=...` ;
- sinon généré au démarrage du Driver :
  `mr2-yyyyMMdd'T'HHmmss'Z'` en UTC.

Il est identique pour toutes les lignes d'une exécution (traçabilité
NF05).

## 8. `quality_flag`

Ordre de priorité (le premier vrai gagne) :

| Priorité | Valeur | Condition |
|---|---|---|
| 1 | `no_data` | `observedSlots == 0` |
| 2 | `no_tariff` | `price_coverage == 0` (coût NULL) |
| 3 | `partial_tariff` | `0 < price_coverage < 1` |
| 4 | `partial_data` | couverture = 1 mais `Σ missingSlots > 0` |
| 5 | `ok` | couverture = 1 et aucun créneau manquant |

`partial_tariff` signifie : coût **partiel**, jamais présenté comme
exact. `partial_data` signifie : tous les créneaux observés sont
tarifés, mais il manque des mesures.

### Changement d'heure

Le calendrier tarifaire contient naïvement 48 créneaux par jour, y
compris les jours de DST. MR2 applique donc la convention d'index
0–47 du calendrier. Les jours à 46/50 créneaux sont signalés par
`partial_data` si MR1 les compte comme incomplets ; la convention DST
complète relève de MR1 et est documentée dans le contrat.

## 9. Tests

### T05 — deux jours, calendrier connu

Entrée : `/p08/test/mr1_daily/mr1_test.tsv` (3 lignes).

| Mois | monthly_kwh | cost_gbp | coverage | max | valid_days | flag |
|---|---|---|---|---|---|---|
| `2013-03` | `46.3` | `6.587564` | `1.0` | `2.5` | `2` | `partial_data` |
| `2012-03` | `25.5` | **NULL** | `0.0` | `2.0` | `1` | `no_tariff` |

Calcul du coût : `46.3 × 14.228 / 100 = 6.587564 £`.
`2013-03` est `partial_data` car la ligne A a 1 créneau manquant.

### T06 — hors tarif

`2012-03` : aucune date dans le calendrier 2013 → aucun prix,
couverture 0, coût NULL. Le test échoue si un `0.0` apparaît dans la
colonne coût.

### Tests unitaires (JUnit)

- `DailyMetricsTest` : sérialisation `Writable` aller-retour.
- `TariffCalendarTest` : lecture d'une ligne, prix Std vs ToU,
  date absente → pas de prix.
- `MapperLogicTest` : série à 47 créneaux → 47 observés, coût sur les
  47, pic correct.
- `ReducerLogicTest` : somme, max, couverture, flag.

## 10. Compteurs Hadoop

| Compteur | Sens |
|---|---|
| `P08_MR2/lines_ok` | lignes MR1 valides |
| `P08_MR2/lines_malformed` | lignes ignorées |
| `P08_MR2/series_slot_mismatch` | `series` ≠ `n_valid_slots` |
| `P08_MR2/series_sum_mismatch` | `Σ series` ≠ `total_kwh` |
| `P08_MR2/series_peak_mismatch` | `max(series)` ≠ `peak_kwh_hh` |
| `P08_MR2/priced_slots` | créneaux tarifés |
| `P08_MR2/unpriced_slots` | créneaux sans prix |
| `P08_MR2/months_written` | lignes de sortie |

## 11. Limites assumées

- Le calendrier officiel ne couvre que 2013 : 2012 et 2014 ont un coût
  NULL, même pour les foyers Std.
- Le coût est une **estimation d'exercice** (hors taxes et frais).
- Les jours de DST suivent la convention d'index du calendrier.
- Aucune réidentification : `household_id` reste le `LCLid`
  pseudonymisé du dataset.
