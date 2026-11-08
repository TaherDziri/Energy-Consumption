# Contrat MR1 → MR2

## 1. Pourquoi un contrat

MR1 et MR2 sont deux jobs séparés qui communiquent uniquement par des
fichiers dans HDFS. Sans contrat, un créneau manquant écrit `0` devient
un faux total, donc un faux coût, **sans aucune erreur visible**. Le
contrat fige l'ordre des colonnes, les types, les unités et surtout la
représentation du manquant.

## 2. Format

TSV, une ligne par `(household_id, date)`, **sans en-tête**, UTF-8,
décimales avec `.` (jamais de virgule), pas de séparateur de milliers.

| # | Champ | Type | Règle |
|---|---|---|---|
| 1 | `household_id` | texte | identifiant pseudonymisé (`MAC000002`) |
| 2 | `date` | texte | `YYYY-MM-DD`, date locale |
| 3 | `tariff_group` | texte | `Std` ou `ToU` |
| 4 | `total_kwh` | décimal | somme des créneaux **observés** |
| 5 | `n_valid_slots` | entier | nombre de créneaux observés |
| 6 | `n_missing_slots` | entier | `attendu(date) − n_valid_slots` ; attendu = **48** (jour GMT de 24 h, tous les jours de l'année) |
| 7 | `peak_kwh_hh` | décimal | max d'un créneau, en **kWh/30 min** |
| 8 | `peak_slot` | entier | indice du pic (0–47) |
| 9 | `avg_valid_kwh_hh` | décimal | `total_kwh / n_valid_slots` |
| 10 | `series` | texte | `slot:kwh;slot:kwh;...` — observés uniquement |

## 3. Règles du contrat

- Un créneau absent **n'apparaît pas** dans `series`. On n'écrit jamais
  `12:0` pour un manquant.
- Un vrai zéro mesuré s'écrit `12:0.0`.
- `slot = heure × 2 + minute / 30` (**heure GMT**). C'est la clé de
  jointure `(date, slot)` avec le calendrier tarifaire : les deux tables
  sont en GMT, aucun décalage n'est appliqué.
- `avg_valid_kwh_hh = total_kwh / n_valid_slots`.
- **Fuseau : tout en GMT (vérifié les 2026-11-06 et 2026-11-09).**
  Le guide officiel du dataset (UK Data Service, `7857_userguide.pdf`)
  indique que les deux tables — consommation **et** `tariff_d.csv` —
  sont horodatées *"in the GMT time-zone"*.
- Preuves mesurées sur `/p08/raw/meters/sample_5households.csv` :
  - `grep -c '2013-03-31 01:00:00'` → **5** (les 5 foyers) : `01:00`
    existe, or il n'existe pas en heure locale → GMT ;
  - 31/03/2013 : **48** timestamps uniques, journée de 24 h complète ;
  - le calendrier tarifaire contient **48** lignes le 31/03 **et** le
    27/10 : il est indexé en GMT (un calendrier local aurait 46 et 50).
- **Conséquences :**
  - MR1 **ne convertit rien** : `date` et `slot` sont calculés en GMT,
    directement depuis les `DateTime` ;
  - un jour GMT fait toujours 24 h → **48 créneaux**, donc
    `n_missing_slots = 48 − n_valid_slots` ;
  - `slot` est borné à `0..47` : un slot `48` ou `49` est une donnée
    invalide, rejetée et comptée ;
  - aucun créneau dupliqué n'est attendu ; s'il en apparaît un, il est
    compté (`duplicate_slots`) et conservé dans `series` ;
  - le doublon GMT `00:00` du 27/10 (`0.181` deux fois) reste une lecture
    dupliquée du dataset, moyennée par MR1.
- MR2 ne fait **aucune** conversion de fuseau non plus : il joint deux
  séries déjà GMT.
- Si `n_valid_slots = 0` : `total_kwh = 0.0`, `peak_kwh_hh` et
  `peak_slot` vides, `series` vide. MR2 **ignore** cette ligne,
  incrémente un compteur, et ne l'ajoute pas à `valid_days`.
- MR2 ne doit jamais dépendre de l'ordre des lignes : le `shuffle`
  regroupe par clé.

## 4. Jeu de test

Foyer `MAC000002`, groupe `Std`, dates ordinaires (hors 31/03 et 27/10).

| Ligne | Date | Contenu | Ce qu'elle teste |
|---|---|---|---|
| A | `2013-03-01` | 47 créneaux, slot 12 manquant, pic 2.5 au slot 18 | manquant ≠ 0, pic |
| B | `2013-03-02` | 48 créneaux, base 0.4, pic 2.0 au slot 19 | somme multi-jours |
| C | `2012-03-01` | 48 créneaux, base 0.5, pic 2.0 au slot 20 | hors tarif → NULL |

## 5. Calculs à la main

**Ligne A — 2013-03-01**

- 46 créneaux à `0.5` + 1 pic à `2.5`
- `total = 46 × 0.5 + 2.5 = 23.0 + 2.5 = 25.5 kWh`
- `n_valid = 47`, `n_missing = 1`, `peak = 2.5` (slot 18)
- `avg = 25.5 / 47 = 0.542553…`

**Ligne B — 2013-03-02**

- 47 créneaux à `0.4` + 1 pic à `2.0`
- `total = 47 × 0.4 + 2.0 = 18.8 + 2.0 = 20.8 kWh`
- `n_valid = 48`, `n_missing = 0`, `peak = 2.0` (slot 19)
- `avg = 20.8 / 48 = 0.433333…`

**Ligne C — 2012-03-01**

- 47 créneaux à `0.5` + 1 pic à `2.0`
- `total = 47 × 0.5 + 2.0 = 23.5 + 2.0 = 25.5 kWh`
- `n_valid = 48`, `n_missing = 0`, `peak = 2.0` (slot 20)
- `avg = 25.5 / 48 = 0.53125`

### Résultats MR2 attendus

| Mois | monthly_kwh | max_half_hour_kwh | valid_days | estimated_cost_gbp | price_coverage |
|---|---|---|---|---|---|
| `2013-03` | `25.5 + 20.8 = 46.3` | `max(2.5, 2.0) = 2.5` | `2` | `46.3 × 14.228 / 100 = 6.587564` (≈ £6.59) | `1.0` |
| `2012-03` | `25.5` | `2.0` | `1` | **`NULL`** | `0.0` |

**Règle tarifaire :** le prix n'est appliqué que si la date existe dans
le calendrier tarifaire (2013). Hors 2013 → coût `NULL`, couverture
`0.0`. On ne projette jamais 2013 sur une autre année.

## 6. Commandes

### 6.1 Créer le dossier de test

```bat
docker exec p08-namenode hdfs dfs -mkdir -p /p08/test/mr1_daily
```

### 6.2 Écrire les 3 lignes directement dans HDFS

Aucun fichier local n'est créé : `printf` est exécuté dans le conteneur
et sa sortie est envoyée à `hdfs dfs -put -` via un pipe.

```bat
docker exec p08-namenode bash -c "printf 'MAC000002\t2013-03-01\tStd\t25.5\t47\t1\t2.5\t18\t0.542553\t0:0.5;1:0.5;2:0.5;3:0.5;4:0.5;5:0.5;6:0.5;7:0.5;8:0.5;9:0.5;10:0.5;11:0.5;13:0.5;14:0.5;15:0.5;16:0.5;17:0.5;18:2.5;19:0.5;20:0.5;21:0.5;22:0.5;23:0.5;24:0.5;25:0.5;26:0.5;27:0.5;28:0.5;29:0.5;30:0.5;31:0.5;32:0.5;33:0.5;34:0.5;35:0.5;36:0.5;37:0.5;38:0.5;39:0.5;40:0.5;41:0.5;42:0.5;43:0.5;44:0.5;45:0.5;46:0.5;47:0.5\nMAC000002\t2013-03-02\tStd\t20.8\t48\t0\t2.0\t19\t0.433333\t0:0.4;1:0.4;2:0.4;3:0.4;4:0.4;5:0.4;6:0.4;7:0.4;8:0.4;9:0.4;10:0.4;11:0.4;12:0.4;13:0.4;14:0.4;15:0.4;16:0.4;17:0.4;18:0.4;19:2.0;20:0.4;21:0.4;22:0.4;23:0.4;24:0.4;25:0.4;26:0.4;27:0.4;28:0.4;29:0.4;30:0.4;31:0.4;32:0.4;33:0.4;34:0.4;35:0.4;36:0.4;37:0.4;38:0.4;39:0.4;40:0.4;41:0.4;42:0.4;43:0.4;44:0.4;45:0.4;46:0.4;47:0.4\nMAC000002\t2012-03-01\tStd\t25.5\t48\t0\t2.0\t20\t0.53125\t0:0.5;1:0.5;2:0.5;3:0.5;4:0.5;5:0.5;6:0.5;7:0.5;8:0.5;9:0.5;10:0.5;11:0.5;12:0.5;13:0.5;14:0.5;15:0.5;16:0.5;17:0.5;18:0.5;19:0.5;20:2.0;21:0.5;22:0.5;23:0.5;24:0.5;25:0.5;26:0.5;27:0.5;28:0.5;29:0.5;30:0.5;31:0.5;32:0.5;33:0.5;34:0.5;35:0.5;36:0.5;37:0.5;38:0.5;39:0.5;40:0.5;41:0.5;42:0.5;43:0.5;44:0.5;45:0.5;46:0.5;47:0.5\n' | hdfs dfs -put -f - /p08/test/mr1_daily/mr1_test.tsv"
```

### 6.3 Vérifier

```bat
docker exec p08-namenode hdfs dfs -ls -h /p08/test/mr1_daily
docker exec p08-namenode bash -c "hdfs dfs -cat /p08/test/mr1_daily/mr1_test.tsv | cat -A"
docker exec p08-namenode bash -c "hdfs dfs -cat /p08/test/mr1_daily/mr1_test.tsv | cut -f1-9"
```

## 7. Résultat attendu

```
MAC000002  2013-03-01  Std  25.5  47  1  2.5  18  0.542553
MAC000002  2013-03-02  Std  20.8  48  0  2.0  19  0.433333
MAC000002  2012-03-01  Std  25.5  48  0  2.0  20  0.53125
```

Vérifications ciblées :

- 3 lignes, 9 tabulations (`^I`) par ligne dans `cat -A` ;
- ligne A : la série **saute `12:`** et contient `18:2.5` ;
- ligne B : contient `19:2.0` ;
- ligne C : contient `20:2.0`.

## 8. Interface avec MR2

- Clé Mapper : `(household_id, year_month, tariff_group)`.
- MR2 lit **uniquement** `/p08/test/mr1_daily` en test, puis
  `/p08/gold/mr1_daily` en production.
- MR2 ne recalcule jamais les totaux journaliers : il fait confiance aux
  champs de MR1 et se concentre sur le mois, le pic, la couverture et le
  coût.

## 9. Décisions figées v1.3 (2026-11-06, révisé le 2026-11-09)

| # | Décision |
|---|---|
| 1 | `tariffs_2013_price.csv` a un en-tête ; MR2 ignore **exactement** la ligne `date,slot,tariff,price_pence` (pas toute ligne commençant par `date`). |
| 2 | `price_coverage = créneaux tarifés / créneaux observés` (couverture du prix, pas des données). |
| 3 | Coût = somme des créneaux tarifés si `pricedSlots > 0` ; `partial_tariff` si couverture < 1 ; couverture toujours écrite. |
| 4 | Prix Std `14.228` p/kWh appliqué **seulement** aux dates du calendrier 2013. Une seule source de vérité : l'intersection avec la plage min/max du calendrier, pas une seconde plage codée en dur. |
| 5 | `DateTime` bruts **et** calendrier tarifaire en GMT. MR1 écrit `slot = heure GMT ×2 + minute/30` sans conversion ; MR2 joint `(date, slot)` sur la même échelle. Chaque jour fait 48 créneaux, y compris le 31/03 et le 27/10. |
| 6 | MR2 ignore les lignes `n_valid_slots = 0` (compteur) ; elles ne comptent pas dans `valid_days`. `n_missing_slots = attendu(date) − n_valid_slots`, avec **attendu = 48**. |
| 7 | Pas de Combiner en v1 ; sommes arrondies à 6 décimales ; comparaisons à `1e-6`. |
| 8 | Prix Std = constante Java `14.228`, jamais lu depuis un CSV arrondi. |
| 9 | Priorité : `no_data` > `no_tariff` > `partial_tariff` > `partial_data` > `ok`, + compteurs. `no_data` reste défensif : avec la décision 6, il est presque inatteignable. |
| 10 | `total_kwh` et `peak` = champs MR1 ; coût calculé depuis `series` ; écart > 0,001 → compteur. |

## 10. Vérification du fuseau horaire (2026-11-06)

Foyer `MAC000002`, fichier `/p08/raw/meters/sample_5households.csv` :

| Contrôle | Résultat observé | Conclusion |
|---|---|---|
| 31/03/2013, `01:00:00` | `grep -c` → **5** lignes (les 5 foyers) | **GMT**, pas heure locale |
| 31/03/2013, journée | 48 timestamps uniques | journée de 24 h complète |
| 27/10/2013, `00:00:00` | 2 lignes, valeur `0.181` identique | **GMT** + une lecture dupliquée |
| En-tête tarifs | `date,slot,tariff,price_pence` | 1 en-tête |
| Calendrier 31/03 / 27/10 | **48 / 48** lignes | calendrier indexé en GMT (46/50 si local) |

Source officielle : guide du dataset Low Carbon London (UK Data Service,
doc `7857`), qui décrit consommation et tarifs comme horodatés
*"in the GMT time-zone"*.

→ Aucune conversion de fuseau, ni dans MR1 ni dans MR2. L'attendu vaut
**48** partout et le `slot` reste dans `0..47`.

Voir §3 et §9 décision 5.
