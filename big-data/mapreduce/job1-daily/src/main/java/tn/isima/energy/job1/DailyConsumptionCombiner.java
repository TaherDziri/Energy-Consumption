package tn.isima.energy.job1;

import java.io.IOException;
import java.util.Map;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;

/** Local pre-aggregation: same (household, day, timestamp) merged before the shuffle. */
public class DailyConsumptionCombiner extends Reducer<Text, Text, Text, Text> {

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
        for (Map.Entry<String, double[]> e : acc.entries().entrySet()) {
            outValue.set(e.getKey() + ";" + e.getValue()[0] + ";" + (long) e.getValue()[1]);
            context.write(key, outValue);
        }
    }
}