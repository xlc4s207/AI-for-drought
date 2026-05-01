#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/results/reco_code1_flash_smrz_v20260401_mswepE_clean"
LOG="$ROOT/reco0401_recovery_watch.log"
DONE_SHAP="$ROOT/shap_process_recoverywin_precipEmean_sample50k_by_biome/Wetland/feature_importance.csv"
DONE_SEM="$ROOT/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260424/by_biome/RECO_code1_Wetland_flash_SMrz_sem_summary.txt"
PIPELINE="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/code/run_0401_smrz_shap_sem_pipeline.sh"

while true; do
    if [[ -f "$DONE_SHAP" && -f "$DONE_SEM" ]]; then
        echo "[DONE] $(date +%F_%T)" >> "$LOG"
        break
    fi

    echo "[RESUME] $(date +%F_%T)" >> "$LOG"
    bash "$PIPELINE" run_reco_recovery >> "$LOG" 2>&1 || true
    sleep 120
done
