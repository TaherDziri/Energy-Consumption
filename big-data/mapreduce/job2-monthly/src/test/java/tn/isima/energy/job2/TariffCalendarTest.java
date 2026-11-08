package tn.isima.energy.job2;

import java.io.IOException;
import java.io.StringReader;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import org.junit.Test;

/**
 * Teste le calendrier sans fichier ni cluster : le CSV est une String.
 */
public class TariffCalendarTest {

    private static final String CSV =
            "date,slot,tariff,price_pence\n"
          + "2013-03-01,0,Std,10.5\n"
          + "2013-03-01,1,Std,9.9\n"
          + "2013-12-31,47,Std,11.25\n";

    @Test
    public void loadsPricesAndSkipsHeader() throws IOException {
        TariffCalendar cal = TariffCalendar.load(new StringReader(CSV));

        assertEquals(3, cal.size());
        assertEquals(0, cal.malformedLines());
        assertEquals("2013-03-01", cal.minDate());
        assertEquals("2013-12-31", cal.maxDate());
        assertEquals(10.5, cal.pricePence("2013-03-01", 0), 1e-9);
        assertEquals(9.9,  cal.pricePence("2013-03-01", 1), 1e-9);
    }

    @Test
    public void unknownSlotHasNoPrice() throws IOException {
        TariffCalendar cal = TariffCalendar.load(new StringReader(CSV));

        assertFalse(cal.hasPrice("2013-03-01", 2));
        assertTrue(Double.isNaN(cal.pricePence("2013-03-01", 2)));
    }

    @Test
    public void coversOnlyTheCalendarRange() throws IOException {
        TariffCalendar cal = TariffCalendar.load(new StringReader(CSV));

        assertTrue(cal.covers("2013-03-01"));
        assertTrue(cal.covers("2013-06-15"));
        assertTrue(cal.covers("2013-12-31"));
        assertFalse(cal.covers("2012-12-31"));
        assertFalse(cal.covers("2014-01-01"));
    }

    @Test
    public void expectedSlotsIsAlways48() {
        // En GMT, aucun jour ne fait 23 h ni 25 h.
        assertEquals(48, TariffCalendar.expectedSlots("2013-03-01"));
        assertEquals(48, TariffCalendar.expectedSlots("2013-03-31"));
        assertEquals(48, TariffCalendar.expectedSlots("2013-10-26"));
        assertEquals(48, TariffCalendar.expectedSlots("2013-10-27"));
        assertEquals(48, TariffCalendar.expectedSlots("2013-10-28"));
    }

    @Test
    public void malformedLinesAndDuplicatesAreCounted() throws IOException {
        String csv = "date,slot,tariff,price_pence\n"
                + "2013-03-01,0,Std,10.5\n"
                + "bad,line\n"                          // 2 colonnes -> malformee
                + "2013-03-01,x,Std,10.5\n"             // slot non entier
                + "2013-03-01,2,Std,notanumber\n"       // prix non numerique
                + "2013-13-01,3,Std,10.0\n"             // mois 13 invalide
                + "2013-03-01,48,Std,10.0\n"            // slot 48 : impossible en GMT
                + "2013-03-01,0,Std,99.9\n";            // doublon (date, slot)

        TariffCalendar cal = TariffCalendar.load(new StringReader(csv));

        assertEquals(1, cal.size());
        assertEquals(5, cal.malformedLines());
        assertEquals(1, cal.duplicateRows());
        // La premiere valeur est conservee, pas la derniere.
        assertEquals(10.5, cal.pricePence("2013-03-01", 0), 1e-9);
    }
}