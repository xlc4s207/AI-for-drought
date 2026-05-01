#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"
PATH_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/13_plot_sem_path_diagrams.py"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
)

PREPEAK_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_prepeak_event_GPP_code1_flash_SMrz_onsetpeak.parquet"
PREPEAK_SHAP_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome"
PREPEAK_SPEC="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs/gpp_code1_flash_smrz_prepeak_event_mechanism_v20260420.txt"
PREPEAK_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/sem_prepeak_event_mechanism_20260420"
PREPEAK_RESULT="$PREPEAK_ROOT/by_biome"

SHOCK_TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_shock_event_GPP_code1_flash_SMrz_onsetpeak.parquet"
SHOCK_SHAP_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/shock_event_shap_sem_20260420/shap_by_biome"
SHOCK_SPEC="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs/gpp_code1_flash_smrz_shock_event_mechanism_v20260420.txt"
SHOCK_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/sem_shock_event_mechanism_20260420"
SHOCK_RESULT="$SHOCK_ROOT/by_biome"

mkdir -p "$PREPEAK_RESULT" "$SHOCK_RESULT"

for biome in "${BIOMES[@]}"; do
  "$PYTHON_BIN" "$SEM_SCRIPT" \
    --table "$PREPEAK_TABLE" \
    --shap-results "$PREPEAK_SHAP_ROOT/$biome" \
    --model-spec-file "$PREPEAK_SPEC" \
    --target "t_recover_to_baseline_abs_peak" \
    --feature-scope "prepeak_event" \
    --metric GPP \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --output-dir "$PREPEAK_RESULT" >"$PREPEAK_RESULT/${biome}.log" 2>&1
done

"$PYTHON_BIN" "$PATH_SCRIPT" \
  --sem-dir "$PREPEAK_RESULT" \
  --output-dir "$PREPEAK_ROOT"

for biome in "${BIOMES[@]}"; do
  "$PYTHON_BIN" "$SEM_SCRIPT" \
    --table "$SHOCK_TABLE" \
    --shap-results "$SHOCK_SHAP_ROOT/$biome" \
    --model-spec-file "$SHOCK_SPEC" \
    --target "t_recover_to_baseline_abs_peak" \
    --feature-scope "shock_event" \
    --metric GPP \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --output-dir "$SHOCK_RESULT" >"$SHOCK_RESULT/${biome}.log" 2>&1
done

"$PYTHON_BIN" "$PATH_SCRIPT" \
  --sem-dir "$SHOCK_RESULT" \
  --output-dir "$SHOCK_ROOT"

echo "[DONE] onset-to-peak mechanism SEM results saved under $PREPEAK_ROOT and $SHOCK_ROOT"
