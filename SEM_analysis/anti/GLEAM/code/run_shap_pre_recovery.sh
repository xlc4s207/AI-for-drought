#!/usr/bin/env bash
# ============================================================
# 口径A: 前置预测型 SHAP (P0+P1+P2)
# GPP code1 flash SMrz — 全局 + 6 biome
# 使用 codex 的 06_shap_analysis.py + pre_recovery 特征表
# ============================================================
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SHAP_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/06_shap_analysis.py"

# 关键区别: 使用 pre_recovery 表 (P0+P1+P2)
TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_tables/gpp_code1_flash_smrz_rechunk_py/feature_table_pre_recovery_GPP_code1_flash_SMrz.parquet"

RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/anti/GLEAM/results/shap_pre_recovery_gpp_code1_flash_smrz"
GLOBAL_DIR="$RESULT_ROOT/shap_global"
BIOME_DIR="$RESULT_ROOT/shap_by_biome"
LOG_DIR="$RESULT_ROOT/logs"
JOBLIB_TMP="/data/flash_drought_joblib_tmp/shap_pre_recovery"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
  "Wetland"
)

mkdir -p "$GLOBAL_DIR" "$BIOME_DIR" "$LOG_DIR" "$JOBLIB_TMP"

echo "[$(date '+%F %T')] PRE_RECOVERY_SHAP_PIPELINE_START" | tee "$RESULT_ROOT/pipeline.log"

# --- 全局模型 ---
echo "[$(date '+%F %T')] GLOBAL_SHAP_START" | tee -a "$RESULT_ROOT/pipeline.log"
env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
"$PYTHON_BIN" "$SHAP_SCRIPT" \
  --table "$TABLE" \
  --metric GPP \
  --code-id code1 \
  --drought-type flash \
  --soil-layer SMrz \
  --output-dir "$GLOBAL_DIR" \
  --shap-sample-size 5000 \
  --n-estimators 500 >"$LOG_DIR/global_shap.log" 2>&1
echo "[$(date '+%F %T')] GLOBAL_SHAP_END" | tee -a "$RESULT_ROOT/pipeline.log"

# --- 分 biome 模型 ---
for biome in "${BIOMES[@]}"; do
  out_dir="$BIOME_DIR/$biome"
  log_file="$LOG_DIR/${biome}.log"
  mkdir -p "$out_dir"
  echo "[$(date '+%F %T')] BIOME_SHAP_START biome=$biome" | tee -a "$RESULT_ROOT/pipeline.log"
  env JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
  "$PYTHON_BIN" "$SHAP_SCRIPT" \
    --table "$TABLE" \
    --metric GPP \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --output-dir "$out_dir" \
    --shap-sample-size 5000 \
    --n-estimators 500 >"$log_file" 2>&1
  echo "[$(date '+%F %T')] BIOME_SHAP_END biome=$biome" | tee -a "$RESULT_ROOT/pipeline.log"
done

echo "[$(date '+%F %T')] PRE_RECOVERY_SHAP_PIPELINE_DONE" | tee -a "$RESULT_ROOT/pipeline.log"
echo "Results in: $RESULT_ROOT"
