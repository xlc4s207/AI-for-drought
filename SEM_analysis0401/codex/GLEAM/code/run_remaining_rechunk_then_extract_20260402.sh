#!/usr/bin/env bash
set -u

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
RECHUNK_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/10_rechunk_era5_parallel.py"
EXTRACT_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/02_extract_era5_features.py"

RECHUNK_DIR="/data/era5_for_GRN/rechunked_spatial_20260402"
LOG_FILE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/logs/rechunk_queue_then_extract_20260402.log"
EXTRACT_LOG="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/logs/02_extract_era5_features_GPP_code1_flash_SMrz_rechunk_py_20260402.log"
EXTRACT_OUT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/data/era5_features_GPP_code1_flash_SMrz_rechunk_py.parquet"

TIME_CHUNK="${TIME_CHUNK:-64}"
READ_WORKERS="${READ_WORKERS:-3}"
MAX_PENDING="${MAX_PENDING:-3}"
TARGET_TIME_CHUNK="${TARGET_TIME_CHUNK:-256}"
TARGET_LAT_CHUNK="${TARGET_LAT_CHUNK:-32}"
TARGET_LON_CHUNK="${TARGET_LON_CHUNK:-32}"

WAIT_SESSIONS=("era5_py_rechunk_20260402" "era5_py_rechunk_tp_20260402")

REMAINING_FILES=(
  "/data/era5_for_GRN/yearly/total_evaporation_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/ssrd_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/strd_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/surface_pressure_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/wind_u_10m_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/wind_v_10m_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/soil_temperature_level_1_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/soil_temperature_level_2_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/soil_temperature_level_3_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/soil_temperature_level_4_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/leaf_area_index_high_vegetation_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/leaf_area_index_low_vegetation_0p25deg_1980_2024.nc"
)

EXPECTED_OUTPUTS=(
  "$RECHUNK_DIR/temperature_2m_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/total_precipitation_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/total_evaporation_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/ssrd_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/strd_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/surface_pressure_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/wind_u_10m_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/wind_v_10m_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/soil_temperature_level_1_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/soil_temperature_level_2_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/soil_temperature_level_3_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/soil_temperature_level_4_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/leaf_area_index_high_vegetation_0p25deg_1980_2024_spatialchunks_py.nc"
  "$RECHUNK_DIR/leaf_area_index_low_vegetation_0p25deg_1980_2024_spatialchunks_py.nc"
)

mkdir -p "$RECHUNK_DIR"
mkdir -p "$(dirname "$LOG_FILE")"
exec >"$LOG_FILE" 2>&1

echo "[$(date '+%F %T')] QUEUE_START"

for session_name in "${WAIT_SESSIONS[@]}"; do
  while tmux has-session -t "$session_name" 2>/dev/null; do
    echo "[$(date '+%F %T')] waiting_for_session=$session_name"
    sleep 60
  done
done

for f in "${REMAINING_FILES[@]}"; do
  base="$(basename "$f")"
  out="$RECHUNK_DIR/${base%.nc}_spatialchunks_py.nc"
  if [ -s "$out" ]; then
    echo "[$(date '+%F %T')] SKIP_EXISTING $base -> $out"
    continue
  fi
  echo "[$(date '+%F %T')] START_REMAINING $base -> $out"
  "$PYTHON_BIN" "$RECHUNK_SCRIPT" \
    --input "$f" \
    --output "$out" \
    --time-chunk "$TIME_CHUNK" \
    --read-workers "$READ_WORKERS" \
    --max-pending "$MAX_PENDING" \
    --target-time-chunk "$TARGET_TIME_CHUNK" \
    --target-lat-chunk "$TARGET_LAT_CHUNK" \
    --target-lon-chunk "$TARGET_LON_CHUNK"
  status=$?
  echo "[$(date '+%F %T')] END_REMAINING status=$status $base"
  if [ "$status" -ne 0 ]; then
    echo "[$(date '+%F %T')] QUEUE_ABORT failed=$base"
    exit "$status"
  fi
done

for out in "${EXPECTED_OUTPUTS[@]}"; do
  if [ ! -s "$out" ]; then
    echo "[$(date '+%F %T')] MISSING_OUTPUT $out"
    exit 1
  fi
done

echo "[$(date '+%F %T')] RECHUNK_ALL_DONE"
echo "[$(date '+%F %T')] EXTRACT_START log=$EXTRACT_LOG output=$EXTRACT_OUT"

"$PYTHON_BIN" "$EXTRACT_SCRIPT" \
  --metric GPP \
  --code-id code1 \
  --drought-type flash \
  --soil-layer SMrz \
  --workers 24 \
  --concurrent-era5-tasks 2 \
  --reserve-cpus 8 \
  --progress-every 10 \
  --vars-per-task 2 \
  --batch-size 200000 \
  --tile-lat-size 16 \
  --tile-lon-size 16 \
  --era5-root-dir "$RECHUNK_DIR" \
  --output "$EXTRACT_OUT" >"$EXTRACT_LOG" 2>&1

extract_status=$?
echo "[$(date '+%F %T')] EXTRACT_END status=$extract_status"
exit "$extract_status"
