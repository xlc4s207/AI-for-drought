#!/usr/bin/env bash
set -euo pipefail

PYTHON="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/41_redraw_prepeak_beeswarm_shortlabels.py"

"$PYTHON" "$SCRIPT" \
  --input-root "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420" \
  --output-dir "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/plot/GPP_prepeak" \
  --max-points 2500

echo "[DONE] GPP prepeak beeswarm plots with short labels saved"
