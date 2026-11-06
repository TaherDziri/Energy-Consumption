"""
P08 - Phase 1 / STEP 7
Streaming profile of CC_LCL-FullData.csv (never loads the 8.5 GB in memory).

Usage:
    python profile_dataset.py            -> full file
    python profile_dataset.py 2000000    -> first 2,000,000 data rows (smoke test)
"""
import collections, sys, time

CSV_IN  = r"C:\dev\P08-Energy-Consumption\data\raw\CC_LCL-FullData.csv"
CSV_OUT = r"C:\dev\P08-Energy-Consumption\data\processed\household_profile.csv"

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 0   # 0 = no limit

t0 = time.time()
total = 0
bad_fields = n_empty = n_null = n_nonnum = n_neg = n_offgrid = n_dupes = 0
id_switches = 0
tariffs = collections.Counter()
ids = set()
min_ts = max_ts = None
grand_kwh = 0.0

per = {}          # household -> [rows, missing, first_ts, last_ts, kwh]
prev_id = None
seen_ts = set()   # timestamps of the CURRENT household only (memory-safe duplicate check)

with open(CSV_IN, "r", encoding="utf-8", errors="replace", newline="") as f:
    print("header:", f.readline().rstrip("\r\n"))

    for line in f:
        total += 1
        if total % 10_000_000 == 0:
            print("   ... {:,} rows  ({:.0f}s)".format(total, time.time() - t0), flush=True)

        parts = line.rstrip("\r\n").split(",")
        if len(parts) != 4:
            bad_fields += 1
            continue
        hid, tariff, ts, raw = parts
        ts = ts.strip()

        # household change -> flush duplicate-detection buffer
        if hid != prev_id:
            if prev_id is not None:
                id_switches += 1
            prev_id = hid
            seen_ts.clear()

        if ts in seen_ts:
            n_dupes += 1
        else:
            seen_ts.add(ts)

        if min_ts is None or ts < min_ts: min_ts = ts
        if max_ts is None or ts > max_ts: max_ts = ts

        # expected grid: HH in 00..23, minutes in {00,30}, seconds 00
        if len(ts) < 19 or ts[14:16] not in ("00", "30") or ts[17:19] != "00":
            n_offgrid += 1

        ids.add(hid)
        tariffs[tariff] += 1

        v = raw.strip()
        kwh = None
        if v == "":
            n_empty += 1
        elif v.lower() == "null":
            n_null += 1
        else:
            try:
                kwh = float(v)
                if kwh < 0:
                    n_neg += 1
                grand_kwh += kwh
            except ValueError:
                n_nonnum += 1

        p = per.get(hid)
        if p is None:
            p = [0, 0, ts, ts, 0.0]
            per[hid] = p
        p[0] += 1
        if kwh is None: p[1] += 1
        else:           p[4] += kwh
        if ts < p[2]: p[2] = ts
        if ts > p[3]: p[3] = ts

        if LIMIT and total >= LIMIT:
            print("   reached LIMIT", LIMIT)
            break

with open(CSV_OUT, "w", encoding="utf-8", newline="") as f:
    f.write("household_id,rows,missing,first_timestamp,last_timestamp,total_kwh\n")
    for hid in sorted(per):
        r = per[hid]
        f.write("{},{},{},{},{},{:.3f}\n".format(hid, r[0], r[1], r[2], r[3], r[4]))

missing_total = n_empty + n_null + n_nonnum
print("\n===== SUMMARY =====")
print("data rows                 : {:,}".format(total))
print("distinct households       : {:,}".format(len(ids)))
print("household blocks (switches):", id_switches)
print("first timestamp           :", min_ts)
print("last  timestamp           :", max_ts)
print("tariffs                   :", dict(tariffs))
print("rows with != 4 fields     : {:,}".format(bad_fields))
print("missing (Null)            : {:,}".format(n_null))
print("missing (empty)           : {:,}".format(n_empty))
print("non numeric               : {:,}".format(n_nonnum))
print("negative values           : {:,}".format(n_neg))
print("off-grid timestamps       : {:,}".format(n_offgrid))
print("duplicate (id,timestamp)  : {:,}".format(n_dupes))
print("total kWh                 : {:,.1f}".format(grand_kwh))
print("missing rate              : {:.3f} %".format(100.0 * missing_total / total if total else 0))
print("per-household profile     :", CSV_OUT)
print("elapsed                   : {:.0f} s".format(time.time() - t0))
