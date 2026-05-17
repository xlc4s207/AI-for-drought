#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SEM_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/07_sem_analysis.py"
SUMMARY_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/12_summarize_candidate_models.py"

TABLE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/feature_table_recovery_phase_RECO_code1_flash_SMrz_mswepE_precipEmean.parquet"
SHAP_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipE_by_biome"
SPEC_DIR="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/sem_specs"
RESULT_ROOT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_reco_precipEmean_candidates_stage2_20260417"

BIOMES=(
  "Forest"
  "Grassland"
  "Savanna"
  "Cropland"
  "Shrubland"
)

MODELS=(
  "M3_delta:reco_code1_flash_smrz_recoverywin_precipEmean_M3_delta_v20260416.txt"
  "M4_tempdelta:reco_code1_flash_smrz_recoverywin_precipEmean_M4_tempdelta_v20260417.txt"
  "M5_precipdirect:reco_code1_flash_smrz_recoverywin_precipEmean_M5_precipdirect_v20260417.txt"
)

mkdir -p "$RESULT_ROOT"

for biome in "${BIOMES[@]}"; do
  for model in "${MODELS[@]}"; do
    model_id="${model%%:*}"
    spec_file="${model#*:}"
    out_dir="$RESULT_ROOT/$biome/$model_id"
    mkdir -p "$out_dir"
    "$PYTHON_BIN" "$SEM_SCRIPT" \
      --table "$TABLE" \
      --shap-results "$SHAP_ROOT/$biome" \
      --model-spec-file "$SPEC_DIR/$spec_file" \
      --target "t_recover_to_baseline_abs_peak" \
      --feature-scope "process_recoverywin" \
      --metric RECO \
      --code-id code1 \
      --biome "$biome" \
      --drought-type flash \
      --soil-layer SMrz \
      --exclude-features "recoverywin_p_minus_et" \
      --output-dir "$out_dir" >"$out_dir/run.log" 2>&1
  done
done

"$PYTHON_BIN" "$SUMMARY_SCRIPT" \
  --result-root "$RESULT_ROOT" \
  --output-csv "$RESULT_ROOT/candidate_model_summary.csv" \
  --output-md "$RESULT_ROOT/candidate_model_summary.md" >"$RESULT_ROOT/candidate_summary.log" 2>&1

echo "[DONE] RECO precipEmean stage2 candidate SEM comparison saved under $RESULT_ROOT"
