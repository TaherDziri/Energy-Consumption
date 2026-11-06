package tn.isima.energy.job1;

import org.junit.Test;
import static org.junit.Assert.*;

public class LineParserTest {

    @Test
    public void parsesValidLine() {
        LineParser.Result r = LineParser.parse("MAC000002,Std,2012-10-12 00:30:00.0000000, 0.123");
        assertEquals(LineParser.Status.OK, r.getStatus());
        assertEquals("MAC000002", r.getReading().getHouseholdId());
        assertEquals("2012-10-12", r.getReading().getDate());
        assertEquals(0.123, r.getReading().getKwh(), 1e-9);
    }

    @Test
    public void detectsHeader() {
        assertEquals(LineParser.Status.HEADER,
                LineParser.parse("LCLid,stdorToU,DateTime,KWH/hh (per half hour)").getStatus());
    }

    @Test
    public void detectsNullValue() {
        assertEquals(LineParser.Status.MISSING,
                LineParser.parse("MAC005565,ToU,2012-12-19 12:32:41.0000000,Null").getStatus());
    }

    @Test
    public void detectsEmptyValue() {
        assertEquals(LineParser.Status.MISSING,
                LineParser.parse("MAC000002,Std,2012-10-12 00:30:00.0000000,").getStatus());
    }

    @Test
    public void detectsWrongFieldCount() {
        assertEquals(LineParser.Status.MALFORMED,
                LineParser.parse("MAC000002,Std,2012-10-12 00:30:00.0000000").getStatus());
    }

    @Test
    public void detectsBadTimestamp() {
        assertEquals(LineParser.Status.MALFORMED,
                LineParser.parse("MAC000002,Std,12/10/2012 00:30,0.5").getStatus());
    }

    @Test
    public void detectsNegativeValue() {
        assertEquals(LineParser.Status.NEGATIVE,
                LineParser.parse("MAC000002,Std,2012-10-12 00:30:00.0000000,-0.5").getStatus());
    }

    @Test
    public void stripsUtf8Bom() {
        assertEquals(LineParser.Status.HEADER,
                LineParser.parse("\uFEFFLCLid,stdorToU,DateTime,KWH/hh (per half hour)").getStatus());
    }

    @Test
    public void checksGrid() {
        assertTrue(LineParser.isOnGrid("2012-10-12 00:30:00.0000000"));
        assertTrue(LineParser.isOnGrid("2012-10-12 23:00:00.0000000"));
        assertFalse(LineParser.isOnGrid("2012-12-19 12:32:41.0000000"));
    }

    @Test
    public void buildsGroupKey() {
        assertEquals("MAC000002|2012-10-12", LineParser.groupKey("MAC000002", "2012-10-12"));
    }
}