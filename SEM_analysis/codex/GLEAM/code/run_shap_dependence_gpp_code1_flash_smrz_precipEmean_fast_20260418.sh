#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"
DEP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/21_batch_dependence_plots_fast.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_recovery_phase_GPP_code1_flash_SMrz_precipEmean.parquet"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/shap_process_recoverywin_precipEmean_lgbm_fast_by_biome"
JOBLIB_TMP="/tmp/gpp_recoverywin_precipEmean_lgbm_fast_20260418"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
  "Wetland"
)

INCLUDE_FEATURES=(
  "recoverywin_total_precipitation_mean"
  "recoverywin_total_evaporation_mean"
  "recoverywin_temperature_2m_mean"
  "recoverywin_VPD_mean"
  "recoverywin_SMrz_mean"
  "recoverywin_lai_total_mean"
  "recoverywin_ssrd_mean"
  "recoverywin_strd_mean"
  "recoverywin_wind_speed_mean"
)

EXCLUDE_FEATURES=(
  "recoverywin_p_minus_et"
  "recoverywin_total_precipitation_sum"
  "recoverywin_total_evaporation_sum"
)

mkdir -p "$RESULT_ROOT" "$JOBLIB_TMP"

for biome in "${BIOMES[@]}"; do
  out_dir="$RESULT_ROOT/$biome"
  mkdir -p "$out_dir"
  env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
  "$PYTHON_BIN" "$SHAP_SCRIPT" \
    --table "$TABLE" \
    --metric GPP \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope "process_recoverywin" \
    --limit 50000 \
    --model-backend "lightgbm" \
    --n-estimators 500 \
    --n-jobs -1 \
    --top-k 9 \
    --shap-sample-size 5000 \
    --include-features "${INCLUDE_FEATURES[@]}" \
    --exclude-features "${EXCLUDE_FEATURES[@]}" \
    --output-dir "$out_dir" >"$out_dir/run.log" 2>&1
done

env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
"$PYTHON_BIN" "$DEP_SCRIPT" \
  --table "$TABLE" \
  --output-root "$RESULT_ROOT" \
  --metric GPP \
  --code-id code1 \
  --drought-type flash \
  --soil-layer SMrz \
  --feature-scope "process_recoverywin" \
  --limit 50000 \
  --model-backend "lightgbm" \
  --n-estimators 500 \
  --n-jobs -1 \
  --shap-sample-size 5000 \
  --biomes "${BIOMES[@]}" \
  --include-features "${INCLUDE_FEATURES[@]}" \
  --exclude-features "${EXCLUDE_FEATURES[@]}" >"$RESULT_ROOT/dependence_fast.log" 2>&1

echo "[DONE] Fast LightGBM SHAP + dependence saved under $RESULT_ROOT"
