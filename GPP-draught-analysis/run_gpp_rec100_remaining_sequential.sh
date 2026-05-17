#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
BASE_DIR="/home/xulc/flash_drought/process/GPP-draught-analysis"

"${PYTHON_BIN}" "${BASE_DIR}/code2_SMs/run_gpp_analysis_SMs_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  > "${BASE_DIR}/code2_SMs/results/run_gpp_analysis_SMs_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log" 2>&1

"${PYTHON_BIN}" "${BASE_DIR}/code3_nonflash_SMrz/run_gpp_analysis_nonflash_SMrz_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  > "${BASE_DIR}/code3_nonflash_SMrz/result/run_gpp_analysis_nonflash_SMrz_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log" 2>&1

"${PYTHON_BIN}" "${BASE_DIR}/code4_nonflash_SMs/run_gpp_analysis_nonflash_SMs_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  > "${BASE_DIR}/code4_nonflash_SMs/result/run_gpp_analysis_nonflash_SMs_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log" 2>&1
