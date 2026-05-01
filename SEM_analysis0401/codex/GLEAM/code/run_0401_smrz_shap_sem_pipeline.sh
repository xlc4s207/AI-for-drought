#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python"
CODE_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/code"
DATA_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/data"
RESULTS_DIR="/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/results"

MERGE_SCRIPT="$CODE_DIR/09_merge_feature_tables.py"
PHASE_SCRIPT="$CODE_DIR/31_build_phase_event_feature_table.py"
SHAP_SCRIPT="$CODE_DIR/06_shap_analysis.py"
SEM_SCRIPT="$CODE_DIR/07_sem_analysis.py"
DEP_SCRIPT="$CODE_DIR/21_batch_dependence_plots_fast.py"
PATH_SCRIPT="$CODE_DIR/13_plot_sem_path_diagrams.py"
COMPARE_SCRIPT="$CODE_DIR/33_plot_prepeak_vs_recoverywin_comparison.py"
ERA5_SCRIPT="$CODE_DIR/02_extract_era5_features.py"
REPLACE_SCRIPT="$CODE_DIR/35_replace_feature_columns.py"

ERA5_RECHUNK_DIR="/data/era5_for_GRN/rechunked_spatial_20260402"
MSWEP_TP_PATH="$ERA5_RECHUNK_DIR/mswep_total_precipitation_0p25deg_1980_2024_spatialchunks_py.nc"

DATE_TAG="20260424"
JOBLIB_TMP="/tmp/sem_analysis0401_smrz"
MPL_TMP="$JOBLIB_TMP/mpl"

mkdir -p "$JOBLIB_TMP" "$MPL_TMP"

GPP_PREPEAK_BIOMES=("Forest" "Grassland" "Savanna" "Cropland" "Shrubland")
ALL_BIOMES=("Forest" "Grassland" "Savanna" "Cropland" "Shrubland" "Wetland")
GPP_COMPARE_BIOMES=("Forest" "Grassland" "Savanna" "Cropland" "Shrubland")
RECO_COMPARE_BIOMES=("Forest" "Grassland" "Savanna" "Cropland" "Shrubland" "Wetland")

PREPEAK_FEATURES=(
  "prepeak_total_precipitation_mean"
  "prepeak_total_evaporation_mean"
  "prepeak_temperature_2m_mean"
  "prepeak_VPD_mean"
  "prepeak_SMrz_mean"
  "prepeak_lai_total_mean"
  "prepeak_ssrd_mean"
  "prepeak_strd_mean"
  "prepeak_wind_speed_mean"
  "event_onset_days"
  "event_duration"
  "event_intensity"
)

RECOVERY_GPP_FEATURES=(
  "recoverywin_total_precipitation_mean"
  "recoverywin_total_evaporation_mean"
  "recoverywin_temperature_2m_mean"
  "recoverywin_VPD_mean"
  "recoverywin_SMrz_mean"
  "recoverywin_lai_total_mean"
  "recoverywin_ssrd_mean"
  "recoverywin_strd_mean"
  "recoverywin_wind_speed_mean"
)

RECOVERY_GPP_EXCLUDE=(
  "recoverywin_p_minus_et"
  "recoverywin_total_precipitation_sum"
  "recoverywin_total_evaporation_sum"
)

RECOVERY_RECO_FEATURES=(
  "recoverywin_total_precipitation_mean"
  "recoverywin_total_evaporation_mean"
  "recoverywin_SMrz_mean"
  "recoverywin_temperature_2m_mean"
  "recoverywin_VPD_mean"
  "recoverywin_wind_speed_mean"
  "recoverywin_lai_total_mean"
  "recoverywin_ssrd_mean"
  "recoverywin_strd_mean"
)

RECOVERY_RECO_EXCLUDE=(
  "recoverywin_p_minus_et"
  "recoverywin_total_precipitation_sum"
  "recoverywin_total_evaporation_sum"
  "recoverywin_SMrz_delta"
)

