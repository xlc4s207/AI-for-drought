#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"
SUMMARY_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/12_summarize_candidate_models.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_merged_GPP_code1_flash_SMrz_mswepE.parquet"
SPEC_DIR="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs"
RESULT_BASE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_mswepE_clean"
SHAP_ROOT="$RESULT_BASE/shap_process_by_biome"
RESULT_ROOT="$RESULT_BASE/sem_candidate_models_all_biomes_process"
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
    --shap-results "$SHAP_ROOT/$biome" \
    --model-spec-file "$spec_file" \
    --target "t_recover_to_baseline_abs_peak" \
    --feature-scope "all" \
    --metric GPP \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --output-dir "$out_dir" >"$log_file" 2>&1
}

run_biome_models() {
  local biome="$1"
  local family="$2"
  case "$family" in
    forest)
      run_model "$biome" "M0_direct" "$SPEC_DIR/gpp_code1_flash_smrz_forest_process_M0_direct_v20260406.txt"
      run_model "$biome" "M1_water" "$SPEC_DIR/gpp_code1_flash_smrz_forest_process_M1_water_v20260406.txt"
      run_model "$biome" "M2_canopy" "$SPEC_DIR/gpp_code1_flash_smrz_forest_process_M2_canopy_v20260406.txt"
      run_model "$biome" "M3_baseline" "$SPEC_DIR/gpp_code1_flash_smrz_forest_process_M3_baseline_v20260406.txt"
      ;;
    nonwetland)
      run_model "$biome" "M0_direct" "$SPEC_DIR/gpp_code1_flash_smrz_nonwetland_process_M0_direct_v20260406.txt"
      run_model "$biome" "M1_water" "$SPEC_DIR/gpp_code1_flash_smrz_nonwetland_process_M1_water_v20260406.txt"
      run_model "$biome" "M2_canopy" "$SPEC_DIR/gpp_code1_flash_smrz_nonwetland_process_M2_canopy_v20260406.txt"
      run_model "$biome" "M3_baseline" "$SPEC_DIR/gpp_code1_flash_smrz_nonwetland_process_M3_baseline_v20260406.txt"
      ;;
    wetland)
      run_model "$biome" "M0_direct" "$SPEC_DIR/gpp_code1_flash_smrz_wetland_process_M0_direct_mswepe_v20260415.txt"
      run_model "$biome" "M1_water" "$SPEC_DIR/gpp_code1_flash_smrz_wetland_process_M1_water_mswepe_v20260415.txt"
      run_model "$biome" "M2_dualwater" "$SPEC_DIR/gpp_code1_flash_smrz_wetland_process_M2_dualwater_mswepe_v20260415.txt"
      run_model "$biome" "M3_baselinewater" "$SPEC_DIR/gpp_code1_flash_smrz_wetland_process_M3_baselinewater_mswepe_v20260415.txt"
      ;;
    *)
      echo "Unknown family: $family" >&2
      return 1
      ;;
  esac
}

run_biome_models "Forest" "forest"
run_biome_models "Grassland" "nonwetland"
run_biome_models "Savanna" "nonwetland"
run_biome_models "Cropland" "nonwetland"
run_biome_models "Shrubland" "nonwetland"
run_biome_models "Wetland" "wetland"

"$PYTHON_BIN" "$SUMMARY_SCRIPT" \
  --result-root "$RESULT_ROOT" \
  --output-csv "$RESULT_ROOT/candidate_model_summary.csv" \
  --output-md "$RESULT_ROOT/candidate_model_summary.md" >"$LOG_DIR/candidate_summary.log" 2>&1

echo "[DONE] all biome candidate models saved under $RESULT_ROOT"
