package tn.isima.energy.job1;

import org.junit.Test;
import static org.junit.Assert.*;

public class TimestampAccumulatorTest {

    @Test
    public void sumsDistinctTimestamps() {
        TimestampAccumulator acc = new TimestampAccumulator();
        acc.add("Std;1;2012-10-12 00:30:00.0000000;0.2");
        acc.add("Std;2;2012-10-12 01:00:00.0000000;0.1");
        assertEquals(2, acc.distinctReadings());
        assertEquals("Std", acc.tariffGroup());
        assertEquals(0.3, acc.totalKwh(), 1e-9);
    }

    @Test
    public void averagesDuplicateTimestamps() {
        TimestampAccumulator acc = new TimestampAccumulator();
        acc.add("Std;1;2012-10-12 00:30:00.0000000;0.2");
        acc.add("Std;1;2012-10-12 00:30:00.0000000;0.4");
        assertEquals(1, acc.distinctReadings());
        assertEquals(0.3, acc.totalKwh(), 1e-9);
        assertEquals(2, acc.occurrences());
    }

    @Test
    public void readsCombinerFormat() {
        TimestampAccumulator acc = new TimestampAccumulator();
        acc.add("Std;1;2012-10-12 00:30:00.0000000;0.6;2");
        assertEquals(1, acc.distinctReadings());
        assertEquals(0.3, acc.totalKwh(), 1e-9);
    }

    @Test
    public void keepsBothFallBackHalfHours() {
        TimestampAccumulator acc = new TimestampAccumulator();
        acc.add("ToU;2;2012-10-28 00:00:00.0000000;0.138");
        acc.add("ToU;2;2012-10-28 01:00:00.0000000;0.082");
        assertEquals(2, acc.distinctReadings());
        assertEquals(0.220, acc.totalKwh(), 1e-9);
    }

    @Test
    public void sortsByUtcTimestamp() {
        TimestampAccumulator acc = new TimestampAccumulator();
        acc.add("Std;47;2012-10-12 23:30:00.0000000;0.3");
        acc.add("Std;1;2012-10-12 00:30:00.0000000;0.1");
        assertEquals("2012-10-12 00:30:00.0000000", acc.sortedEntries().get(0).getKey());
        assertEquals("2012-10-12 23:30:00.0000000", acc.sortedEntries().get(1).getKey());
    }

    @Test
    public void flagsTariffConflict() {
        TimestampAccumulator acc = new TimestampAccumulator();
        acc.add("Std;1;2012-10-12 00:30:00.0000000;0.2");
        acc.add("ToU;2;2012-10-12 01:00:00.0000000;0.1");
        assertTrue(acc.tariffConflict());
        assertEquals("Std", acc.tariffGroup());
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsMalformedValue() {
        new TimestampAccumulator().add("only-one-field");
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsNonNumericValue() {
        new TimestampAccumulator().add("Std;1;2012-10-12 00:30:00.0000000;abc");
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsSlotOutOfRange() {
        new TimestampAccumulator().add("Std;48;2012-10-12 00:30:00.0000000;0.1");
    }
}
