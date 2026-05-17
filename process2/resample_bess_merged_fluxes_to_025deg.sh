#!/usr/bin/env bash
set -euo pipefail

OUTPUT_ROOT="/data/BESS_V2"
TMP_DIR="/data/BESS_V2/tmp_bess_merged_r025"
THREADS="${NCO_THREADS:-4}"
DEFLATE=1
ALGORITHM="ncoaave"
FORCE=0
ONLY_VAR=""

readonly GRID_NAME="bess_flux_r025_720x1440_scrip.nc"
readonly GRID_SPEC="ttl=Equi-Angular_0.25x0.25_degree_uniform_grid_r025_720x1440#latlon=720,1440#lat_typ=uni#lon_typ=180_wst"
readonly STANDARD_FILL_FLOAT="1.0e36"

usage() {
    cat <<'EOF'
Usage: resample_bess_merged_fluxes_to_025deg.sh [options]

Directly resample the merged 0.1 degree BESS flux files to 0.25 degree and
save the results under /data/BESS_V2.

Variables handled:
  NEE  : keep real negative values, mask only <= -1000 as invalid
  RECO : direct area-weighted remap
  GPP  : mask all negative values as invalid before remapping

Options:
  --output-root DIR   Output directory, default /data/BESS_V2
  --tmp-dir DIR       Temporary directory, default /data/BESS_V2/tmp_bess_merged_r025
  --threads N         Threads passed to ncremap
  --deflate N         NetCDF deflate level, 0-9
  --algorithm NAME    ncremap algorithm, default ncoaave
  --only NAME         Process only one variable: NEE | RECO | GPP
  --force             Overwrite existing outputs
  --help              Show this message
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
            --output-root)
                OUTPUT_ROOT="$2"
                shift 2
                ;;
            --tmp-dir)
                TMP_DIR="$2"
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
            --only)
                ONLY_VAR="$2"
                shift 2
                ;;
            --force)
                FORCE=1
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
    if [[ -n "$ONLY_VAR" ]]; then
        case "$ONLY_VAR" in
            NEE|RECO|GPP) ;;
            *) die "--only must be one of: NEE, RECO, GPP" ;;
        esac
    fi
}

run_cmd() {
    "$@"
}

ensure_dirs() {
    mkdir -p "$OUTPUT_ROOT"
    mkdir -p "$TMP_DIR"
}

grid_file() {
    printf '%s/%s\n' "$OUTPUT_ROOT" "$GRID_NAME"
}

ensure_destination_grid() {
    local grid_path
    grid_path="$(grid_file)"

    if [[ -f "$grid_path" ]]; then
        printf '%s\n' "$grid_path"
        return
    fi

    log "creating destination grid: $grid_path"
    run_cmd ncremap --no_stdin -4 --dfl_lvl=1 -G "$GRID_SPEC" -g "$grid_path"
    printf '%s\n' "$grid_path"
}

input_file_for() {
    case "$1" in
        NEE) printf '/data/BESS_V2/NEE_1982-2022_0.1deg.nc\n' ;;
        RECO) printf '/data/BESS_V2/BESS_RECO_1982-2022_0.1deg.nc\n' ;;
        GPP) printf '/data/BESS_V2/BESS_GPP_1982_2022.nc\n' ;;
        *) die "unsupported variable: $1" ;;
    esac
}

output_file_for() {
    case "$1" in
        NEE) printf '%s/NEE_1982-2022_0.25deg.nc\n' "$OUTPUT_ROOT" ;;
        RECO) printf '%s/BESS_RECO_1982-2022_0.25deg.nc\n' "$OUTPUT_ROOT" ;;
        GPP) printf '%s/BESS_GPP_1982_2022_0.25deg.nc\n' "$OUTPUT_ROOT" ;;
        *) die "unsupported variable: $1" ;;
    esac
}

long_name_for() {
    case "$1" in
        NEE) printf 'Net Ecosystem Exchange (0.25 degree)\n' ;;
        RECO) printf 'Ecosystem Respiration (0.25 degree)\n' ;;
        GPP) printf 'Gross Primary Production (0.25 degree)\n' ;;
        *) die "unsupported variable: $1" ;;
    esac
}

title_for() {
    case "$1" in
        NEE) printf 'BESS V2 Daily NEE 1982-2022 (0.25 degree resolution)\n' ;;
        RECO) printf 'BESS V2 Daily RECO 1982-2022 (0.25 degree resolution)\n' ;;
        GPP) printf 'BESS V2 Daily GPP 1982-2022 (0.25 degree resolution)\n' ;;
        *) die "unsupported variable: $1" ;;
    esac
}

