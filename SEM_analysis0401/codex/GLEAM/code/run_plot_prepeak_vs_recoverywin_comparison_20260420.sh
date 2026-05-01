#!/usr/bin/env bash
set -euo pipefail

PYTHON="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/33_plot_prepeak_vs_recoverywin_comparison.py"

"$PYTHON" "$SCRIPT" \
  --prepeak-root "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome" \
  --recoverywin-root "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome" \
  --output-dir "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_compare_prepeak_vs_recoverywin_20260420"

echo "[DONE] prepeak vs recoverywin comparison figures saved"
