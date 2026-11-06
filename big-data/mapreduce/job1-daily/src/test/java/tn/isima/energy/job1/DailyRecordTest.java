package tn.isima.energy.job1;

import java.time.LocalDate;
import java.util.List;
import java.util.Locale;
import org.junit.Test;
import static org.junit.Assert.*;

/**
 * Acceptance tests of the MR1 contract v1.1, mirroring the three reference
 * rows of docs/01_MR1_MR2_CONTRACT.md plus the DST cases.
 */
public class DailyRecordTest {

    private static String ts(String date, int slot) {
        return String.format(Locale.ROOT, "%s %02d:%02d:00.0000000",
                date, slot / 2, (slot % 2) * 30);
    }

    private static TimestampAccumulator day(String date, double base, int peakSlot, double peak,
                                            int skipSlot) {
        TimestampAccumulator acc = new TimestampAccumulator();
        for (int slot = 0; slot < 48; slot++) {
            if (slot == skipSlot) continue;
            double value = slot == peakSlot ? peak : base;
            acc.add("Std;" + slot + ";" + ts(date, slot) + ";" + value);
        }
        return acc;
    }

    @Test
    public void referenceRowA_47SlotsWithOneMissing() {
        TimestampAccumulator acc = day("2013-03-01", 0.5, 18, 2.5, 12);
        String line = DailyRecord.format("MAC000002", LocalDate.parse("2013-03-01"), acc);
        String[] f = line.split("\t", -1);

        assertEquals(10, f.length);
        assertEquals("MAC000002", f[0]);
        assertEquals("2013-03-01", f[1]);
        assertEquals("Std", f[2]);
        assertEquals("25.500", f[3]);
        assertEquals("47", f[4]);
        assertEquals("1", f[5]);
        assertEquals("2.5", f[6]);
        assertEquals("18", f[7]);
        assertEquals("0.542553", f[8]);
        assertFalse("missing slot must be absent", f[9].contains("12:"));
        assertEquals(47, DailyRecord.seriesPairs(line));
        assertEquals(25.5, seriesSum(line), 1e-6);
    }

    @Test
    public void referenceRowB_48Slots() {
        TimestampAccumulator acc = day("2013-03-02", 0.4, 19, 2.0, -1);
        String line = DailyRecord.format("MAC000002", LocalDate.parse("2013-03-02"), acc);
        String[] f = line.split("\t", -1);

        assertEquals("20.800", f[3]);
        assertEquals("48", f[4]);
        assertEquals("0", f[5]);
        assertEquals("2.0", f[6]);
        assertEquals("19", f[7]);
        assertEquals("0.433333", f[8]);
        assertEquals(48, DailyRecord.seriesPairs(line));
        assertEquals(20.8, seriesSum(line), 1e-6);
    }

    @Test
    public void referenceRowC_2012() {
        TimestampAccumulator acc = day("2012-03-01", 0.5, 20, 2.0, -1);
        String line = DailyRecord.format("MAC000002", LocalDate.parse("2012-03-01"), acc);
        String[] f = line.split("\t", -1);

        assertEquals("25.500", f[3]);
        assertEquals("48", f[4]);
        assertEquals("0", f[5]);
        assertEquals("2.0", f[6]);
        assertEquals("20", f[7]);
        assertEquals("0.53125", f[8]);
    }

    @Test
    public void emptyDayKeepsTheContractShape() {
        TimestampAccumulator acc = new TimestampAccumulator();
        String line = DailyRecord.format("MAC000002", LocalDate.parse("2013-03-01"), acc);
        String[] f = line.split("\t", -1);

        assertEquals(10, f.length);
        assertEquals("0.000", f[3]);
        assertEquals("0", f[4]);
        assertEquals("48", f[5]);
        assertEquals("", f[6]);
        assertEquals("", f[7]);
        assertEquals("", f[8]);
        assertEquals("", f[9]);
    }

    @Test
    public void measuredZeroIsWrittenAsZero() {
        TimestampAccumulator acc = new TimestampAccumulator();
        acc.add("Std;0;" + ts("2013-03-01", 0) + ";0.0");
        String line = DailyRecord.format("MAC000002", LocalDate.parse("2013-03-01"), acc);
        String[] f = line.split("\t", -1);

        assertEquals("0.000", f[3]);
        assertEquals("0.0", f[6]);
        assertEquals("0", f[7]);
        assertEquals("0:0.0", f[9]);
    }

    @Test
    public void peakTieKeepsTheEarliestSlot() {
        TimestampAccumulator acc = new TimestampAccumulator();
        acc.add("Std;5;" + ts("2013-03-01", 5) + ";2.0");
        acc.add("Std;9;" + ts("2013-03-01", 9) + ";2.0");
        String line = DailyRecord.format("MAC000002", LocalDate.parse("2013-03-01"), acc);
        String[] f = line.split("\t", -1);

        assertEquals("2.0", f[6]);
        assertEquals("5", f[7]);
    }

    @Test
    public void fallBackDayHas50SlotsAndRepeatedSlotIndexes() {
        TimestampAccumulator acc = day("2013-10-27", 0.4, 20, 2.0, -1);
        // two extra physical half-hours sharing the local slots 2 and 3
        acc.add("Std;2;2013-10-27 00:00:30.0000000;0.138");
        acc.add("Std;3;2013-10-27 00:30:30.0000000;0.086");

        String line = DailyRecord.format("MAC000002", LocalDate.parse("2013-10-27"), acc);
        String[] f = line.split("\t", -1);
        List<String> tokens = DailyRecord.seriesTokens(line);

        assertEquals("50", f[4]);
        assertEquals("0", f[5]);
        assertEquals(50, tokens.size());
        long slot2 = tokens.stream().filter(t -> t.startsWith("2:")).count();
        long slot3 = tokens.stream().filter(t -> t.startsWith("3:")).count();
        assertEquals(2, slot2);
        assertEquals(2, slot3);
        assertEquals(seriesSum(line), Double.parseDouble(f[3]), 0.001);
    }

    @Test
    public void springForwardDayHas46Slots() {
        TimestampAccumulator acc = new TimestampAccumulator();
        for (int slot = 0; slot < 48; slot++) {
            if (slot == 2 || slot == 3) continue;
            acc.add("Std;" + slot + ";" + ts("2013-03-31", slot) + ";0.3");
        }
        String line = DailyRecord.format("MAC000002", LocalDate.parse("2013-03-31"), acc);
        String[] f = line.split("\t", -1);

        assertEquals("46", f[4]);
        assertEquals("0", f[5]);
        for (String token : DailyRecord.seriesTokens(line)) {
            assertFalse(token.startsWith("2:"));
            assertFalse(token.startsWith("3:"));
        }
    }

    @Test
    public void numberFormattingIsCompactAndStable() {
        assertEquals("0.5", DailyRecord.number(0.5));
        assertEquals("0.0", DailyRecord.number(0.0));
        assertEquals("2.5", DailyRecord.number(2.5));
        assertEquals("12.0", DailyRecord.number(12.0));
        assertEquals("0.512346", DailyRecord.number(0.5123456));
        assertEquals("0.000001", DailyRecord.number(0.000001));
        assertEquals("25.500", DailyRecord.fixed3(25.5));
    }

    private static double seriesSum(String line) {
        double sum = 0.0;
        for (String token : DailyRecord.seriesTokens(line)) {
            int colon = token.indexOf(':');
            sum += Double.parseDouble(token.substring(colon + 1));
        }
        return sum;
    }
}
