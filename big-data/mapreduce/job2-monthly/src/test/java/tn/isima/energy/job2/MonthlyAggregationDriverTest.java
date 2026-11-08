package tn.isima.energy.job2;

import org.apache.hadoop.conf.Configuration;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import org.junit.Test;

/**
 * Teste uniquement la resolution du run_id (le reste demande un cluster).
 */
public class MonthlyAggregationDriverTest {

    @Test
    public void generatesUtcRunIdWhenAbsent() {
        Configuration conf = new Configuration();

        String runId = MonthlyAggregationDriver.resolveRunId(conf);

        // mr2-20261108T182834Z
        assertTrue("format inattendu : " + runId,
                runId.matches("mr2-\\d{8}T\\d{6}Z"));
    }

    @Test
    public void usesExplicitRunIdWhenProvided() {
        Configuration conf = new Configuration();
        conf.set("p08.run_id", "  mr2-test  ");

        assertEquals("mr2-test", MonthlyAggregationDriver.resolveRunId(conf));
    }
        @Test
    public void dropsTheClassNameAddedToTheCommandLine() {
        String[] rest = MonthlyAggregationDriver.normalizeArgs(new String[] {
                "tn.isima.energy.job2.MonthlyAggregationDriver",
                "/p08/test/mr1_daily/mr1_test.tsv",
                "/p08/gold/mr2_monthly_test",
                "/p08/raw/tariffs/tariffs_2013_price.csv" });

        assertEquals(3, rest.length);
        assertEquals("/p08/test/mr1_daily/mr1_test.tsv", rest[0]);
        assertEquals("/p08/gold/mr2_monthly_test", rest[1]);
        assertEquals("/p08/raw/tariffs/tariffs_2013_price.csv", rest[2]);
    }

    @Test
    public void keepsThreeArgumentsUntouched() {
        String[] rest = MonthlyAggregationDriver.normalizeArgs(new String[] {
                "in", "out", "tariffs.csv" });

        assertEquals(3, rest.length);
        assertEquals("in", rest[0]);
        assertEquals("out", rest[1]);
        assertEquals("tariffs.csv", rest[2]);
    }
}