#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
BASE_DIR="/home/xulc/flash_drought"
LOG_DIR="${BASE_DIR}/process/logs"
RUN_TS="$(date +%Y%m%d_%H%M%S)"
MASTER_LOG="${LOG_DIR}/run_peakctrl_sequential_${RUN_TS}.log"

mkdir -p "${LOG_DIR}"

run_one() {
  local script_path="$1"
  local step_name="$2"
  local step_log="${LOG_DIR}/${step_name}_${RUN_TS}.log"

  echo "[$(date '+%F %T')] START ${step_name}" | tee -a "${MASTER_LOG}"
  echo "[$(date '+%F %T')] SCRIPT ${script_path}" | tee -a "${MASTER_LOG}"
  "${PYTHON_BIN}" "${script_path}" >"${step_log}" 2>&1
  echo "[$(date '+%F %T')] DONE  ${step_name}" | tee -a "${MASTER_LOG}"
  echo "[$(date '+%F %T')] LOG   ${step_log}" | tee -a "${MASTER_LOG}"
}

echo "[$(date '+%F %T')] Sequential peakctrl run started." | tee -a "${MASTER_LOG}"
echo "[$(date '+%F %T')] Master log: ${MASTER_LOG}" | tee -a "${MASTER_LOG}"

# GPP (code1 already run before this batch; skip it here)
run_one "${BASE_DIR}/process/GPP-draught-analysis/code2_SMs/run_gpp_analysis_SMs_v20260322_lu_025deg_peakctrl.py" "gpp_code2_peakctrl"
run_one "${BASE_DIR}/process/GPP-draught-analysis/code3_nonflash_SMrz/run_gpp_analysis_nonflash_SMrz_v20260322_lu_025deg_peakctrl.py" "gpp_code3_peakctrl"
run_one "${BASE_DIR}/process/GPP-draught-analysis/code4_nonflash_SMs/run_gpp_analysis_nonflash_SMs_v20260322_lu_025deg_peakctrl.py" "gpp_code4_peakctrl"

# NEE
run_one "${BASE_DIR}/process/NEE-draught-analysis/code1SMrz/run_nee_analysis_v20260322_lu_025deg_peakctrl.py" "nee_code1_peakctrl"
run_one "${BASE_DIR}/process/NEE-draught-analysis/code2SMs/run_nee_analysis_SMs_v20260322_lu_025deg_peakctrl.py" "nee_code2_peakctrl"
run_one "${BASE_DIR}/process/NEE-draught-analysis/code3_nonflash_SMrz/run_nee_analysis_nonflash_SMrz_v20260322_lu_025deg_peakctrl.py" "nee_code3_peakctrl"
run_one "${BASE_DIR}/process/NEE-draught-analysis/code4_nonflash_SMs/run_nee_analysis_nonflash_SMs_v20260322_lu_025deg_peakctrl.py" "nee_code4_peakctrl"

# RECO
run_one "${BASE_DIR}/process/RECO-draught-analysis/code1/run_reco_analysis_v20260322_lu_025deg_peakctrl.py" "reco_code1_peakctrl"
run_one "${BASE_DIR}/process/RECO-draught-analysis/code2_SMs/run_reco_analysis_SMs_v20260322_lu_025deg_peakctrl.py" "reco_code2_peakctrl"
run_one "${BASE_DIR}/process/RECO-draught-analysis/code3_nonflash_SMrz/run_reco_analysis_nonflash_SMrz_v20260322_lu_025deg_peakctrl.py" "reco_code3_peakctrl"
run_one "${BASE_DIR}/process/RECO-draught-analysis/code4_nonflash_SMs/run_reco_analysis_nonflash_SMs_v20260322_lu_025deg_peakctrl.py" "reco_code4_peakctrl"

echo "[$(date '+%F %T')] All sequential peakctrl tasks finished." | tee -a "${MASTER_LOG}"
