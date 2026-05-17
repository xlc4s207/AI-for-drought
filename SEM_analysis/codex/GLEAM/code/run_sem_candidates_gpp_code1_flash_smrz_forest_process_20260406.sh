#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_tables/gpp_code1_flash_smrz_rechunk_py/feature_table_merged_GPP_code1_flash_SMrz.parquet"
SHAP_RESULTS="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/shap_process_by_biome/Forest"
SPEC_DIR="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/sem_candidate_models_forest_process"
LOG_DIR="$RESULT_ROOT/logs"

mkdir -p "$RESULT_ROOT" "$LOG_DIR"

run_model() {
  local model_id="$1"
  local spec_file="$2"
  local out_dir="$RESULT_ROOT/$model_id"
  local log_file="$LOG_DIR/${model_id}.log"
  mkdir -p "$out_dir"
  "$PYTHON_BIN" "$SEM_SCRIPT" \
    --table "$TABLE" \
    --shap-results "$SHAP_RESULTS" \
    --model-spec-file "$spec_file" \
    --target "t_recover_to_baseline_abs_peak" \
    --feature-scope "all" \
    --metric GPP \
    --code-id code1 \
    --biome Forest \
    --drought-type flash \
    --soil-layer SMrz \
    --output-dir "$out_dir" >"$log_file" 2>&1
}

run_model "M0_direct" "$SPEC_DIR/gpp_code1_flash_smrz_forest_process_M0_direct_v20260406.txt"
run_model "M1_water" "$SPEC_DIR/gpp_code1_flash_smrz_forest_process_M1_water_v20260406.txt"
run_model "M2_canopy" "$SPEC_DIR/gpp_code1_flash_smrz_forest_process_M2_canopy_v20260406.txt"
run_model "M3_baseline" "$SPEC_DIR/gpp_code1_flash_smrz_forest_process_M3_baseline_v20260406.txt"

echo "[DONE] candidate models saved under $RESULT_ROOT"
