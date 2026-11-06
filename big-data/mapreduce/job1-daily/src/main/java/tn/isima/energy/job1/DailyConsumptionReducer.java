package tn.isima.energy.job1;

import java.io.IOException;
import java.util.Locale;
import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

/**
 * Writes exactly one CSV line per (household, day):
 *    household_id,date,total_kwh,reading_count
 * No header, no tab: the output separator is set to "" in the Driver.
 */
public class DailyConsumptionReducer extends Reducer<Text, Text, NullWritable, Text> {

    private final Text outValue = new Text();

    @Override
    protected void reduce(Text key, Iterable<Text> values, Context context)
            throws IOException, InterruptedException {

        TimestampAccumulator acc = new TimestampAccumulator();
        for (Text v : values) {
            try {
                acc.add(v.toString());
            } catch (IllegalArgumentException e) {
                context.getCounter("P08", "value_parse_error").increment(1);
            }
        }
        if (acc.isEmpty()) {
            context.getCounter("P08", "days_dropped_empty").increment(1);
            return;
        }

        long duplicates = acc.occurrences() - acc.distinctReadings();
        if (duplicates > 0) context.getCounter("P08", "duplicate_rows_averaged").increment(duplicates);

        int readings = acc.distinctReadings();
        if (readings > 48) context.getCounter("P08", "days_more_than_48").increment(1);

        String[] k = key.toString().split("\\|");
        outValue.set(k[0] + "," + k[1] + ","
                + String.format(Locale.ROOT, "%.3f", acc.totalKwh()) + ","
                + readings);
        context.write(NullWritable.get(), outValue);
    }
}