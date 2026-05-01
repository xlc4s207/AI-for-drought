#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_recovery_phase_RECO_code1_flash_SMrz_mswepE.parquet"
SHAP_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_no_sum"
SPEC_DIR="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_reco_weighted4_compare_20260415"
LOG_DIR="$RESULT_ROOT/logs"

mkdir -p "$RESULT_ROOT" "$LOG_DIR"

run_model() {
  local biome="$1"
  local model_id="$2"
  local spec_file="$3"
  local out_dir="$RESULT_ROOT/$biome/$model_id"
  local log_file="$LOG_DIR/${biome}_${model_id}.log"
  mkdir -p "$out_dir"
  "$PYTHON_BIN" "$SEM_SCRIPT" \
    --table "$TABLE" \
    --shap-results "$SHAP_ROOT" \
    --model-spec-file "$spec_file" \
    --target "t_recover_to_baseline_abs_peak" \
    --feature-scope "process_recoverywin" \
    --metric RECO \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --output-dir "$out_dir" >"$log_file" 2>&1
}

run_biome_models() {
  local biome="$1"
  run_model "$biome" "DPT_WGT4" "$SPEC_DIR/reco_code1_flash_smrz_recoverywin_dewpoint_delta_weighted_v20260415.txt"
  run_model "$biome" "VPD_WGT4" "$SPEC_DIR/reco_code1_flash_smrz_recoverywin_vpd_delta_weighted_v20260415.txt"
}

run_biome_models "Forest"
run_biome_models "Grassland"
run_biome_models "Savanna"
run_biome_models "Cropland"
run_biome_models "Shrubland"
run_biome_models "Wetland"

echo "[DONE] RECO weighted4 SEM candidate models saved under $RESULT_ROOT"