GPP_MERGED="$DATA_DIR/feature_table_merged_GPP_code1_flash_SMrz_0401.parquet"
GPP_PRE="$DATA_DIR/feature_table_pre_recovery_GPP_code1_flash_SMrz_0401.parquet"
GPP_REC="$DATA_DIR/feature_table_recovery_phase_GPP_code1_flash_SMrz_0401.parquet"
GPP_PREPEAK="$DATA_DIR/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet"

RECO_MSWEP_ERA5="$DATA_DIR/era5_features_RECO_code1_flash_SMrz_0401_mswepE.parquet"
RECO_MSWEP_PRECIP_ONLY="$DATA_DIR/era5_features_RECO_code1_flash_SMrz_0401_mswepE_precip_only.parquet"
RECO_MERGED="$DATA_DIR/feature_table_merged_RECO_code1_flash_SMrz_0401_mswepE.parquet"
RECO_PRE="$DATA_DIR/feature_table_pre_recovery_RECO_code1_flash_SMrz_0401_mswepE.parquet"
RECO_REC="$DATA_DIR/feature_table_recovery_phase_RECO_code1_flash_SMrz_0401_mswepE.parquet"
RECO_PREPEAK="$DATA_DIR/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet"

GPP_PREPEAK_RESULT_ROOT="$RESULTS_DIR/gpp_code1_flash_smrz_v20260401_onsetpeak_clean/prepeak_event_shap_sem_${DATE_TAG}"
GPP_PREPEAK_SHAP_ROOT="$GPP_PREPEAK_RESULT_ROOT/shap_by_biome"
GPP_PREPEAK_SEM_ROOT="$GPP_PREPEAK_RESULT_ROOT/sem_by_biome"
GPP_PREPEAK_MECH_ROOT="$RESULTS_DIR/gpp_code1_flash_smrz_v20260401_onsetpeak_clean/sem_prepeak_event_mechanism_${DATE_TAG}"
GPP_PREPEAK_MECH_BY_BIOME="$GPP_PREPEAK_MECH_ROOT/by_biome"

GPP_REC_RESULT_ROOT="$RESULTS_DIR/gpp_code1_flash_smrz_v20260401_recoverywin_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome"
GPP_REC_SEM_ROOT="$RESULTS_DIR/gpp_code1_flash_smrz_v20260401_recoverywin_clean/sem_process_recoverywin_precipEmean_usertrim_${DATE_TAG}/by_biome"
GPP_REC_MECH_ROOT="$RESULTS_DIR/gpp_code1_flash_smrz_v20260401_recoverywin_clean/sem_process_recoverywin_precipEmean_usertrim_${DATE_TAG}"
GPP_COMPARE_ROOT="$RESULTS_DIR/gpp_code1_flash_smrz_compare_prepeak_vs_recoverywin_v20260401_${DATE_TAG}"

RECO_PREPEAK_RESULT_ROOT="$RESULTS_DIR/reco_code1_flash_smrz_v20260401_mswepE_clean/prepeak_event_shap_sem_${DATE_TAG}"
RECO_PREPEAK_SHAP_ROOT="$RECO_PREPEAK_RESULT_ROOT/shap_by_biome"
RECO_PREPEAK_SEM_ROOT="$RECO_PREPEAK_RESULT_ROOT/sem_by_biome"
RECO_PREPEAK_MECH_ROOT="$RESULTS_DIR/reco_code1_flash_smrz_v20260401_mswepE_clean/sem_prepeak_event_mechanism_${DATE_TAG}"
RECO_PREPEAK_MECH_BY_BIOME="$RECO_PREPEAK_MECH_ROOT/by_biome"

RECO_REC_RESULT_ROOT="$RESULTS_DIR/reco_code1_flash_smrz_v20260401_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome"
RECO_REC_SEM_ROOT="$RESULTS_DIR/reco_code1_flash_smrz_v20260401_mswepE_clean/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_${DATE_TAG}/by_biome"
RECO_REC_MECH_ROOT="$RESULTS_DIR/reco_code1_flash_smrz_v20260401_mswepE_clean/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_${DATE_TAG}"
RECO_COMPARE_ROOT="$RESULTS_DIR/reco_code1_flash_smrz_compare_prepeak_vs_recoverywin_v20260401_${DATE_TAG}"

