#!/bin/bash
set -euo pipefail

BASE_DIR="/home/xulc/flash_drought"
PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
LOG_DIR="${BASE_DIR}/process/fluxsat-draught-analysis/results"

mkdir -p "${LOG_DIR}"

declare -A COMMANDS=(
  [fluxsat_0401_rec100cap_smrz]="${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code1/run_fluxsat_analysis_SMrz_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap.py"
  [fluxsat_0401_rec100cap_sms]="${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/run_fluxsat_analysis_SMs_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap.py"
  [fluxsat_0401_rec120cap_smrz]="${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code1/run_fluxsat_analysis_SMrz_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap.py"
  [fluxsat_0401_rec120cap_sms]="${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/run_fluxsat_analysis_SMs_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec120cap.py"
  [fluxsat_0401_rec100cap_gs07_smrz]="${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code1/run_fluxsat_analysis_SMrz_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07.py"
  [fluxsat_0401_rec100cap_gs07_sms]="${PYTHON_BIN} ${BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/run_fluxsat_analysis_SMs_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_gsfrac07.py"
)

for session in "${!COMMANDS[@]}"; do
  if tmux has-session -t "${session}" 2>/dev/null; then
    echo "SKIP ${session}: already running"
    continue
  fi
  log_file="${LOG_DIR}/${session}.log"
  tmux new-session -d -s "${session}" "cd ${BASE_DIR} && ${COMMANDS[$session]} >> ${log_file} 2>&1"
  echo "START ${session}"
done

echo "tmux ls"
tmux ls || true
