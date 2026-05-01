#!/usr/bin/env bash
set -u

OUT_DIR="/data/era5_for_GRN/rechunked_spatial_20260402"
LOG_FILE="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/logs/rechunk_era5_batch_20260402.log"

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

echo "[$(date '+%F %T')] BATCH_START out_dir=$OUT_DIR count=${#FILES[@]}"

for f in "${FILES[@]}"; do
  base="$(basename "$f")"
  out="$OUT_DIR/${base%.nc}_spatialchunks.nc"
  echo "[$(date '+%F %T')] START $base -> $out"
  ncks -O -7 -L 1 --cnk_plc all --cnk_dmn time,256 --cnk_dmn lat,32 --cnk_dmn lon,32 -t 16 "$f" "$out"
  status=$?
  echo "[$(date '+%F %T')] END status=$status $base"
  if [ "$status" -ne 0 ]; then
    echo "[$(date '+%F %T')] BATCH_ABORT failed=$base"
    exit "$status"
  fi
done

echo "[$(date '+%F %T')] BATCH_DONE"
