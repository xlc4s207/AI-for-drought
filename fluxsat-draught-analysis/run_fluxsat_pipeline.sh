#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
BASE_DIR="/home/xulc/flash_drought/process/fluxsat-draught-analysis"
FLUXSAT_RESAMPLE_JOBS="${FLUXSAT_RESAMPLE_JOBS:-4}"

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

log "Step 1/5: resample monthly FluxSat to 0.25 degree with ${FLUXSAT_RESAMPLE_JOBS} workers"
"$PYTHON_BIN" "$BASE_DIR/preprocess/resample_fluxsat_monthly_to_025deg.py" --jobs "$FLUXSAT_RESAMPLE_JOBS"

log "Step 2/5: merge monthly 0.25 degree files"
"$PYTHON_BIN" "$BASE_DIR/preprocess/merge_fluxsat_monthly_025deg_daily.py" --force

log "Step 3/5: diagnose merged FluxSat preprocessing outputs"
"$PYTHON_BIN" "$BASE_DIR/preprocess/diagnose_fluxsat_preprocessing.py"

log "Step 4/5: run FluxSat drought analyses"
"$PYTHON_BIN" "$BASE_DIR/code1/run_fluxsat_analysis_SMrz_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.py"
"$PYTHON_BIN" "$BASE_DIR/code2_SMs/run_fluxsat_analysis_SMs_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.py"

log "Step 5/5: build FluxSat vs BESS summary"
"$PYTHON_BIN" "$BASE_DIR/results/build_fluxsat_vs_bess_2000_2019_comparison.py"

log "Pipeline completed"
