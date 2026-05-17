#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
CODE_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/code"
MAIN_CODE_DIR="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code"
DATA_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/data"
RESULTS_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/results"
SEM_CONCLUSION_DIR="$RESULTS_DIR/SEM_conclusion"

SEM_SCRIPT="$CODE_DIR/07_sem_analysis.py"
PLOT_SCRIPT="$CODE_DIR/13_plot_sem_path_diagrams.py"
EXPORT_SCRIPT="$MAIN_CODE_DIR/42_export_sem_path_effects.py"

DATE_TAG="20260502"
RUN_ROOT="$SEM_CONCLUSION_DIR/sem_halfunified_${DATE_TAG}"
JOBLIB_TMP="/tmp/sem_analysis0401_halfunified_${DATE_TAG}"
MPL_TMP="$JOBLIB_TMP/mpl"

mkdir -p "$RUN_ROOT" "$JOBLIB_TMP" "$MPL_TMP"

GPP_PRE_TABLE="$DATA_DIR/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet"
GPP_REC_TABLE="$DATA_DIR/feature_table_recovery_phase_GPP_code1_flash_SMrz_0401.parquet"
RECO_PRE_TABLE="$DATA_DIR/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet"
RECO_REC_TABLE="$DATA_DIR/feature_table_recovery_phase_RECO_code1_flash_SMrz_0401_mswepE.parquet"

GPP_PRE_SHAP_ROOT="$RESULTS_DIR/gpp_code1_flash_smrz_v20260401_onsetpeak_clean/prepeak_event_shap_sem_20260424/shap_by_biome"
GPP_REC_SHAP_ROOT="$RESULTS_DIR/gpp_code1_flash_smrz_v20260401_recoverywin_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome"
RECO_PRE_SHAP_ROOT="$RESULTS_DIR/reco_code1_flash_smrz_v20260401_mswepE_clean/prepeak_event_shap_sem_20260424/shap_by_biome"
RECO_REC_SHAP_ROOT="$RESULTS_DIR/reco_code1_flash_smrz_v20260401_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome"

GPP_PRE_SPEC="$CODE_DIR/sem_specs/gpp_code1_flash_smrz_sem_halfunified_prepeak_v20260502.txt"
GPP_REC_SPEC="$CODE_DIR/sem_specs/gpp_code1_flash_smrz_sem_halfunified_recoverywin_v20260502.txt"
RECO_PRE_SPEC="$CODE_DIR/sem_specs/reco_code1_flash_smrz_sem_halfunified_prepeak_v20260502.txt"
RECO_REC_SPEC="$CODE_DIR/sem_specs/reco_code1_flash_smrz_sem_halfunified_recoverywin_v20260502.txt"

run_python() {
  env MPLCONFIGDIR="$MPL_TMP" JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
    "$PYTHON_BIN" "$@"
}

list_biomes() {
  local shap_root="$1"
  find "$shap_root" -maxdepth 1 -mindepth 1 -type d \
    | while read -r path; do
        local name
        name="$(basename "$path")"
        if [[ -f "$path/feature_importance.csv" ]]; then
          printf '%s\n' "$name"
        fi
      done \
    | sort
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

  mapfile -t BIOMES < <(list_biomes "$shap_root")
  if [[ "${#BIOMES[@]}" -eq 0 ]]; then
    echo "[ERROR] No biome SHAP directories found under $shap_root" >&2
    exit 1
  fi

  printf '[INFO] %s biomes:' "$scope_name" >"$output_root/run.log"
  for biome in "${BIOMES[@]}"; do
    printf ' %s' "$biome" >>"$output_root/run.log"
  done
  printf '\n' >>"$output_root/run.log"

  for biome in "${BIOMES[@]}"; do
    echo "[RUN] $scope_name :: $biome" | tee -a "$output_root/run.log"
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

GPP_OUTPUT_ROOT="$RUN_ROOT/gpp_code1_flash_smrz_v20260401_halfunified"
RECO_OUTPUT_ROOT="$RUN_ROOT/reco_code1_flash_smrz_v20260401_halfunified"

mkdir -p "$GPP_OUTPUT_ROOT" "$RECO_OUTPUT_ROOT"

run_sem_block \
  "$GPP_PRE_TABLE" \
  "$GPP_PRE_SHAP_ROOT" \
  "$GPP_PRE_SPEC" \
  "prepeak_event" \
  "GPP" \
  "$GPP_OUTPUT_ROOT/sem_prepeak" \
  "gpp_prepeak_halfunified_0401"

run_sem_block \
  "$GPP_REC_TABLE" \
  "$GPP_REC_SHAP_ROOT" \
  "$GPP_REC_SPEC" \
  "process_recoverywin" \
  "GPP" \
  "$GPP_OUTPUT_ROOT/sem_recoverywin" \
  "gpp_recoverywin_halfunified_0401"

run_sem_block \
  "$RECO_PRE_TABLE" \
  "$RECO_PRE_SHAP_ROOT" \
  "$RECO_PRE_SPEC" \
  "prepeak_event" \
  "RECO" \
  "$RECO_OUTPUT_ROOT/sem_prepeak" \
  "reco_prepeak_halfunified_0401"

run_sem_block \
  "$RECO_REC_TABLE" \
  "$RECO_REC_SHAP_ROOT" \
  "$RECO_REC_SPEC" \
  "process_recoverywin" \
  "RECO" \
  "$RECO_OUTPUT_ROOT/sem_recoverywin" \
  "reco_recoverywin_halfunified_0401"

cat >"$RUN_ROOT/README.md" <<EOF
# 0401 Half-unified SEM Conclusion

Generated on ${DATE_TAG}.

Outputs:
- $GPP_OUTPUT_ROOT
- $RECO_OUTPUT_ROOT

Half-unified path skeleton:
- STRD -> TMP
- TMP + WIND -> VPD
- PRE + VPD -> EVA
- PRE + EVA -> SMrz

Terminal paths:
- GPP: TMP + VPD + EVA + SMrz -> t_recover
- RECO: TMP + VPD + SMrz -> t_recover
EOF

echo "[DONE] 0401 half-unified SEM outputs saved under $RUN_ROOT"
