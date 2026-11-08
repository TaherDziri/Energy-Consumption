package tn.isima.energy.job2;

import java.net.URI;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;
import org.apache.hadoop.util.GenericOptionsParser;

/**
 * Point d'entree du job 2.
 * Usage :
 *   MonthlyAggregationDriver <sortie MR1> <sortie MR2> <calendrier tarifaire>
 *
 * Exemple :
 *   hadoop jar job2-monthly-aggregation.jar \
 *     tn.isima.energy.job2.MonthlyAggregationDriver \
 *     /p08/gold/mr1_daily /p08/gold/mr2_monthly \
 *     /p08/raw/tariffs/tariffs_2013_price.csv
 */
public final class MonthlyAggregationDriver {

    public static final String CONF_RUN_ID = MonthlyReducer.CONF_RUN_ID;

    /** Nom du lien cree par le DistributedCache dans chaque conteneur. */
    private static final String CACHE_ALIAS = "tariffs.csv";

    private MonthlyAggregationDriver() { }

    public static void main(String[] args) throws Exception {
        Configuration conf = new Configuration();
        String[] rest = normalizeArgs(new GenericOptionsParser(conf, args).getRemainingArgs());

        if (rest.length != 3) {
            System.err.println("Usage: MonthlyAggregationDriver <mr1 output> <output> <tariffs csv>");
            System.exit(2);
        }

        // NullWritable + separateur "" => la ligne CSV est ecrite telle quelle.
        conf.set("mapreduce.output.textoutputformat.separator", "");

        // run_id identique pour toutes les lignes du run (tracabilite NF05).
        String runId = resolveRunId(conf);
        conf.set(CONF_RUN_ID, runId);

        Job job = Job.getInstance(conf, "P08 job2 - monthly aggregation");

        // Calendrier tarifaire : URI qualifiee + alias local "tariffs.csv".
        URI calendarUri = FileSystem.get(conf).makeQualified(new Path(rest[2])).toUri();
        job.addCacheFile(new URI(calendarUri.toString() + "#" + CACHE_ALIAS));
        job.getConfiguration().set(MonthlyMapper.CONF_CALENDAR, CACHE_ALIAS);

        job.setJarByClass(MonthlyAggregationDriver.class);

        job.setMapperClass(MonthlyMapper.class);
        job.setReducerClass(MonthlyReducer.class);
        // Decision 7 : aucun Combiner en v1.

        job.setMapOutputKeyClass(HouseholdMonthKey.class);
        job.setMapOutputValueClass(DailyMetrics.class);
        job.setOutputKeyClass(NullWritable.class);
        job.setOutputValueClass(Text.class);

        FileInputFormat.addInputPath(job, new Path(rest[0]));
        FileOutputFormat.setOutputPath(job, new Path(rest[1]));

        long start = System.currentTimeMillis();
        boolean ok = job.waitForCompletion(true);
        long elapsed = System.currentTimeMillis() - start;

        System.out.println("===== P08 JOB 2 COUNTERS =====");
        String[] names = {
            "lines_read", "lines_ok", "lines_malformed", "empty_day_skipped",
            "series_slot_mismatch", "series_mismatch", "peak_mismatch",
            "dst_duplicate_slots", "priced_slots", "unpriced_slots",
            "missing_slots_total", "tariff_lines_loaded", "tariff_header_skipped",
            "flag_ok", "flag_partial_data", "flag_partial_tariff",
            "flag_no_tariff", "flag_no_data", "months_written"
        };
        for (String name : names) {
            System.out.println(name + " = "
                    + job.getCounters().findCounter("P08_MR2", name).getValue());
        }
        System.out.println("run_id = " + runId);
        System.out.println("elapsed_ms = " + elapsed);
        System.out.println(ok ? "JOB2 STATUS = SUCCESS" : "JOB2 STATUS = FAILED");

        System.exit(ok ? 0 : 1);
    }

    /**
     * Hadoop RunJar ne consomme le nom de classe que si le manifeste n'a PAS
     * de Main-Class. Notre jar en a un : "hadoop jar jar Classe a b c" passe
     * donc 4 arguments au main. On retire le nom de classe quand il est la.
     *
     * Resultat : les deux syntaxes fonctionnent.
     *   hadoop jar job2.jar a b c
     *   hadoop jar job2.jar tn.isima.energy.job2.MonthlyAggregationDriver a b c
     */
    static String[] normalizeArgs(String[] args) {
        if (args.length == 4 && args[0] != null) {
            String first = args[0].trim();
            if (MonthlyAggregationDriver.class.getName().equals(first)
                    || MonthlyAggregationDriver.class.getSimpleName().equals(first)) {
                return new String[] { args[1], args[2], args[3] };
            }
        }
        return args;
    }
    
    /** -Dp08.run_id=... si fourni, sinon mr2-yyyyMMddTHHmmssZ en UTC. */
    static String resolveRunId(Configuration conf) {
        String provided = conf.get(CONF_RUN_ID);
        if (provided != null && !provided.trim().isEmpty()) {
            return provided.trim();
        }

        SimpleDateFormat format =
                new SimpleDateFormat("yyyyMMdd'T'HHmmss'Z'", Locale.ROOT);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return "mr2-" + format.format(new Date());
    }
}