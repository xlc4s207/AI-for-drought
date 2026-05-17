#!/usr/bin/env bash
set -euo pipefail

SMRZ_DIR="/home/xulc/flash_drought/gleam/SMrz_dd"
SMS_DIR="/home/xulc/flash_drought/gleam/SMs"
OUTPUT_DIR="/data/GLEAM/0p25deg_yearly"
WORK_DIR=""
THREADS="${NCO_THREADS:-4}"
DEFLATE=1
ALGORITHM="ncoaave"
VARS_CSV="SMrz,SMs"
DRY_RUN=0
RESUME=0

readonly GRID_NAME="r025_720x1440_scrip.nc"
readonly GRID_SPEC="ttl=Equi-Angular_0.25x0.25_degree_uniform_grid_r025_720x1440#latlon=720,1440#lat_typ=uni#lon_typ=180_wst"
readonly MAP_NAME="gleam_0p10_to_0p25_ncoaave.nc"

usage() {
    cat <<'EOF'
Usage: resample_gleam_to_025deg.sh [options]

Resample yearly GLEAM 0.1 degree files to 0.25 degree, then merge them back into
one file per variable. This avoids the whole-file memory blow-up seen with the
45-year merged inputs.

Options:
  --smrz-dir DIR     Directory containing yearly SMrz files
  --sms-dir DIR      Directory containing yearly SMs files
  --output-dir DIR   Output root directory for yearly and merged 0.25 degree files
  --work-dir DIR     Working directory for grid, map, and temporary files
  --vars LIST        Comma-separated list: SMrz, SMs, or SMrz,SMs
  --threads N        Threads passed to NCO operators
  --deflate N        NetCDF deflate level for outputs (default: 1)
  --algorithm NAME   NCO remap algorithm (default: ncoaave)
  --resume           Skip completed yearly outputs and merged outputs when possible
  --dry-run          Print commands without executing them
  --help             Show this message

Recommended:
  bash process/process2/resample_gleam_to_025deg.sh \
    --vars SMrz,SMs \
    --threads 8 \
    --resume
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

run_cmd() {
    if (( DRY_RUN )); then
        printf '+'
        printf ' %q' "$@"
        printf '\n'
    else
        "$@"
    fi
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --smrz-dir)
                SMRZ_DIR="$2"
                shift 2
                ;;
            --sms-dir)
                SMS_DIR="$2"
                shift 2
                ;;
            --output-dir)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            --work-dir)
                WORK_DIR="$2"
                shift 2
                ;;
            --vars)
                VARS_CSV="$2"
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
            --resume)
                RESUME=1
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

    if [[ -z "$WORK_DIR" ]]; then
        WORK_DIR="$OUTPUT_DIR/work"
    fi

    if (( ! DRY_RUN )); then
        [[ -d "$SMRZ_DIR" ]] || die "SMrz directory not found: $SMRZ_DIR"
        [[ -d "$SMS_DIR" ]] || die "SMs directory not found: $SMS_DIR"
    fi
}

selected_vars() {
    local item trimmed
    IFS=',' read -r -a items <<<"$VARS_CSV"
    for item in "${items[@]}"; do
        trimmed="$(trim "$item")"
        case "$trimmed" in
            SMrz|SMs)
                printf '%s\n' "$trimmed"
                ;;
            *)
                die "unsupported variable in --vars: $trimmed"
                ;;
        esac
    done
}

input_dir_for_var() {
    case "$1" in
        SMrz) printf '%s' "$SMRZ_DIR" ;;
        SMs) printf '%s' "$SMS_DIR" ;;
        *) die "unknown variable: $1" ;;
    esac
}

