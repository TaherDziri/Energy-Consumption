package tn.isima.energy.job2;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.Reader;
import java.time.Duration;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeParseException;
import java.util.HashMap;
import java.util.Map;

/**
 * Calendrier tarifaire 2013 charge en memoire.
 * Jointure : (date, slot) -> prix en pence/kWh.
 * Fichier attendu avec un en-tete exact : date,slot,tariff,price_pence
 *
 * Depuis le contrat v1.1 (decision Taher, docs/02 §8), MR1 ecrit des
 * jours et des creneaux LOCAUX (Europe/London). Le calendrier est une
 * grille locale naive 00:00-23:30 : les slots restent dans 0..47, mais
 * un jour local comporte 46, 48 ou 50 demi-heures physiques. La
 * convention debut/fin de periode reste une hypothese non verifiee.
 */
public final class TariffCalendar {

    /** Prix standard officiel en pence/kWh : constante Java, jamais relu d'un CSV arrondi. */
    public static final double STD_PRICE_PENCE = 14.228;

    private static final String HEADER = "date,slot,tariff,price_pence";
    private static final ZoneId ZONE = ZoneId.of("Europe/London");
    /** Indice de slot maximal : 0..47, meme le jour de 50 demi-heures. */
    public static final int SLOTS_PER_DAY = 48;

    // Cle "date|slot" -> prix en pence/kWh
    private final Map<String, Double> priceByKey = new HashMap<>();

    private String minDate = null;
    private String maxDate = null;
    private int malformedLines = 0;
    private int duplicateRows = 0;
    private int headerLines = 0;

    private TariffCalendar() {
    }

    // ---------- chargement ----------

    /**
     * Lit le calendrier depuis un Reader (fichier, StringReader dans les tests...).
     * Une ligne mal formee est comptee et ignoree : elle ne fabrique jamais de prix.
     */
    public static TariffCalendar load(Reader reader) throws IOException {
        TariffCalendar cal = new TariffCalendar();
        BufferedReader in = new BufferedReader(reader);
        String line;

        while ((line = in.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty()) continue;

            // En-tete exact uniquement (decision 1 du contrat)
            if (HEADER.equals(line)) {
                cal.headerLines++;
                continue;
            }

            String[] f = line.split(",", -1);
            if (f.length != 4) {
                cal.malformedLines++;
                continue;
            }

            String date = f[0].trim();
            int slot;
            double price;

            try {
                LocalDate.parse(date);           // valide le format YYYY-MM-DD
                slot = Integer.parseInt(f[1].trim());
                price = Double.parseDouble(f[3].trim());
            } catch (NumberFormatException | DateTimeParseException e) {
                cal.malformedLines++;
                continue;
            }

            // slot 0..47 : grille locale naive, meme le 27/10 (50 demi-heures)
            if (slot < 0 || slot >= SLOTS_PER_DAY || price < 0.0 || Double.isNaN(price)) {
                cal.malformedLines++;
                continue;
            }

            String key = key(date, slot);
            if (cal.priceByKey.containsKey(key)) {
                cal.duplicateRows++;             // on garde la premiere valeur : deterministe
                continue;
            }
            cal.priceByKey.put(key, price);

            if (cal.minDate == null || date.compareTo(cal.minDate) < 0) cal.minDate = date;
            if (cal.maxDate == null || date.compareTo(cal.maxDate) > 0) cal.maxDate = date;
        }
        return cal;
    }

    // ---------- jointure (date, slot) ----------

    /** true si un prix existe pour ce couple. */
    public boolean hasPrice(String date, int slot) {
        return priceByKey.containsKey(key(date, slot));
    }

    /** Prix en pence/kWh, ou NaN si le creneau n'est pas tarife. */
    public double pricePence(String date, int slot) {
        Double p = priceByKey.get(key(date, slot));
        return p == null ? Double.NaN : p;
    }

    /** Decision 4 : le prix Std ne s'applique que dans la plage du calendrier. */
    public boolean covers(String date) {
        return minDate != null
                && minDate.compareTo(date) <= 0
                && date.compareTo(maxDate) <= 0;
    }

    // ---------- attendu d'un jour LOCAL ----------

    /**
     * Nombre de demi-heures physiques dans le jour local : 46 au printemps,
     * 50 en automne, 48 sinon. Calcule depuis les regles de Europe/London,
     * jamais code en dur. Le contrat v1.1 impose cette meme definition a
     * MR1 (n_missing = attendu - n_valid) et a MR2 (controle de coherence).
     * Sur le jour de 50 demi-heures les slots 2 et 3 apparaissent deux fois
     * dans la serie MR1 : deux paires distinctes, un seul prix par slot.
     */
    public static int expectedSlots(String date) {
        LocalDate day = LocalDate.parse(date);   // valide le format YYYY-MM-DD
        ZonedDateTime start = day.atStartOfDay(ZONE);
        ZonedDateTime next = day.plusDays(1).atStartOfDay(ZONE);
        return (int) (Duration.between(start, next).toMinutes() / 30);
    }

    // ---------- diagnostic ----------

    public int size()            { return priceByKey.size(); }
    public String minDate()      { return minDate; }
    public String maxDate()      { return maxDate; }
    public int malformedLines()  { return malformedLines; }
    public int duplicateRows()   { return duplicateRows; }
    public int headerLines()     { return headerLines; }
    public boolean isEmpty()     { return priceByKey.isEmpty(); }

    private static String key(String date, int slot) {
        return date + "|" + slot;
    }
}