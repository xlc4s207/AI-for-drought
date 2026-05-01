#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
ERA5_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/23_extract_prepeak_precip_only.py"
BUILD_TABLE_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/22_build_reco_prepeak_precip_table.py"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"

BASE_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_recovery_phase_RECO_code1_flash_SMrz_mswepE_precipEmean.parquet"
PRECIP_ONLY_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/era5_features_RECO_code1_flash_SMrz_prepeak_precip_only.parquet"
PREPEAK_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_recovery_phase_RECO_code1_flash_SMrz_mswepE_precipEmean_prepeak.parquet"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_precip_shap_20260418/shap_by_biome"
JOBLIB_TMP="/tmp/reco_prepeak_precip_shap_20260418"

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
  "recoverywin_total_evaporation_mean"
  "recoverywin_SMrz_mean"
  "recoverywin_temperature_2m_mean"
  "recoverywin_VPD_mean"
  "recoverywin_wind_speed_mean"
  "recoverywin_lai_total_mean"
  "recoverywin_ssrd_mean"
  "recoverywin_strd_mean"
)

EXCLUDE_FEATURES=(
  "recoverywin_p_minus_et"
  "recoverywin_total_precipitation_sum"
  "recoverywin_total_evaporation_sum"
  "recoverywin_total_precipitation_mean"
  "recoverywin_SMrz_delta"
)

mkdir -p "$RESULT_ROOT" "$JOBLIB_TMP"

"$PYTHON_BIN" "$ERA5_SCRIPT" \
  --metric RECO \
  --code-id code1 \
  --drought-type flash \
  --soil-layer SMrz \
  --variables total_precipitation \
  --workers 48 \
  --concurrent-era5-tasks 1 \
  --reserve-cpus 8 \
  --vars-per-task 1 \
  --output "$PRECIP_ONLY_TABLE"

"$PYTHON_BIN" "$BUILD_TABLE_SCRIPT" \
  --base-table "$BASE_TABLE" \
  --precip-features "$PRECIP_ONLY_TABLE" \
  --output-table "$PREPEAK_TABLE"

for biome in "${BIOMES[@]}"; do
  out_dir="$RESULT_ROOT/$biome"
  mkdir -p "$out_dir"
  env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
  "$PYTHON_BIN" "$SHAP_SCRIPT" \
    --table "$PREPEAK_TABLE" \
    --metric RECO \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope "all" \
    --limit 50000 \
    --model-backend "lightgbm" \
    --n-estimators 120 \
    --n-jobs 12 \
    --top-k 9 \
    --shap-sample-size 5000 \
    --include-features "${INCLUDE_FEATURES[@]}" \
    --exclude-features "${EXCLUDE_FEATURES[@]}" \
    --output-dir "$out_dir" >"$out_dir/run.log" 2>&1
done

echo "[DONE] RECO prepeak-precip SHAP saved under $RESULT_ROOT"
