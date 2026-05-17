#!/usr/bin/env bash
set -euo pipefail
#
# Resample ERA5 2m dewpoint temperature from 0.1° → 0.25°,
# merge into a single multi-year file, then rechunk for spatial access.
#
# Step 1: ncremap per-year → /data/era5_for_GRN/tmp_resample_dewpoint/
# Step 2: Python merge → /data/era5_for_GRN/yearly/dewpoint_temperature_0p25deg_1980_2024.nc
# Step 3: Python rechunk → /data/era5_for_GRN/rechunked_spatial_20260402/dewpoint_temperature_0p25deg_1980_2024_spatialchunks_py.nc
#

PYTHON="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"

# ── Paths ──────────────────────────────────────────────
INPUT_DIR="/data/era5_for_GRN/total_dewpoint_tem_nc"
TMP_DIR="/data/era5_for_GRN/tmp_resample_dewpoint"
WORK_DIR="/tmp/era5_dewpoint_r025_tmp"
YEARLY_DIR="/data/era5_for_GRN/yearly"
RECHUNK_DIR="/data/era5_for_GRN/rechunked_spatial_20260402"
GRID_FILE="$YEARLY_DIR/era5_r025_720x1440_scrip.nc"

MERGE_SCRIPT="/home/xulc/flash_drought/process/process2/merge_era5_attribute_yearly.py"
RECHUNK_SCRIPT="/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/code/10_rechunk_era5_parallel.py"

VAR_NAME="dewpoint_temperature"
START_YEAR=1980
END_YEAR=2024
THREADS=2
DEFLATE=1

MERGED_FILE="$YEARLY_DIR/${VAR_NAME}_0p25deg_${START_YEAR}_${END_YEAR}.nc"
RECHUNKED_FILE="$RECHUNK_DIR/${VAR_NAME}_0p25deg_${START_YEAR}_${END_YEAR}_spatialchunks_py.nc"

export HDF5_USE_FILE_LOCKING=FALSE

log() {
    printf '[%s] %s\n' "$(date '+%F %T')" "$*" >&2
}

# ══════════════════════════════════════════════════════════════════
# Step 0: Sanity checks
# ══════════════════════════════════════════════════════════════════
command -v ncremap >/dev/null 2>&1 || { log "ERROR: ncremap not found"; exit 1; }
[[ -d "$INPUT_DIR" ]] || { log "ERROR: input dir not found: $INPUT_DIR"; exit 1; }
[[ -f "$GRID_FILE" ]] || { log "ERROR: grid file not found: $GRID_FILE"; exit 1; }

mkdir -p "$TMP_DIR" "$WORK_DIR" "$YEARLY_DIR" "$RECHUNK_DIR"

# ══════════════════════════════════════════════════════════════════
# Step 1: Resample each year 0.1° → 0.25° with ncremap
# ══════════════════════════════════════════════════════════════════
if [[ -f "$MERGED_FILE" ]]; then
    log "Merged file already exists: $MERGED_FILE — skipping steps 1 & 2."
else
    log "=== STEP 1: Resampling yearly files to 0.25 degree ==="

    SUCCESS_COUNT=0
    FAIL_COUNT=0
    for input_file in "$INPUT_DIR"/${VAR_NAME}_*.nc; do
        year=$(basename "$input_file" | grep -oE '[0-9]{4}')
        [[ -n "$year" ]] || continue
        if (( year < START_YEAR || year > END_YEAR )); then
            continue
        fi

        out_file="$TMP_DIR/${VAR_NAME}_${year}_0p25deg.nc"
        if [[ -f "$out_file" ]]; then
            log "  [Y$year] reuse existing: $(basename "$out_file")"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
            continue
        fi

        log "  [Y$year] regridding $(basename "$input_file")..."
        if ncremap \
            --no_stdin \
            -4 \
            -L "$DEFLATE" \
            -a ncoaave \
            -v "$VAR_NAME" \
            -g "$GRID_FILE" \
            -T "$WORK_DIR" \
            -t "$THREADS" \
            "$input_file" \
            "$out_file" 2>/dev/null; then
            log "  [Y$year] OK"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            log "  [Y$year] FAIL — removing partial output"
            rm -f "$out_file"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    done

    log "Step 1 done: success=$SUCCESS_COUNT fail=$FAIL_COUNT"

    # ══════════════════════════════════════════════════════════════════
    # Step 2: Merge all yearly 0.25° files into a single multi-year NetCDF
    # ══════════════════════════════════════════════════════════════════
    log "=== STEP 2: Merging yearly files → $(basename "$MERGED_FILE") ==="

    "$PYTHON" "$MERGE_SCRIPT" \
        --input-dir "$TMP_DIR" \
        --output-path "$MERGED_FILE" \
        --filename-regex "${VAR_NAME}_(\d{4})_0p25deg\.nc$" \
        --var-name "$VAR_NAME" \
        --title "${VAR_NAME} 0.25 degree ${START_YEAR}-${END_YEAR}" \
        --start-year "$START_YEAR" \
        --end-year "$END_YEAR" \
        --deflate "$DEFLATE" \
        --force

    log "Step 2 done: $(du -h "$MERGED_FILE" | cut -f1)"
fi

# ══════════════════════════════════════════════════════════════════
# Step 3: Rechunk for spatial access (256, 32, 32)
# ══════════════════════════════════════════════════════════════════
if [[ -f "$RECHUNKED_FILE" ]]; then
    log "Rechunked file already exists: $RECHUNKED_FILE — skipping step 3."
else
    log "=== STEP 3: Rechunking → $(basename "$RECHUNKED_FILE") ==="

    "$PYTHON" "$RECHUNK_SCRIPT" \
        --input "$MERGED_FILE" \
        --output "$RECHUNKED_FILE" \
        --time-chunk 64 \
        --read-workers 2 \
        --max-pending 2 \
        --target-time-chunk 256 \
        --target-lat-chunk 32 \
        --target-lon-chunk 32

    log "Step 3 done: $(du -h "$RECHUNKED_FILE" | cut -f1)"
fi

log "=== ALL DONE ==="
log "  Merged:    $MERGED_FILE"
log "  Rechunked: $RECHUNKED_FILE"
