#!/bin/bash
# =============================================================================
# 4D Drought Event Analysis Pipeline for GLEAM SMrz Data
# =============================================================================
#
# This script runs the complete pipeline:
# 1. Calculate drought threshold (10th percentile for warm season 1981-2010)
# 2. Generate daily drought boolean masks
# 3. Track drought events across time
# 4. Calculate event characteristics
#
# Usage:
#   ./run_pipeline.sh <year>
#   ./run_pipeline.sh 2020
#   ./run_pipeline.sh 1981 2024  # Process year range
#
# =============================================================================

set -e  # Exit on error

# Configuration
INPUT_FILE="/data/GLEAM/SMrz_45years.nc"
OUTPUT_BASE="/data/GLEAM/drought_3D"
CODE_DIR="$(dirname "$0")"

# Derived paths
BOOL_DIR="${OUTPUT_BASE}/sm_bool"
THRESHOLD_DIR="${OUTPUT_BASE}/threshold"
EVENT_DIR="${OUTPUT_BASE}/events"
CHAR_DIR="${OUTPUT_BASE}/characteristics"

# Parse arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <year> [end_year]"
    echo "  Single year: $0 2020"
    echo "  Year range:  $0 1981 2024"
    exit 1
fi

START_YEAR=$1
END_YEAR=${2:-$START_YEAR}

echo "============================================================"
echo "4D Drought Event Analysis Pipeline"
echo "============================================================"
echo "Input file:    ${INPUT_FILE}"
echo "Output base:   ${OUTPUT_BASE}"
echo "Year range:    ${START_YEAR} - ${END_YEAR}"
echo "============================================================"

# Create directories
mkdir -p "${BOOL_DIR}" "${THRESHOLD_DIR}" "${EVENT_DIR}" "${CHAR_DIR}"

# Step 1: Calculate threshold (only if not exists)
echo ""
echo "[Step 1/4] Checking/calculating drought threshold..."
if [ ! -f "${THRESHOLD_DIR}/threshold_p10.npy" ]; then
    echo "Calculating threshold (this may take a while)..."
    python "${CODE_DIR}/generate_drought_bool_batch.py" \
        --input "${INPUT_FILE}" \
        --output_dir "${BOOL_DIR}" \
        --threshold_dir "${THRESHOLD_DIR}" \
        --calc_threshold_only
else
    echo "Threshold file exists, skipping calculation."
fi

# Process each year
for YEAR in $(seq ${START_YEAR} ${END_YEAR}); do
    echo ""
    echo "============================================================"
    echo "Processing year: ${YEAR}"
    echo "============================================================"
    
    # Step 2: Generate boolean masks
    echo ""
    echo "[Step 2/4] Generating drought boolean masks..."
    if [ -d "${BOOL_DIR}/${YEAR}" ]; then
        echo "Boolean masks for ${YEAR} exist, skipping..."
    else
        python "${CODE_DIR}/generate_drought_bool_batch.py" \
            --input "${INPUT_FILE}" \
            --output_dir "${BOOL_DIR}" \
            --threshold_dir "${THRESHOLD_DIR}" \
            --year ${YEAR}
    fi
    
    # Step 3: Track drought events
    echo ""
    echo "[Step 3/4] Tracking drought events..."
    if [ -d "${EVENT_DIR}/${YEAR}" ]; then
        echo "Events for ${YEAR} exist, skipping..."
    else
        # Determine warm season DOY range
        # NH warm season: DOY 121-273 (May 1 - Sep 30)
        # SH warm season: DOY 305-365, 1-90 (Nov 1 - Mar 31)
        # For simplicity, process full year and let the script handle hemisphere filtering
        python "${CODE_DIR}/track_4D_SMrz.py" \
            --input_dir "${BOOL_DIR}" \
            --output_dir "${EVENT_DIR}" \
            --year ${YEAR} \
            --start_doy 1 \
            --end_doy 365 \
            --overlap 0.5 \
            --min_size 10 \
            --min_duration 3
    fi
    
    # Step 4: Calculate event characteristics
    echo ""
    echo "[Step 4/4] Calculating event characteristics..."
    if [ -f "${CHAR_DIR}/event_chars_${YEAR}.csv" ]; then
        echo "Characteristics for ${YEAR} exist, skipping..."
    else
        python "${CODE_DIR}/calc_event_chars_SMrz.py" \
            --year ${YEAR} \
            --event_dir "${EVENT_DIR}" \
            --output_dir "${CHAR_DIR}" \
            --threshold_file "${THRESHOLD_DIR}/threshold_p10.nc"
    fi
    
    echo "Year ${YEAR} complete!"
done

echo ""
echo "============================================================"
echo "Pipeline complete!"
echo "============================================================"
echo "Output directories:"
echo "  Boolean masks:    ${BOOL_DIR}"
echo "  Threshold:        ${THRESHOLD_DIR}"
echo "  Event tracks:     ${EVENT_DIR}"
echo "  Characteristics:  ${CHAR_DIR}"
echo "============================================================"