discover_input_files() {
    local var_name="$1"
    local input_dir prefix
    local -a matches

    input_dir="$(input_dir_for_var "$var_name")"
    prefix="$var_name"
    shopt -s nullglob
    matches=( "$input_dir"/"${prefix}"_*_GLEAM_v4.2a.nc )
    shopt -u nullglob

    (( ${#matches[@]} > 0 )) || die "no yearly files found for ${var_name} in ${input_dir}"
    printf '%s\n' "${matches[@]}"
}

year_from_file() {
    local filename
    filename="$(basename "$1")"
    printf '%s\n' "$filename" | sed -E 's/^[^_]+_([0-9]{4})_GLEAM_v4\.2a\.nc$/\1/'
}

yearly_output_dir_for_var() {
    printf '%s/yearly/%s' "$OUTPUT_DIR" "$1"
}

merged_output_for_var() {
    printf '%s/%s_45years_0p25deg.nc' "$OUTPUT_DIR" "$1"
}

yearly_output_for_file() {
    local var_name="$1"
    local input_file="$2"
    local year
    year="$(year_from_file "$input_file")"
    printf '%s/%s_%s_GLEAM_v4.2a_0p25deg.nc' "$(yearly_output_dir_for_var "$var_name")" "$var_name" "$year"
}

tmp_dir() {
    printf '%s/tmp' "$WORK_DIR"
}

ensure_dirs() {
    if (( DRY_RUN )); then
        return
    fi

    mkdir -p \
        "$OUTPUT_DIR" \
        "$WORK_DIR" \
        "$(tmp_dir)" \
        "$(yearly_output_dir_for_var SMrz)" \
        "$(yearly_output_dir_for_var SMs)"
}

ensure_destination_grid() {
    local grid_file="$WORK_DIR/$GRID_NAME"

    if [[ -f "$grid_file" ]]; then
        printf '%s\n' "$grid_file"
        return
    fi

    log "creating destination grid: $grid_file"
    run_cmd ncremap --no_stdin -4 --dfl_lvl=1 -G "$GRID_SPEC" -g "$grid_file"
    printf '%s\n' "$grid_file"
}

ensure_map_file() {
    local var_name="$1"
    local sample_input="$2"
    local grid_file map_file sample_slice sample_regrid

    grid_file="$(ensure_destination_grid)"
    map_file="$WORK_DIR/$MAP_NAME"

    if [[ -f "$map_file" ]]; then
        printf '%s\n' "$map_file"
        return
    fi

    sample_slice="$(tmp_dir)/map_seed_${var_name}.nc"
    sample_regrid="$(tmp_dir)/map_seed_${var_name}_0p25deg.nc"

    log "creating reusable weight map: $map_file"
    run_cmd ncks -O -d time,0,0 -v "${var_name},lat,lon,time" "$sample_input" "$sample_slice"
    run_cmd ncremap \
        --no_stdin \
        -4 \
        -L "$DEFLATE" \
        -a "$ALGORITHM" \
        -v "$var_name" \
        -g "$grid_file" \
        -m "$map_file" \
        -T "$(tmp_dir)" \
        -t "$THREADS" \
        "$sample_slice" \
        "$sample_regrid"

    if (( ! DRY_RUN )); then
        rm -f "$sample_slice" "$sample_regrid"
    fi

    printf '%s\n' "$map_file"
}

remap_yearly_file() {
    local var_name="$1"
    local input_file="$2"
    local map_file="$3"
    local year index total yearly_output tmp_output

    year="$(year_from_file "$input_file")"
    index="$4"
    total="$5"
    yearly_output="$(yearly_output_for_file "$var_name" "$input_file")"
    tmp_output="$(tmp_dir)/${var_name}_${year}_0p25deg_tmp.nc"

    if (( RESUME )) && [[ -s "$yearly_output" ]]; then
        log "[${var_name}] ${year} (${index}/${total}) already exists, skipping"
        return
    fi

    log "[${var_name}] ${year} (${index}/${total}) regridding"
    run_cmd ncks \
        -O \
        -4 \
        -L "$DEFLATE" \
        -v "$var_name" \
        --map "$map_file" \
        --rgr lat_nm_out=lat \
        --rgr lon_nm_out=lon \
        -t "$THREADS" \
        "$input_file" \
        "$tmp_output"
    run_cmd ncks -O -4 -L "$DEFLATE" --mk_rec_dmn time "$tmp_output" "$yearly_output"

    if (( ! DRY_RUN )); then
        rm -f "$tmp_output"
    fi
}

merge_yearly_outputs() {
    local var_name="$1"
    local merged_output
    local -a inputs yearly_outputs
    local input_file yearly_output

    merged_output="$(merged_output_for_var "$var_name")"
    mapfile -t inputs < <(discover_input_files "$var_name")

    for input_file in "${inputs[@]}"; do
        yearly_output="$(yearly_output_for_file "$var_name" "$input_file")"
        yearly_outputs+=( "$yearly_output" )
    done

    if (( RESUME )) && [[ -s "$merged_output" ]]; then
        log "[${var_name}] merged output exists, skipping merge"
        return
    fi

    log "[${var_name}] merging ${#yearly_outputs[@]} yearly files -> $(basename "$merged_output")"
    run_cmd ncrcat -4 -L "$DEFLATE" -O "${yearly_outputs[@]}" "$merged_output"
}

process_var() {
    local var_name="$1"
    local map_file
    local -a inputs
    local i total

    mapfile -t inputs < <(discover_input_files "$var_name")
    total="${#inputs[@]}"
    map_file="$(ensure_map_file "$var_name" "${inputs[0]}")"

    for (( i=0; i<total; i++ )); do
        remap_yearly_file "$var_name" "${inputs[$i]}" "$map_file" "$((i+1))" "$total"
    done

    merge_yearly_outputs "$var_name"
}

main() {
    local var_name

    parse_args "$@"
    validate_args
    require_cmd ncks
    require_cmd ncremap
    require_cmd ncrcat
    ensure_dirs

    log "smrz_dir=$SMRZ_DIR"
    log "sms_dir=$SMS_DIR"
    log "output_dir=$OUTPUT_DIR"
    log "work_dir=$WORK_DIR"
    log "vars=$VARS_CSV"
    log "algorithm=$ALGORITHM"
    log "threads=$THREADS"
    log "deflate=$DEFLATE"
    log "resume=$RESUME"

    while IFS= read -r var_name; do
        process_var "$var_name"
    done < <(selected_vars)

    log "all requested GLEAM variables finished"
}

main "$@"
