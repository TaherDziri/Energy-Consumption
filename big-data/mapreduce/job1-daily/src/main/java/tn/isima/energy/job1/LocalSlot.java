package tn.isima.energy.job1;

import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;

/**
 * UTC -> Europe/London conversion for the daily contract v1.1.
 *
 * The raw DateTime column is UTC. A "day" in the contract is a LOCAL day,
 * and a slot is the local clock slot: slot = hour * 2 + minute / 30.
 *
 * DST consequences, computed from the timezone rules (never hardcoded):
 *   spring forward (last Sunday of March) -> 46 half-hours, slots 2 and 3 absent
 *   fall back      (last Sunday of October) -> 50 half-hours, slots 2 and 3 twice
 */
public final class LocalSlot {

    public static final ZoneId ZONE = ZoneId.of("Europe/London");

    private static final DateTimeFormatter UTC_FORMAT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private LocalSlot() { }

    /** Parses the raw UTC timestamp and returns it in Europe/London. */
    public static ZonedDateTime toLocal(String utcTimestamp) {
        return LocalDateTime.parse(utcTimestamp.substring(0, 19), UTC_FORMAT)
                .atZone(ZoneOffset.UTC)
                .withZoneSameInstant(ZONE);
    }

    /** Local calendar date as yyyy-MM-dd. */
    public static String localDate(String utcTimestamp) {
        return toLocal(utcTimestamp).toLocalDate().toString();
    }

    /** Local clock slot 0..47. On fall back, 01:00 and 01:30 both map to 2 and 3. */
    public static int slot(String utcTimestamp) {
        LocalDateTime local = toLocal(utcTimestamp).toLocalDateTime();
        return local.getHour() * 2 + local.getMinute() / 30;
    }

    /** Number of half-hours in a local day: 46, 48 or 50. */
    public static int expectedSlots(LocalDate date) {
        ZonedDateTime start = date.atStartOfDay(ZONE);
        ZonedDateTime next = date.plusDays(1).atStartOfDay(ZONE);
        long minutes = Duration.between(start, next).toMinutes();
        return (int) (minutes / 30);
    }
}
