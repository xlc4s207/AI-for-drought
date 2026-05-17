#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"
SUMMARY_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/12_summarize_candidate_models.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_recovery_phase_RECO_code1_flash_SMrz_mswepE.parquet"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean"
SHAP_BIOME_DIR="$RESULT_ROOT/shap_process_recoverywin_precipE_by_biome"
SEM_RESULT_ROOT="$RESULT_ROOT/sem_reco_precipE_l4"
LOG_DIR="$SEM_RESULT_ROOT/logs"
SPEC_DIR="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs"
JOBLIB_TMP="/tmp/reco_precipE_recoverywin_biome"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
  "Wetland"
)

mkdir -p "$SHAP_BIOME_DIR" "$SEM_RESULT_ROOT" "$LOG_DIR" "$JOBLIB_TMP"

run_biome() {
  local biome="$1"
  local biome_shap_dir="$SHAP_BIOME_DIR/$biome"
  mkdir -p "$biome_shap_dir"
  env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
  "$PYTHON_BIN" "$SHAP_SCRIPT" \
    --table "$TABLE" \
    --metric RECO \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope "process_recoverywin" \
    --exclude-features "recoverywin_p_minus_et" \
    --output-dir "$biome_shap_dir" >"$LOG_DIR/shap_${biome}.log" 2>&1

  local dpt_dir="$SEM_RESULT_ROOT/$biome/DPT_precipE_L4"
  local vpd_dir="$SEM_RESULT_ROOT/$biome/VPD_precipE_L4"
  mkdir -p "$dpt_dir" "$vpd_dir"

  "$PYTHON_BIN" "$SEM_SCRIPT" \
    --table "$TABLE" \
    --shap-results "$biome_shap_dir" \
    --model-spec-file "$SPEC_DIR/reco_code1_flash_smrz_recoverywin_dewpoint_precipE_l4_v20260415.txt" \
    --target "t_recover_to_baseline_abs_peak" \
    --feature-scope "process_recoverywin" \
    --metric RECO \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --exclude-features "recoverywin_p_minus_et" \
    --output-dir "$dpt_dir" >"$LOG_DIR/sem_${biome}_dpt.log" 2>&1

  "$PYTHON_BIN" "$SEM_SCRIPT" \
    --table "$TABLE" \
    --shap-results "$biome_shap_dir" \
    --model-spec-file "$SPEC_DIR/reco_code1_flash_smrz_recoverywin_vpd_precipE_l4_v20260415.txt" \
    --target "t_recover_to_baseline_abs_peak" \
    --feature-scope "process_recoverywin" \
    --metric RECO \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --exclude-features "recoverywin_p_minus_et" \
    --output-dir "$vpd_dir" >"$LOG_DIR/sem_${biome}_vpd.log" 2>&1
}

for biome in "${BIOMES[@]}"; do
  run_biome "$biome"
done

"$PYTHON_BIN" "$SUMMARY_SCRIPT" \
  --result-root "$SEM_RESULT_ROOT" \
  --output-csv "$SEM_RESULT_ROOT/candidate_model_summary.csv" \
  --output-md "$SEM_RESULT_ROOT/candidate_model_summary.md" >"$LOG_DIR/candidate_summary.log" 2>&1

echo "[DONE] RECO precipE by-biome SHAP+SEM saved under $RESULT_ROOT"
