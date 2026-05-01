#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_recovery_phase_RECO_code1_flash_SMrz_mswepE_precipEmean.parquet"
SHAP_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipE_by_biome"
SPEC_FILE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs/reco_code1_flash_smrz_recoverywin_gpp_precipEmean_vpd_hybrid_pruned_v20260416.txt"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_recoverywin_gpp_precipEmean_vpd_hybrid_pruned_20260416/by_biome"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
)

mkdir -p "$RESULT_ROOT"

for biome in "${BIOMES[@]}"; do
  "$PYTHON_BIN" "$SEM_SCRIPT" \
    --table "$TABLE" \
    --shap-results "$SHAP_ROOT/$biome" \
    --model-spec-file "$SPEC_FILE" \
    --target "t_recover_to_baseline_abs_peak" \
    --feature-scope "process_recoverywin" \
    --metric RECO \
    --code-id code1 \
    --biome "$biome" \
    --drought-type flash \
    --soil-layer SMrz \
    --exclude-features "recoverywin_p_minus_et" \
    --output-dir "$RESULT_ROOT" >"$RESULT_ROOT/${biome}.log" 2>&1
done

echo "[DONE] RECO pruned GPP-like precipEmean VPD hybrid SEM saved under $RESULT_ROOT"
