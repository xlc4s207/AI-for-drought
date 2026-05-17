#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_tables/gpp_code1_flash_smrz_rechunk_py/feature_table_pre_recovery_GPP_code1_flash_SMrz.parquet"
SHAP_RESULTS_ROOT="/home/xulc/flash_drought/process/SEM_analysis/anti/GLEAM/results/shap_pre_recovery_gpp_code1_flash_smrz"
SEM_RESULTS_ROOT="/home/xulc/flash_drought/process/SEM_analysis/anti/GLEAM/results/sem_pre_recovery_gpp_code1_flash_smrz"

LOG_DIR="$SEM_RESULTS_ROOT/logs"
mkdir -p "$SEM_RESULTS_ROOT/sem_global" "$SEM_RESULTS_ROOT/sem_by_biome" "$LOG_DIR"

echo "[$(date '+%F %T')] PRE_RECOVERY_SEM_PIPELINE_START" | tee "$SEM_RESULTS_ROOT/pipeline.log"

# --- 全局 SEM ---
echo "[$(date '+%F %T')] GLOBAL_SEM_START" | tee -a "$SEM_RESULTS_ROOT/pipeline.log"
"$PYTHON_BIN" "$SEM_SCRIPT" \
  --table "$TABLE" \
  --shap-results "$SHAP_RESULTS_ROOT/shap_global/feature_importance.csv" \
  --metric GPP \
  --code-id code1 \
  --drought-type flash \
  --soil-layer SMrz \
  --feature-scope predictive \
  --biome "None" \
  --output-dir "$SEM_RESULTS_ROOT/sem_global" \
  --top-k 8 >"$LOG_DIR/global_sem.log" 2>&1
echo "[$(date '+%F %T')] GLOBAL_SEM_END" | tee -a "$SEM_RESULTS_ROOT/pipeline.log"

# --- 分 biome SEM ---
BIOMES=("Forest" "Grassland" "Savanna" "Cropland" "Shrubland" "Wetland")
for biome in "${BIOMES[@]}"; do
  out_dir="$SEM_RESULTS_ROOT/sem_by_biome/$biome"
  log_file="$LOG_DIR/${biome}.log"
  mkdir -p "$out_dir"
  echo "[$(date '+%F %T')] BIOME_SEM_START biome=$biome" | tee -a "$SEM_RESULTS_ROOT/pipeline.log"
  "$PYTHON_BIN" "$SEM_SCRIPT" \
    --table "$TABLE" \
    --shap-results "$SHAP_RESULTS_ROOT/shap_by_biome/$biome/feature_importance.csv" \
    --metric GPP \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope predictive \
    --output-dir "$out_dir" \
    --top-k 8 >"$log_file" 2>&1
  echo "[$(date '+%F %T')] BIOME_SEM_END biome=$biome" | tee -a "$SEM_RESULTS_ROOT/pipeline.log"
done

echo "[$(date '+%F %T')] PRE_RECOVERY_SEM_PIPELINE_DONE" | tee -a "$SEM_RESULTS_ROOT/pipeline.log"
