#!/usr/bin/env bash
set -u

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/10_rechunk_era5_parallel.py"
OUT_DIR="/data/era5_for_GRN/rechunked_spatial_20260402"
LOG_FILE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/logs/rechunk_era5_python_batch_20260402.log"

TIME_CHUNK="${TIME_CHUNK:-64}"
READ_WORKERS="${READ_WORKERS:-2}"
MAX_PENDING="${MAX_PENDING:-2}"
TARGET_TIME_CHUNK="${TARGET_TIME_CHUNK:-256}"
TARGET_LAT_CHUNK="${TARGET_LAT_CHUNK:-32}"
TARGET_LON_CHUNK="${TARGET_LON_CHUNK:-32}"

FILES=(
  "/data/era5_for_GRN/yearly/temperature_2m_0p25deg_1980_2024.nc"
  "/data/era5_for_GRN/yearly/total_precipitation_0p25deg_1980_2024.nc"
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

mkdir -p "$OUT_DIR"
mkdir -p "$(dirname "$LOG_FILE")"
exec >"$LOG_FILE" 2>&1

echo "[$(date '+%F %T')] BATCH_START out_dir=$OUT_DIR count=${#FILES[@]} time_chunk=$TIME_CHUNK read_workers=$READ_WORKERS max_pending=$MAX_PENDING"

for f in "${FILES[@]}"; do
  base="$(basename "$f")"
  out="$OUT_DIR/${base%.nc}_spatialchunks_py.nc"
  echo "[$(date '+%F %T')] START $base -> $out"
  "$PYTHON_BIN" "$SCRIPT" \
    --input "$f" \
    --output "$out" \
    --time-chunk "$TIME_CHUNK" \
    --read-workers "$READ_WORKERS" \
    --max-pending "$MAX_PENDING" \
    --target-time-chunk "$TARGET_TIME_CHUNK" \
    --target-lat-chunk "$TARGET_LAT_CHUNK" \
    --target-lon-chunk "$TARGET_LON_CHUNK"
  status=$?
  echo "[$(date '+%F %T')] END status=$status $base"
  if [ "$status" -ne 0 ]; then
    echo "[$(date '+%F %T')] BATCH_ABORT failed=$base"
    exit "$status"
  fi
done

echo "[$(date '+%F %T')] BATCH_DONE"