GPP_PREPEAK_SPEC="$CODE_DIR/sem_specs/gpp_code1_flash_smrz_prepeak_event_mechanism_v20260420.txt"
GPP_REC_SPEC="$CODE_DIR/sem_specs/gpp_code1_flash_smrz_recoverywin_precipEmean_usertrim_v20260415.txt"
RECO_PREPEAK_SPEC="$CODE_DIR/sem_specs/reco_code1_flash_smrz_prepeak_event_mechanism_v20260421.txt"
RECO_REC_SPEC="$CODE_DIR/sem_specs/reco_code1_flash_smrz_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_v20260415.txt"

run_python() {
  env MPLCONFIGDIR="$MPL_TMP" JOBLIB_TEMP_FOLDER="$JOBLIB_TMP" TMPDIR="$JOBLIB_TMP" \
    "$PYTHON_BIN" "$@"
}

biome_shap_done() {
  local biome_dir="$1"
  [[ -f "$biome_dir/feature_importance.csv" && -f "$biome_dir/run_summary.txt" ]]
}

biome_sem_done() {
  local sem_root="$1"
  local prefix="$2"
  [[ -f "$sem_root/${prefix}_sem_summary.txt" && -f "$sem_root/${prefix}_estimates.csv" ]]
}

ensure_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "[ERROR] missing file: $path" >&2
    exit 1
  fi
}

merge_gpp_tables() {
  ensure_file "$DATA_DIR/era5_features_GPP_code1_flash_SMrz_0401.parquet"
  ensure_file "$DATA_DIR/gleam_sm_features_GPP_code1_flash_SMrz_0401.parquet"
  ensure_file "$DATA_DIR/drought_event_features_GPP_code1_flash_SMrz_0401.parquet"

  run_python "$MERGE_SCRIPT" \
    --era5 "$DATA_DIR/era5_features_GPP_code1_flash_SMrz_0401.parquet" \
    --gleam-sm "$DATA_DIR/gleam_sm_features_GPP_code1_flash_SMrz_0401.parquet" \
    --drought "$DATA_DIR/drought_event_features_GPP_code1_flash_SMrz_0401.parquet" \
    --metric GPP \
    --code-id code1 \
    --drought-type flash \
    --soil-layer SMrz \
    --merged-output "$GPP_MERGED" \
    --pre-output "$GPP_PRE" \
    --recovery-output "$GPP_REC"

  run_python "$PHASE_SCRIPT" \
    --source-table "$GPP_PRE" \
    --phase prepeak \
    --output-table "$GPP_PREPEAK"
}

extract_reco_mswep_precip_only() {
  if [[ -f "$RECO_MSWEP_PRECIP_ONLY" ]]; then
    echo "[INFO] existing MSWEP precip-only table found: $RECO_MSWEP_PRECIP_ONLY"
    return
  fi
  run_python "$ERA5_SCRIPT" \
    --metric RECO \
    --code-id code1 \
    --drought-type flash \
    --soil-layer SMrz \
    --era5-root-dir "$ERA5_RECHUNK_DIR" \
    --total-precipitation-path "$MSWEP_TP_PATH" \
    --variables \
      total_precipitation \
    --workers 16 \
    --concurrent-era5-tasks 1 \
    --reserve-cpus 8 \
    --vars-per-task 1 \
    --output "$RECO_MSWEP_PRECIP_ONLY"
}

build_reco_mswep_era5() {
  if [[ -f "$RECO_MSWEP_ERA5" ]]; then
    echo "[INFO] existing RECO MSWEP ERA5 table found: $RECO_MSWEP_ERA5"
    return
  fi
  ensure_file "$DATA_DIR/era5_features_RECO_code1_flash_SMrz_0401.parquet"
  ensure_file "$RECO_MSWEP_PRECIP_ONLY"

  run_python "$REPLACE_SCRIPT" \
    --base-table "$DATA_DIR/era5_features_RECO_code1_flash_SMrz_0401.parquet" \
    --override-table "$RECO_MSWEP_PRECIP_ONLY" \
    --output-table "$RECO_MSWEP_ERA5" \
    --column-substring total_precipitation
}

