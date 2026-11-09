package tn.isima.energy.job2;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.Reader;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.HashMap;
import java.util.Map;

/**
 * Calendrier tarifaire 2013 charge en memoire.
 * Jointure : (date, slot) -> prix en pence/kWh.
 * Fichier attendu avec un en-tete exact : date,slot,tariff,price_pence
 *
 * Hypothese de travail : les deux tables du dataset Low Carbon London
 * sont indexees en GMT (guide officiel UK Data Service 7857, a
 * verifier). Le calendrier contient donc 48 lignes par jour, y compris
 * le 31/03 et le 27/10. Un jour GMT fait toujours 24 h, donc l'attendu
 * est toujours 48.
 */
public final class TariffCalendar {

    /** Prix standard officiel en pence/kWh : constante Java, jamais relu d'un CSV arrondi. */
    public static final double STD_PRICE_PENCE = 14.228;

    private static final String HEADER = "date,slot,tariff,price_pence";
    /** Un jour GMT fait 24 h, soit 48 creneaux de 30 min. */
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

            // slot 0..47 : en GMT il y a exactement 48 creneaux par jour
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

    // ---------- attendu d'un jour GMT ----------

    /**
     * Nombre de creneaux attendus pour ce jour : toujours 48.
     * Consommation et tarifs sont tous deux en GMT, donc aucun jour
     * ne fait 23 h ni 25 h. La methode existe pour que le contrat
     * MR1 -> MR2 n'ait qu'une seule definition de l'attendu.
     */
    public static int expectedSlots(String date) {
        LocalDate.parse(date);          // valide le format YYYY-MM-DD
        return SLOTS_PER_DAY;
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