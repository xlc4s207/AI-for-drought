#!/usr/bin/env bash
set -euo pipefail

BASE="/home/xulc/flash_drought"
MAMBA_EXE="/home/xulc/.local/bin/micromamba"
MASTER_LOG="$BASE/process/era5_remaining_11_seq_20260330.log"

mkdir -p "$BASE/process"
: > "$MASTER_LOG"

# shellcheck disable=SC1090
source <("$MAMBA_EXE" shell hook -s bash)
micromamba activate Flash_dra

run_task() {
  local label="$1"
  local script="$2"
  local log_file="$3"
  echo "[$(date '+%F %T %Z')] START $label" | tee -a "$MASTER_LOG"
  python "$script" 2>&1 | tee "$log_file"
  local rc=${PIPESTATUS[0]}
  echo "[$(date '+%F %T %Z')] END   $label rc=$rc" | tee -a "$MASTER_LOG"
  return "$rc"
}

run_task "NEE code1 ERA5 root flash" \
  "$BASE/process/NEE-draught-analysis/code1_ERA5_root/run_nee_analysis_SMrz_ERA5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "$BASE/process/NEE-draught-analysis/code1_ERA5_root/result/run_era5_nee_code1.log"
run_task "RECO code1 ERA5 root flash" \
  "$BASE/process/RECO-draught-analysis/code1_ERA5_root/run_reco_analysis_SMrz_ERA5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "$BASE/process/RECO-draught-analysis/code1_ERA5_root/results/run_era5_reco_code1.log"
run_task "GPP code2 ERA5 swvl1 flash" \
  "$BASE/process/GPP-draught-analysis/code2_ERA5_swvl1/run_gpp_analysis_SMs_ERA5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "$BASE/process/GPP-draught-analysis/code2_ERA5_swvl1/results/run_era5_gpp_code2.log"
run_task "NEE code2 ERA5 swvl1 flash" \
  "$BASE/process/NEE-draught-analysis/code2_ERA5_swvl1/run_nee_analysis_SMs_ERA5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "$BASE/process/NEE-draught-analysis/code2_ERA5_swvl1/result/run_era5_nee_code2.log"
run_task "RECO code2 ERA5 swvl1 flash" \
  "$BASE/process/RECO-draught-analysis/code2_ERA5_swvl1/run_reco_analysis_SMs_ERA5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "$BASE/process/RECO-draught-analysis/code2_ERA5_swvl1/results/run_era5_reco_code2.log"
run_task "GPP code3 ERA5 root slow" \
  "$BASE/process/GPP-draught-analysis/code3_ERA5_root_nonflash/run_gpp_analysis_nonflash_SMrz_ERA5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "$BASE/process/GPP-draught-analysis/code3_ERA5_root_nonflash/result/run_era5_gpp_code3.log"
run_task "GPP code4 ERA5 swvl1 slow" \
  "$BASE/process/GPP-draught-analysis/code4_ERA5_swvl1_nonflash/run_gpp_analysis_nonflash_SMs_ERA5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "$BASE/process/GPP-draught-analysis/code4_ERA5_swvl1_nonflash/result/run_era5_gpp_code4.log"
run_task "NEE code3 ERA5 root slow" \
  "$BASE/process/NEE-draught-analysis/code3_ERA5_root_nonflash/run_nee_analysis_nonflash_SMrz_ERA5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "$BASE/process/NEE-draught-analysis/code3_ERA5_root_nonflash/result/run_era5_nee_code3.log"
run_task "NEE code4 ERA5 swvl1 slow" \
  "$BASE/process/NEE-draught-analysis/code4_ERA5_swvl1_nonflash/run_nee_analysis_nonflash_SMs_ERA5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "$BASE/process/NEE-draught-analysis/code4_ERA5_swvl1_nonflash/result/run_era5_nee_code4.log"
run_task "RECO code3 ERA5 root slow" \
  "$BASE/process/RECO-draught-analysis/code3_ERA5_root_nonflash/run_reco_analysis_nonflash_SMrz_ERA5_root_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "$BASE/process/RECO-draught-analysis/code3_ERA5_root_nonflash/result/run_era5_reco_code3.log"
run_task "RECO code4 ERA5 swvl1 slow" \
  "$BASE/process/RECO-draught-analysis/code4_ERA5_swvl1_nonflash/run_reco_analysis_nonflash_SMs_ERA5_swvl1_v20260330_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.py" \
  "$BASE/process/RECO-draught-analysis/code4_ERA5_swvl1_nonflash/result/run_era5_reco_code4.log"

echo "[$(date '+%F %T %Z')] ALL_DONE" | tee -a "$MASTER_LOG"
