package tn.isima.energy.job1;

/** One validated 30-minute electricity reading. Immutable. */
public final class Reading {

    private final String householdId;
    private final String timestamp;
    private final String date;
    private final double kwh;

    public Reading(String householdId, String timestamp, String date, double kwh) {
        this.householdId = householdId;
        this.timestamp = timestamp;
        this.date = date;
        this.kwh = kwh;
    }

    public String getHouseholdId() { return householdId; }
    public String getTimestamp()   { return timestamp; }
    public String getDate()        { return date; }
    public double getKwh()         { return kwh; }
}