merge_reco_mswep_tables() {
  ensure_file "$RECO_MSWEP_ERA5"
  ensure_file "$DATA_DIR/gleam_sm_features_RECO_code1_flash_SMrz_0401.parquet"
  ensure_file "$DATA_DIR/drought_event_features_RECO_code1_flash_SMrz_0401.parquet"

  run_python "$MERGE_SCRIPT" \
    --era5 "$RECO_MSWEP_ERA5" \
    --gleam-sm "$DATA_DIR/gleam_sm_features_RECO_code1_flash_SMrz_0401.parquet" \
    --drought "$DATA_DIR/drought_event_features_RECO_code1_flash_SMrz_0401.parquet" \
    --metric RECO \
    --code-id code1 \
    --drought-type flash \
    --soil-layer SMrz \
    --merged-output "$RECO_MERGED" \
    --pre-output "$RECO_PRE" \
    --recovery-output "$RECO_REC"

  run_python "$PHASE_SCRIPT" \
    --source-table "$RECO_PRE" \
    --phase prepeak \
    --output-table "$RECO_PREPEAK"
}

run_gpp_prepeak() {
  mkdir -p "$GPP_PREPEAK_SHAP_ROOT" "$GPP_PREPEAK_SEM_ROOT" "$GPP_PREPEAK_MECH_BY_BIOME"
  local biome
  for biome in "${GPP_PREPEAK_BIOMES[@]}"; do
    mkdir -p "$GPP_PREPEAK_SHAP_ROOT/$biome"
    if ! biome_shap_done "$GPP_PREPEAK_SHAP_ROOT/$biome"; then
      run_python "$SHAP_SCRIPT" \
        --table "$GPP_PREPEAK" \
        --metric GPP \
        --code-id code1 \
        --biome "$biome" \
        --drought-type flash \
        --soil-layer SMrz \
        --feature-scope prepeak_event \
        --limit 50000 \
        --model-backend lightgbm \
        --n-estimators 120 \
        --n-jobs 12 \
        --top-k 12 \
        --shap-sample-size 5000 \
        --include-features "${PREPEAK_FEATURES[@]}" \
        --output-dir "$GPP_PREPEAK_SHAP_ROOT/$biome" \
        >"$GPP_PREPEAK_SHAP_ROOT/$biome/run.log" 2>&1
    fi

    if ! biome_sem_done "$GPP_PREPEAK_SEM_ROOT" "GPP_code1_${biome}_flash_SMrz"; then
      run_python "$SEM_SCRIPT" \
        --table "$GPP_PREPEAK" \
        --shap-results "$GPP_PREPEAK_SHAP_ROOT/$biome" \
        --model-spec-file "$GPP_PREPEAK_SPEC" \
        --target t_recover_to_baseline_abs_peak \
        --feature-scope prepeak_event \
        --metric GPP \
        --code-id code1 \
        --biome "$biome" \
        --drought-type flash \
        --soil-layer SMrz \
        --include-features "${PREPEAK_FEATURES[@]}" \
        --output-dir "$GPP_PREPEAK_SEM_ROOT" \
        >"$GPP_PREPEAK_SEM_ROOT/${biome}.log" 2>&1
    fi
  done

  run_python "$DEP_SCRIPT" \
    --table "$GPP_PREPEAK" \
    --output-root "$GPP_PREPEAK_SHAP_ROOT" \
    --metric GPP \
    --code-id code1 \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope prepeak_event \
    --limit 50000 \
    --model-backend lightgbm \
    --n-estimators 120 \
    --n-jobs 12 \
    --shap-sample-size 5000 \
    --biomes "${GPP_PREPEAK_BIOMES[@]}" \
    --include-features "${PREPEAK_FEATURES[@]}" \
    >"$GPP_PREPEAK_RESULT_ROOT/dependence_fast.log" 2>&1

  run_python "$PATH_SCRIPT" \
    --sem-dir "$GPP_PREPEAK_SEM_ROOT" \
    --output-dir "$GPP_PREPEAK_RESULT_ROOT" \
    >"$GPP_PREPEAK_RESULT_ROOT/plot.log" 2>&1

  cp -a "$GPP_PREPEAK_SEM_ROOT/." "$GPP_PREPEAK_MECH_BY_BIOME/"
  run_python "$PATH_SCRIPT" \
    --sem-dir "$GPP_PREPEAK_MECH_BY_BIOME" \
    --output-dir "$GPP_PREPEAK_MECH_ROOT" \
    >"$GPP_PREPEAK_MECH_ROOT/plot.log" 2>&1
}

