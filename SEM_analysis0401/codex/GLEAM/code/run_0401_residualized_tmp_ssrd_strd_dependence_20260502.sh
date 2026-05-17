#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
CODE_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/code"
DEP_SCRIPT="$CODE_DIR/21_batch_dependence_plots_fast.py"

DATA_ROOT="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/data/residualized_shap_inputs_20260502_tmp_rad"
OUTPUT_ROOT="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/results/residualized_shap_tmp_ssrd_strd_20260502"
JOBLIB_TMP="/tmp/residualized_tmp_ssrd_strd_dependence_20260502"
MPL_TMP="$JOBLIB_TMP/mpl"

mkdir -p "$OUTPUT_ROOT/_logs" "$JOBLIB_TMP" "$MPL_TMP"

run_dependence_block() {
  local scenario="$1"
  local table="$2"
  local out_root="$3"
  local metric="$4"
  local feature_scope="$5"
  local biomes_str="$6"
  local include_str="$7"
  local exclude_str="$8"

  # shellcheck disable=SC2206
  local biomes=( $biomes_str )
  # shellcheck disable=SC2206
  local include_features=( $include_str )
  # shellcheck disable=SC2206
  local exclude_features=( $exclude_str )

  echo "[RUN] dependence $scenario"
  env MPLCONFIGDIR="$MPL_TMP/$scenario" JOBLIB_TEMP_FOLDER="$JOBLIB_TMP/$scenario" TMPDIR="$JOBLIB_TMP/$scenario" \
    "$PYTHON_BIN" "$DEP_SCRIPT" \
    --table "$table" \
    --output-root "$out_root" \
    --metric "$metric" \
    --code-id code1 \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope "$feature_scope" \
    --model-backend "lightgbm" \
    --n-estimators 200 \
    --n-jobs 80 \
    --shap-sample-size 5000 \
    --biomes "${biomes[@]}" \
    --include-features "${include_features[@]}" \
    --exclude-features "${exclude_features[@]}" >"$OUTPUT_ROOT/_logs/${scenario}_dependence.log" 2>&1
  echo "[DONE] dependence $scenario"
}

PRE_INCLUDE="prepeak_total_precipitation_mean prepeak_total_evaporation_resid prepeak_temperature_2m_mean prepeak_VPD_resid prepeak_SMrz_mean prepeak_lai_total_mean prepeak_ssrd_resid_tmp prepeak_strd_resid_tmp prepeak_wind_speed_mean event_onset_days event_duration event_intensity"
PRE_EXCLUDE="prepeak_total_evaporation_mean prepeak_VPD_mean prepeak_ssrd_mean prepeak_strd_mean"
REC_INCLUDE="recoverywin_total_precipitation_mean recoverywin_total_evaporation_resid recoverywin_temperature_2m_mean recoverywin_VPD_resid recoverywin_SMrz_mean recoverywin_lai_total_mean recoverywin_ssrd_resid_tmp recoverywin_strd_resid_tmp recoverywin_wind_speed_mean"
REC_EXCLUDE="recoverywin_total_evaporation_mean recoverywin_VPD_mean recoverywin_ssrd_mean recoverywin_strd_mean recoverywin_total_precipitation_sum recoverywin_total_evaporation_sum recoverywin_SMrz_delta recoverywin_p_minus_et"

GPP_PRE_BIOMES="Forest Grassland Savanna Cropland Shrubland"
GPP_REC_BIOMES="Forest Grassland Savanna Cropland Shrubland Wetland"
RECO_PRE_BIOMES="Forest Grassland Savanna Cropland Shrubland Wetland"
RECO_REC_BIOMES="Forest Grassland Savanna Cropland Shrubland Wetland"

run_dependence_block \
  "gpp_prepeak_tmpRad" \
  "$DATA_ROOT/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401_residRtmpRad.parquet" \
  "$OUTPUT_ROOT/gpp_prepeak_by_biome" \
  "GPP" \
  "all" \
  "$GPP_PRE_BIOMES" \
  "$PRE_INCLUDE" \
  "$PRE_EXCLUDE"

run_dependence_block \
  "gpp_recovery_tmpRad" \
  "$DATA_ROOT/feature_table_recovery_phase_GPP_code1_flash_SMrz_0401_residRtmpRad.parquet" \
  "$OUTPUT_ROOT/gpp_recovery_by_biome" \
  "GPP" \
  "process_recoverywin" \
  "$GPP_REC_BIOMES" \
  "$REC_INCLUDE" \
  "$REC_EXCLUDE"

run_dependence_block \
  "reco_prepeak_tmpRad" \
  "$DATA_ROOT/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE_residRtmpRad.parquet" \
  "$OUTPUT_ROOT/reco_prepeak_by_biome" \
  "RECO" \
  "all" \
  "$RECO_PRE_BIOMES" \
  "$PRE_INCLUDE" \
  "$PRE_EXCLUDE"

run_dependence_block \
  "reco_recovery_tmpRad" \
  "$DATA_ROOT/feature_table_recovery_phase_RECO_code1_flash_SMrz_0401_mswepE_residRtmpRad.parquet" \
  "$OUTPUT_ROOT/reco_recovery_by_biome" \
  "RECO" \
  "process_recoverywin" \
  "$RECO_REC_BIOMES" \
  "$REC_INCLUDE" \
  "$REC_EXCLUDE"

echo "[DONE] residualized TMP+SSRD+STRD dependence outputs saved under $OUTPUT_ROOT"
