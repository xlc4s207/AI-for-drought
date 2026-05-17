#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
BASE_DIR="/home/xulc/flash_drought/process/fluxsat-draught-analysis"
MONTHLY_OUT="${BASE_DIR}/preprocess/results/monthly_025deg_fixlon_v20260426"
MERGED_OUT="${BASE_DIR}/preprocess/results/FluxSat_GPP_2000_2019_0.25deg_fixlon_v20260426.nc"
REPORT_OUT="${BASE_DIR}/analysis/fluxsat_monthly_inventory_2000_2019_fixlon_v20260426.md"
RESAMPLE_JOBS="${FLUXSAT_FIXLON_RESAMPLE_JOBS:-4}"
SMRZ_LOG="${BASE_DIR}/results/fluxsat_fixlon_v20260426_smrz.log"
SMS_LOG="${BASE_DIR}/results/fluxsat_fixlon_v20260426_sms.log"

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

log "Step 1/4: resample monthly FluxSat to 0.25 degree with ${RESAMPLE_JOBS} workers"
"$PYTHON_BIN" "$BASE_DIR/preprocess/resample_fluxsat_monthly_to_025deg.py" \
  --output-dir "$MONTHLY_OUT" \
  --jobs "$RESAMPLE_JOBS" \
  --force

log "Step 2/4: merge fixed-longitude monthly files"
"$PYTHON_BIN" "$BASE_DIR/preprocess/merge_fluxsat_monthly_025deg_daily.py" \
  --input-dir "$MONTHLY_OUT" \
  --output-path "$MERGED_OUT" \
  --report-path "$REPORT_OUT" \
  --force

log "Step 3/4: run SMrz rec100cap fixlon analysis"
"$PYTHON_BIN" \
  "$BASE_DIR/code1/run_fluxsat_analysis_SMrz_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426.py" \
  | tee "$SMRZ_LOG"

log "Step 4/4: run SMs rec100cap fixlon analysis"
"$PYTHON_BIN" \
  "$BASE_DIR/code2_SMs/run_fluxsat_analysis_SMs_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426.py" \
  | tee "$SMS_LOG"

log "FluxSat fixlon v20260426 pipeline completed"