run_gpp_recovery() {
  mkdir -p "$GPP_REC_RESULT_ROOT" "$GPP_REC_SEM_ROOT"
  local biome
  for biome in "${ALL_BIOMES[@]}"; do
    mkdir -p "$GPP_REC_RESULT_ROOT/$biome"
    if ! biome_shap_done "$GPP_REC_RESULT_ROOT/$biome"; then
      run_python "$SHAP_SCRIPT" \
        --table "$GPP_REC" \
        --metric GPP \
        --code-id code1 \
        --biome "$biome" \
        --drought-type flash \
        --soil-layer SMrz \
        --feature-scope process_recoverywin \
        --limit 50000 \
        --model-backend random_forest \
        --n-estimators 60 \
        --n-jobs 4 \
        --top-k 9 \
        --shap-sample-size 5000 \
        --include-features "${RECOVERY_GPP_FEATURES[@]}" \
        --exclude-features "${RECOVERY_GPP_EXCLUDE[@]}" \
        --output-dir "$GPP_REC_RESULT_ROOT/$biome" \
        >"$GPP_REC_RESULT_ROOT/$biome/run.log" 2>&1
    fi

    if ! biome_sem_done "$GPP_REC_SEM_ROOT" "GPP_code1_${biome}_flash_SMrz"; then
      run_python "$SEM_SCRIPT" \
        --table "$GPP_REC" \
        --shap-results "$GPP_REC_RESULT_ROOT/$biome" \
        --model-spec-file "$GPP_REC_SPEC" \
        --target t_recover_to_baseline_abs_peak \
        --feature-scope process_recoverywin \
        --metric GPP \
        --code-id code1 \
        --biome "$biome" \
        --drought-type flash \
        --soil-layer SMrz \
        --include-features "${RECOVERY_GPP_FEATURES[@]}" \
        --exclude-features "${RECOVERY_GPP_EXCLUDE[@]}" \
        --output-dir "$GPP_REC_SEM_ROOT" \
        >"$GPP_REC_SEM_ROOT/${biome}.log" 2>&1
    fi
  done

  run_python "$DEP_SCRIPT" \
    --table "$GPP_REC" \
    --output-root "$GPP_REC_RESULT_ROOT" \
    --metric GPP \
    --code-id code1 \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope process_recoverywin \
    --limit 50000 \
    --model-backend random_forest \
    --n-estimators 60 \
    --n-jobs 4 \
    --shap-sample-size 5000 \
    --biomes "${ALL_BIOMES[@]}" \
    --include-features "${RECOVERY_GPP_FEATURES[@]}" \
    --exclude-features "${RECOVERY_GPP_EXCLUDE[@]}" \
    >"$RESULTS_DIR/gpp_code1_flash_smrz_v20260401_recoverywin_clean/dependence_fast.log" 2>&1

  run_python "$PATH_SCRIPT" \
    --sem-dir "$GPP_REC_SEM_ROOT" \
    --output-dir "$GPP_REC_MECH_ROOT" \
    >"$GPP_REC_MECH_ROOT/plot.log" 2>&1
}

