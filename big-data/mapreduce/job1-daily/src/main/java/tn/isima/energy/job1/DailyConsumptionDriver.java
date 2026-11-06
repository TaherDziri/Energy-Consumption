package tn.isima.energy.job1;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;
import org.apache.hadoop.util.GenericOptionsParser;

/**
 * Job 1 entry point.
 * Usage: hadoop jar job1-daily-consumption.jar <input> <output>
 */
public final class DailyConsumptionDriver {

    private DailyConsumptionDriver() { }

    public static void main(String[] args) throws Exception {
        Configuration conf = new Configuration();
        String[] rest = new GenericOptionsParser(conf, args).getRemainingArgs();

        if (rest.length != 2) {
            System.err.println("Usage: DailyConsumptionDriver <input path> <output path>");
            System.exit(2);
        }

        // NullWritable key + separator "" => the output is a pure CSV line.
        conf.set("mapreduce.output.textoutputformat.separator", "");

        Job job = Job.getInstance(conf, "P08 job1 - daily consumption per household");
        job.setJarByClass(DailyConsumptionDriver.class);

        job.setMapperClass(DailyConsumptionMapper.class);
        job.setCombinerClass(DailyConsumptionCombiner.class);
        job.setReducerClass(DailyConsumptionReducer.class);

        job.setMapOutputKeyClass(Text.class);
        job.setMapOutputValueClass(Text.class);
        job.setOutputKeyClass(NullWritable.class);
        job.setOutputValueClass(Text.class);

        FileInputFormat.addInputPath(job, new Path(rest[0]));
        FileOutputFormat.setOutputPath(job, new Path(rest[1]));

        long start = System.currentTimeMillis();
        boolean ok = job.waitForCompletion(true);
        long elapsed = System.currentTimeMillis() - start;

        System.out.println("===== P08 JOB 1 COUNTERS =====");
        String[] names = {
            "readings_valid", "missing_null", "malformed", "negative",
            "header_skipped", "readings_off_grid", "value_parse_error",
            "duplicate_rows_averaged", "days_more_than_48", "days_dropped_empty"
        };
        for (String n : names) {
            System.out.println(n + " = " + job.getCounters().findCounter("P08", n).getValue());
        }
        System.out.println("elapsed_ms = " + elapsed);
        System.out.println(ok ? "JOB1 STATUS = SUCCESS" : "JOB1 STATUS = FAILED");

        System.exit(ok ? 0 : 1);
    }
}