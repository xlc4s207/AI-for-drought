#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"
SUMMARY_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/12_summarize_candidate_models.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_merged_RECO_code1_flash_SMrz_mswepE.parquet"
SHAP_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_dedup_wind_lai_r2"
SPEC_DIR="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_reco_r2boost_stage1_20260415"
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
  run_model "$biome" "DPT_L4" "$SPEC_DIR/reco_code1_flash_smrz_recoverywin_dewpoint_delta_v20260415.txt"
  run_model "$biome" "DPT_L3" "$SPEC_DIR/reco_code1_flash_smrz_recoverywin_dewpoint_delta_l3_v20260415.txt"
  run_model "$biome" "VPD_L4" "$SPEC_DIR/reco_code1_flash_smrz_recoverywin_vpd_delta_v20260415.txt"
  run_model "$biome" "VPD_L3" "$SPEC_DIR/reco_code1_flash_smrz_recoverywin_vpd_delta_l3_v20260415.txt"
}

run_biome_models "Forest"
run_biome_models "Grassland"
run_biome_models "Savanna"
run_biome_models "Cropland"
run_biome_models "Shrubland"
run_biome_models "Wetland"

"$PYTHON_BIN" "$SUMMARY_SCRIPT" \
  --result-root "$RESULT_ROOT" \
  --output-csv "$RESULT_ROOT/candidate_model_summary.csv" \
  --output-md "$RESULT_ROOT/candidate_model_summary.md" >"$LOG_DIR/candidate_summary.log" 2>&1

echo "[DONE] RECO Stage 1 SEM candidate models saved under $RESULT_ROOT"
