#!/usr/bin/env bash
set -euo pipefail

INPUT_ROOT="/data/era5_for_GRN"
OUTPUT_ROOT="/data/era5_for_GRN"
TMP_DIR="/tmp/era5_sm_r025_tmp"
LAYERS_CSV="1,2,3,4"
START_YEAR=1980
END_YEAR=2024
THREADS="${NCO_THREADS:-2}"
DEFLATE=1
ALGORITHM="ncoaave"
FORCE=0
DRY_RUN=0

readonly GRID_NAME="era5_r025_720x1440_scrip.nc"
readonly GRID_SPEC="ttl=Equi-Angular_0.25x0.25_degree_uniform_grid_r025_720x1440#latlon=720,1440#lat_typ=uni#lon_typ=180_wst"

usage() {
    cat <<'EOF'
Usage: resample_era5_soil_water_to_025deg.sh [options]

Resample yearly ERA5-Land volumetric soil water layer files from 0.1 degree
to 0.25 degree using ncremap area-weighted averaging.

Options:
  --input-root DIR    Root directory containing volunmetric_water1..4
  --output-root DIR   Root directory for volunmetric_water1_0p25deg..4_0p25deg
  --tmp-dir DIR       Directory for ncremap scratch files
  --layers LIST       Comma-separated layer list, e.g. 1 or 1,2,3,4
  --start-year YEAR   First year to process
  --end-year YEAR     Last year to process
  --threads N         Threads passed to ncremap
  --deflate N         NetCDF deflate level for outputs
  --algorithm NAME    ncremap algorithm, default ncoaave
  --force             Overwrite existing outputs
  --dry-run           Print commands without executing them
  --help              Show this message

Example:
  bash process/process2/resample_era5_soil_water_to_025deg.sh \
    --layers 1,2,3,4 \
    --start-year 1980 \
    --end-year 1980 \
    --threads 2
EOF
}

log() {
    printf '[%s] %s\n' "$(date '+%F %T')" "$*" >&2
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

trim() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "$value"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --input-root)
                INPUT_ROOT="$2"
                shift 2
                ;;
            --output-root)
                OUTPUT_ROOT="$2"
                shift 2
                ;;
            --tmp-dir)
                TMP_DIR="$2"
                shift 2
                ;;
            --layers)
                LAYERS_CSV="$2"
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
            --threads)
                THREADS="$2"
                shift 2
                ;;
            --deflate)
                DEFLATE="$2"
                shift 2
                ;;
            --algorithm)
                ALGORITHM="$2"
                shift 2
                ;;
            --force)
                FORCE=1
                shift
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                die "unknown option: $1"
                ;;
        esac
    done
}

validate_args() {
    [[ "$THREADS" =~ ^[1-9][0-9]*$ ]] || die "--threads must be a positive integer"
    [[ "$DEFLATE" =~ ^[0-9]+$ ]] || die "--deflate must be an integer between 0 and 9"
    (( DEFLATE >= 0 && DEFLATE <= 9 )) || die "--deflate must be between 0 and 9"
    (( START_YEAR <= END_YEAR )) || die "--start-year must be <= --end-year"
}

selected_layers() {
    local item trimmed
    IFS=',' read -r -a items <<<"$LAYERS_CSV"
    for item in "${items[@]}"; do
        trimmed="$(trim "$item")"
        case "$trimmed" in
            1|2|3|4)
                printf '%s\n' "$trimmed"
                ;;
            *)
                die "unsupported layer in --layers: $trimmed"
                ;;
        esac
    done
}

layer_input_dir() {
    printf '%s/volunmetric_water%s' "$INPUT_ROOT" "$1"
}

layer_output_dir() {
    printf '%s/volunmetric_water%s_0p25deg' "$OUTPUT_ROOT" "$1"
}

layer_var_name() {
    printf 'swvl%s' "$1"
}

year_file_name() {
    printf 'volumetric_soil_water_layer_%s_%s.nc' "$1" "$2"
}

run_cmd() {
    if (( DRY_RUN )); then
        printf '+'
        printf ' %q' "$@"
        printf '\n'
    else
        "$@"
    fi
}

ensure_dirs() {
    if (( DRY_RUN )); then
        return
    fi
    mkdir -p "$TMP_DIR"
}

ensure_destination_grid() {
    local grid_file="$OUTPUT_ROOT/$GRID_NAME"

    if [[ -f "$grid_file" ]]; then
        printf '%s\n' "$grid_file"
        return
    fi

    log "creating destination grid: $grid_file"
    run_cmd ncremap --no_stdin -4 --dfl_lvl=1 -G "$GRID_SPEC" -g "$grid_file"
    printf '%s\n' "$grid_file"
}

resample_one() {
    local layer="$1"
    local year="$2"
    local input_dir output_dir input_file output_file grid_file var_name

    input_dir="$(layer_input_dir "$layer")"
    output_dir="$(layer_output_dir "$layer")"
    input_file="${input_dir}/$(year_file_name "$layer" "$year")"
    output_file="${output_dir}/$(year_file_name "$layer" "$year")"
    var_name="$(layer_var_name "$layer")"

    [[ -f "$input_file" ]] || die "input file not found: $input_file"

    if [[ -f "$output_file" && "$FORCE" -ne 1 ]]; then
        log "skip existing output: $output_file"
        return
    fi

    if (( ! DRY_RUN )); then
        mkdir -p "$output_dir"
    fi

    grid_file="$(ensure_destination_grid)"

    log "regridding layer ${layer} year ${year}: $(basename "$input_file")"
    run_cmd ncremap \
        --no_stdin \
        -4 \
        -L "$DEFLATE" \
        -a "$ALGORITHM" \
        -v "$var_name" \
        -g "$grid_file" \
        -T "$TMP_DIR" \
        -t "$THREADS" \
        "$input_file" \
        "$output_file"
}

main() {
    local layer year

    parse_args "$@"
    validate_args
    require_cmd ncremap
    require_cmd ncks
    ensure_dirs

    log "input_root=$INPUT_ROOT"
    log "output_root=$OUTPUT_ROOT"
    log "tmp_dir=$TMP_DIR"
    log "layers=$LAYERS_CSV"
    log "years=${START_YEAR}-${END_YEAR}"
    log "algorithm=$ALGORITHM"
    log "threads=$THREADS"
    log "deflate=$DEFLATE"

    while IFS= read -r layer; do
        for ((year = START_YEAR; year <= END_YEAR; year++)); do
            resample_one "$layer" "$year"
        done
    done < <(selected_layers)

    log "all requested ERA5 soil-water resampling finished"
}

main "$@"
