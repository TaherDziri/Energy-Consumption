package tn.isima.energy.job2;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

/**
 * Teste la sortie du Reducer sans cluster.
 * Les deux premiers tests reproduisent exactement T05 et T06.
 */
public class MonthlyReducerTest {

    private static DailyMetrics bucket(double kwh, double peak, double cost,
                                       long observed, long priced, long missing, int days) {
        DailyMetrics m = new DailyMetrics();
        m.setTotalKwh(kwh);
        m.setPeakKwhHh(peak);
        m.setCostGbp(cost);
        m.setObservedSlots(observed);
        m.setPricedSlots(priced);
        m.setMissingSlots(missing);
        m.setValidDays(days);
        return m;
    }

    @Test
    public void formatsMarch2013() {
        DailyMetrics m = bucket(46.3, 2.5, 6.587564, 95, 95, 1, 2);

        assertEquals(
                "MAC000002,2013-03,Std,46.300000,6.587564,1.000000,2.500000,2,partial_data,mr2-test",
                MonthlyReducer.outputLine("MAC000002", "2013-03", "Std", m, "mr2-test"));
    }

    @Test
    public void formatsMarch2012WithNullCost() {
        DailyMetrics m = bucket(25.5, 2.0, 0.0, 48, 0, 0, 1);

        assertEquals(
                "MAC000002,2012-03,Std,25.500000,,0.000000,2.000000,1,no_tariff,mr2-test",
                MonthlyReducer.outputLine("MAC000002", "2012-03", "Std", m, "mr2-test"));
    }

    @Test
    public void mergesTwoDaysLikeTheReducerDoes() {
        DailyMetrics dayA = bucket(25.5, 2.5, 3.62814, 47, 47, 1, 1);
        DailyMetrics dayB = bucket(20.8, 2.0, 2.959424, 48, 48, 0, 1);

        DailyMetrics month = new DailyMetrics();
        month.merge(dayA);
        month.merge(dayB);

        assertEquals(
                "MAC000002,2013-03,Std,46.300000,6.587564,1.000000,2.500000,2,partial_data,mr2-test",
                MonthlyReducer.outputLine("MAC000002", "2013-03", "Std", month, "mr2-test"));
    }

    @Test
    public void flagPriorityIsRespected() {
        // no_data : aucune donnee
        assertEquals("no_data",
                MonthlyReducer.qualityFlag(bucket(0, 0, 0, 0, 0, 0, 0)));

        // no_tariff : des donnees, aucun prix
        assertEquals("no_tariff",
                MonthlyReducer.qualityFlag(bucket(10, 1, 0, 10, 0, 3, 1)));

        // partial_tariff domine partial_data (priorite 3 avant 4)
        assertEquals("partial_tariff",
                MonthlyReducer.qualityFlag(bucket(10, 1, 1, 10, 9, 3, 1)));

        // tous les creneaux tarifes, mais des mesures manquent
        assertEquals("partial_data",
                MonthlyReducer.qualityFlag(bucket(10, 1, 1, 10, 10, 3, 1)));

        // rien a signaler
        assertEquals("ok",
                MonthlyReducer.qualityFlag(bucket(10, 1, 1, 10, 10, 0, 1)));
    }

    @Test
    public void coverageIsPricedOverObserved() {
        // 9 creneaux tarifes sur 10 observes -> 0.900000
        DailyMetrics m = bucket(5.0, 1.0, 0.5, 10, 9, 0, 1);

        assertEquals(
                "MAC000002,2013-03,ToU,5.000000,0.500000,0.900000,1.000000,1,partial_tariff,mr2-test",
                MonthlyReducer.outputLine("MAC000002", "2013-03", "ToU", m, "mr2-test"));
    }
}