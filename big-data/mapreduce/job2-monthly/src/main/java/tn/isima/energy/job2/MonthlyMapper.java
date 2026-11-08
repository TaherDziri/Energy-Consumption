package tn.isima.energy.job2;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.HashSet;
import java.util.Set;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

/**
 * Lit une ligne TSV de MR1 (10 champs, sans en-tete) et emet :
 *   cle    = (foyer, YYYY-MM, groupe tarifaire)
 *   valeur = DailyMetrics du jour
 *
 * Le calendrier tarifaire est charge une seule fois, dans setup().
 * Aucune conversion de fuseau ici : MR1 a deja ecrit des slots locaux.
 */
public class MonthlyMapper
        extends Mapper<LongWritable, Text, HouseholdMonthKey, DailyMetrics> {

    /** Cle de configuration : chemin HDFS du calendrier tarifaire. */
    public static final String CONF_CALENDAR = "p08.tariff.calendar.path";

    private static final String GROUP = "P08_MR2";
    private static final double SUM_TOLERANCE  = 0.001;
    private static final double PEAK_TOLERANCE = 1e-6;

    private TariffCalendar calendar;
    private final HouseholdMonthKey outKey = new HouseholdMonthKey();
    private final Diagnostics diag = new Diagnostics();

    @Override
    protected void setup(Context context) throws IOException, InterruptedException {
        Configuration conf = context.getConfiguration();
        String calendarPath = conf.get(CONF_CALENDAR);
        if (calendarPath == null || calendarPath.trim().isEmpty()) {
            throw new IOException("configuration manquante : " + CONF_CALENDAR);
        }

        Path path = new Path(calendarPath);
        // fichier localise par le DistributedCache : nom sans schema -> FS local
        FileSystem fs = path.toUri().getScheme() == null
                ? FileSystem.getLocal(conf)
                : path.getFileSystem(conf);
        try (BufferedReader in = new BufferedReader(
                new InputStreamReader(fs.open(path), StandardCharsets.UTF_8))) {
            calendar = TariffCalendar.load(in);
        }

        context.getCounter(GROUP, "tariff_lines_loaded").increment(calendar.size());
        context.getCounter(GROUP, "tariff_header_skipped").increment(calendar.headerLines());
    }

    @Override
    protected void map(LongWritable offset, Text value, Context context)
            throws IOException, InterruptedException {

        String line = value.toString().trim();
        if (line.isEmpty()) return;
        context.getCounter(GROUP, "lines_read").increment(1);

        // 1. exactement 10 champs separes par des tabulations
        String[] f = line.split("\t", -1);
        if (f.length != 10) {
            context.getCounter(GROUP, "lines_malformed").increment(1);
            return;
        }

        // 2. lecture des champs utiles (7 sur 10)
        String householdId = f[0].trim();
        String date        = f[1].trim();
        String tariffGroup = f[2].trim();

        double totalKwh;
        int nValidSlots;
        int nMissingSlots;
        double peakKwhHh;
        try {
            LocalDate.parse(date);
            totalKwh      = Double.parseDouble(f[3].trim());
            nValidSlots   = Integer.parseInt(f[4].trim());
            nMissingSlots = Integer.parseInt(f[5].trim());
            peakKwhHh     = Double.parseDouble(f[6].trim());
        } catch (NumberFormatException | DateTimeParseException e) {
            context.getCounter(GROUP, "lines_malformed").increment(1);
            return;
        }

        if (householdId.isEmpty() || tariffGroup.isEmpty()
                || totalKwh < 0.0 || peakKwhHh < 0.0
                || nValidSlots < 0 || nMissingSlots < 0) {
            context.getCounter(GROUP, "lines_malformed").increment(1);
            return;
        }

        // 3. decision 6 : un jour sans creneau ne cree pas de cle
        if (nValidSlots == 0) {
            context.getCounter(GROUP, "empty_day_skipped").increment(1);
            return;
        }

        // 4. construction des metriques
        diag.reset();
        DailyMetrics metrics = buildMetrics(date, tariffGroup, totalKwh, nValidSlots,
                nMissingSlots, peakKwhHh, f[9], calendar, diag);

        // une paire mal formee fait rejeter toute la ligne
        if (diag.seriesError) {
            context.getCounter(GROUP, "lines_malformed").increment(1);
            return;
        }

        // 5. compteurs (jamais bloquants)
        context.getCounter(GROUP, "lines_ok").increment(1);
        context.getCounter(GROUP, "priced_slots").increment(diag.pricedSlots);
        context.getCounter(GROUP, "unpriced_slots").increment(diag.unpricedSlots);
        context.getCounter(GROUP, "missing_slots_total").increment(nMissingSlots);
        context.getCounter(GROUP, "dst_duplicate_slots").increment(diag.dstDuplicates);
        if (diag.slotCountMismatch) {
            context.getCounter(GROUP, "series_slot_mismatch").increment(1);
        }
        if (diag.sumMismatch) {
            context.getCounter(GROUP, "series_mismatch").increment(1);
        }
        if (diag.peakMismatch) {
            context.getCounter(GROUP, "peak_mismatch").increment(1);
        }

        // 6. emission
        outKey.setHouseholdId(householdId);
        outKey.setYearMonth(date.substring(0, 7));   // 2013-03-01 -> 2013-03
        outKey.setTariffGroup(tariffGroup);
        context.write(outKey, metrics);
    }

    /**
     * Construit les metriques d'un jour depuis ses 10 champs MR1.
     * Retourne null si la serie est illisible (diag.seriesError = true).
     *
     * Regle de prix :
     *   - date hors calendrier -> aucun prix (ni Std, ni ToU) ;
     *   - foyer Std -> constante 14.228 p/kWh ;
     *   - foyer ToU -> price_pence du couple (date, slot).
     */
    static DailyMetrics buildMetrics(String date, String tariffGroup,
                                     double totalKwh, int nValidSlots, int nMissingSlots,
                                     double peakKwhHh, String series,
                                     TariffCalendar calendar, Diagnostics diag) {

        boolean covered = calendar.covers(date);
        boolean flatStd = "Std".equals(tariffGroup);
        Set<Integer> seenSlots = new HashSet<Integer>();

        double costGbp = 0.0;
        double sumKwh  = 0.0;
        double maxKwh  = 0.0;
        long priced    = 0;
        long unpriced  = 0;

        String[] pairs = series.split(";", -1);
        for (String raw : pairs) {
            String pair = raw.trim();
            if (pair.isEmpty()) continue;

            int colon = pair.indexOf(':');
            if (colon <= 0 || colon == pair.length() - 1) {
                diag.seriesError = true;
                return null;
            }

            int slot;
            double kwh;
            try {
                slot = Integer.parseInt(pair.substring(0, colon).trim());
                kwh  = Double.parseDouble(pair.substring(colon + 1).trim());
            } catch (NumberFormatException e) {
                diag.seriesError = true;
                return null;
            }

            // 0..49 : 50 est possible le 27/10/2013
            if (slot < 0 || slot > 49 || kwh < 0.0 || Double.isNaN(kwh)) {
                diag.seriesError = true;
                return null;
            }

            // Une liste de paires, jamais une Map : le 27/10 a deux fois le slot 2
            if (!seenSlots.add(slot)) diag.dstDuplicates++;
            diag.pairs++;
            sumKwh += kwh;
            if (kwh > maxKwh) maxKwh = kwh;

            // Prix du creneau
            double price = Double.NaN;
            if (covered) {
                price = flatStd
                        ? TariffCalendar.STD_PRICE_PENCE
                        : calendar.pricePence(date, slot);
            }

            if (Double.isNaN(price)) {
                unpriced++;                       // manquant ou non tarife
            } else {
                costGbp += kwh * price / 100.0;   // pence -> GBP
                priced++;
            }
        }

        if (diag.pairs == 0) {
            diag.seriesError = true;              // serie vide : ligne inutilisable
            return null;
        }

        DailyMetrics m = new DailyMetrics();
        m.setTotalKwh(totalKwh);                  // champ 4 de MR1, jamais recalcule
        m.setPeakKwhHh(peakKwhHh);                // champ 7 de MR1
        m.setCostGbp(costGbp);                    // 0.0 si aucun prix
        m.setObservedSlots(diag.pairs);           // nombre de paires observees
        m.setPricedSlots(priced);
        m.setMissingSlots(nMissingSlots);         // champ 6 de MR1
        m.setValidDays(1);                        // une ligne MR1 = un jour

        diag.pricedSlots   = priced;
        diag.unpricedSlots = unpriced;
        diag.sum           = sumKwh;
        diag.max           = maxKwh;
        diag.slotCountMismatch = (diag.pairs != nValidSlots);
        diag.sumMismatch       = Math.abs(sumKwh - totalKwh) > SUM_TOLERANCE;
        diag.peakMismatch      = Math.abs(maxKwh - peakKwhHh) > PEAK_TOLERANCE;

        return m;
    }

    /** Diagnostics d'une ligne, traduits en compteurs Hadoop par map(). */
    static final class Diagnostics {
        long pairs;
        long pricedSlots;
        long unpricedSlots;
        long dstDuplicates;
        double sum;
        double max;
        boolean seriesError;
        boolean slotCountMismatch;
        boolean sumMismatch;
        boolean peakMismatch;

        void reset() {
            pairs = 0;
            pricedSlots = 0;
            unpricedSlots = 0;
            dstDuplicates = 0;
            sum = 0.0;
            max = 0.0;
            seriesError = false;
            slotCountMismatch = false;
            sumMismatch = false;
            peakMismatch = false;
        }
    }
}