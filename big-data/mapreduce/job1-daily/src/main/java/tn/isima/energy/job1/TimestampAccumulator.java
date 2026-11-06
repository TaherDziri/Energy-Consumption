package tn.isima.energy.job1;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Accumulates every half-hourly value of ONE (household, local day).
 *
 * A timestamp seen several times (duplicate rows) is AVERAGED, not summed twice.
 * The UTC timestamp string stays the key, so the two physical half-hours that
 * share the same local slot on a fall-back day stay distinct.
 *
 * Accepted value formats (semicolon separated):
 *   "tariff;slot;timestamp;kwh"          one reading, from the Mapper
 *   "tariff;slot;timestamp;sum;count"    already aggregated, from the Combiner
 *
 * Internally stores {sum, count, slot}; the contribution of a timestamp is
 * sum / count.
 */
public final class TimestampAccumulator {

    private final Map<String, double[]> byTimestamp = new HashMap<>(); // ts -> {sum, count, slot}
    private String tariffGroup;
    private boolean tariffConflict;
    private long occurrences = 0;

    public void add(String rawValue) {
        String[] f = rawValue.split(";");
        if (f.length == 4) {
            accumulate(f[0], parseInt(f[1]), f[2], toDouble(f[3]), 1);
        } else if (f.length == 5) {
            accumulate(f[0], parseInt(f[1]), f[2], toDouble(f[3]), (int) toDouble(f[4]));
        } else {
            throw new IllegalArgumentException("malformed value: " + rawValue);
        }
    }

    /** sum = sum of the values, count = number of readings behind that sum. */
    public void accumulate(String tariff, int slot, String timestamp, double sum, int count) {
        if (count <= 0) throw new IllegalArgumentException("count must be > 0: " + timestamp);
        if (slot < 0 || slot > 47) throw new IllegalArgumentException("slot out of range: " + slot);

        if (tariffGroup == null) {
            tariffGroup = tariff;
        } else if (!tariffGroup.equals(tariff)) {
            tariffConflict = true;
        }

        double[] cell = byTimestamp.get(timestamp);
        if (cell == null) {
            cell = new double[] {0.0, 0.0, slot};
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

    /** Entries sorted by UTC timestamp, i.e. chronological order (fixed-width format). */
    public List<Map.Entry<String, double[]>> sortedEntries() {
        List<Map.Entry<String, double[]>> entries = new ArrayList<>(byTimestamp.entrySet());
        entries.sort(Map.Entry.comparingByKey());
        return entries;
    }

    public String tariffGroup()      { return tariffGroup; }
    public boolean tariffConflict()  { return tariffConflict; }
    public int distinctReadings()    { return byTimestamp.size(); }
    public long occurrences()        { return occurrences; }
    public boolean isEmpty()         { return byTimestamp.isEmpty(); }

    public Map<String, double[]> entries() { return Collections.unmodifiableMap(byTimestamp); }

    private static double toDouble(String s) {
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("not a number: " + s, e);
        }
    }

    private static int parseInt(String s) {
        try {
            return Integer.parseInt(s);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("not an integer: " + s, e);
        }
    }
}
