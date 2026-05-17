#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
EXTRACT_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/02_extract_era5_features.py"
GLEAM_SM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/03_extract_gleam_sm_features.py"
BUILD_SOURCE_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/34_build_reco_prepeak_event_source_table.py"
BUILD_PHASE_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/31_build_phase_event_feature_table.py"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"
DEP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/21_batch_dependence_plots_fast.py"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"
PLOT_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/13_plot_sem_path_diagrams.py"

BASE_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_pre_recovery_RECO_code1_flash_SMrz_mswepE.parquet"
PREPEAK_FEATURES_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/era5_features_RECO_code1_flash_SMrz_mswepE_prepeak_predictors.parquet"
PREPEAK_SM_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/gleam_sm_features_RECO_code1_flash_SMrz_mswepE_prepeak.parquet"
PREPEAK_SOURCE_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_pre_recovery_RECO_code1_flash_SMrz_mswepE_with_prepeak.parquet"
PREPEAK_EVENT_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_prepeak_event_RECO_code1_flash_SMrz_mswepE.parquet"
SPEC_FILE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs/reco_code1_flash_smrz_prepeak_event_mechanism_v20260421.txt"
ERA5_RECHUNK_DIR="/data/era5_for_GRN/rechunked_spatial_20260402"
MSWEP_TP_PATH="$ERA5_RECHUNK_DIR/mswep_total_precipitation_0p25deg_1980_2024_spatialchunks_py.nc"

RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421"
SHAP_ROOT="$RESULT_ROOT/shap_by_biome"
SEM_ROOT="$RESULT_ROOT/sem_by_biome"
MECH_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_prepeak_event_mechanism_20260421"
MECH_BY_BIOME="$MECH_ROOT/by_biome"

JOBLIB_TMP="/tmp/reco_prepeak_event_shap_sem_20260421"
MPL_TMP="$JOBLIB_TMP/mpl"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
  "Wetland"
)

INCLUDE_FEATURES=(
  "prepeak_total_precipitation_mean"
  "prepeak_total_evaporation_mean"
  "prepeak_temperature_2m_mean"
  "prepeak_VPD_mean"
  "prepeak_SMrz_mean"
  "prepeak_lai_total_mean"
  "prepeak_ssrd_mean"
  "prepeak_strd_mean"
  "prepeak_wind_speed_mean"
  "event_onset_days"
  "event_duration"
  "event_intensity"
)

mkdir -p "$SHAP_ROOT" "$SEM_ROOT" "$MECH_BY_BIOME" "$JOBLIB_TMP" "$MPL_TMP"

env MPLCONFIGDIR="$MPL_TMP" JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
"$PYTHON_BIN" "$EXTRACT_SCRIPT" \
  --metric RECO \
  --code-id code1 \
  --drought-type flash \
  --soil-layer SMrz \
  --era5-root-dir "$ERA5_RECHUNK_DIR" \
  --total-precipitation-path "$MSWEP_TP_PATH" \
  --variables \
    total_precipitation \
    total_evaporation \
    temperature_2m \
    dewpoint_temperature \
    ssrd \
    strd \
    wind_u_10m \
    wind_v_10m \
    leaf_area_index_high_vegetation \
    leaf_area_index_low_vegetation \
  --workers 48 \
  --concurrent-era5-tasks 1 \
  --reserve-cpus 8 \
  --vars-per-task 11 \
  --output "$PREPEAK_FEATURES_TABLE"

env MPLCONFIGDIR="$MPL_TMP" JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
"$PYTHON_BIN" "$GLEAM_SM_SCRIPT" \
  --metric RECO \
  --code-id code1 \
  --drought-type flash \
  --soil-layer SMrz \
  --workers 48 \
  --output "$PREPEAK_SM_TABLE"

"$PYTHON_BIN" "$BUILD_SOURCE_SCRIPT" \
  --base-table "$BASE_TABLE" \
  --prepeak-features "$PREPEAK_FEATURES_TABLE" \
  --sm-features "$PREPEAK_SM_TABLE" \
  --output-table "$PREPEAK_SOURCE_TABLE"

"$PYTHON_BIN" "$BUILD_PHASE_SCRIPT" \
  --source-table "$PREPEAK_SOURCE_TABLE" \
  --phase prepeak \
  --output-table "$PREPEAK_EVENT_TABLE"

for biome in "${BIOMES[@]}"; do
  shap_out="$SHAP_ROOT/$biome"
  mkdir -p "$shap_out"
  env MPLCONFIGDIR="$MPL_TMP" JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
  "$PYTHON_BIN" "$SHAP_SCRIPT" \
    --table "$PREPEAK_EVENT_TABLE" \
    --metric RECO \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope "prepeak_event" \
    --limit 50000 \
    --model-backend "lightgbm" \
    --n-estimators 120 \
    --n-jobs 12 \
    --top-k 12 \
    --shap-sample-size 5000 \
    --include-features "${INCLUDE_FEATURES[@]}" \
    --output-dir "$shap_out" >"$shap_out/run.log" 2>&1

  "$PYTHON_BIN" "$SEM_SCRIPT" \
    --table "$PREPEAK_EVENT_TABLE" \
    --shap-results "$shap_out" \
    --model-spec-file "$SPEC_FILE" \
    --target "t_recover_to_baseline_abs_peak" \
    --feature-scope "prepeak_event" \
    --metric RECO \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --include-features "${INCLUDE_FEATURES[@]}" \
    --output-dir "$SEM_ROOT" >"$SEM_ROOT/${biome}.log" 2>&1
done

env MPLCONFIGDIR="$MPL_TMP" JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
"$PYTHON_BIN" "$DEP_SCRIPT" \
  --table "$PREPEAK_EVENT_TABLE" \
  --output-root "$SHAP_ROOT" \
  --metric RECO \
  --code-id code1 \
  --drought-type flash \
  --soil-layer SMrz \
  --feature-scope "prepeak_event" \
  --limit 50000 \
  --model-backend "lightgbm" \
  --n-estimators 120 \
  --n-jobs 12 \
  --shap-sample-size 5000 \
  --biomes "${BIOMES[@]}" \
  --include-features "${INCLUDE_FEATURES[@]}" \
  >"$RESULT_ROOT/dependence_fast.log" 2>&1

"$PYTHON_BIN" "$PLOT_SCRIPT" \
  --sem-dir "$SEM_ROOT" \
  --output-dir "$RESULT_ROOT" >"$RESULT_ROOT/plot.log" 2>&1

cp -a "$SEM_ROOT/." "$MECH_BY_BIOME/"

"$PYTHON_BIN" "$PLOT_SCRIPT" \
  --sem-dir "$MECH_BY_BIOME" \
  --output-dir "$MECH_ROOT" >"$MECH_ROOT/plot.log" 2>&1

echo "[DONE] prepeak_event table: $PREPEAK_EVENT_TABLE"
echo "[DONE] SHAP+SEM root: $RESULT_ROOT"
echo "[DONE] mechanism root: $MECH_ROOT"
