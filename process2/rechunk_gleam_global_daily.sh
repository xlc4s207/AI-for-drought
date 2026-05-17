#!/usr/bin/env bash
set -euo pipefail

INPUT_ROOT="/data/GLEAM"
LOG_DIR="/home/xulc/flash_drought/process/process2/logs"
DEFLATE=4
FORCE=0

usage() {
    cat <<'EOF'
Usage: rechunk_gleam_global_daily.sh [options]

Rechunk the merged global GLEAM daily files so the main data variable uses
time=1, lat=1800, lon=3600 chunks. The two files are launched in parallel in
separate tmux sessions.

Outputs:
  /data/GLEAM/SMs_45years_chunk1x1800x3600.nc
  /data/GLEAM/SMrz_45years_chunk1x1800x3600.nc

Options:
  --input-root DIR   Input directory, default /data/GLEAM
  --log-dir DIR      Log directory, default process/process2/logs
  --deflate N        Output deflate level, default 4
  --force            Overwrite existing outputs
  --help             Show this message
EOF
}

log() {
    printf '[%s] %s\n' "$(date '+%F %T')" "$*" >&2
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --input-root)
                INPUT_ROOT="$2"
                shift 2
                ;;
            --log-dir)
                LOG_DIR="$2"
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

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

start_one() {
    local var_name="$1"
    local session_name="$2"
    local input_file output_file log_file cmd

    input_file="${INPUT_ROOT}/${var_name}_45years.nc"
    output_file="${INPUT_ROOT}/${var_name}_45years_chunk1x1800x3600.nc"
    log_file="${LOG_DIR}/rechunk_${var_name}_45years_$(date '+%Y%m%d_%H%M%S').log"

    [[ -f "$input_file" ]] || die "input file not found: $input_file"

    if [[ -f "$output_file" && "$FORCE" -ne 1 ]]; then
        log "skip existing output: $output_file"
        return
    fi

    mkdir -p "$LOG_DIR"

    cmd="ncks -O -4 -L ${DEFLATE} --cnk_map=dmn --cnk_dmn time,1 --cnk_dmn lat,1800 --cnk_dmn lon,3600 '$input_file' '$output_file' > '$log_file' 2>&1"
    tmux new-session -d -s "$session_name" "$cmd"

    log "started ${var_name} rechunk"
    log "  session: ${session_name}"
    log "  output : ${output_file}"
    log "  log    : ${log_file}"
}

main() {
    parse_args "$@"
    require_cmd ncks
    require_cmd tmux

    start_one "SMs" "gleam_sms_rechunk_$(date '+%m%d_%H%M%S')"
    start_one "SMrz" "gleam_smrz_rechunk_$(date '+%m%d_%H%M%S')"
}

main "$@"
