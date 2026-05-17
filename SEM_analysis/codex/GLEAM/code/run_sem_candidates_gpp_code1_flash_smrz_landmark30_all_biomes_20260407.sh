#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"
SUMMARY_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/12_summarize_candidate_models.py"
MECH_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/13_summarize_main_mechanisms.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_tables/gpp_code1_flash_smrz_rechunk_py/feature_table_merged_GPP_code1_flash_SMrz.parquet"
SPEC_DIR="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs"
SHAP_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/shap_process_by_biome"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/sem_candidate_models_all_biomes_landmark30"
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
    --feature-scope "process" \
    --target-min-days 30 \
    --target-residual-offset 30 \
    --top-k 0 \
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
      run_model "$biome" "M0_direct" "$SPEC_DIR/gpp_code1_flash_smrz_forest_landmark30_M0_direct_v20260407.txt"
      run_model "$biome" "M1_water" "$SPEC_DIR/gpp_code1_flash_smrz_forest_landmark30_M1_water_v20260407.txt"
      run_model "$biome" "M2_canopy" "$SPEC_DIR/gpp_code1_flash_smrz_forest_landmark30_M2_canopy_v20260407.txt"
      run_model "$biome" "M3_joint" "$SPEC_DIR/gpp_code1_flash_smrz_forest_landmark30_M3_joint_v20260407.txt"
      ;;
    nonwetland)
      run_model "$biome" "M0_direct" "$SPEC_DIR/gpp_code1_flash_smrz_nonwetland_landmark30_M0_direct_v20260407.txt"
      run_model "$biome" "M1_water" "$SPEC_DIR/gpp_code1_flash_smrz_nonwetland_landmark30_M1_water_v20260407.txt"
      run_model "$biome" "M2_canopy" "$SPEC_DIR/gpp_code1_flash_smrz_nonwetland_landmark30_M2_canopy_v20260407.txt"
      run_model "$biome" "M3_joint" "$SPEC_DIR/gpp_code1_flash_smrz_nonwetland_landmark30_M3_joint_v20260407.txt"
      ;;
    wetland)
      run_model "$biome" "M0_direct" "$SPEC_DIR/gpp_code1_flash_smrz_wetland_landmark30_M0_direct_v20260407.txt"
      run_model "$biome" "M1_water" "$SPEC_DIR/gpp_code1_flash_smrz_wetland_landmark30_M1_water_v20260407.txt"
      run_model "$biome" "M2_dualwater" "$SPEC_DIR/gpp_code1_flash_smrz_wetland_landmark30_M2_dualwater_v20260407.txt"
      run_model "$biome" "M3_hydroclimate" "$SPEC_DIR/gpp_code1_flash_smrz_wetland_landmark30_M3_hydroclimate_v20260407.txt"
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

"$PYTHON_BIN" "$SUMMARY_SCRIPT" --result-root "$RESULT_ROOT" >"$LOG_DIR/summary.log" 2>&1
"$PYTHON_BIN" "$MECH_SCRIPT" --result-root "$RESULT_ROOT" >"$LOG_DIR/primary_mechanism.log" 2>&1

echo "[DONE] all biome landmark-30 candidate models saved under $RESULT_ROOT"
