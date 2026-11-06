package tn.isima.energy.job1;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/**
 * Accumulates every half-hourly value of ONE (household, day).
 * A timestamp seen several times (duplicate rows) is AVERAGED, not summed twice.
 * Accepts two value formats:
 *    "timestamp;kwh"         one reading, from the Mapper
 *    "timestamp;sum;count"   already aggregated, from the Combiner
 * Internally stores {sum of values, number of values}; the contribution of a
 * timestamp is sum / count.
 */
public final class TimestampAccumulator {

    private final Map<String, double[]> byTimestamp = new HashMap<>(); // ts -> {sum, count}
    private long occurrences = 0;

    public void add(String rawValue) {
        String[] f = rawValue.split(";");
        if (f.length == 2) {
            accumulate(f[0], toDouble(f[1]), 1);
        } else if (f.length == 3) {
            accumulate(f[0], toDouble(f[1]), (int) toDouble(f[2]));
        } else {
            throw new IllegalArgumentException("malformed value: " + rawValue);
        }
    }

    /** sum = sum of the values, count = number of readings behind that sum. */
    public void accumulate(String timestamp, double sum, int count) {
        if (count <= 0) throw new IllegalArgumentException("count must be > 0: " + timestamp);
        double[] cell = byTimestamp.get(timestamp);
        if (cell == null) {
            cell = new double[] {0.0, 0.0};
            byTimestamp.put(timestamp, cell);
        }
        cell[0] += sum;
        cell[1] += count;
        this.occurrences += count;
    }

    /** Daily energy = sum over distinct timestamps of the averaged value. */
    public double totalKwh() {
        double total = 0.0;
        for (double[] c : byTimestamp.values()) total += c[0] / c[1];
        return total;
    }

    public int distinctReadings() { return byTimestamp.size(); }
    public long occurrences()     { return occurrences; }
    public boolean isEmpty()      { return byTimestamp.isEmpty(); }

    public Map<String, double[]> entries() { return Collections.unmodifiableMap(byTimestamp); }

    private static double toDouble(String s) {
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("not a number: " + s, e);
        }
    }
}