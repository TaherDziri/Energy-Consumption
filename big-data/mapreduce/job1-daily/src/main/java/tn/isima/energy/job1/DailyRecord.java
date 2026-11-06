package tn.isima.energy.job1;

import java.time.LocalDate;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Builds the contract v1.1 output line, one per (household, local day):
 *
 *   household_id \t date \t tariff_group \t total_kwh \t n_valid_slots
 *   \t n_missing_slots \t peak_kwh_hh \t peak_slot \t avg_valid_kwh_hh \t series
 *
 * Rules (docs/data-contract.md v1.1):
 *  - a missing slot is ABSENT from series, never "slot:0";
 *  - a measured zero is "slot:0.0";
 *  - n_missing_slots = expected(day) - n_valid_slots, expected in {46, 48, 50};
 *  - series values are the deduplicated (averaged) values, in chronological order;
 *  - peak_slot is the slot of the maximum value; on a tie the earliest wins;
 *  - when n_valid_slots = 0: total 0.000, peak/peak_slot/avg empty, series empty.
 */
public final class DailyRecord {

    private DailyRecord() { }

    public static String format(String householdId, LocalDate date, TimestampAccumulator acc) {
        int expected = LocalSlot.expectedSlots(date);
        int valid = acc.distinctReadings();
        int missing = Math.max(0, expected - valid);
        double total = acc.totalKwh();
        String tariff = acc.tariffGroup() == null ? "" : acc.tariffGroup();

        StringBuilder series = new StringBuilder();
        double peak = -1.0;
        int peakSlot = -1;

        for (Map.Entry<String, double[]> entry : acc.sortedEntries()) {
            double[] cell = entry.getValue();
            double value = cell[0] / cell[1];
            int slot = (int) cell[2];
            if (series.length() > 0) series.append(';');
            series.append(slot).append(':').append(number(value));
            if (value > peak) {
                peak = value;
                peakSlot = slot;
            }
        }

        String peakKwh = valid == 0 ? "" : number(peak);
        String peakIndex = valid == 0 ? "" : Integer.toString(peakSlot);
        String average = valid == 0 ? "" : number(total / valid);

        StringBuilder line = new StringBuilder(64 + series.length());
        line.append(householdId).append('\t')
            .append(date.toString()).append('\t')
            .append(tariff).append('\t')
            .append(fixed3(total)).append('\t')
            .append(valid).append('\t')
            .append(missing).append('\t')
            .append(peakKwh).append('\t')
            .append(peakIndex).append('\t')
            .append(average).append('\t')
            .append(series);
        return line.toString();
    }

    /** 3 decimals, locale independent: matches the v1.0 total_kwh precision. */
    static String fixed3(double value) {
        return String.format(Locale.ROOT, "%.3f", value);
    }

    /** Up to 6 decimals, trailing zeros stripped, always at least one decimal. */
    static String number(double value) {
        String s = String.format(Locale.ROOT, "%.6f", value);
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == '0') end--;
        if (end > 0 && s.charAt(end - 1) == '.') end++;
        if (end == 0) return "0.0";
        return s.substring(0, end);
    }

    /** Exposes the number of expected slots; used by the reducer counters. */
    public static int expectedSlots(LocalDate date) {
        return LocalSlot.expectedSlots(date);
    }

    /** Only used by tests: count of series pairs in a formatted line. */
    static int seriesPairs(String line) {
        int tab = line.lastIndexOf('\t');
        String series = line.substring(tab + 1);
        if (series.isEmpty()) return 0;
        return series.split(";", -1).length;
    }

    /** Only used by tests: ordered slots of a formatted line. */
    static List<String> seriesTokens(String line) {
        int tab = line.lastIndexOf('\t');
        String series = line.substring(tab + 1);
        if (series.isEmpty()) return java.util.Collections.emptyList();
        return java.util.Arrays.asList(series.split(";", -1));
    }
}
