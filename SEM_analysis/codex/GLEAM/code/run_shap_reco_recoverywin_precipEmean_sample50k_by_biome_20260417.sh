#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_recovery_phase_RECO_code1_flash_SMrz_mswepE_precipEmean.parquet"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome"
JOBLIB_TMP="/tmp/reco_shap_recoverywin_precipEmean_sample50k"

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

mkdir -p "$RESULT_ROOT" "$JOBLIB_TMP"

for biome in "${BIOMES[@]}"; do
  out_dir="$RESULT_ROOT/$biome"
  mkdir -p "$out_dir"
  env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
  "$PYTHON_BIN" "$SHAP_SCRIPT" \
    --table "$TABLE" \
    --metric RECO \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope "process_recoverywin" \
    --limit 50000 \
    --model-backend "random_forest" \
    --n-estimators 60 \
    --n-jobs 4 \
    --top-k 9 \
    --shap-sample-size 5000 \
    --include-features "${INCLUDE_FEATURES[@]}" \
    --exclude-features "${EXCLUDE_FEATURES[@]}" \
    --output-dir "$out_dir" >"$out_dir/run.log" 2>&1
done

echo "[DONE] RECO recoverywin precipEmean sample50k SHAP saved under $RESULT_ROOT"
