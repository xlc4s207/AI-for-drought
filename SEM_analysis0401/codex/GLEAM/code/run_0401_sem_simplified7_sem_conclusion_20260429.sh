#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
CODE_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/code"
MAIN_CODE_DIR="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code"
DATA_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/data"
RESULTS_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/results"
SEM_CONCLUSION_DIR="$RESULTS_DIR/SEM_conclusion"

DEP_SCRIPT="$CODE_DIR/21_batch_dependence_plots_fast.py"
SEM_SCRIPT="$CODE_DIR/07_sem_analysis.py"
PLOT_SCRIPT="$CODE_DIR/13_plot_sem_path_diagrams.py"
EXPORT_SCRIPT="$MAIN_CODE_DIR/42_export_sem_path_effects.py"

DATE_TAG="20260429"
JOBLIB_TMP="/tmp/sem_analysis0401_simplified7_20260429"
MPL_TMP="$JOBLIB_TMP/mpl"

mkdir -p "$SEM_CONCLUSION_DIR" "$JOBLIB_TMP" "$MPL_TMP"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
)

GPP_PRE_TABLE="$DATA_DIR/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet"
GPP_REC_TABLE="$DATA_DIR/feature_table_recovery_phase_GPP_code1_flash_SMrz_0401.parquet"
RECO_PRE_TABLE="$DATA_DIR/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet"
RECO_REC_TABLE="$DATA_DIR/feature_table_recovery_phase_RECO_code1_flash_SMrz_0401_mswepE.parquet"

GPP_PRE_SHAP_ROOT="$RESULTS_DIR/gpp_code1_flash_smrz_v20260401_onsetpeak_clean/prepeak_event_shap_sem_20260424/shap_by_biome"
GPP_REC_SHAP_ROOT="$RESULTS_DIR/gpp_code1_flash_smrz_v20260401_recoverywin_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome"
RECO_PRE_SHAP_ROOT="$RESULTS_DIR/reco_code1_flash_smrz_v20260401_mswepE_clean/prepeak_event_shap_sem_20260424/shap_by_biome"
RECO_REC_SHAP_ROOT="$RESULTS_DIR/reco_code1_flash_smrz_v20260401_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome"

GPP_PRE_SPEC="$CODE_DIR/sem_specs/gpp_code1_flash_smrz_sem_simplified7_prepeak_v20260429.txt"
GPP_REC_SPEC="$CODE_DIR/sem_specs/gpp_code1_flash_smrz_sem_simplified7_recoverywin_v20260429.txt"
RECO_PRE_SPEC="$CODE_DIR/sem_specs/reco_code1_flash_smrz_sem_simplified7_prepeak_v20260429.txt"
RECO_REC_SPEC="$CODE_DIR/sem_specs/reco_code1_flash_smrz_sem_simplified7_recoverywin_v20260429.txt"

run_python() {
  env MPLCONFIGDIR="$MPL_TMP" JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
    "$PYTHON_BIN" "$@"
}

run_sem_block() {
  local table="$1"
  local shap_root="$2"
  local spec_file="$3"
  local feature_scope="$4"
  local metric="$5"
  local output_root="$6"
  local scope_name="$7"

  local sem_dir="$output_root/by_biome"
  mkdir -p "$sem_dir"

  for biome in "${BIOMES[@]}"; do
    run_python "$SEM_SCRIPT" \
      --table "$table" \
      --shap-results "$shap_root/$biome" \
      --model-spec-file "$spec_file" \
      --target "t_recover_to_baseline_abs_peak" \
      --feature-scope "$feature_scope" \
      --metric "$metric" \
      --code-id code1 \
      --biome "$biome" \
      --drought-type flash \
      --soil-layer SMrz \
      --output-dir "$sem_dir" >"$sem_dir/${biome}.log" 2>&1
  done

  run_python "$PLOT_SCRIPT" \
    --sem-dir "$sem_dir" \
    --output-dir "$output_root" >"$output_root/plot.log" 2>&1

  run_python "$EXPORT_SCRIPT" \
    --sem-dir "$sem_dir" \
    --scope-name "$scope_name" \
    --output-prefix "$output_root/$scope_name" >"$output_root/export.log" 2>&1
}

GPP_OUTPUT_ROOT="$SEM_CONCLUSION_DIR/gpp_code1_flash_smrz_v20260401_sem_simplified7_${DATE_TAG}"
RECO_OUTPUT_ROOT="$SEM_CONCLUSION_DIR/reco_code1_flash_smrz_v20260401_sem_simplified7_${DATE_TAG}"

mkdir -p "$GPP_OUTPUT_ROOT" "$RECO_OUTPUT_ROOT"

run_sem_block \
  "$GPP_PRE_TABLE" \
  "$GPP_PRE_SHAP_ROOT" \
  "$GPP_PRE_SPEC" \
  "prepeak_event" \
  "GPP" \
  "$GPP_OUTPUT_ROOT/sem_prepeak" \
  "gpp_prepeak_simplified7_0401"

run_sem_block \
  "$GPP_REC_TABLE" \
  "$GPP_REC_SHAP_ROOT" \
  "$GPP_REC_SPEC" \
  "process_recoverywin" \
  "GPP" \
  "$GPP_OUTPUT_ROOT/sem_recoverywin" \
  "gpp_recoverywin_simplified7_0401"

run_sem_block \
  "$RECO_PRE_TABLE" \
  "$RECO_PRE_SHAP_ROOT" \
  "$RECO_PRE_SPEC" \
  "prepeak_event" \
  "RECO" \
  "$RECO_OUTPUT_ROOT/sem_prepeak" \
  "reco_prepeak_simplified7_0401"

run_sem_block \
  "$RECO_REC_TABLE" \
  "$RECO_REC_SHAP_ROOT" \
  "$RECO_REC_SPEC" \
  "process_recoverywin" \
  "RECO" \
  "$RECO_OUTPUT_ROOT/sem_recoverywin" \
  "reco_recoverywin_simplified7_0401"

cat >"$SEM_CONCLUSION_DIR/README_20260429.md" <<EOF
# 0401 Simplified7 SEM Conclusion

Generated on ${DATE_TAG}.

Outputs:
- $GPP_OUTPUT_ROOT
- $RECO_OUTPUT_ROOT

Notes:
- The 0401 RECO recoverywin SHAP root was rebuilt in place at:
  - $RECO_REC_SHAP_ROOT
- The SHAP sample size for RECO recoverywin was increased from 5000 to 20000 before regenerating dependence artifacts.
- Wetland was excluded in this SEM conclusion bundle to keep GPP and RECO biome sets aligned.
EOF

echo "[DONE] 0401 simplified7 SEM outputs saved under $SEM_CONCLUSION_DIR"
