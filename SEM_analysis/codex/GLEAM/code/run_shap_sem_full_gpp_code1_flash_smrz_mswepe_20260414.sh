#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code"

echo "[$(date '+%F %T')] MSWEPE_PIPELINE_START"
bash "$SCRIPT_DIR/run_shap_sem_scope_split_gpp_code1_flash_smrz_mswepe_20260414.sh"
echo "[$(date '+%F %T')] MSWEPE_SCOPE_DONE"
bash "$SCRIPT_DIR/run_sem_candidates_gpp_code1_flash_smrz_mswepe_process_all_biomes_20260414.sh"
echo "[$(date '+%F %T')] MSWEPE_PIPELINE_DONE"
