#!/usr/bin/env bash
set -euo pipefail

LAYER1_DIR="/data/era5_for_GRN/volunmetric_water1"
LAYER2_DIR="/data/era5_for_GRN/volunmetric_water2"
LAYER3_DIR="/data/era5_for_GRN/volunmetric_water3"
LAYER4_DIR="/data/era5_for_GRN/volunmetric_water4"
OUTPUT_DIR="/data/era5_for_GRN/volunmetric_root_water"
OUTPUT_PREFIX="volumetric_root_soil_water"
START_YEAR=1980
END_YEAR=2024
FORCE=0
COMPRESSION_LEVEL=1

usage() {
  cat <<'EOF'
Usage: create_era5_root_zone_soil_water.sh [options]

Options:
  --layer1-dir PATH      Directory for layer 1 yearly files.
  --layer2-dir PATH      Directory for layer 2 yearly files.
  --layer3-dir PATH      Directory for layer 3 yearly files.
  --layer4-dir PATH      Directory for layer 4 yearly files.
  --output-dir PATH      Directory for root-zone yearly outputs.
  --output-prefix NAME   Output filename prefix before _YYYY.nc.
  --start-year YEAR      First year to process.
  --end-year YEAR        Last year to process.
  --compression-level N  NetCDF compression level for ncks (-L).
  --force                Overwrite existing outputs.
  --help                 Show this help message.
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Required command not found: $1" >&2
    exit 1
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --layer1-dir)
        LAYER1_DIR="$2"
        shift 2
        ;;
      --layer2-dir)
        LAYER2_DIR="$2"
        shift 2
        ;;
      --layer3-dir)
        LAYER3_DIR="$2"
        shift 2
        ;;
      --layer4-dir)
        LAYER4_DIR="$2"
        shift 2
        ;;
      --output-dir)
        OUTPUT_DIR="$2"
        shift 2
        ;;
      --output-prefix)
        OUTPUT_PREFIX="$2"
        shift 2
        ;;
      --start-year)
        START_YEAR="$2"
        shift 2
        ;;
      --end-year)
        END_YEAR="$2"
        shift 2
        ;;
      --compression-level)
        COMPRESSION_LEVEL="$2"
        shift 2
        ;;
      --force)
        FORCE=1
        shift
        ;;
      --help)
        usage
        exit 0
        ;;
      *)
        echo "[ERROR] Unknown option: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done
}

input_file_for_year() {
  local layer="$1"
  local directory="$2"
  local year="$3"
  printf '%s/volumetric_soil_water_layer_%s_%s.nc' "$directory" "$layer" "$year"
}

process_year() {
  local year="$1"
  local in1 in2 in3 in4 out_file tmp_file timestamp

  in1="$(input_file_for_year 1 "$LAYER1_DIR" "$year")"
  in2="$(input_file_for_year 2 "$LAYER2_DIR" "$year")"
  in3="$(input_file_for_year 3 "$LAYER3_DIR" "$year")"
  in4="$(input_file_for_year 4 "$LAYER4_DIR" "$year")"
  out_file="${OUTPUT_DIR}/${OUTPUT_PREFIX}_${year}.nc"
  tmp_file="${OUTPUT_DIR}/.${OUTPUT_PREFIX}_${year}.$$.$RANDOM.tmp.nc"

  for input_file in "$in1" "$in2" "$in3" "$in4"; do
    if [[ ! -f "$input_file" ]]; then
      echo "[WARN] ${year}: missing input ${input_file}, skip" >&2
      return
    fi
  done

  if [[ -f "$out_file" && "$FORCE" -ne 1 ]]; then
    echo "[SKIP] ${year}: ${out_file} exists"
    return
  fi

  (
    trap 'rm -f "$tmp_file"' EXIT
    timestamp="$(date '+%F %T %Z')"

    rm -f "$tmp_file" "$out_file"

    ncks -O -4 -L "$COMPRESSION_LEVEL" -v time,lat,lon,swvl1 "$in1" "$tmp_file"
    ncks -A -v swvl2 "$in2" "$tmp_file"
    ncks -A -v swvl3 "$in3" "$tmp_file"
    ncks -A -v swvl4 "$in4" "$tmp_file"

    ncap2 -O -4 -L "$COMPRESSION_LEVEL" -s 'root_water=(7.0f*swvl1+21.0f*swvl2+72.0f*swvl3+189.0f*swvl4)/289.0f; root_water@units="m3 m-3"; root_water@long_name="Root zone soil water content (0-289 cm)"; root_water@standard_name="volume_fraction_of_condensed_water_in_soil"; root_water@coordinates="time lat lon"; root_water@comment="Thickness-weighted average of ERA5-Land layers 1-4 using depths 0-7 cm, 7-28 cm, 28-100 cm, and 100-289 cm."' \
      "$tmp_file" "$tmp_file"

    ncks -O -4 -L "$COMPRESSION_LEVEL" -x -v swvl1,swvl2,swvl3,swvl4 "$tmp_file" "$tmp_file"

    ncatted -O \
      -a title,global,o,c,"Root Zone Volumetric Soil Water - ${year}" \
      -a source,global,o,c,"ERA5-Land reanalysis" \
      -a history,global,o,c,"Created on ${timestamp} with create_era5_root_zone_soil_water.sh" \
      -a conventions,global,o,c,"CF-1.6" \
      -a description,global,o,c,"Root zone soil water content (0-289 cm) computed as the thickness-weighted average of ERA5-Land volumetric soil water layers 1-4: (7*swvl1 + 21*swvl2 + 72*swvl3 + 189*swvl4) / 289." \
      "$tmp_file"

    mv "$tmp_file" "$out_file"
    trap - EXIT
  )

  echo "[OK] ${year}: wrote ${out_file}"
}

main() {
  parse_args "$@"

  require_cmd ncks
  require_cmd ncap2
  require_cmd ncatted
  require_cmd date

  if (( START_YEAR > END_YEAR )); then
    echo "[ERROR] start year ${START_YEAR} is greater than end year ${END_YEAR}" >&2
    exit 1
  fi

  mkdir -p "$OUTPUT_DIR"

  echo "[INFO] Root-zone weighting formula: (7*swvl1 + 21*swvl2 + 72*swvl3 + 189*swvl4) / 289"
  echo "[INFO] Output directory: ${OUTPUT_DIR}"
  echo "[INFO] Output prefix: ${OUTPUT_PREFIX}"

  local year
  for ((year = START_YEAR; year <= END_YEAR; year++)); do
    process_year "$year"
  done
}

main "$@"
