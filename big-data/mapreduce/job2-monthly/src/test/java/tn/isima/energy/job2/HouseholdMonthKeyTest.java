package tn.isima.energy.job2;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import org.junit.Test;

/**
 * Teste la cle sans cluster : on la serialise en octets, on la relit,
 * et les deux objets doivent etre identiques.
 */
public class HouseholdMonthKeyTest {

    /** Simule le transport Hadoop : write -> octets -> readFields. */
    private static HouseholdMonthKey roundTrip(HouseholdMonthKey k) throws IOException {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bos);
        k.write(out);          // ecriture
        out.flush();

        DataInputStream in = new DataInputStream(
                new ByteArrayInputStream(bos.toByteArray()));
        HouseholdMonthKey copy = new HouseholdMonthKey(); // objet vide, comme Hadoop
        copy.readFields(in);   // relecture
        return copy;
    }

    @Test
    public void serializationRoundTrip() throws IOException {
        HouseholdMonthKey original = new HouseholdMonthKey("MAC000002", "2013-03", "Std");
        HouseholdMonthKey copy = roundTrip(original);

        assertEquals(original, copy);
        assertEquals(original.hashCode(), copy.hashCode());
        assertEquals(original.toString(), copy.toString());
    }

    @Test
    public void compareToOrdersByHouseholdThenMonthThenTariff() {
        HouseholdMonthKey m2012 = new HouseholdMonthKey("MAC000002", "2012-03", "Std");
        HouseholdMonthKey m2013 = new HouseholdMonthKey("MAC000002", "2013-03", "Std");
        HouseholdMonthKey m2014 = new HouseholdMonthKey("MAC000002", "2013-04", "Std");

        // Ordre par mois : 2012-03 < 2013-03 < 2013-04
        assertTrue(m2012.compareTo(m2013) < 0);
        assertTrue(m2013.compareTo(m2014) < 0);
        assertTrue(m2012.compareTo(m2014) < 0);

        // Meme cle -> 0
        assertEquals(0, m2013.compareTo(new HouseholdMonthKey("MAC000002", "2013-03", "Std")));

        // Le foyer passe avant le mois
        assertTrue(new HouseholdMonthKey("MAC000001", "2013-12", "Std")
                .compareTo(new HouseholdMonthKey("MAC000002", "2012-01", "Std")) < 0);

        // Le tarif tranche en dernier ("Std" < "ToU")
        assertTrue(new HouseholdMonthKey("MAC000002", "2013-03", "Std")
                .compareTo(new HouseholdMonthKey("MAC000002", "2013-03", "ToU")) < 0);
    }

    @Test
    public void nullStringsBecomeEmptyAfterRoundTrip() throws IOException {
        HouseholdMonthKey k = new HouseholdMonthKey(null, "2013-03", null);
        HouseholdMonthKey copy = roundTrip(k);

        assertEquals("", copy.getHouseholdId());
        assertEquals("", copy.getTariffGroup());
        assertEquals(k, copy);
    }
}