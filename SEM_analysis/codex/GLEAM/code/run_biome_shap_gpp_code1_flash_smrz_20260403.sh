#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"
TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_tables/gpp_code1_flash_smrz_rechunk_py/feature_table_recovery_phase_GPP_code1_flash_SMrz.parquet"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py/shap_by_biome"
LOG_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py/shap_by_biome_logs"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
  "Wetland"
)

mkdir -p "$RESULT_ROOT" "$LOG_ROOT"

echo "[$(date '+%F %T')] BIOME_SHAP_START"

for biome in "${BIOMES[@]}"; do
  out_dir="$RESULT_ROOT/$biome"
  log_file="$LOG_ROOT/${biome}.log"
  mkdir -p "$out_dir"
  echo "[$(date '+%F %T')] START biome=$biome out=$out_dir log=$log_file"
  "$PYTHON_BIN" "$SHAP_SCRIPT" \
    --table "$TABLE" \
    --metric GPP \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --output-dir "$out_dir" >"$log_file" 2>&1
  echo "[$(date '+%F %T')] END biome=$biome"
done

echo "[$(date '+%F %T')] BIOME_SHAP_DONE"
