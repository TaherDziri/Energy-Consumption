#!/bin/bash
# Mesure F11 : execute MR2 sur un volume et imprime temps + compteurs.
# Usage (dans le conteneur) : run_f11.sh <label> <entree HDFS> <sortie HDFS>
# Le jar MR2 doit etre present dans le conteneur (/tmp), voir docs/00 etape 24.
set -u
VOL="$1"
INPUT="$2"
OUT="$3"
JAR="${JAR:-/tmp/job2-monthly-aggregation.jar}"
LOG="/tmp/f11_${VOL}.log"

hdfs dfs -rm -r -f "$OUT" >/dev/null 2>&1
S=$(date +%s%3N)
hadoop jar "$JAR" -D p08.run_id="f11-${VOL}" \
  "$INPUT" "$OUT" /p08/raw/tariffs/tariffs_2013_price.csv > "$LOG" 2>&1
RC=$?
E=$(date +%s%3N)

echo "===== VOLUME=$VOL RC=$RC WALL_MS=$((E - S)) LOG=$LOG"
grep -E "^(lines_read|lines_ok|lines_malformed|months_written|priced_slots|unpriced_slots|duplicate_slots|missing_slots_mismatch|flag_.*|elapsed_ms|run_id) =" "$LOG"
grep -E "Launched (map|reduce) tasks|Total time spent by all (map|reduce) tasks" "$LOG"
hdfs dfs -ls -h "$OUT" | grep -v "_SUCCESS"
