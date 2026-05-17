#!/usr/bin/env bash
set -euo pipefail

INPUT_ROOT="/data/BESS_V2/GPP_Daily/yearly0.1"
OUTPUT_ROOT="/data/BESS_V2/GPP_Daily/yearly0.25"
TMP_DIR="/tmp/bess_gpp_daily_r025_tmp"
START_YEAR=1982
END_YEAR=2022
THREADS="${NCO_THREADS:-2}"
DEFLATE=1
ALGORITHM="ncoaave"
FORCE=0
DRY_RUN=0

readonly VAR_NAME="GPP"
readonly STANDARD_FILL_VALUE="1.0e36"
readonly GRID_NAME="bess_gpp_daily_r025_720x1440_scrip.nc"
readonly GRID_SPEC="ttl=Equi-Angular_0.25x0.25_degree_uniform_grid_r025_720x1440#latlon=720,1440#lat_typ=uni#lon_typ=180_wst"

usage() {
    cat <<'EOF'
Usage: resample_bess_gpp_daily_to_025deg.sh [options]

Resample BESS daily GPP yearly NetCDF files from 0.1 degree to 0.25 degree
using ncremap area-weighted averaging.

The source files contain negative sentinel values in the GPP field. This script
normalizes NaN/negative values to a standard numeric fill value before
regridding so they are excluded from the area-weighted average.

Options:
  --input-root DIR    Input directory containing BESS_GPP_<YEAR>_0.1deg.nc
  --output-root DIR   Output directory for BESS_GPP_<YEAR>_0.25deg.nc
  --tmp-dir DIR       Scratch directory used by ncremap
  --start-year YEAR   First year to process
  --end-year YEAR     Last year to process
  --threads N         Threads passed to ncremap
  --deflate N         NetCDF deflate level, 0-9
  --algorithm NAME    ncremap algorithm, default ncoaave
  --force             Overwrite existing output files
  --dry-run           Print commands without executing them
  --help              Show this message

Example:
  bash process/process2/resample_bess_gpp_daily_to_025deg.sh \
    --start-year 1982 \
    --end-year 1982 \
    --threads 4
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
    [[ "$START_YEAR" =~ ^[0-9]{4}$ ]] || die "--start-year must be a four-digit year"
    [[ "$END_YEAR" =~ ^[0-9]{4}$ ]] || die "--end-year must be a four-digit year"
    [[ "$THREADS" =~ ^[1-9][0-9]*$ ]] || die "--threads must be a positive integer"
    [[ "$DEFLATE" =~ ^[0-9]+$ ]] || die "--deflate must be an integer between 0 and 9"
    (( DEFLATE >= 0 && DEFLATE <= 9 )) || die "--deflate must be between 0 and 9"
    (( START_YEAR <= END_YEAR )) || die "--start-year must be <= --end-year"
}

run_cmd() {
    if (( DRY_RUN )); then
        printf '+' >&2
        printf ' %q' "$@" >&2
        printf '\n' >&2
    else
        "$@"
    fi
}

ensure_dirs() {
    if (( DRY_RUN )); then
        return
    fi
    mkdir -p "$TMP_DIR"
    mkdir -p "$OUTPUT_ROOT"
}

year_input_file() {
    printf '%s/BESS_GPP_%s_0.1deg.nc' "$INPUT_ROOT" "$1"
}

year_output_file() {
    printf '%s/BESS_GPP_%s_0.25deg.nc' "$OUTPUT_ROOT" "$1"
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

prepare_input_file() {
    local year="$1"
    local input_file="$2"
    local prepared_file

    if (( DRY_RUN )); then
        prepared_file="${TMP_DIR}/BESS_GPP_${year}_prepared_for_r025.nc"
    else
        prepared_file="$(mktemp "${TMP_DIR}/BESS_GPP_${year}_prepared_for_r025_XXXXXX.nc")"
    fi

    log "preparing sanitized input for year ${year}: $(basename "$prepared_file")"
    run_cmd ncap2 -O \
        -s "where(${VAR_NAME} != ${VAR_NAME} || ${VAR_NAME} < 0.0f) ${VAR_NAME}=${STANDARD_FILL_VALUE}f" \
        "$input_file" \
        "$prepared_file"
    run_cmd ncatted -O \
        -a _FillValue,"$VAR_NAME",o,f,"$STANDARD_FILL_VALUE" \
        -a missing_value,"$VAR_NAME",o,f,"$STANDARD_FILL_VALUE" \
        "$prepared_file"

    printf '%s\n' "$prepared_file"
}

cleanup_file() {
    local path="$1"

    if (( DRY_RUN )); then
        return
    fi

    [[ -n "$path" && -f "$path" ]] && rm -f "$path"
}

update_metadata() {
    local year="$1"
    local output_file="$2"

    if ! command -v ncatted >/dev/null 2>&1; then
        log "ncatted not found, skip metadata update for $(basename "$output_file")"
        return
    fi

    run_cmd ncatted -O \
        -a long_name,"$VAR_NAME",o,c,"Gross Primary Production (0.25 degree)" \
        -a title,global,o,c,"BESS V2 Daily GPP ${year} (0.25 degree)" \
        -a source,global,o,c,"Resampled from 0.1 degree data using ncremap area-weighted averaging (ncoaave)" \
        "$output_file"
}

resample_one() {
    local year="$1"
    local input_file output_file grid_file prepared_input

    input_file="$(year_input_file "$year")"
    output_file="$(year_output_file "$year")"

    [[ -f "$input_file" ]] || die "input file not found: $input_file"

    if [[ -f "$output_file" && "$FORCE" -ne 1 ]]; then
        log "skip existing output: $output_file"
        return
    fi

    grid_file="$(ensure_destination_grid)"
    prepared_input="$(prepare_input_file "$year" "$input_file")"

    log "regridding year ${year}: $(basename "$input_file")"
    run_cmd ncremap \
        --no_stdin \
        -4 \
        -L "$DEFLATE" \
        -a "$ALGORITHM" \
        -v "$VAR_NAME" \
        -g "$grid_file" \
        -T "$TMP_DIR" \
        -t "$THREADS" \
        "$prepared_input" \
        "$output_file"

    if (( ! DRY_RUN )); then
        update_metadata "$year" "$output_file"
    fi

    cleanup_file "$prepared_input"
}

main() {
    local year

    parse_args "$@"
    validate_args
    require_cmd ncremap
    require_cmd ncap2
    require_cmd ncatted
    ensure_dirs

    log "input_root=$INPUT_ROOT"
    log "output_root=$OUTPUT_ROOT"
    log "tmp_dir=$TMP_DIR"
    log "years=${START_YEAR}-${END_YEAR}"
    log "algorithm=$ALGORITHM"
    log "threads=$THREADS"
    log "deflate=$DEFLATE"

    for ((year = START_YEAR; year <= END_YEAR; year++)); do
        resample_one "$year"
    done

    log "all requested BESS daily GPP resampling finished"
}

main "$@"
