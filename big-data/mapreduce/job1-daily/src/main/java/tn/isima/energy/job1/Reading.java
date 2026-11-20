package tn.isima.energy.job1;

/** One validated 30-minute electricity reading. Immutable. */
public final class Reading {

    private final String householdId;
    private final String tariffGroup;
    private final String timestamp;
    private final String localDate;
    private final int localSlot;
    private final double kwh;

    public Reading(String householdId, String tariffGroup, String timestamp,
                   String localDate, int localSlot, double kwh) {
        this.householdId = householdId;
        this.tariffGroup = tariffGroup;
        this.timestamp = timestamp;
        this.localDate = localDate;
        this.localSlot = localSlot;
        this.kwh = kwh;
    }

    public String getHouseholdId() { return householdId; }
    public String getTariffGroup() { return tariffGroup; }

    /** Raw UTC timestamp, kept verbatim so duplicate detection stays exact. */
    public String getTimestamp()   { return timestamp; }

    /** Local (Europe/London) calendar date, yyyy-MM-dd. */
    public String getLocalDate()   { return localDate; }

    /** Local clock slot, 0..47. */
    public int getLocalSlot()      { return localSlot; }

    public double getKwh()         { return kwh; }
}
