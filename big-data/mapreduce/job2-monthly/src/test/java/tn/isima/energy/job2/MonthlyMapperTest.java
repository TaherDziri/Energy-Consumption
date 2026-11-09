package tn.isima.energy.job2;

import java.io.IOException;
import java.io.StringReader;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import org.junit.Test;

/**
 * Teste la logique du Mapper sans Hadoop :
 * calendrier en memoire + appel direct a buildMetrics().
 */
public class MonthlyMapperTest {

    private static TariffCalendar calendarFor(String... rows) throws IOException {
        StringBuilder sb = new StringBuilder("date,slot,tariff,price_pence\n");
        for (String row : rows) sb.append(row).append('\n');
        return TariffCalendar.load(new StringReader(sb.toString()));
    }

    @Test
    public void stdHouseholdUsesFlatPrice() throws IOException {
        TariffCalendar cal = calendarFor("2013-03-01,0,Normal,11.76");
        MonthlyMapper.Diagnostics diag = new MonthlyMapper.Diagnostics();

        DailyMetrics m = MonthlyMapper.buildMetrics(
                "2013-03-01", "Std", 3.0, 3, 0, 1.5,
                "0:1.0;1:1.5;2:0.5", cal, diag);

        assertNotNull(m);
        assertFalse(diag.seriesError);
        assertEquals(3, m.getObservedSlots());
        assertEquals(3, m.getPricedSlots());
        assertEquals(0, m.getMissingSlots());
        assertEquals(1, m.getValidDays());
        assertEquals(3.0, m.getTotalKwh(), 1e-12);
        assertEquals(1.5, m.getPeakKwhHh(), 1e-12);
        // 3.0 kWh * 14.228 / 100 = 0.42684 GBP
        assertEquals(0.42684, m.getCostGbp(), 1e-9);

        assertFalse(diag.slotCountMismatch);
        assertFalse(diag.sumMismatch);
        assertFalse(diag.peakMismatch);
        assertEquals(3.0, diag.sum, 1e-12);
        assertEquals(1.5, diag.max, 1e-12);
    }

    @Test
    public void touHouseholdUsesTheSlotPrice() throws IOException {
        TariffCalendar cal = calendarFor(
                "2013-03-01,0,Low,3.99",
                "2013-03-01,1,High,67.20");
        MonthlyMapper.Diagnostics diag = new MonthlyMapper.Diagnostics();

        DailyMetrics m = MonthlyMapper.buildMetrics(
                "2013-03-01", "ToU", 3.0, 2, 0, 2.0,
                "0:1.0;1:2.0", cal, diag);

        assertNotNull(m);
        assertEquals(2, m.getPricedSlots());
        // (1.0 * 3.99 + 2.0 * 67.20) / 100 = 1.3839 GBP
        assertEquals(1.3839, m.getCostGbp(), 1e-9);
    }

    @Test
    public void dateOutsideCalendarHasNoPrice() throws IOException {
        TariffCalendar cal = calendarFor("2013-03-01,0,Normal,11.76");
        MonthlyMapper.Diagnostics diag = new MonthlyMapper.Diagnostics();

        DailyMetrics m = MonthlyMapper.buildMetrics(
                "2012-03-01", "Std", 2.0, 2, 0, 1.0,
                "0:1.0;1:1.0", cal, diag);

        assertNotNull(m);
        assertEquals(0, m.getPricedSlots());       // 2012 : hors calendrier
        assertEquals(2, diag.unpricedSlots);
        assertEquals(0.0, m.getCostGbp(), 1e-12);  // NULL sera decide en sortie
        assertTrue(Double.isNaN(cal.pricePence("2012-03-01", 0)));
    }

    @Test
    public void duplicatePairIsCountedNotMerged() throws IOException {
        TariffCalendar cal = calendarFor("2013-10-27,2,Normal,11.76");
        MonthlyMapper.Diagnostics diag = new MonthlyMapper.Diagnostics();

        DailyMetrics m = MonthlyMapper.buildMetrics(
                "2013-10-27", "ToU", 1.0, 3, 0, 0.5,
                "2:0.2;2:0.3;3:0.5", cal, diag);

        assertNotNull(m);
        assertEquals(3, m.getObservedSlots());     // 3 paires, pas 2 slots
        assertEquals(1, diag.duplicateSlots);       // slot 2 vu deux fois
        assertEquals(1.0, diag.sum, 1e-12);
        assertEquals(2, m.getPricedSlots());       // les deux paires du slot 2
        assertEquals(1, diag.unpricedSlots);       // slot 3 absent du calendrier
        assertEquals(0.0588, m.getCostGbp(), 1e-9);
    }

    @Test
    public void inconsistenciesAreFlaggedNotFatal() throws IOException {
        TariffCalendar cal = calendarFor("2013-03-01,0,Normal,11.76");
        MonthlyMapper.Diagnostics diag = new MonthlyMapper.Diagnostics();

        DailyMetrics m = MonthlyMapper.buildMetrics(
                "2013-03-01", "Std", 9.9, 47, 1, 5.0,
                "0:1.0;1:1.0", cal, diag);

        assertNotNull(m);
        assertEquals(2, m.getObservedSlots());
        assertTrue(diag.slotCountMismatch);        // 2 paires contre 47 annoncees
        assertTrue(diag.sumMismatch);              // 2.0 contre 9.9
        assertTrue(diag.peakMismatch);             // 1.0 contre 5.0
        assertFalse(diag.missingSlotsMismatch);    // 47 + 1 = 48
    }

    @Test
    public void missingSlotsMismatchIsCountedNotFatal() throws IOException {
        TariffCalendar cal = calendarFor("2013-03-01,0,Normal,11.76");
        MonthlyMapper.Diagnostics diag = new MonthlyMapper.Diagnostics();

        DailyMetrics m = MonthlyMapper.buildMetrics(
                "2013-03-01", "Std", 1.0, 47, 0, 1.0,
                "0:1.0", cal, diag);

        assertNotNull(m);                          // la ligne est conservee
        assertTrue(diag.missingSlotsMismatch);     // 47 + 0 != 48

        diag.reset();
        m = MonthlyMapper.buildMetrics(
                "2013-03-01", "Std", 1.0, 47, 1, 1.0,
                "0:1.0", cal, diag);

        assertNotNull(m);
        assertFalse(diag.missingSlotsMismatch);    // 47 + 1 == 48
    }

    @Test
    public void malformedSeriesIsRejected() throws IOException {
        TariffCalendar cal = calendarFor("2013-03-01,0,Normal,11.76");
        MonthlyMapper.Diagnostics diag = new MonthlyMapper.Diagnostics();

        assertNull(MonthlyMapper.buildMetrics(
                "2013-03-01", "Std", 1.0, 1, 0, 1.0, "0", cal, diag));
        assertTrue(diag.seriesError);              // pas de ":"

        diag.reset();
        assertNull(MonthlyMapper.buildMetrics(
                "2013-03-01", "Std", 1.0, 1, 0, 1.0, "0:abc", cal, diag));
        assertTrue(diag.seriesError);              // kWh non numerique
    }
}