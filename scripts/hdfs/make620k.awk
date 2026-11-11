BEGIN { FS = "\t"; OFS = "\t" }
# Duplique synthetic_155k.tsv en 4 blocs de foyers distincts.
# 5 000 foyers x 4 = 20 000 foyers x 31 jours = 620 000 lignes.
# Jeu SYNTHETIQUE : aucune mesure reelle.
{
  id = $1
  for (b = 1; b <= 4; b++) {
    $1 = "VOL" b "-" id
    print
  }
}
