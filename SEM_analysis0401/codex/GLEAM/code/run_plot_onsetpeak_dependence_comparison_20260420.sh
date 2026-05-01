#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/32_plot_onsetpeak_dependence_comparison.py"

"$PYTHON_BIN" "$SCRIPT" \
  --prepeak-root "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome" \
  --shock-root "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/shock_event_shap_sem_20260420/shap_by_biome" \
  --output-dir "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/core_dependence_compare_20260420"

echo "[DONE] onset-to-peak side-by-side dependence figures saved"
