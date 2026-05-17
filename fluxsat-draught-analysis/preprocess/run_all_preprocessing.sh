#!/bin/bash
set -euo pipefail

PYTHON="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
BASE_DIR="/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess"
RESULTS_DIR="${BASE_DIR}/results"

cd "${BASE_DIR}"

echo "=== Step 1: Merging monthly FluxSat files (2000-2019) ==="
"${PYTHON}" merge_fluxsat_monthly_daily.py 2>&1 | tee "${RESULTS_DIR}/01_merge.log"

echo "=== Step 2: Converting longitude to 0..360 ==="
"${PYTHON}" convert_fluxsat_lon_to_360.py 2>&1 | tee "${RESULTS_DIR}/02_convert_lon.log"

echo "=== Step 3: Resampling to 0.25 degree ==="
"${PYTHON}" resample_fluxsat_to_025deg.py 2>&1 | tee "${RESULTS_DIR}/03_resample.log"

echo "=== Step 4: Generating diagnostics ==="
"${PYTHON}" diagnose_fluxsat_preprocessing.py 2>&1 | tee "${RESULTS_DIR}/04_diagnostics.log"

echo "=== All preprocessing steps completed ==="
