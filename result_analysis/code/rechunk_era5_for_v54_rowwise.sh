#!/usr/bin/env bash
set -euo pipefail

# 目的: 将 ERA5 输入重分块为更适合 v5.4 按行读取的布局
# 目标 chunk: time=365, lat=1, lon=1440
# 输出目录: /home/xulc/flash_drought/era5/optimized_input

IN_SWVL1="/data/era5_for_GRN/yearly/volumetric_soil_water_layer_1_0p25deg_1980_2024.nc"
IN_ROOT="/data/era5_for_GRN/yearly/volumetric_root_soil_water_0p25deg_1980_2024.nc"
OUT_DIR="/home/xulc/flash_drought/era5/optimized_input"
OUT_SWVL1="${OUT_DIR}/volumetric_soil_water_layer_1_0p25deg_1980_2024_chunk_t365_lat1_lon1440.nc"
OUT_ROOT="${OUT_DIR}/volumetric_root_soil_water_0p25deg_1980_2024_chunk_t365_lat1_lon1440.nc"

mkdir -p "${OUT_DIR}"

echo "[INFO] 输出目录: ${OUT_DIR}"
echo "[INFO] 目标 chunk: time/365,lat/1,lon/1440"

if [[ ! -f "${OUT_SWVL1}" ]]; then
  echo "[STEP] 重分块 swvl1..."
  env HDF5_USE_FILE_LOCKING=FALSE nccopy -k nc4 -d 1 -c time/365,lat/1,lon/1440 "${IN_SWVL1}" "${OUT_SWVL1}"
  echo "[DONE] ${OUT_SWVL1}"
else
  echo "[SKIP] 已存在: ${OUT_SWVL1}"
fi

if [[ ! -f "${OUT_ROOT}" ]]; then
  echo "[STEP] 重分块 root..."
  env HDF5_USE_FILE_LOCKING=FALSE nccopy -k nc4 -d 1 -c time/365,lat/1,lon/1440 "${IN_ROOT}" "${OUT_ROOT}"
  echo "[DONE] ${OUT_ROOT}"
else
  echo "[SKIP] 已存在: ${OUT_ROOT}"
fi

echo "[INFO] 输出文件信息:"
ls -lh "${OUT_SWVL1}" "${OUT_ROOT}"


echo "[INFO] chunk 信息抽查:"
ncdump -s -h "${OUT_SWVL1}" | rg -n 'swvl1|_ChunkSizes|_Storage|_DeflateLevel' | sed -n '1,40p'
ncdump -s -h "${OUT_ROOT}" | rg -n 'root_water|_ChunkSizes|_Storage|_DeflateLevel' | sed -n '1,40p'
