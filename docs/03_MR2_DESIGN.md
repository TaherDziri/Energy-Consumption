# MR2 — Conception détaillée

**Version :** 1.1 — 2026-11-06
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
   Reducer -> une ligne par foyer / mois / groupe   (sans Combiner en v1)
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

Fichier `tariffs_2013_price.csv`, séparé par virgules, **avec en-tête**.
Le Mapper ignore la première ligne (elle commence par `date,`) :

```
date,slot,tariff,price_pence
2013-01-01,0,Normal,11.76
2013-01-01,1,Normal,11.76
...
```

- 17 520 lignes de données + 1 en-tête = 17 521 lignes, **2013 uniquement**.
- 365 jours × 48 créneaux, y compris les jours de changement d'heure.
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
   `n_valid_slots`, `n_missing_slots`, `series` ;
3. si `n_valid_slots = 0` : incrémenter `empty_day_skipped` et **ignorer**
   la ligne (elle ne compte pas dans `valid_days`) ;
4. pour chaque paire `slot:kwh` de `series` :
   - `observedSlots++` ;
   - vérifier que la date existe dans le calendrier ;
   - si oui, choisir le prix :
     - `ToU` → `price_pence` du signal `(date, slot)` ;
     - `Std` → **14.228** p/kWh (tarif plat), quel que soit le signal ;
   - si un prix existe : `costGbp += kwh * price / 100`, `pricedSlots++` ;
5. contrôles (compteurs, pas d'échec bloquant) :
   - `observedSlots == n_valid_slots` ;
   - `sum(series) ≈ total_kwh` (tolérance 0,001) ;
   - `max(series) == peak_kwh_hh`.

**Convention de slot.** `slot = heure × 2 + minute / 30`, heure locale
affichée. La jointure est `(date, slot)`. Aucun décalage les jours de
changement d'heure : le 27/10/2013, `series` peut contenir deux paires
de même slot (01:00–01:59 existe deux fois) ; MR2 les additionne, elles
ont le même prix.

Une ligne mal formée est **comptée** et ignorée : elle ne fabrique
jamais de valeurs.

## 5. Combiner

**Pas de Combiner en v1.** Le PDF ne l'impose pas et il ajoute un risque
d'arrondi inutile. On l'ajoutera seulement après validation de T05/T06.

Les opérations prévues restent associatives (somme + max) ; aucune
moyenne ni ratio ne sera calculé dans un Combiner.

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
La couverture mesure la disponibilité du **prix**, pas la complétude des
données : un jour à 47 créneaux tarifés a une couverture de `1.0` et un
`partial_data` via les créneaux manquants.

**Règle de coût.** Dès qu'un seul créneau est tarifé, le coût est écrit
(somme partielle) avec `price_coverage < 1` et `partial_tariff`. Aucun
seuil n'est appliqué en v1 : la couverture reste toujours visible, le
coût n'est jamais présenté comme exact.

Les sommes sont formatées à **6 décimales** (`%.6f`) en sortie ; les
comparaisons de test utilisent une tolérance de `1e-6`.

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

Convention figée : `slot = heure × 2 + minute / 30`, heure locale
affichée, jointure `(date, slot)`, aucun décalage.

- 31/03/2013 : 46 créneaux (01:00 et 01:30 n'existent pas) ;
  `n_missing_slots = 0`.
- 27/10/2013 : 50 créneaux ; `series` contient deux fois les slots
  01:00–01:59. MR2 additionne les deux paires (même prix).

La convention complète relève de MR1 et est documentée dans le contrat.

### Priorité et cumul

La priorité `partial_tariff` > `partial_data` masque un mois qui cumule
les deux problèmes. Les compteurs Hadoop conservent les deux
informations ; le schéma de sortie (10 champs) ne change pas.

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

## 10. Compteurs Hadoop (groupe `P08_MR2`)

| Compteur | Sens |
|---|---|
| `lines_read` | lignes lues dans l'entrée MR1 |
| `lines_ok` | lignes MR1 valides |
| `lines_malformed` | lignes ignorées (mauvais nombre de champs, parse error) |
| `empty_day_skipped` | lignes `n_valid_slots = 0` ignorées |
| `series_slot_mismatch` | nombre de paires de `series` ≠ `n_valid_slots` |
| `series_mismatch` | `|Σ series − total_kwh| > 0.001` |
| `peak_mismatch` | `max(series)` ≠ `peak_kwh_hh` |
| `dst_duplicate_slots` | slots répétés dans `series` (27/10/2013) |
| `priced_slots` | créneaux observés avec un prix |
| `unpriced_slots` | créneaux observés sans prix |
| `missing_slots_total` | `Σ n_missing_slots` |
| `tariff_lines_loaded` | lignes tarifaires chargées |
| `tariff_header_skipped` | en-tête ignoré (0 ou 1) |
| `flag_ok` | mois écrits avec `ok` |
| `flag_partial_data` | mois écrits avec `partial_data` |
| `flag_partial_tariff` | mois écrits avec `partial_tariff` |
| `flag_no_tariff` | mois écrits avec `no_tariff` |
| `flag_no_data` | mois écrits avec `no_data` |
| `months_written` | total des lignes de sortie |

## 11. Limites assumées

- Le calendrier officiel ne couvre que 2013 : 2012 et 2014 ont un coût
  NULL, même pour les foyers Std. Choix prudent aligné sur T06, plage
  configurable.
- Le coût est une **estimation d'exercice** (hors taxes et frais).
- Les jours de DST suivent la convention `slot = heure × 2 + minute / 30` :
  46 créneaux le 31/03/2013, 50 le 27/10/2013 (deux fois 01:00–01:59).
- Aucune réidentification : `household_id` reste le `LCLid`
  pseudonymisé du dataset.

## 12. Décisions figées v1.1 (2026-11-06)

| # | Décision |
|---|---|
| 1 | `tariffs_2013_price.csv` a un en-tête ; MR2 ignore la ligne qui commence par `date,`. |
| 2 | `price_coverage = créneaux tarifés / créneaux observés` (couverture du prix, pas des données). |
| 3 | Coût = somme des créneaux tarifés si `pricedSlots > 0` ; `partial_tariff` si couverture < 1 ; couverture toujours écrite. |
| 4 | Prix Std `14.228` p/kWh appliqué **seulement** aux dates du calendrier 2013 (plage configurable). |
| 5 | Slot = heure affichée ×2 + minute/30 ; jointure `(date, slot)`, aucun décalage. |
| 6 | MR2 ignore les lignes `n_valid_slots = 0` (compteur) ; elles ne comptent pas dans `valid_days`. |
| 7 | Pas de Combiner en v1 ; sommes arrondies à 6 décimales ; comparaisons à `1e-6`. |
| 8 | Prix Std = constante Java `14.228`, jamais lu depuis un CSV arrondi. |
| 9 | Priorité : `no_data` > `no_tariff` > `partial_tariff` > `partial_data` > `ok`, + compteurs. |
| 10 | `total_kwh` et `peak` = champs MR1 ; coût calculé depuis `series` ; écart > 0,001 → compteur. |
