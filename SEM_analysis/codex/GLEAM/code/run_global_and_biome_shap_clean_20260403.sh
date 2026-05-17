#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"
TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_tables/gpp_code1_flash_smrz_rechunk_py/feature_table_recovery_phase_GPP_code1_flash_SMrz.parquet"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean"
GLOBAL_DIR="$RESULT_ROOT/shap_global"
BIOME_DIR="$RESULT_ROOT/shap_by_biome"
LOG_DIR="$RESULT_ROOT/logs"
JOBLIB_TMP="/data/flash_drought_joblib_tmp/gpp_code1_flash_smrz_clean"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
  "Wetland"
)

mkdir -p "$GLOBAL_DIR" "$BIOME_DIR" "$LOG_DIR" "$JOBLIB_TMP"

echo "[$(date '+%F %T')] CLEAN_SHAP_PIPELINE_START"

echo "[$(date '+%F %T')] GLOBAL_SHAP_START out=$GLOBAL_DIR"
env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
"$PYTHON_BIN" "$SHAP_SCRIPT" \
  --table "$TABLE" \
  --metric GPP \
  --code-id code1 \
  --drought-type flash \
  --soil-layer SMrz \
  --output-dir "$GLOBAL_DIR" >"$LOG_DIR/global_shap.log" 2>&1
echo "[$(date '+%F %T')] GLOBAL_SHAP_END"

for biome in "${BIOMES[@]}"; do
  out_dir="$BIOME_DIR/$biome"
  log_file="$LOG_DIR/${biome}.log"
  mkdir -p "$out_dir"
  echo "[$(date '+%F %T')] BIOME_SHAP_START biome=$biome out=$out_dir"
  env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
  "$PYTHON_BIN" "$SHAP_SCRIPT" \
    --table "$TABLE" \
    --metric GPP \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --output-dir "$out_dir" >"$log_file" 2>&1
  echo "[$(date '+%F %T')] BIOME_SHAP_END biome=$biome"
done

echo "[$(date '+%F %T')] CLEAN_SHAP_PIPELINE_DONE"
