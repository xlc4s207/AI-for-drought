#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"
DEP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/21_batch_dependence_plots_fast.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_recovery_phase_GPP_code1_flash_SMrz_precipEmean_prepeak.parquet"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/dual_precip_shap_20260418"
SHAP_ROOT="$RESULT_ROOT/shap_by_biome"
JOBLIB_TMP="/tmp/gpp_dual_precip_shap_20260418"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
)

INCLUDE_FEATURES=(
  "prepeak_total_precipitation_mean"
  "recoverywin_total_precipitation_mean"
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
  "recoverywin_SMrz_delta"
)

mkdir -p "$SHAP_ROOT" "$JOBLIB_TMP"

run_one_biome() {
  local biome="$1"
  local out_dir="$SHAP_ROOT/$biome"
  mkdir -p "$out_dir"
  env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
  "$PYTHON_BIN" "$SHAP_SCRIPT" \
    --table "$TABLE" \
    --metric GPP \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope "all" \
    --limit 50000 \
    --model-backend "lightgbm" \
    --n-estimators 120 \
    --n-jobs 12 \
    --top-k 10 \
    --shap-sample-size 5000 \
    --include-features "${INCLUDE_FEATURES[@]}" \
    --exclude-features "${EXCLUDE_FEATURES[@]}" \
    --output-dir "$out_dir" >"$out_dir/run.log" 2>&1
}

for biome in "${BIOMES[@]}"; do
  run_one_biome "$biome" &
done
wait

env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
"$PYTHON_BIN" "$DEP_SCRIPT" \
  --table "$TABLE" \
  --output-root "$SHAP_ROOT" \
  --metric GPP \
  --code-id code1 \
  --drought-type flash \
  --soil-layer SMrz \
  --feature-scope "all" \
  --limit 50000 \
  --model-backend "lightgbm" \
  --n-estimators 120 \
  --n-jobs 12 \
  --shap-sample-size 5000 \
  --biomes "${BIOMES[@]}" \
  --include-features "${INCLUDE_FEATURES[@]}" \
  --exclude-features "${EXCLUDE_FEATURES[@]}" >"$RESULT_ROOT/dependence.log" 2>&1

echo "[DONE] Dual-precip SHAP saved under $RESULT_ROOT"
