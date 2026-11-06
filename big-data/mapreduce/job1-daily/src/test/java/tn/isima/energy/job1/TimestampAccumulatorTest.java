package tn.isima.energy.job1;

import org.junit.Test;
import static org.junit.Assert.*;

public class TimestampAccumulatorTest {

    @Test
    public void sumsDistinctTimestamps() {
        TimestampAccumulator acc = new TimestampAccumulator();
        acc.add("2012-10-12 00:30:00.0000000;0.2");
        acc.add("2012-10-12 01:00:00.0000000;0.1");
        assertEquals(2, acc.distinctReadings());
        assertEquals(0.3, acc.totalKwh(), 1e-9);
    }

    @Test
    public void averagesDuplicateTimestamps() {
        TimestampAccumulator acc = new TimestampAccumulator();
        acc.add("2012-10-12 00:30:00.0000000;0.2");
        acc.add("2012-10-12 00:30:00.0000000;0.4");
        assertEquals(1, acc.distinctReadings());
        assertEquals(0.3, acc.totalKwh(), 1e-9);
        assertEquals(2, acc.occurrences());
    }

    @Test
    public void readsCombinerFormat() {
        TimestampAccumulator acc = new TimestampAccumulator();
        acc.add("2012-10-12 00:30:00.0000000;0.6;2");
        assertEquals(1, acc.distinctReadings());
        assertEquals(0.3, acc.totalKwh(), 1e-9);
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsMalformedValue() {
        new TimestampAccumulator().add("only-one-field");
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsNonNumericValue() {
        new TimestampAccumulator().add("2012-10-12 00:30:00.0000000;abc");
    }
}