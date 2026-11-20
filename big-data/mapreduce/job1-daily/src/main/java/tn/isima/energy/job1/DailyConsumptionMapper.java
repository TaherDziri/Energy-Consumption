package tn.isima.energy.job1;

import java.io.IOException;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;

/**
 * Emits: key = "LCLid|localDate", value = "tariff;slot;timestamp;kwh".
 * The date and the slot are LOCAL (Europe/London); the timestamp stays raw UTC
 * so duplicate detection and chronological ordering stay exact.
 */
public class DailyConsumptionMapper extends Mapper<LongWritable, Text, Text, Text> {

    private final Text outKey = new Text();
    private final Text outValue = new Text();

    @Override
    protected void map(LongWritable offset, Text line, Context context)
            throws IOException, InterruptedException {

        LineParser.Result result = LineParser.parse(line.toString());

        switch (result.getStatus()) {
            case OK:
                Reading r = result.getReading();
                outKey.set(LineParser.groupKey(r.getHouseholdId(), r.getLocalDate()));
                outValue.set(r.getTariffGroup() + ";" + r.getLocalSlot() + ";"
                        + r.getTimestamp() + ";" + r.getKwh());
                context.write(outKey, outValue);
                context.getCounter("P08", "readings_valid").increment(1);
                if (!LineParser.isOnGrid(r.getTimestamp())) {
                    context.getCounter("P08", "readings_off_grid").increment(1);
                }
                break;
            case HEADER:
                context.getCounter("P08", "header_skipped").increment(1);
                break;
            case MISSING:
                context.getCounter("P08", "missing_null").increment(1);
                break;
            case NEGATIVE:
                context.getCounter("P08", "negative").increment(1);
                break;
            case UNKNOWN_TARIFF:
                context.getCounter("P08", "unknown_tariff").increment(1);
                break;
            default:
                context.getCounter("P08", "malformed").increment(1);
                break;
        }
    }
}
