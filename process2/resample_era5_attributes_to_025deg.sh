#!/usr/bin/env bash
set -euo pipefail

INPUT_ROOT="/data/era5_for_GRN"
OUTPUT_ROOT="/data/era5_for_GRN/yearly"
TMP_ROOT="/data/era5_for_GRN/tmp_resample_0p25deg"
WORK_ROOT="/tmp/era5_attr_r025_tmp"
ATTRS_CSV="ALL"
START_YEAR=1980
END_YEAR=2024
THREADS="${NCO_THREADS:-2}"
JOBS=1
DEFLATE=1
FORCE=0
KEEP_INTERMEDIATE=0
DRY_RUN=0
HDF5_USE_FILE_LOCKING="${HDF5_USE_FILE_LOCKING:-FALSE}"
REPORT_FILE=""
DIAG_SCRIPT="/home/xulc/flash_drought/process/process2/diagnose_netcdf_time_read_errors.py"
MERGE_SCRIPT="/home/xulc/flash_drought/process/process2/merge_era5_attribute_yearly.py"
FLASH_PYTHON="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"

readonly GRID_NAME="era5_r025_720x1440_scrip.nc"
readonly GRID_SPEC="ttl=Equi-Angular_0.25x0.25_degree_uniform_grid_r025_720x1440#latlon=720,1440#lat_typ=uni#lon_typ=180_wst"
readonly DEFAULT_ATTRS=(
    "era5_tem_mean_2m"
    "LAI_high_nc"
    "LAI_low_nc"
    "soil_temperature1_nc"
    "soil_temperature2_nc"
    "soil_temperature3"
    "soil_temperature4"
    "SSRD"
    "SSTD"
    "surface_pressure_nc"
    "total_evaporation_global_nc"
    "total_precipitation_nc"
    "wind_10m_u_nc"
    "wind_10m_v_nc"
)

