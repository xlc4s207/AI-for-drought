#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"
SUMMARY_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/11_summarize_scope_results.py"

TABLE_PRED="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_pre_recovery_GPP_code1_flash_SMrz_mswepE.parquet"
TABLE_PROC="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_recovery_phase_GPP_code1_flash_SMrz_mswepE.parquet"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_mswepE_clean"
LOG_ROOT="$RESULT_ROOT/logs_scope_split"
JOBLIB_TMP="/tmp/gpp_code1_flash_smrz_mswepE_scope_split"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
  "Wetland"
)

mkdir -p "$RESULT_ROOT" "$LOG_ROOT" "$JOBLIB_TMP"

run_scope() {
  local scope="$1"
  local table="$2"
  local shap_global_dir="$RESULT_ROOT/shap_${scope}"
  local shap_biome_dir="$RESULT_ROOT/shap_${scope}_by_biome"
  local sem_dir="$RESULT_ROOT/sem_${scope}/by_biome"
  local scope_log_dir="$LOG_ROOT/$scope"

  mkdir -p "$shap_global_dir" "$shap_biome_dir" "$sem_dir" "$scope_log_dir"

  echo "[$(date '+%F %T')] SCOPE_START scope=$scope table=$table"

  env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
  "$PYTHON_BIN" "$SHAP_SCRIPT" \
    --table "$table" \
    --metric GPP \
    --code-id code1 \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope "$scope" \
    --output-dir "$shap_global_dir" >"$scope_log_dir/global_shap.log" 2>&1

  for biome in "${BIOMES[@]}"; do
    local biome_shap_dir="$shap_biome_dir/$biome"
    local biome_log="$scope_log_dir/shap_${biome}.log"
    mkdir -p "$biome_shap_dir"
    env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
    "$PYTHON_BIN" "$SHAP_SCRIPT" \
      --table "$table" \
      --metric GPP \
      --code-id code1 \
      --biome "$biome" \
      --drought-type flash \
      --soil-layer SMrz \
      --feature-scope "$scope" \
      --output-dir "$biome_shap_dir" >"$biome_log" 2>&1

    local sem_log="$scope_log_dir/sem_${biome}.log"
    if "$PYTHON_BIN" "$SEM_SCRIPT" \
      --table "$table" \
      --shap-results "$biome_shap_dir" \
      --target "t_recover_to_baseline_abs_peak" \
      --feature-scope "$scope" \
      --metric GPP \
      --code-id code1 \
      --biome "$biome" \
      --drought-type flash \
      --soil-layer SMrz \
      --output-dir "$sem_dir" >"$sem_log" 2>&1; then
      echo "[$(date '+%F %T')] SEM_OK scope=$scope biome=$biome"
    else
      echo "[$(date '+%F %T')] SEM_FAIL scope=$scope biome=$biome log=$sem_log"
    fi
  done

  echo "[$(date '+%F %T')] SCOPE_DONE scope=$scope"
}

run_scope "predictive" "$TABLE_PRED"
run_scope "process" "$TABLE_PROC"

"$PYTHON_BIN" "$SUMMARY_SCRIPT" --result-root "$RESULT_ROOT" >"$LOG_ROOT/scope_summary.log" 2>&1
echo "[$(date '+%F %T')] PIPELINE_DONE summary=$RESULT_ROOT/scope_summary.md"
