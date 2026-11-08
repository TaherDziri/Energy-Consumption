package tn.isima.energy.job2;

import java.io.IOException;
import java.util.Locale;

import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

/**
 * Fusionne tous les jours d'un (foyer, mois, tarif) puis ecrit UNE ligne CSV :
 * household_id,month,tariff_group,monthly_kwh,estimated_cost_gbp,
 * price_coverage,max_half_hour_kwh,valid_days,quality_flag,run_id
 *
 * Le cout est NULL (champ vide) si aucun creneau n'a de prix.
 * Les arrondis %.6f sont faits ici, et seulement ici.
 */
public class MonthlyReducer
        extends Reducer<HouseholdMonthKey, DailyMetrics, NullWritable, Text> {

    private static final String GROUP = "P08_MR2";

    /** Cle de configuration du run_id (voir docs/03 §7). */
    public static final String CONF_RUN_ID = "p08.run_id";
    private static final String DEFAULT_RUN_ID = "mr2-local";

    private final Text outValue = new Text();
    private String runId;

    @Override
    protected void setup(Context context) {
        String v = context.getConfiguration().get(CONF_RUN_ID);
        runId = (v == null || v.trim().isEmpty()) ? DEFAULT_RUN_ID : v.trim();
    }

    @Override
    protected void reduce(HouseholdMonthKey key, Iterable<DailyMetrics> values,
                          Context context) throws IOException, InterruptedException {

        // Seau neuf a chaque cle : aucune fuite d'un mois sur le suivant.
        DailyMetrics month = new DailyMetrics();
        for (DailyMetrics day : values) {
            month.merge(day);          // SOMME + MAX, jamais de moyenne
        }

        String flag = qualityFlag(month);

        // Un compteur par flag : flag_ok, flag_partial_data, ...
        context.getCounter(GROUP, "flag_" + flag).increment(1);
        context.getCounter(GROUP, "months_written").increment(1);

        outValue.set(outputLine(key.getHouseholdId(), key.getYearMonth(),
                key.getTariffGroup(), month, runId));
        context.write(NullWritable.get(), outValue);
    }

    /**
     * Priorite (le premier vrai gagne) :
     * no_data > no_tariff > partial_tariff > partial_data > ok
     */
    static String qualityFlag(DailyMetrics m) {
        if (m.getObservedSlots() == 0 || m.getValidDays() == 0) return "no_data";
        if (m.getPricedSlots() == 0) return "no_tariff";
        if (m.getPricedSlots() < m.getObservedSlots()) return "partial_tariff";
        if (m.getMissingSlots() > 0) return "partial_data";
        return "ok";
    }

    /** Construit la ligne de sortie complete (sans en-tete). */
    static String outputLine(String householdId, String yearMonth, String tariffGroup,
                             DailyMetrics m, String runId) {

        // Couverture du prix, pas de la donnee : prix trouves / creneaux observes.
        double coverage = m.getObservedSlots() == 0
                ? 0.0
                : (double) m.getPricedSlots() / (double) m.getObservedSlots();

        // NULL = champ vide. On n'ecrit jamais 0.0 pour un cout inconnu.
        String cost = m.getPricedSlots() == 0 ? "" : format6(m.getCostGbp());

        return new StringBuilder()
                .append(householdId).append(',')
                .append(yearMonth).append(',')
                .append(tariffGroup).append(',')
                .append(format6(m.getTotalKwh())).append(',')
                .append(cost).append(',')
                .append(format6(coverage)).append(',')
                .append(format6(m.getPeakKwhHh())).append(',')
                .append(m.getValidDays()).append(',')
                .append(qualityFlag(m)).append(',')
                .append(runId)
                .toString();
    }

    /** Arrondi d'affichage uniquement. Locale.ROOT impose le point decimal. */
    private static String format6(double v) {
        return String.format(Locale.ROOT, "%.6f", v);
    }
}