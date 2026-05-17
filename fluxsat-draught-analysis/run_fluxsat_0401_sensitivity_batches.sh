#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/home/xulc/flash_drought"
PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
LOG_DIR="${BASE_DIR}/process/fluxsat-draught-analysis/results"

mkdir -p "${LOG_DIR}"

run_pair() {
  local name1="$1"
  local cmd1="$2"
  local log1="${LOG_DIR}/${name1}.log"
  local name2="$3"
  local cmd2="$4"
  local log2="${LOG_DIR}/${name2}.log"

  echo "[$(date '+%F %T')] START ${name1}"
  echo "[$(date '+%F %T')] START ${name2}"
  (
    cd "${BASE_DIR}"
    exec ${cmd1}
  ) >> "${log1}" 2>&1 &
  pid1=$!
  (
    cd "${BASE_DIR}"
    exec ${cmd2}
  ) >> "${log2}" 2>&1 &
  pid2=$!

  wait "${pid1}"
  status1=$?
  wait "${pid2}"
  status2=$?

  echo "[$(date '+%F %T')] DONE ${name1} status=${status1}"
  echo "[$(date '+%F %T')] DONE ${name2} status=${status2}"

  if [ "${status1}" -ne 0 ] || [ "${status2}" -ne 0 ]; then
    echo "Batch failed: ${name1}=${status1}, ${name2}=${status2}" >&2
    exit 1
  fi
}

run_pair \
  "fluxsat_0401_rec100cap_smrz" \
  "${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code1/run_fluxsat_analysis_SMrz_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap.py" \
  "fluxsat_0401_rec100cap_sms" \
  "${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/run_fluxsat_analysis_SMs_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap.py"

run_pair \
  "fluxsat_0401_rec120cap_smrz" \
  "${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code1/run_fluxsat_analysis_SMrz_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap.py" \
  "fluxsat_0401_rec120cap_sms" \
  "${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/run_fluxsat_analysis_SMs_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap.py"

run_pair \
  "fluxsat_0401_rec100cap_gs07_smrz" \
  "${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code1/run_fluxsat_analysis_SMrz_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07.py" \
  "fluxsat_0401_rec100cap_gs07_sms" \
  "${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/run_fluxsat_analysis_SMs_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07.py"
