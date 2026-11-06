package tn.isima.energy.job1;

/**
 * Parses one CSV line of CC_LCL-FullData.csv:
 *    LCLid,stdorToU,DateTime,KWH/hh (per half hour)
 *
 * Rules (frozen in Phase 1):
 *  - value "Null" or empty  -> MISSING (never counted as 0.0)
 *  - value < 0              -> NEGATIVE (defensive, dataset has none)
 *  - timestamp not ISO-like -> MALFORMED
 *  - first field "LCLid"    -> HEADER
 * The date key is the first 10 characters of the timestamp (attribution rule A).
 */
public final class LineParser {

    public enum Status { OK, HEADER, MISSING, MALFORMED, NEGATIVE }

    public static final class Result {
        private final Status status;
        private final Reading reading;

        private Result(Status status, Reading reading) {
            this.status = status;
            this.reading = reading;
        }

        static Result of(Status s)            { return new Result(s, null); }
        static Result ok(Reading r)           { return new Result(Status.OK, r); }

        public Status getStatus()   { return status; }
        public Reading getReading() { return reading; }
    }

    private LineParser() { }

    public static Result parse(String line) {
        if (line == null) return Result.of(Status.MALFORMED);

        String clean = line;
        if (!clean.isEmpty() && clean.charAt(0) == '\uFEFF') clean = clean.substring(1);
        if (clean.trim().isEmpty()) return Result.of(Status.MALFORMED);

        String[] f = clean.split(",", -1);
        if (f.length != 4) return Result.of(Status.MALFORMED);

        String id = f[0].trim();
        String ts = f[2].trim();
        if (id.isEmpty() || "LCLid".equals(id)) return Result.of(Status.HEADER);
        if (!isIsoTimestamp(ts)) return Result.of(Status.MALFORMED);

        String raw = f[3].trim();
        if (raw.isEmpty() || "null".equalsIgnoreCase(raw)) return Result.of(Status.MISSING);

        double kwh;
        try {
            kwh = Double.parseDouble(raw);
        } catch (NumberFormatException e) {
            return Result.of(Status.MALFORMED);
        }
        if (Double.isNaN(kwh) || Double.isInfinite(kwh)) return Result.of(Status.MALFORMED);
        if (kwh < 0.0) return Result.of(Status.NEGATIVE);

        return Result.ok(new Reading(id, ts, ts.substring(0, 10), kwh));
    }

    /** yyyy-MM-dd HH:mm:ss(.fffffff) */
    private static boolean isIsoTimestamp(String ts) {
        return ts.length() >= 19
                && ts.charAt(4) == '-' && ts.charAt(7) == '-'
                && ts.charAt(10) == ' '
                && ts.charAt(13) == ':' && ts.charAt(16) == ':';
    }

    /** true when the reading sits on the 30-minute grid (:00 or :30, seconds 00). */
    public static boolean isOnGrid(String ts) {
        if (ts == null || ts.length() < 19) return false;
        String mm = ts.substring(14, 16);
        String ss = ts.substring(17, 19);
        return ("00".equals(mm) || "30".equals(mm)) && "00".equals(ss);
    }

    public static String groupKey(String householdId, String date) {
        return householdId + "|" + date;
    }
}