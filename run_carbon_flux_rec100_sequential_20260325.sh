#!/usr/bin/env bash
set -euo pipefail

PYTHON="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
BASE="/home/xulc/flash_drought/process"

run_job() {
  local script="$1"
  local log="$2"
  echo "[$(date '+%F %T')] START ${script}"
  "${PYTHON}" "${script}" > "${log}" 2>&1
  echo "[$(date '+%F %T')] DONE  ${script}"
}

run_job \
  "${BASE}/NEE-draught-analysis/code1SMrz/run_nee_analysis_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "${BASE}/NEE-draught-analysis/code1SMrz/results/run_nee_analysis_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"

run_job \
  "${BASE}/NEE-draught-analysis/code2SMs/run_nee_analysis_SMs_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "${BASE}/NEE-draught-analysis/code2SMs/results/run_nee_analysis_SMs_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"

run_job \
  "${BASE}/NEE-draught-analysis/code3_nonflash_SMrz/run_nee_analysis_nonflash_SMrz_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "${BASE}/NEE-draught-analysis/code3_nonflash_SMrz/results/run_nee_analysis_nonflash_SMrz_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"

run_job \
  "${BASE}/NEE-draught-analysis/code4_nonflash_SMs/run_nee_analysis_nonflash_SMs_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "${BASE}/NEE-draught-analysis/code4_nonflash_SMs/results/run_nee_analysis_nonflash_SMs_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"

run_job \
  "${BASE}/RECO-draught-analysis/code1/run_reco_analysis_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "${BASE}/RECO-draught-analysis/code1/results/run_reco_analysis_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"

run_job \
  "${BASE}/RECO-draught-analysis/code2_SMs/run_reco_analysis_SMs_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "${BASE}/RECO-draught-analysis/code2_SMs/results/run_reco_analysis_SMs_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"

run_job \
  "${BASE}/RECO-draught-analysis/code3_nonflash_SMrz/run_reco_analysis_nonflash_SMrz_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "${BASE}/RECO-draught-analysis/code3_nonflash_SMrz/results/run_reco_analysis_nonflash_SMrz_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"

run_job \
  "${BASE}/RECO-draught-analysis/code4_nonflash_SMs/run_reco_analysis_nonflash_SMs_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "${BASE}/RECO-draught-analysis/code4_nonflash_SMs/results/run_reco_analysis_nonflash_SMs_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.log"