usage() {
    cat <<'EOF'
Usage: resample_era5_attributes_to_025deg.sh [options]

Resample yearly ERA5-Land attribute files from 0.1 degree to 0.25 degree,
merge each attribute into a single 1980-2024 NetCDF, and clean intermediate files.

Options:
  --input-root DIR         Root directory containing ERA5 attribute folders
  --output-root DIR        Final merged output directory
  --tmp-root DIR           Intermediate yearly 0.25deg directory
  --work-root DIR          ncremap scratch directory
  --attrs LIST             Comma-separated attribute directories, or ALL
  --start-year YEAR        First year to process
  --end-year YEAR          Last year to process
  --threads N              Threads passed to ncremap
  --jobs N                 Number of attributes to process concurrently
  --deflate N              NetCDF deflate level for outputs
  --force                  Overwrite existing final outputs
  --keep-intermediate      Keep intermediate per-year files after success
  --hdf5-file-locking VAL  Value exported to HDF5_USE_FILE_LOCKING, default FALSE
  --report-file PATH       TSV report for problematic yearly files
  --dry-run                Print commands without executing them
  --help                   Show this message

Example:
  bash process/process2/resample_era5_attributes_to_025deg.sh \
    --attrs era5_tem_mean_2m,total_precipitation_nc \
    --threads 2 \
    --jobs 2
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
            --tmp-root)
                TMP_ROOT="$2"
                shift 2
                ;;
            --work-root)
                WORK_ROOT="$2"
                shift 2
                ;;
            --attrs)
                ATTRS_CSV="$2"
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
            --jobs)
                JOBS="$2"
                shift 2
                ;;
            --deflate)
                DEFLATE="$2"
                shift 2
                ;;
            --force)
                FORCE=1
                shift
                ;;
            --keep-intermediate)
                KEEP_INTERMEDIATE=1
                shift
                ;;
            --hdf5-file-locking)
                HDF5_USE_FILE_LOCKING="$2"
                shift 2
                ;;
            --report-file)
                REPORT_FILE="$2"
                shift 2
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
    [[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || die "--jobs must be a positive integer"
    [[ "$DEFLATE" =~ ^[0-9]+$ ]] || die "--deflate must be an integer between 0 and 9"
    (( DEFLATE >= 0 && DEFLATE <= 9 )) || die "--deflate must be between 0 and 9"
    (( START_YEAR <= END_YEAR )) || die "--start-year must be <= --end-year"
}

selected_attrs() {
    local item trimmed found attr
    if [[ "$ATTRS_CSV" == "ALL" ]]; then
        printf '%s\n' "${DEFAULT_ATTRS[@]}"
        return
    fi

    IFS=',' read -r -a items <<<"$ATTRS_CSV"
    for item in "${items[@]}"; do
        trimmed="$(trim "$item")"
        found=0
        for attr in "${DEFAULT_ATTRS[@]}"; do
            if [[ "$trimmed" == "$attr" ]]; then
                found=1
                printf '%s\n' "$trimmed"
                break
            fi
        done
        (( found == 1 )) || die "unsupported attribute in --attrs: $trimmed"
    done
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
    mkdir -p "$OUTPUT_ROOT" "$TMP_ROOT" "$WORK_ROOT"
}

ensure_report_file() {
    if (( DRY_RUN )); then
        return
    fi
    if [[ -z "$REPORT_FILE" ]]; then
        REPORT_FILE="/home/xulc/flash_drought/process/result_analysis/performance/era5_attr025_bad_files_$(date +%Y%m%d_%H%M%S).tsv"
    fi
    mkdir -p "$(dirname "$REPORT_FILE")"
    if [[ ! -f "$REPORT_FILE" ]]; then
        printf 'attribute\tyear\tinput_file\tvariable\tstage\tbad_periods\terror\n' >"$REPORT_FILE"
    fi
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

detect_main_var() {
    local sample_file="$1"
    ncks -m "$sample_file" | awk '
        /variables:/ {in_vars=1; next}
        /group \// {in_vars=0}
        in_vars && /\(time,lat,lon\)/ && found == "" {
            gsub(/^[[:space:]]+/, "", $0)
            split($2, parts, "(")
            if (parts[1] != "time" && parts[1] != "lat" && parts[1] != "lon") {
                found = parts[1]
            }
        }
        END {
            if (found != "") {
                print found
            }
        }
    '
}

attribute_output_name() {
    local attr="$1"
    local var_name="$2"
    printf '%s_0p25deg_%s_%s.nc' "$var_name" "$START_YEAR" "$END_YEAR"
}

wait_for_slot() {
    local current
    while :; do
        current="$(jobs -pr | wc -l)"
        if (( current < JOBS )); then
            return
        fi
        wait -n
    done
}

sanitize_error() {
    local value="$1"
    value="${value//$'\t'/ }"
    value="${value//$'\n'/ }"
    printf '%s' "$value"
}

diagnose_bad_periods() {
    local input_file="$1"
    local var_name="$2"
    if (( DRY_RUN )); then
        printf 'dry-run'
        return
    fi
    if [[ ! -x "$DIAG_SCRIPT" && ! -f "$DIAG_SCRIPT" ]]; then
        printf 'unknown'
        return
    fi
    if ! command -v /home/xulc/.local/share/mamba/envs/Flash_dra/bin/python >/dev/null 2>&1; then
        printf 'unknown'
        return
    fi
    /home/xulc/.local/share/mamba/envs/Flash_dra/bin/python "$DIAG_SCRIPT" --file "$input_file" --var "$var_name" 2>/dev/null || printf 'unknown'
}

record_failure() {
    local attr="$1"
    local year="$2"
    local input_file="$3"
    local var_name="$4"
    local stage="$5"
    local bad_periods="$6"
    local error_text="$7"
    local safe_error

    safe_error="$(sanitize_error "$error_text")"
    log "[$attr] skip bad year ${year}: ${input_file} | stage=${stage} | bad_periods=${bad_periods}"
    if (( DRY_RUN )); then
        return
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$attr" "$year" "$input_file" "$var_name" "$stage" "$bad_periods" "$safe_error" >>"$REPORT_FILE"
}

resample_one_year() {
    local attr="$1"
    local var_name="$2"
    local grid_file="$3"
    local input_file="$4"
    local output_file="$5"
    local error_log
    local bad_periods
    local error_text

    if [[ -f "$output_file" && "$FORCE" -ne 1 ]]; then
        log "[$attr] reuse existing yearly output: $(basename "$output_file")"
        return
    fi

    log "[$attr] regridding $(basename "$input_file")"
    error_log="$(mktemp)"
    if ! run_cmd ncremap \
        --no_stdin \
        -4 \
        -L "$DEFLATE" \
        -a ncoaave \
        -v "$var_name" \
        -g "$grid_file" \
        -T "$WORK_ROOT" \
        -t "$THREADS" \
        "$input_file" \
        "$output_file" 2>"$error_log"; then
        error_text="$(cat "$error_log")"
        rm -f "$error_log" "$output_file"
        bad_periods="$(diagnose_bad_periods "$input_file" "$var_name")"
        record_failure "$attr" "$(basename "$input_file" | grep -oE '[0-9]{4}' | tail -n 1)" "$input_file" "$var_name" "regrid" "$bad_periods" "$error_text"
        return 1
    fi
    rm -f "$error_log"

    # The Python merge helper concatenates fixed-size yearly files directly.
    # Converting time to a record dimension is no longer required and can
    # trigger HDF errors on otherwise valid yearly outputs.
}

process_attribute() {
    local attr="$1"
    local attr_dir="$INPUT_ROOT/$attr"
    local attr_tmp_dir="$TMP_ROOT/$attr"
    local sample_file var_name final_name final_path grid_file
    local file year year_out
    local -a yearly_outputs=()

    [[ -d "$attr_dir" ]] || die "attribute directory not found: $attr_dir"

    sample_file="$(find "$attr_dir" -maxdepth 1 -name '*.nc' -print | sort | sed -n '1p')"
    [[ -n "$sample_file" ]] || die "no NetCDF files found in: $attr_dir"

    var_name="$(detect_main_var "$sample_file")"
    [[ -n "$var_name" ]] || die "failed to detect main variable in: $sample_file"

    final_name="$(attribute_output_name "$attr" "$var_name")"
    final_path="$OUTPUT_ROOT/$final_name"

    if [[ -f "$final_path" && "$FORCE" -ne 1 ]]; then
        log "[$attr] skip existing final output: $final_path"
        return
    fi

    if (( ! DRY_RUN )); then
        if (( FORCE == 1 )); then
            rm -rf "$attr_tmp_dir"
        fi
        mkdir -p "$attr_tmp_dir"
    fi

    grid_file="$(ensure_destination_grid)"

    while IFS= read -r file; do
        year="$(basename "$file" | grep -oE '[0-9]{4}' | tail -n 1)"
        [[ -n "$year" ]] || die "failed to extract year from file: $file"
        if (( year < START_YEAR || year > END_YEAR )); then
            continue
        fi
        year_out="$attr_tmp_dir/${var_name}_${year}_0p25deg.nc"
        if resample_one_year "$attr" "$var_name" "$grid_file" "$file" "$year_out"; then
            yearly_outputs+=("$year_out")
        fi
    done < <(find "$attr_dir" -maxdepth 1 -name '*.nc' | sort)

    if (( ${#yearly_outputs[@]} == 0 )); then
        log "[$attr] no valid yearly files available for merge in ${START_YEAR}-${END_YEAR}"
        return
    fi

    log "[$attr] merging ${#yearly_outputs[@]} yearly files -> $(basename "$final_path")"
    if ! run_cmd "$FLASH_PYTHON" "$MERGE_SCRIPT" \
        --input-dir "$attr_tmp_dir" \
        --output-path "$final_path" \
        --filename-regex "${var_name}_(\\d{4})_0p25deg\\.nc$" \
        --var-name "$var_name" \
        --title "${var_name} 0.25 degree ${START_YEAR}-${END_YEAR}" \
        --start-year "$START_YEAR" \
        --end-year "$END_YEAR" \
        --deflate "$DEFLATE" \
        --force; then
        record_failure "$attr" "ALL" "$attr_dir" "$var_name" "merge" "unknown" "ncrcat merge failed"
        return
    fi

    if (( KEEP_INTERMEDIATE == 0 )); then
        run_cmd rm -rf "$attr_tmp_dir"
    fi
}

main() {
    local attr

    parse_args "$@"
    validate_args
    require_cmd ncremap
    require_cmd ncks
    require_cmd "$FLASH_PYTHON"
    ensure_dirs
    ensure_report_file

    log "input_root=$INPUT_ROOT"
    log "output_root=$OUTPUT_ROOT"
    log "tmp_root=$TMP_ROOT"
    log "work_root=$WORK_ROOT"
    log "report_file=$REPORT_FILE"
    log "HDF5_USE_FILE_LOCKING=$HDF5_USE_FILE_LOCKING"
    log "attrs=$ATTRS_CSV"
    log "years=${START_YEAR}-${END_YEAR}"
    log "threads=$THREADS"
    log "jobs=$JOBS"
    log "deflate=$DEFLATE"

    export HDF5_USE_FILE_LOCKING
    ensure_destination_grid >/dev/null

    while IFS= read -r attr; do
        process_attribute "$attr"
    done < <(selected_attrs)
    log "all requested ERA5 attribute resampling and merging finished"
}

main "$@"
