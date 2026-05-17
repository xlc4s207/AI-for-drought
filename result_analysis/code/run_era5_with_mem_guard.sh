#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <entry_script.py> <label> [workers] [min_available_mb] [max_rss_mb]"
  exit 2
fi

ENTRY_SCRIPT="$1"
LABEL="$2"
WORKERS="${3:-8}"
MIN_AVAILABLE_MB="${4:-16000}"
MAX_RSS_MB="${5:-50000}"
CHECK_INTERVAL_SEC=20
PY="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python3.13"

if [[ ! -f "$ENTRY_SCRIPT" ]]; then
  echo "[ERROR] Entry script not found: $ENTRY_SCRIPT"
  exit 2
fi

LOG_DIR="/home/xulc/flash_drought/process/result_analysis/performance"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/${LABEL}_rerun_with_mem_guard_$(date +%Y%m%d_%H%M%S).log"

echo "[INFO] Start $LABEL with memory guard"
echo "[INFO] Entry: $ENTRY_SCRIPT"
echo "[INFO] Workers: $WORKERS"
echo "[INFO] Thresholds: MemAvailable >= ${MIN_AVAILABLE_MB}MB, RSS <= ${MAX_RSS_MB}MB"
echo "[INFO] Log: $LOG_FILE"

set +e
"$PY" "$ENTRY_SCRIPT" --workers "$WORKERS" >"$LOG_FILE" 2>&1 &
MAIN_PID=$!
set -e

echo "[INFO] Main PID: $MAIN_PID"

sum_rss_mb() {
  local pattern="$1"
  local pids
  pids="$(pgrep -f "$pattern" || true)"
  if [[ -z "$pids" ]]; then
    echo 0
    return
  fi
  ps -o rss= -p $pids | awk '{s+=$1} END {printf("%d\n", s/1024)}'
}

while kill -0 "$MAIN_PID" 2>/dev/null; do
  AVAILABLE_MB="$(awk '/MemAvailable:/ {printf("%d\n", $2/1024)}' /proc/meminfo)"
  RSS_MB="$(sum_rss_mb "${ENTRY_SCRIPT} --workers ${WORKERS}")"

  echo "[MON] $(date '+%F %T') avail=${AVAILABLE_MB}MB rss=${RSS_MB}MB"

  if [[ "$AVAILABLE_MB" -lt "$MIN_AVAILABLE_MB" ]]; then
    echo "[KILL] MemAvailable too low: ${AVAILABLE_MB}MB < ${MIN_AVAILABLE_MB}MB"
    pkill -f "${ENTRY_SCRIPT} --workers ${WORKERS}" || true
    wait "$MAIN_PID" || true
    exit 99
  fi

  if [[ "$RSS_MB" -gt "$MAX_RSS_MB" ]]; then
    echo "[KILL] Process RSS too high: ${RSS_MB}MB > ${MAX_RSS_MB}MB"
    pkill -f "${ENTRY_SCRIPT} --workers ${WORKERS}" || true
    wait "$MAIN_PID" || true
    exit 98
  fi

  sleep "$CHECK_INTERVAL_SEC"
done

wait "$MAIN_PID"
RC=$?
echo "[INFO] $LABEL finished with exit code $RC"
echo "[INFO] Log file: $LOG_FILE"
exit "$RC"

