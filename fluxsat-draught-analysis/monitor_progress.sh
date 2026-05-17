#!/bin/bash
# FluxSat preprocessing progress monitor

RESULTS_DIR="/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results"

echo "=== FluxSat Preprocessing Progress Monitor ==="
echo "Time: $(date)"
echo ""

echo "--- Output Files ---"
ls -lh "${RESULTS_DIR}"/*.nc 2>/dev/null || echo "No .nc files yet"
echo ""

echo "--- Log Files ---"
ls -lh "${RESULTS_DIR}"/*.log 2>/dev/null || echo "No log files yet"
echo ""

echo "--- Running Processes ---"
ps aux | grep -E "(merge_fluxsat|convert_fluxsat|resample_fluxsat|diagnose_fluxsat)" | grep -v grep || echo "No FluxSat processes running"
echo ""

echo "--- Recent Log Tail (last 10 lines) ---"
for log in "${RESULTS_DIR}"/*.log; do
    if [ -f "$log" ]; then
        echo "==> $(basename $log)"
        tail -10 "$log"
        echo ""
    fi
done
