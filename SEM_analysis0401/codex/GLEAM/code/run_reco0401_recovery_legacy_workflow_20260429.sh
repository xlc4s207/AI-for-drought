#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
CODE_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/code"
DEP_SCRIPT="$CODE_DIR/18_batch_dependence_plots_reco0401_recovery_legacy.py"
TABLE="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/data/feature_table_recovery_phase_RECO_code1_flash_SMrz_0401_mswepE.parquet"
OUTPUT_ROOT="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/results/reco_code1_flash_smrz_v20260401_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome"
JOBLIB_TMP="/tmp/reco0401_recovery_legacy_20260429"
TARGET_SAMPLE_SIZE=5000
TOTAL_CPUS=$(nproc)
PARALLEL_BIOMES=${PARALLEL_BIOMES:-4}
if [[ "$PARALLEL_BIOMES" -lt 1 ]]; then
  PARALLEL_BIOMES=1
fi
N_JOBS_PER_BIOME=${N_JOBS_PER_BIOME:-$(( TOTAL_CPUS / PARALLEL_BIOMES ))}
if [[ "$N_JOBS_PER_BIOME" -lt 1 ]]; then
  N_JOBS_PER_BIOME=1
fi

BIOMES=(
  "Cropland"
  "Forest"
  "Grassland"
  "Savanna"
  "Shrubland"
)

INCLUDE_FEATURES=(
  "recoverywin_total_precipitation_mean"
  "recoverywin_total_evaporation_mean"
  "recoverywin_SMrz_mean"
  "recoverywin_temperature_2m_mean"
  "recoverywin_VPD_mean"
  "recoverywin_wind_speed_mean"
  "recoverywin_lai_total_mean"
  "recoverywin_ssrd_mean"
  "recoverywin_strd_mean"
)

EXCLUDE_FEATURES=(
  "recoverywin_p_minus_et"
  "recoverywin_total_precipitation_sum"
  "recoverywin_total_evaporation_sum"
  "recoverywin_SMrz_delta"
)

mkdir -p "$OUTPUT_ROOT/_logs" "$JOBLIB_TMP"

needs_rebuild() {
  local biome="$1"
  local parquet_path="$OUTPUT_ROOT/$biome/dependence_sample_features.parquet"
  if [[ ! -f "$parquet_path" ]]; then
    return 0
  fi
  local row_count
  row_count=$(env PARQUET_PATH="$parquet_path" "$PYTHON_BIN" - <<'PY'
import os
import pandas as pd
path = os.environ["PARQUET_PATH"]
try:
    print(len(pd.read_parquet(path)))
except Exception:
    print(-1)
PY
)
  [[ "$row_count" -lt "$TARGET_SAMPLE_SIZE" ]]
}

pending_biomes=()
for biome in "${BIOMES[@]}"; do
  if needs_rebuild "$biome"; then
    pending_biomes+=("$biome")
  else
    echo "[SKIP] biome=$biome already has >=${TARGET_SAMPLE_SIZE} dependence samples"
  fi
done

if [[ "${#pending_biomes[@]}" -eq 0 ]]; then
  echo "[DONE] no biome requires legacy rebuild"
  exit 0
fi

active_jobs=0
pids=()
names=()
for biome in "${pending_biomes[@]}"; do
  echo "[RUN] legacy biome=$biome n_jobs=$N_JOBS_PER_BIOME parallel_biomes=$PARALLEL_BIOMES total_cpus=$TOTAL_CPUS"
  mkdir -p "$JOBLIB_TMP/$biome"
  mkdir -p "$JOBLIB_TMP/$biome/mpl"
  : >"$OUTPUT_ROOT/_logs/${biome}_legacy_dependence_20260429.log"
  env MPLCONFIGDIR="$JOBLIB_TMP/$biome/mpl" JOBLIB_TEMP_FOLDER="$JOBLIB_TMP/$biome" TMPDIR="$JOBLIB_TMP/$biome" \
    "$PYTHON_BIN" "$DEP_SCRIPT" \
    --datasets reco0401_recoverywin_mean \
    --biomes "$biome" \
    --n-jobs-override "$N_JOBS_PER_BIOME" \
    --shap-sample-size-override "$TARGET_SAMPLE_SIZE" >"$OUTPUT_ROOT/_logs/${biome}_legacy_dependence_20260429.log" 2>&1 &
  pids+=("$!")
  names+=("$biome")
  active_jobs=$((active_jobs + 1))

  if [[ "$active_jobs" -ge "$PARALLEL_BIOMES" ]]; then
    wait -n
    active_jobs=$((active_jobs - 1))
  fi
done

failed=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    echo "[ERROR] biome=${names[$i]} failed; see $OUTPUT_ROOT/_logs/${names[$i]}_legacy_dependence_20260429.log" >&2
    failed=1
  fi
done

if [[ "$failed" -ne 0 ]]; then
  exit 1
fi

echo "[DONE] RECO 0401 recovery legacy workflow completed."
