#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"
PLOT_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/13_plot_sem_path_diagrams.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_recovery_phase_GPP_code1_flash_SMrz_precipEmean_prepeak.parquet"
SPEC_FILE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs/gpp_code1_flash_smrz_recoverywin_prepeak_precip_v20260417.txt"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/prepeak_precip_shap_sem_20260417"
SHAP_ROOT="$RESULT_ROOT/shap_by_biome"
SEM_ROOT="$RESULT_ROOT/sem_by_biome"
JOBLIB_TMP="/tmp/gpp_prepeak_precip_shap_sem_20260417"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
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

mkdir -p "$SHAP_ROOT" "$SEM_ROOT" "$JOBLIB_TMP"

for biome in "${BIOMES[@]}"; do
  shap_out="$SHAP_ROOT/$biome"
  mkdir -p "$shap_out"
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
    --top-k 9 \
    --shap-sample-size 5000 \
    --include-features "${INCLUDE_FEATURES[@]}" \
    --exclude-features "${EXCLUDE_FEATURES[@]}" \
    --output-dir "$shap_out" >"$shap_out/run.log" 2>&1

  "$PYTHON_BIN" "$SEM_SCRIPT" \
    --table "$TABLE" \
    --shap-results "$shap_out" \
    --model-spec-file "$SPEC_FILE" \
    --target "t_recover_to_baseline_abs_peak" \
    --feature-scope "all" \
    --metric GPP \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --include-features "${INCLUDE_FEATURES[@]}" \
    --exclude-features "${EXCLUDE_FEATURES[@]}" \
    --output-dir "$SEM_ROOT" >"$SEM_ROOT/${biome}.log" 2>&1
done

"$PYTHON_BIN" "$PLOT_SCRIPT" \
  --sem-dir "$SEM_ROOT" \
  --output-dir "$RESULT_ROOT" >"$RESULT_ROOT/plot.log" 2>&1

echo "[DONE] GPP prepeak-precip SHAP+SEM saved under $RESULT_ROOT"
