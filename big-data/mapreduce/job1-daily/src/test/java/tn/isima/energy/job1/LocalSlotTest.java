package tn.isima.energy.job1;

import org.junit.Test;
import static org.junit.Assert.*;

/** Contract v1.1: raw UTC -> local Europe/London date and clock slot. */
public class LocalSlotTest {

    @Test
    public void springForwardDayHas46Slots() {
        assertEquals(46, LocalSlot.expectedSlots(java.time.LocalDate.parse("2012-03-25")));
        assertEquals(46, LocalSlot.expectedSlots(java.time.LocalDate.parse("2013-03-31")));
    }

    @Test
    public void fallBackDayHas50Slots() {
        assertEquals(50, LocalSlot.expectedSlots(java.time.LocalDate.parse("2012-10-28")));
        assertEquals(50, LocalSlot.expectedSlots(java.time.LocalDate.parse("2013-10-27")));
    }

    @Test
    public void ordinaryDayHas48Slots() {
        assertEquals(48, LocalSlot.expectedSlots(java.time.LocalDate.parse("2013-03-01")));
        assertEquals(48, LocalSlot.expectedSlots(java.time.LocalDate.parse("2012-12-01")));
    }

    @Test
    public void springForwardSkipsSlots2And3() {
        // 01:00 UTC is the transition instant: local clock jumps to 02:00.
        assertEquals(1, LocalSlot.slot("2012-03-25 00:30:00.0000000"));
        assertEquals(4, LocalSlot.slot("2012-03-25 01:00:00.0000000"));
        assertEquals(5, LocalSlot.slot("2012-03-25 01:30:00.0000000"));
    }

    @Test
    public void fallBackRepeatsSlots2And3() {
        // 01:00 BST and 01:00 GMT are two distinct physical half-hours.
        assertEquals(3, LocalSlot.slot("2012-10-28 00:30:00.0000000"));
        assertEquals(3, LocalSlot.slot("2012-10-28 01:30:00.0000000"));
        assertEquals(2, LocalSlot.slot("2012-10-28 00:00:00.0000000"));
        assertEquals(2, LocalSlot.slot("2012-10-28 01:00:00.0000000"));
    }

    @Test
    public void summerBoundaryMovesToNextLocalDay() {
        // 23:30 UTC in BST is 00:30 the next local day.
        assertEquals("2012-10-13", LocalSlot.localDate("2012-10-12 23:30:00.0000000"));
        assertEquals(1, LocalSlot.slot("2012-10-12 23:30:00.0000000"));
    }

    @Test
    public void winterBoundaryStaysOnTheSameLocalDay() {
        assertEquals("2012-12-01", LocalSlot.localDate("2012-12-01 23:30:00.0000000"));
        assertEquals(47, LocalSlot.slot("2012-12-01 23:30:00.0000000"));
    }
}
