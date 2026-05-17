#!/usr/bin/env bash

set -uo pipefail

WATCH_PATTERN='run_gpp_analysis_SMrz_v11_global_with_abs.py'
MASTER_LOG='/home/xulc/flash_drought/process/run_after_gpp_v11_then_nee_reco_v20260319_restart.log'

run_one() {
  local name="$1"
  local script_path="$2"
  local log_path="$3"

  mkdir -p "$(dirname "$log_path")"

  {
    printf '[%s] START %s\n' "$(date '+%F %T')" "$name"
    printf '[%s] SCRIPT %s\n' "$(date '+%F %T')" "$script_path"
    printf '[%s] LOG %s\n' "$(date '+%F %T')" "$log_path"
  } | tee -a "$MASTER_LOG"

  bash -lc "eval \"\$(micromamba shell hook --shell bash)\" && micromamba activate Flash_dra && python -u '$script_path' > '$log_path' 2>&1"
  rc=$?

  printf '[%s] END %s rc=%s\n' "$(date '+%F %T')" "$name" "$rc" | tee -a "$MASTER_LOG"
  if [ "$rc" -ne 0 ]; then
    printf '[%s] STOP queue because %s failed\n' "$(date '+%F %T')" "$name" | tee -a "$MASTER_LOG"
  fi
  return "$rc"
}

printf '[%s] WATCHING %s\n' "$(date '+%F %T')" "$WATCH_PATTERN" | tee -a "$MASTER_LOG"

while pgrep -af "$WATCH_PATTERN" >/dev/null 2>&1; do
  printf '[%s] WAIT current GPP v11 with_abs still running\n' "$(date '+%F %T')" | tee -a "$MASTER_LOG"
  sleep 60
done

printf '[%s] DETECT current GPP v11 with_abs finished, starting queue\n' "$(date '+%F %T')" | tee -a "$MASTER_LOG"

run_one \
  "nee_code1" \
  "/home/xulc/flash_drought/process/NEE-draught-analysis/code1SMrz/run_nee_analysis_v20260316.py" \
  "/home/xulc/flash_drought/process/NEE-draught-analysis/code1SMrz/results/nee_code1_v20260316_restart_20260319.log" || exit $?

run_one \
  "nee_code2" \
  "/home/xulc/flash_drought/process/NEE-draught-analysis/code2SMs/run_nee_analysis_SMs_v20260316.py" \
  "/home/xulc/flash_drought/process/NEE-draught-analysis/code2SMs/results/nee_code2_v20260316_restart_20260319.log" || exit $?

run_one \
  "nee_code3" \
  "/home/xulc/flash_drought/process/NEE-draught-analysis/code3_nonflash_SMrz/run_nee_analysis_nonflash_SMrz_v20260316.py" \
  "/home/xulc/flash_drought/process/NEE-draught-analysis/code3_nonflash_SMrz/results/nee_code3_v20260316_restart_20260319.log" || exit $?

run_one \
  "nee_code4" \
  "/home/xulc/flash_drought/process/NEE-draught-analysis/code4_nonflash_SMs/run_nee_analysis_nonflash_SMs_v20260316.py" \
  "/home/xulc/flash_drought/process/NEE-draught-analysis/code4_nonflash_SMs/results/nee_code4_v20260316_restart_20260319.log" || exit $?

run_one \
  "reco_code1" \
  "/home/xulc/flash_drought/process/RECO-draught-analysis/code1/run_reco_analysis_v20260316.py" \
  "/home/xulc/flash_drought/process/RECO-draught-analysis/code1/results/reco_code1_v20260316_restart_20260319.log" || exit $?

run_one \
  "reco_code2" \
  "/home/xulc/flash_drought/process/RECO-draught-analysis/code2_SMs/run_reco_analysis_SMs_v20260316.py" \
  "/home/xulc/flash_drought/process/RECO-draught-analysis/code2_SMs/results/reco_code2_v20260316_restart_20260319.log" || exit $?

run_one \
  "reco_code3" \
  "/home/xulc/flash_drought/process/RECO-draught-analysis/code3_nonflash_SMrz/run_reco_analysis_nonflash_SMrz_v20260316.py" \
  "/home/xulc/flash_drought/process/RECO-draught-analysis/code3_nonflash_SMrz/results/reco_code3_v20260316_restart_20260319.log" || exit $?

run_one \
  "reco_code4" \
  "/home/xulc/flash_drought/process/RECO-draught-analysis/code4_nonflash_SMs/run_reco_analysis_nonflash_SMs_v20260316.py" \
  "/home/xulc/flash_drought/process/RECO-draught-analysis/code4_nonflash_SMs/results/reco_code4_v20260316_restart_20260319.log" || exit $?

printf '[%s] ALL_DONE\n' "$(date '+%F %T')" | tee -a "$MASTER_LOG"
