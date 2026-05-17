#!/bin/bash
# Quick progress check for FluxSat preprocessing

echo "=== FluxSat Merge Progress ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check running process
PROC=$(ps aux | grep "merge_fluxsat_monthly_daily.py" | grep -v grep)
if [ -n "$PROC" ]; then
    echo "✓ Merge process RUNNING"
    echo "$PROC" | awk '{printf "  PID: %s, CPU: %s%%, MEM: %s%%, Runtime: %s\n", $2, $3, $4, $10}'
else
    echo "✗ No merge process running"
fi
echo ""

# Check output file
OUTPUT="/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results/FluxSat_GPP_2000_2019_daily_005deg.nc"
if [ -f "$OUTPUT" ]; then
    SIZE=$(du -h "$OUTPUT" | cut -f1)
    echo "Output file size: $SIZE"
    ls -lh "$OUTPUT"
else
    echo "Output file not yet created"
fi
echo ""

# Check log tail (filter getfattr noise)
LOG="/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results/merge_fluxsat_rerun.log"
if [ -f "$LOG" ]; then
    echo "--- Recent log (last 10 real lines) ---"
    grep -v "getfattr" "$LOG" | tail -10
fi
