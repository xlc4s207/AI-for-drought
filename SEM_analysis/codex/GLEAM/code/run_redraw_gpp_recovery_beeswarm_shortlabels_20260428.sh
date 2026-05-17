#!/usr/bin/env bash
set -euo pipefail

PYTHON="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/41_redraw_prepeak_beeswarm_shortlabels.py"

"$PYTHON" "$SCRIPT" \
  --input-root "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome" \
  --output-dir "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/plot/GPP_recovery" \
  --max-points 2500 \
  --title-prefix "Recoverywin" \
  --output-suffix "recoverywin"

echo "[DONE] GPP recovery beeswarm plots with short labels saved"
