package tn.isima.energy.job1;

import java.io.IOException;
import java.time.LocalDate;
import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

/**
 * Writes exactly one TSV line per (household, local day), contract v1.1:
 *    household_id, date, tariff_group, total_kwh, n_valid_slots,
 *    n_missing_slots, peak_kwh_hh, peak_slot, avg_valid_kwh_hh, series
 * No header, tab separated (separator is set in the Driver).
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
        if (acc.tariffConflict()) context.getCounter("P08", "tariff_conflict").increment(1);

        String[] k = key.toString().split("\\|");
        LocalDate date = LocalDate.parse(k[1]);

        int expected = DailyRecord.expectedSlots(date);
        if (expected != 48) context.getCounter("P08", "dst_days").increment(1);
        if (acc.distinctReadings() > expected) {
            context.getCounter("P08", "days_more_than_expected").increment(1);
        }

        outValue.set(DailyRecord.format(k[0], date, acc));
        context.write(NullWritable.get(), outValue);
    }
}