run_reco_prepeak() {
  mkdir -p "$RECO_PREPEAK_SHAP_ROOT" "$RECO_PREPEAK_SEM_ROOT" "$RECO_PREPEAK_MECH_BY_BIOME"
  local biome
  for biome in "${ALL_BIOMES[@]}"; do
    mkdir -p "$RECO_PREPEAK_SHAP_ROOT/$biome"
    if ! biome_shap_done "$RECO_PREPEAK_SHAP_ROOT/$biome"; then
      run_python "$SHAP_SCRIPT" \
        --table "$RECO_PREPEAK" \
        --metric RECO \
        --code-id code1 \
        --biome "$biome" \
        --drought-type flash \
        --soil-layer SMrz \
        --feature-scope prepeak_event \
        --limit 50000 \
        --model-backend lightgbm \
        --n-estimators 120 \
        --n-jobs 12 \
        --top-k 12 \
        --shap-sample-size 5000 \
        --include-features "${PREPEAK_FEATURES[@]}" \
        --output-dir "$RECO_PREPEAK_SHAP_ROOT/$biome" \
        >"$RECO_PREPEAK_SHAP_ROOT/$biome/run.log" 2>&1
    fi

    if ! biome_sem_done "$RECO_PREPEAK_SEM_ROOT" "RECO_code1_${biome}_flash_SMrz"; then
      run_python "$SEM_SCRIPT" \
        --table "$RECO_PREPEAK" \
        --shap-results "$RECO_PREPEAK_SHAP_ROOT/$biome" \
        --model-spec-file "$RECO_PREPEAK_SPEC" \
        --target t_recover_to_baseline_abs_peak \
        --feature-scope prepeak_event \
        --metric RECO \
        --code-id code1 \
        --biome "$biome" \
        --drought-type flash \
        --soil-layer SMrz \
        --include-features "${PREPEAK_FEATURES[@]}" \
        --output-dir "$RECO_PREPEAK_SEM_ROOT" \
        >"$RECO_PREPEAK_SEM_ROOT/${biome}.log" 2>&1
    fi
  done

  run_python "$DEP_SCRIPT" \
    --table "$RECO_PREPEAK" \
    --output-root "$RECO_PREPEAK_SHAP_ROOT" \
    --metric RECO \
    --code-id code1 \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope prepeak_event \
    --limit 50000 \
    --model-backend lightgbm \
    --n-estimators 120 \
    --n-jobs 12 \
    --shap-sample-size 5000 \
    --biomes "${ALL_BIOMES[@]}" \
    --include-features "${PREPEAK_FEATURES[@]}" \
    >"$RECO_PREPEAK_RESULT_ROOT/dependence_fast.log" 2>&1

  run_python "$PATH_SCRIPT" \
    --sem-dir "$RECO_PREPEAK_SEM_ROOT" \
    --output-dir "$RECO_PREPEAK_RESULT_ROOT" \
    >"$RECO_PREPEAK_RESULT_ROOT/plot.log" 2>&1

  cp -a "$RECO_PREPEAK_SEM_ROOT/." "$RECO_PREPEAK_MECH_BY_BIOME/"
  run_python "$PATH_SCRIPT" \
    --sem-dir "$RECO_PREPEAK_MECH_BY_BIOME" \
    --output-dir "$RECO_PREPEAK_MECH_ROOT" \
    >"$RECO_PREPEAK_MECH_ROOT/plot.log" 2>&1
}

