#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/home/xulc/flash_drought"
PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
MASTER_LOG="${BASE_DIR}/process/batch_logs/run_rel0_controls_sequential_v20260328.log"

mkdir -p "$(dirname "${MASTER_LOG}")"

run_one() {
    local script_path="$1"
    local log_path="$2"
    mkdir -p "$(dirname "${log_path}")"
    printf '[%s] START %s\n' "$(date '+%F %T')" "${script_path}" | tee -a "${MASTER_LOG}"
    env PYTHONUNBUFFERED=1 "${PYTHON_BIN}" "${script_path}" > "${log_path}" 2>&1
    printf '[%s] DONE  %s\n' "$(date '+%F %T')" "${script_path}" | tee -a "${MASTER_LOG}"
}

printf '[%s] BATCH START\n' "$(date '+%F %T')" | tee "${MASTER_LOG}"

run_one \
    "${BASE_DIR}/process/GPP-draught-analysis/code2_SMs/run_gpp_analysis_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
    "${BASE_DIR}/process/GPP-draught-analysis/code2_SMs/results/run_gpp_analysis_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"
run_one \
    "${BASE_DIR}/process/GPP-draught-analysis/code3_nonflash_SMrz/run_gpp_analysis_nonflash_SMrz_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
    "${BASE_DIR}/process/GPP-draught-analysis/code3_nonflash_SMrz/result/run_gpp_analysis_nonflash_SMrz_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"
run_one \
    "${BASE_DIR}/process/GPP-draught-analysis/code4_nonflash_SMs/run_gpp_analysis_nonflash_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
    "${BASE_DIR}/process/GPP-draught-analysis/code4_nonflash_SMs/result/run_gpp_analysis_nonflash_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"

run_one \
    "${BASE_DIR}/process/NEE-draught-analysis/code1SMrz/run_nee_analysis_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
    "${BASE_DIR}/process/NEE-draught-analysis/code1SMrz/result/run_nee_analysis_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"
run_one \
    "${BASE_DIR}/process/NEE-draught-analysis/code2SMs/run_nee_analysis_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
    "${BASE_DIR}/process/NEE-draught-analysis/code2SMs/result/run_nee_analysis_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"
run_one \
    "${BASE_DIR}/process/NEE-draught-analysis/code3_nonflash_SMrz/run_nee_analysis_nonflash_SMrz_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
    "${BASE_DIR}/process/NEE-draught-analysis/code3_nonflash_SMrz/result/run_nee_analysis_nonflash_SMrz_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"
run_one \
    "${BASE_DIR}/process/NEE-draught-analysis/code4_nonflash_SMs/run_nee_analysis_nonflash_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
    "${BASE_DIR}/process/NEE-draught-analysis/code4_nonflash_SMs/result/run_nee_analysis_nonflash_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"

run_one \
    "${BASE_DIR}/process/RECO-draught-analysis/code1/run_reco_analysis_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
    "${BASE_DIR}/process/RECO-draught-analysis/code1/results/run_reco_analysis_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"
run_one \
    "${BASE_DIR}/process/RECO-draught-analysis/code2_SMs/run_reco_analysis_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
    "${BASE_DIR}/process/RECO-draught-analysis/code2_SMs/results/run_reco_analysis_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"
run_one \
    "${BASE_DIR}/process/RECO-draught-analysis/code3_nonflash_SMrz/run_reco_analysis_nonflash_SMrz_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
    "${BASE_DIR}/process/RECO-draught-analysis/code3_nonflash_SMrz/result/run_reco_analysis_nonflash_SMrz_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"
run_one \
    "${BASE_DIR}/process/RECO-draught-analysis/code4_nonflash_SMs/run_reco_analysis_nonflash_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
    "${BASE_DIR}/process/RECO-draught-analysis/code4_nonflash_SMs/result/run_reco_analysis_nonflash_SMs_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"

printf '[%s] BATCH DONE\n' "$(date '+%F %T')" | tee -a "${MASTER_LOG}"