source_for() {
    case "$1" in
        NEE) printf 'Resampled from 0.1 degree merged daily file using ncremap area-weighted averaging; values <= -1000 treated as invalid\n' ;;
        RECO) printf 'Resampled from 0.1 degree merged daily file using ncremap area-weighted averaging\n' ;;
        GPP) printf 'Resampled from 0.1 degree merged daily file using ncremap area-weighted averaging; negative values treated as invalid\n' ;;
        *) die "unsupported variable: $1" ;;
    esac
}

prepare_input_if_needed() {
    local var_name="$1"
    local input_file="$2"
    local prepared_file

    case "$var_name" in
        RECO)
            printf '%s\n' "$input_file"
            return
            ;;
        NEE)
            prepared_file="$(mktemp "${TMP_DIR}/NEE_merged_prepared_XXXXXX.nc")"
            log "preparing sanitized input for NEE: $(basename "$prepared_file")"
            run_cmd ncap2 -O -4 -L "$DEFLATE" \
                -s 'where(NEE <= -1000s) NEE=-9999s' \
                "$input_file" \
                "$prepared_file"
            printf '%s\n' "$prepared_file"
            ;;
        GPP)
            prepared_file="$(mktemp "${TMP_DIR}/GPP_merged_prepared_XXXXXX.nc")"
            log "preparing sanitized input for GPP: $(basename "$prepared_file")"
            run_cmd ncap2 -O -4 -L "$DEFLATE" \
                -s "where(GPP != GPP || GPP < 0.0f) GPP=${STANDARD_FILL_FLOAT}f" \
                "$input_file" \
                "$prepared_file"
            run_cmd ncatted -O \
                -a _FillValue,GPP,o,f,"$STANDARD_FILL_FLOAT" \
                -a missing_value,GPP,o,f,"$STANDARD_FILL_FLOAT" \
                "$prepared_file"
            printf '%s\n' "$prepared_file"
            ;;
        *)
            die "unsupported variable: $var_name"
            ;;
    esac
}

cleanup_temp_file() {
    local var_name="$1"
    local path="$2"

    if [[ "$var_name" == "RECO" ]]; then
        return
    fi

    if [[ -n "$path" && -f "$path" ]]; then
        rm -f "$path"
    fi
}

update_metadata() {
    local var_name="$1"
    local output_file="$2"
    local title source long_name

    title="$(title_for "$var_name")"
    source="$(source_for "$var_name")"
    long_name="$(long_name_for "$var_name")"

    run_cmd ncatted -O \
        -a long_name,"$var_name",o,c,"$long_name" \
        -a title,global,o,c,"$title" \
        -a source,global,o,c,"$source" \
        "$output_file"
}

process_one() {
    local var_name="$1"
    local input_file output_file grid_path prepared_input

    input_file="$(input_file_for "$var_name")"
    output_file="$(output_file_for "$var_name")"

    [[ -f "$input_file" ]] || die "input file not found: $input_file"

    if [[ -f "$output_file" && "$FORCE" -ne 1 ]]; then
        log "skip existing output: $output_file"
        return
    fi

    grid_path="$(ensure_destination_grid)"
    prepared_input="$(prepare_input_if_needed "$var_name" "$input_file")"

    log "regridding ${var_name}: $(basename "$input_file") -> $(basename "$output_file")"
    run_cmd ncremap \
        --no_stdin \
        -4 \
        -L "$DEFLATE" \
        -a "$ALGORITHM" \
        -v "$var_name" \
        -g "$grid_path" \
        -T "$TMP_DIR" \
        -t "$THREADS" \
        "$prepared_input" \
        "$output_file"

    update_metadata "$var_name" "$output_file"
    cleanup_temp_file "$var_name" "$prepared_input"
}

main() {
    parse_args "$@"
    validate_args
    require_cmd ncremap
    require_cmd ncap2
    require_cmd ncatted
    ensure_dirs

    log "output_root=$OUTPUT_ROOT"
    log "tmp_dir=$TMP_DIR"
    log "threads=$THREADS"
    log "deflate=$DEFLATE"
    log "algorithm=$ALGORITHM"

    if [[ -n "$ONLY_VAR" ]]; then
        process_one "$ONLY_VAR"
    else
        process_one NEE
        process_one RECO
        process_one GPP
    fi

    log "all requested merged BESS flux resampling finished"
}

main "$@"
