#!/usr/bin/env bash
set -euo pipefail

/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python \
  /home/xulc/flash_drought/process/process2/merge_era5_root_water_yearly.py \
  --input-dir /data/era5_for_GRN/volunmetric_water1_0p25deg \
  --output-dir /data/era5_for_GRN/yearly \
  --output-name volumetric_soil_water_layer_1_0p25deg_1980_2024.nc \
  --glob-pattern 'volumetric_soil_water_layer_1_*.nc' \
  --var-name swvl1 \
  --title 'Volumetric Soil Water Layer 1 0.25 degree 1980-2024' \
  --description 'Merged yearly ERA5 volumetric soil water layer 1 files with unified time axis in days since 1980-01-01 00:00:00.' \
  --force