run_reco_recovery() {
  mkdir -p "$RECO_REC_RESULT_ROOT" "$RECO_REC_SEM_ROOT"
  local biome
  for biome in "${ALL_BIOMES[@]}"; do
    mkdir -p "$RECO_REC_RESULT_ROOT/$biome"
    if ! biome_shap_done "$RECO_REC_RESULT_ROOT/$biome"; then
      run_python "$SHAP_SCRIPT" \
        --table "$RECO_REC" \
        --metric RECO \
        --code-id code1 \
        --biome "$biome" \
        --drought-type flash \
        --soil-layer SMrz \
        --feature-scope process_recoverywin \
        --limit 50000 \
        --model-backend random_forest \
        --n-estimators 60 \
        --n-jobs 4 \
        --top-k 9 \
        --shap-sample-size 5000 \
        --include-features "${RECOVERY_RECO_FEATURES[@]}" \
        --exclude-features "${RECOVERY_RECO_EXCLUDE[@]}" \
        --output-dir "$RECO_REC_RESULT_ROOT/$biome" \
        >"$RECO_REC_RESULT_ROOT/$biome/run.log" 2>&1
    fi

    if ! biome_sem_done "$RECO_REC_SEM_ROOT" "RECO_code1_${biome}_flash_SMrz"; then
      run_python "$SEM_SCRIPT" \
        --table "$RECO_REC" \
        --shap-results "$RECO_REC_RESULT_ROOT/$biome" \
        --model-spec-file "$RECO_REC_SPEC" \
        --target t_recover_to_baseline_abs_peak \
        --feature-scope process_recoverywin \
        --metric RECO \
        --code-id code1 \
        --biome "$biome" \
        --drought-type flash \
        --soil-layer SMrz \
        --exclude-features "${RECOVERY_RECO_EXCLUDE[@]}" \
        --output-dir "$RECO_REC_SEM_ROOT" \
        >"$RECO_REC_SEM_ROOT/${biome}.log" 2>&1
    fi
  done

  run_python "$DEP_SCRIPT" \
    --table "$RECO_REC" \
    --output-root "$RECO_REC_RESULT_ROOT" \
    --metric RECO \
    --code-id code1 \
    --drought-type flash \
    --soil-layer SMrz \
    --feature-scope process_recoverywin \
    --limit 50000 \
    --model-backend random_forest \
    --n-estimators 60 \
    --n-jobs 4 \
    --shap-sample-size 5000 \
    --biomes "${ALL_BIOMES[@]}" \
    --include-features "${RECOVERY_RECO_FEATURES[@]}" \
    --exclude-features "${RECOVERY_RECO_EXCLUDE[@]}" \
    >"$RESULTS_DIR/reco_code1_flash_smrz_v20260401_mswepE_clean/dependence_fast.log" 2>&1

  run_python "$PATH_SCRIPT" \
    --sem-dir "$RECO_REC_SEM_ROOT" \
    --output-dir "$RECO_REC_MECH_ROOT" \
    >"$RECO_REC_MECH_ROOT/plot.log" 2>&1
}

run_compare() {
  mkdir -p "$GPP_COMPARE_ROOT" "$RECO_COMPARE_ROOT"
  run_python "$COMPARE_SCRIPT" \
    --prepeak-root "$GPP_PREPEAK_SHAP_ROOT" \
    --recoverywin-root "$GPP_REC_RESULT_ROOT" \
    --output-dir "$GPP_COMPARE_ROOT" \
    --biomes "${GPP_COMPARE_BIOMES[@]}" \
    --beeswarm-max-points 5000

  run_python "$COMPARE_SCRIPT" \
    --prepeak-root "$RECO_PREPEAK_SHAP_ROOT" \
    --recoverywin-root "$RECO_REC_RESULT_ROOT" \
    --output-dir "$RECO_COMPARE_ROOT" \
    --biomes "${RECO_COMPARE_BIOMES[@]}" \
    --beeswarm-max-points 5000
}

run_postextract_all() {
  merge_gpp_tables
  extract_reco_mswep_precip_only
  build_reco_mswep_era5
  merge_reco_mswep_tables
  run_gpp_prepeak
  run_gpp_recovery
  run_reco_prepeak
  run_reco_recovery
  run_compare
}

usage() {
  cat <<'EOF'
Usage:
  run_0401_smrz_shap_sem_pipeline.sh <mode>

Modes:
  merge_gpp
  extract_reco_mswep_era5
  build_reco_mswep_era5
  merge_reco_mswep
  run_gpp_prepeak
  run_gpp_recovery
  run_reco_prepeak
  run_reco_recovery
  compare
  postextract_all
EOF
}

MODE="${1:-}"
case "$MODE" in
  merge_gpp)
    merge_gpp_tables
    ;;
  extract_reco_mswep_era5|extract_reco_mswep_precip_only)
    extract_reco_mswep_precip_only
    ;;
  build_reco_mswep_era5)
    build_reco_mswep_era5
    ;;
  merge_reco_mswep)
    merge_reco_mswep_tables
    ;;
  run_gpp_prepeak)
    run_gpp_prepeak
    ;;
  run_gpp_recovery)
    run_gpp_recovery
    ;;
  run_reco_prepeak)
    run_reco_prepeak
    ;;
  run_reco_recovery)
    run_reco_recovery
    ;;
  compare)
    run_compare
    ;;
  postextract_all)
    run_postextract_all
    ;;
  *)
    usage
    exit 1
    ;;
esac
