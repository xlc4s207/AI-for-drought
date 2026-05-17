#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
DEP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/21_batch_dependence_plots_fast.py"
JOBLIB_TMP="/tmp/gpp_onsetpeak_dependence_20260420"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
)

PREPEAK_FEATURES=(
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

SHOCK_FEATURES=(
  "shock_total_precipitation_mean"
  "shock_total_evaporation_mean"
  "shock_temperature_2m_mean"
  "shock_VPD_mean"
  "shock_SMrz_mean"
  "shock_lai_total_mean"
  "shock_ssrd_mean"
  "shock_strd_mean"
  "shock_wind_speed_mean"
  "event_onset_days"
  "event_duration"
  "event_intensity"
)

mkdir -p "$JOBLIB_TMP"

env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
"$PYTHON_BIN" "$DEP_SCRIPT" \
  --table "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_prepeak_event_GPP_code1_flash_SMrz_onsetpeak.parquet" \
  --output-root "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome" \
  --metric GPP \
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
  --include-features "${PREPEAK_FEATURES[@]}" \
  >"/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/dependence_fast.log" 2>&1

env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
"$PYTHON_BIN" "$DEP_SCRIPT" \
  --table "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_shock_event_GPP_code1_flash_SMrz_onsetpeak.parquet" \
  --output-root "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/shock_event_shap_sem_20260420/shap_by_biome" \
  --metric GPP \
  --code-id code1 \
  --drought-type flash \
  --soil-layer SMrz \
  --feature-scope "shock_event" \
  --limit 50000 \
  --model-backend "lightgbm" \
  --n-estimators 120 \
  --n-jobs 12 \
  --shap-sample-size 5000 \
  --biomes "${BIOMES[@]}" \
  --include-features "${SHOCK_FEATURES[@]}" \
  >"/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/shock_event_shap_sem_20260420/dependence_fast.log" 2>&1

echo "[DONE] onset-to-peak dependence plots saved under existing prepeak/shock result roots"
