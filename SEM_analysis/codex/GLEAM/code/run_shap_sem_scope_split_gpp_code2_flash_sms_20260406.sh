#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
ERA5_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/02_extract_era5_features.py"
MERGE_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/09_merge_feature_tables.py"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"
SUMMARY_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/11_summarize_scope_results.py"

MASTER_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/event_master_table_valid.parquet"
GLEAM_SM_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/gleam_sm_features_flash_sms.parquet"
DROUGHT_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/drought_event_features_flash.parquet"
ERA5_RECHUNK_DIR="/data/era5_for_GRN/rechunked_spatial_20260402"
ERA5_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/era5_features_GPP_code2_flash_SMs_rechunk_py.parquet"

FEATURE_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_tables/gpp_code2_flash_sms_rechunk_py"
TABLE_MERGED="$FEATURE_ROOT/feature_table_merged_GPP_code2_flash_SMs.parquet"
TABLE_PRED="$FEATURE_ROOT/feature_table_pre_recovery_GPP_code2_flash_SMs.parquet"
TABLE_PROC="$FEATURE_ROOT/feature_table_recovery_phase_GPP_code2_flash_SMs.parquet"

RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code2_flash_sms_rechunk_py_clean"
LOG_ROOT="$RESULT_ROOT/logs_scope_split"
PIPELINE_LOG="$RESULT_ROOT/pipeline.log"
JOBLIB_TMP="/tmp/gpp_code2_flash_sms_scope_split"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
  "Wetland"
)

mkdir -p "$FEATURE_ROOT" "$RESULT_ROOT" "$LOG_ROOT" "$JOBLIB_TMP"
touch "$PIPELINE_LOG"
exec > >(tee -a "$PIPELINE_LOG") 2>&1

timestamp() {
  date '+%F %T'
}

echo "[$(timestamp)] PIPELINE_START result_root=$RESULT_ROOT"
echo "[$(timestamp)] PIPELINE_CONTEXT metric=GPP code_id=code2 drought_type=flash soil_layer=SMs"
echo "[$(timestamp)] PIPELINE_SCOPE predictive=event_+pre30_+onset_+shock_ process=postpeak30_+postpeak60_"

echo "[$(timestamp)] ERA5_EXTRACT_START output=$ERA5_TABLE"
"$PYTHON_BIN" "$ERA5_SCRIPT" \
  --metric GPP \
  --code-id code2 \
  --drought-type flash \
  --soil-layer SMs \
  --workers 24 \
  --concurrent-era5-tasks 2 \
  --reserve-cpus 8 \
  --progress-every 10 \
  --vars-per-task 2 \
  --batch-size 200000 \
  --tile-lat-size 16 \
  --tile-lon-size 16 \
  --era5-root-dir "$ERA5_RECHUNK_DIR" \
  --output "$ERA5_TABLE" >"$LOG_ROOT/01_era5_extract.log" 2>&1
echo "[$(timestamp)] ERA5_EXTRACT_DONE output=$ERA5_TABLE"

echo "[$(timestamp)] MERGE_START feature_root=$FEATURE_ROOT"
"$PYTHON_BIN" "$MERGE_SCRIPT" \
  --master "$MASTER_TABLE" \
  --era5 "$ERA5_TABLE" \
  --gleam-sm "$GLEAM_SM_TABLE" \
  --drought "$DROUGHT_TABLE" \
  --metric GPP \
  --code-id code2 \
  --drought-type flash \
  --soil-layer SMs \
  --merged-output "$TABLE_MERGED" \
  --pre-output "$TABLE_PRED" \
  --recovery-output "$TABLE_PROC" >"$LOG_ROOT/02_merge.log" 2>&1
echo "[$(timestamp)] MERGE_DONE merged=$TABLE_MERGED"

run_scope() {
  local scope="$1"
  local table="$2"
  local shap_global_dir="$RESULT_ROOT/shap_${scope}"
  local shap_biome_dir="$RESULT_ROOT/shap_${scope}_by_biome"
  local sem_dir="$RESULT_ROOT/sem_${scope}/by_biome"
  local scope_log_dir="$LOG_ROOT/$scope"

  mkdir -p "$shap_global_dir" "$shap_biome_dir" "$sem_dir" "$scope_log_dir"

  echo "[$(timestamp)] SCOPE_START scope=$scope table=$table"

  env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
  "$PYTHON_BIN" "$SHAP_SCRIPT" \
    --table "$table" \
    --metric GPP \
    --code-id code2 \
    --drought-type flash \
    --soil-layer SMs \
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
      --code-id code2 \
      --biome "$biome" \
      --drought-type flash \
      --soil-layer SMs \
      --feature-scope "$scope" \
      --output-dir "$biome_shap_dir" >"$biome_log" 2>&1

    local sem_log="$scope_log_dir/sem_${biome}.log"
    if "$PYTHON_BIN" "$SEM_SCRIPT" \
      --table "$table" \
      --shap-results "$biome_shap_dir" \
      --target "t_recover_to_baseline_abs_peak" \
      --feature-scope "$scope" \
      --metric GPP \
      --code-id code2 \
      --biome "$biome" \
      --drought-type flash \
      --soil-layer SMs \
      --output-dir "$sem_dir" >"$sem_log" 2>&1; then
      echo "[$(timestamp)] SEM_OK scope=$scope biome=$biome"
    else
      echo "[$(timestamp)] SEM_FAIL scope=$scope biome=$biome log=$sem_log"
    fi
  done

  echo "[$(timestamp)] SCOPE_DONE scope=$scope"
}

run_scope "predictive" "$TABLE_PRED"
run_scope "process" "$TABLE_PROC"

echo "[$(timestamp)] SUMMARY_START"
"$PYTHON_BIN" "$SUMMARY_SCRIPT" --result-root "$RESULT_ROOT" >"$LOG_ROOT/03_scope_summary.log" 2>&1
echo "[$(timestamp)] SUMMARY_DONE summary=$RESULT_ROOT/scope_summary.md"
echo "[$(timestamp)] PIPELINE_DONE"
