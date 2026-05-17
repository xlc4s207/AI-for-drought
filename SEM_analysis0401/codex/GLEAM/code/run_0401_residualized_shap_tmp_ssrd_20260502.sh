#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
CODE_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/code"
SHAP_SCRIPT="$CODE_DIR/06_shap_analysis.py"
BUILD_SCRIPT="$CODE_DIR/46_build_residualized_feature_tables.py"

DATA_ROOT="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/data/residualized_shap_inputs_20260502"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/results/residualized_shap_tmp_ssrd_20260502"
JOBLIB_TMP="/tmp/residualized_shap_tmp_ssrd_20260502"

mkdir -p "$RESULT_ROOT" "$JOBLIB_TMP"

"$PYTHON_BIN" "$BUILD_SCRIPT"

run_shap_block() {
  local scenario="$1"
  local table="$2"
  local metric="$3"
  local feature_scope="$4"
  local include_str="$5"
  local exclude_str="$6"
  local out_root="$7"
  local biome_list_str="$8"

  mkdir -p "$out_root"
  # shellcheck disable=SC2206
  local include_features=( $include_str )
  # shellcheck disable=SC2206
  local exclude_features=( $exclude_str )
  # shellcheck disable=SC2206
  local biomes=( $biome_list_str )

  for biome in "${biomes[@]}"; do
    local out_dir="$out_root/$biome"
    mkdir -p "$out_dir"
    env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
      "$PYTHON_BIN" "$SHAP_SCRIPT" \
      --table "$table" \
      --metric "$metric" \
      --code-id code1 \
      --biome "$biome" \
      --drought-type flash \
      --soil-layer SMrz \
      --feature-scope "$feature_scope" \
      --model-backend "lightgbm" \
      --n-estimators 200 \
      --n-jobs 80 \
      --top-k 12 \
      --shap-sample-size 5000 \
      --include-features "${include_features[@]}" \
      --exclude-features "${exclude_features[@]}" \
      --output-dir "$out_dir" >"$out_dir/run.log" 2>&1
    echo "[DONE] $scenario :: $biome"
  done
}

COMMON_PRE_INCLUDE="prepeak_total_precipitation_mean prepeak_total_evaporation_resid prepeak_temperature_2m_mean prepeak_VPD_resid prepeak_SMrz_mean prepeak_lai_total_mean prepeak_ssrd_mean prepeak_wind_speed_mean event_onset_days event_duration event_intensity"
COMMON_PRE_EXCLUDE="prepeak_total_evaporation_mean prepeak_VPD_mean prepeak_strd_mean"
COMMON_REC_INCLUDE="recoverywin_total_precipitation_mean recoverywin_total_evaporation_resid recoverywin_temperature_2m_mean recoverywin_VPD_resid recoverywin_SMrz_mean recoverywin_lai_total_mean recoverywin_ssrd_mean recoverywin_wind_speed_mean"
COMMON_REC_EXCLUDE="recoverywin_total_evaporation_mean recoverywin_VPD_mean recoverywin_strd_mean recoverywin_total_precipitation_sum recoverywin_total_evaporation_sum recoverywin_SMrz_delta recoverywin_p_minus_et"

GPP_PRE_BIOMES="Forest Grassland Savanna Cropland Shrubland"
GPP_REC_BIOMES="Forest Grassland Savanna Cropland Shrubland Wetland"
RECO_PRE_BIOMES="Forest Grassland Savanna Cropland Shrubland Wetland"
RECO_REC_BIOMES="Forest Grassland Savanna Cropland Shrubland Wetland"

run_shap_block \
  "gpp_prepeak_residR1" \
  "$DATA_ROOT/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401_residR1_tmp_ssrd.parquet" \
  "GPP" \
  "all" \
  "$COMMON_PRE_INCLUDE" \
  "$COMMON_PRE_EXCLUDE" \
  "$RESULT_ROOT/gpp_prepeak_by_biome" \
  "$GPP_PRE_BIOMES"

run_shap_block \
  "gpp_recovery_residR1" \
  "$DATA_ROOT/feature_table_recovery_phase_GPP_code1_flash_SMrz_0401_residR1_tmp_ssrd.parquet" \
  "GPP" \
  "process_recoverywin" \
  "$COMMON_REC_INCLUDE" \
  "$COMMON_REC_EXCLUDE" \
  "$RESULT_ROOT/gpp_recovery_by_biome" \
  "$GPP_REC_BIOMES"

run_shap_block \
  "reco_prepeak_residR1" \
  "$DATA_ROOT/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE_residR1_tmp_ssrd.parquet" \
  "RECO" \
  "all" \
  "$COMMON_PRE_INCLUDE" \
  "$COMMON_PRE_EXCLUDE" \
  "$RESULT_ROOT/reco_prepeak_by_biome" \
  "$RECO_PRE_BIOMES"

run_shap_block \
  "reco_recovery_residR1" \
  "$DATA_ROOT/feature_table_recovery_phase_RECO_code1_flash_SMrz_0401_mswepE_residR1_tmp_ssrd.parquet" \
  "RECO" \
  "process_recoverywin" \
  "$COMMON_REC_INCLUDE" \
  "$COMMON_REC_EXCLUDE" \
  "$RESULT_ROOT/reco_recovery_by_biome" \
  "$RECO_REC_BIOMES"

cat >"$RESULT_ROOT/README.md" <<EOF
# Residualized SHAP TMP+SSRD sensitivity (20260502)

This run keeps:
- TMP
- SSRD

This run removes:
- STRD
- raw VPD
- raw EVA

Residualized replacements:
- VPD_resid ~ TMP + wind
- total_evaporation_resid ~ PRE + VPD
EOF

echo "[DONE] residualized TMP+SSRD SHAP outputs saved under $RESULT_ROOT"
