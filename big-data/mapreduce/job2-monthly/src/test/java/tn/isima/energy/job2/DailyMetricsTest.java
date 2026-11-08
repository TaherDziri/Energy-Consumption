package tn.isima.energy.job2;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

/**
 * Teste le seau de metriques : serialisation et fusion (SOMME + MAX).
 */
public class DailyMetricsTest {

    /** Simule le transport Hadoop : write -> octets -> readFields. */
    private static DailyMetrics roundTrip(DailyMetrics m) throws IOException {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bos);
        m.write(out);          // ecriture
        out.flush();

        DataInputStream in = new DataInputStream(
                new ByteArrayInputStream(bos.toByteArray()));
        DailyMetrics copy = new DailyMetrics(); // objet vide, comme Hadoop
        copy.readFields(in);   // relecture
        return copy;
    }

    @Test
    public void serializationRoundTrip() throws IOException {
        DailyMetrics m = new DailyMetrics();
        m.setTotalKwh(46.3);
        m.setPeakKwhHh(2.5);
        m.setCostGbp(6.587564);
        m.setObservedSlots(46);
        m.setPricedSlots(46);
        m.setMissingSlots(0);
        m.setValidDays(2);

        DailyMetrics copy = roundTrip(m);

        assertEquals(m, copy);
        assertEquals(m.hashCode(), copy.hashCode());
        assertEquals(m.toString(), copy.toString());
    }

    @Test
    public void mergeSumsAdditiveFieldsAndKeepsMaxPeak() {
        DailyMetrics day1 = new DailyMetrics();
        day1.setTotalKwh(10.0);
        day1.setPeakKwhHh(1.5);
        day1.setCostGbp(2.0);
        day1.setObservedSlots(20);
        day1.setPricedSlots(18);
        day1.setMissingSlots(4);
        day1.setValidDays(1);

        DailyMetrics day2 = new DailyMetrics();
        day2.setTotalKwh(5.5);
        day2.setPeakKwhHh(2.5);
        day2.setCostGbp(1.0);
        day2.setObservedSlots(26);
        day2.setPricedSlots(26);
        day2.setMissingSlots(0);
        day2.setValidDays(2);

        day1.merge(day2);

        // SOMME
        assertEquals(15.5, day1.getTotalKwh(), 1e-12);
        assertEquals(3.0,  day1.getCostGbp(), 1e-12);
        assertEquals(46,   day1.getObservedSlots());
        assertEquals(44,   day1.getPricedSlots());
        assertEquals(4,    day1.getMissingSlots());
        assertEquals(3,    day1.getValidDays());

        // MAX : 2.5, surtout pas 4.0
        assertEquals(2.5,  day1.getPeakKwhHh(), 1e-12);
    }

    @Test
    public void mergingAnEmptyBucketChangesNothing() {
        DailyMetrics month = new DailyMetrics();
        month.setTotalKwh(12.5);
        month.setPeakKwhHh(1.25);
        month.setCostGbp(1.7785);
        month.setObservedSlots(48);
        month.setPricedSlots(48);
        month.setMissingSlots(0);
        month.setValidDays(1);

        // Fusionner un seau vide ne doit rien changer.
        month.merge(new DailyMetrics());

        assertEquals(12.5,   month.getTotalKwh(), 1e-12);
        assertEquals(1.25,   month.getPeakKwhHh(), 1e-12);
        assertEquals(1.7785, month.getCostGbp(), 1e-12);
        assertEquals(48,     month.getObservedSlots());
        assertEquals(48,     month.getPricedSlots());
        assertEquals(0,      month.getMissingSlots());
        assertEquals(1,      month.getValidDays());
    }
}