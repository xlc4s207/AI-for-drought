#!/usr/bin/env bash
set -euo pipefail

PYTHON="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
BASE="/home/xulc/flash_drought"
LOG_DIR="$BASE/process/logs"
mkdir -p "$LOG_DIR"

timestamp() {
  date '+%F %T'
}

run_job() {
  local name="$1"
  local script_path="$2"
  local log_path="$3"

  echo "[$(timestamp)] START $name"
  echo "[$(timestamp)] SCRIPT $script_path"
  "$PYTHON" "$script_path" 2>&1 | tee "$log_path"
  echo "[$(timestamp)] END $name"
}

run_job \
  "GPP_code2_SMs_v20260401_gsdays" \
  "$BASE/process/GPP-draught-analysis/code2_SMs/run_gpp_analysis_SMs_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.py" \
  "$LOG_DIR/gpp_code2_v20260401_growingseason_recovery_gsdays.log"

run_job \
  "NEE_code1_SMrz_v20260401_gsdays" \
  "$BASE/process/NEE-draught-analysis/code1SMrz/run_nee_analysis_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.py" \
  "$LOG_DIR/nee_code1_v20260401_growingseason_recovery_gsdays.log"

run_job \
  "NEE_code2_SMs_v20260401_gsdays" \
  "$BASE/process/NEE-draught-analysis/code2SMs/run_nee_analysis_SMs_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.py" \
  "$LOG_DIR/nee_code2_v20260401_growingseason_recovery_gsdays.log"

run_job \
  "RECO_code1_SMrz_v20260401_gsdays" \
  "$BASE/process/RECO-draught-analysis/code1/run_reco_analysis_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.py" \
  "$LOG_DIR/reco_code1_v20260401_growingseason_recovery_gsdays.log"

run_job \
  "RECO_code2_SMs_v20260401_gsdays" \
  "$BASE/process/RECO-draught-analysis/code2_SMs/run_reco_analysis_SMs_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.py" \
  "$LOG_DIR/reco_code2_v20260401_growingseason_recovery_gsdays.log"

echo "[$(timestamp)] ALL_DONE"
