#!/usr/bin/env python
"""Common helpers for GLEAM recovery-time SHAP+SEM workflow."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol


BASE_DIR = Path("/home/xulc/flash_drought")
PROCESS_DIR = BASE_DIR / "process"
SEM_GLEAM_DIR = PROCESS_DIR / "SEM_analysis" / "codex" / "GLEAM"
CODE_DIR = SEM_GLEAM_DIR / "code"
DATA_DIR = SEM_GLEAM_DIR / "data"
RESULTS_DIR = SEM_GLEAM_DIR / "results"
PLOTS_DIR = SEM_GLEAM_DIR / "plots"

LAND_USE_TIF = BASE_DIR / "land_use" / "MCD12C1_LC_Type1_2010_11km.tif"

MASTER_ALL_PATH = DATA_DIR / "event_master_table_all.parquet"
MASTER_VALID_PATH = DATA_DIR / "event_master_table_valid.parquet"
EVENT_COUNT_SUMMARY_PATH = DATA_DIR / "event_count_summary.csv"
PRE_RECOVERY_TABLE_PATH = DATA_DIR / "feature_table_pre_recovery.parquet"
RECOVERY_PHASE_TABLE_PATH = DATA_DIR / "feature_table_recovery_phase.parquet"

IGBP_TO_BIOME = {
    1: "Forest",
    2: "Forest",
    3: "Forest",
    4: "Forest",
    5: "Forest",
    6: "Shrubland",
    7: "Shrubland",
    8: "Savanna_Grassland",
    9: "Savanna_Grassland",
    10: "Savanna_Grassland",
    11: "Wetland",
    12: "Cropland",
    14: "Cropland",
}

EXCLUDE_IGBP = {0, 13, 15, 16, 255}

COMMON_EVENT_FIELDS = [
    "lat",
    "lon",
    "event_id",
    "onset_year",
    "onset_doy",
    "drought_start_year",
    "drought_start_doy",
    "actual_window_after",
    "lu_event_valid",
    "response_detected",
    "t_response_onset_start",
    "t_response_drought_start",
    "t_peak",
    "t_peak_abs",
    "t_peak_drought_start",
    "t_peak_abs_drought_start",
    "t_impact",
    "amp_max",
    "legacy_duration",
    "t_recover_to_baseline",
    "t_recover_to_baseline_abs_peak",
    "t_recover_onset_start",
    "t_recover_drought_start",
    "t_recover_post_drought",
    "recovery_rate_to_baseline",
]

METRIC_FIELDS = {
    "GPP": [
        "gpp_baseline_abs",
        "gpp_baseline_std_abs",
        "gpp_min_abs",
        "gpp_change_to_peak_abs",
        "gpp_loss_total_abs",
        "gpp_loss_drought_phase_abs",
        "gpp_loss_post_drought_phase_abs",
        "gpp_peak_deficit_abs",
    ],
    "NEE": [
        "nee_baseline_abs",
        "nee_baseline_std_abs",
        "nee_min_abs",
        "nee_change_to_peak_abs",
        "nee_loss_total_abs",
        "nee_loss_drought_phase_abs",
        "nee_loss_post_drought_phase_abs",
        "nee_peak_deficit_abs",
    ],
    "RECO": [
        "reco_baseline_abs",
        "reco_baseline_std_abs",
        "reco_min_abs",
        "reco_change_to_peak_abs",
        "reco_loss_total_abs",
        "reco_loss_drought_phase_abs",
        "reco_loss_post_drought_phase_abs",
        "reco_peak_deficit_abs",
    ],
}

UNIFIED_METRIC_COLUMNS = [
    "flux_baseline_abs",
    "flux_baseline_std_abs",
    "flux_min_abs",
    "flux_change_to_peak_abs",
    "flux_loss_total_abs",
    "flux_loss_drought_phase_abs",
    "flux_loss_post_drought_phase_abs",
    "flux_peak_deficit_abs",
]

ERA5_VARIABLE_SPECS = {
    "temperature_2m": Path("/data/era5_for_GRN/yearly/temperature_2m_0p25deg_1980_2024.nc"),
    "total_precipitation": Path("/data/era5_for_GRN/yearly/total_precipitation_0p25deg_1980_2024.nc"),
    "total_evaporation": Path("/data/era5_for_GRN/yearly/total_evaporation_0p25deg_1980_2024.nc"),
    "ssrd": Path("/data/era5_for_GRN/yearly/ssrd_0p25deg_1980_2024.nc"),
    "strd": Path("/data/era5_for_GRN/yearly/strd_0p25deg_1980_2024.nc"),
    "surface_pressure": Path("/data/era5_for_GRN/yearly/surface_pressure_0p25deg_1980_2024.nc"),
    "wind_u_10m": Path("/data/era5_for_GRN/yearly/wind_u_10m_0p25deg_1980_2024.nc"),
    "wind_v_10m": Path("/data/era5_for_GRN/yearly/wind_v_10m_0p25deg_1980_2024.nc"),
    "soil_temperature_level_1": Path("/data/era5_for_GRN/yearly/soil_temperature_level_1_0p25deg_1980_2024.nc"),
    "soil_temperature_level_2": Path("/data/era5_for_GRN/yearly/soil_temperature_level_2_0p25deg_1980_2024.nc"),
    "soil_temperature_level_3": Path("/data/era5_for_GRN/yearly/soil_temperature_level_3_0p25deg_1980_2024.nc"),
    "soil_temperature_level_4": Path("/data/era5_for_GRN/yearly/soil_temperature_level_4_0p25deg_1980_2024.nc"),
    "leaf_area_index_high_vegetation": Path("/data/era5_for_GRN/yearly/leaf_area_index_high_vegetation_0p25deg_1980_2024.nc"),
    "leaf_area_index_low_vegetation": Path("/data/era5_for_GRN/yearly/leaf_area_index_low_vegetation_0p25deg_1980_2024.nc"),
    "dewpoint_temperature": Path("/data/era5_for_GRN/yearly/dewpoint_temperature_0p25deg_1980_2024.nc"),
}

GLEAM_SM_SPECS = {
    "SMrz": Path("/data/GLEAM/0p25deg_yearly/SMrz_45years_0p25deg.nc"),
    "SMs": Path("/data/GLEAM/0p25deg_yearly/SMs_45years_0p25deg.nc"),
}

DROUGHT_EVENT_SPECS = {
    ("SMrz", "flash"): BASE_DIR / "gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc",
    ("SMrz", "nonflash"): BASE_DIR / "gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc",
    ("SMs", "flash"): BASE_DIR / "gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc",
    ("SMs", "nonflash"): BASE_DIR / "gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc",
}

EVENT_ATTRIBUTE_FIELDS = [
    "onset_days",
    "duration",
    "days_below_p20",
    "onset_drop",
    "onset_rate",
    "intensity",
    "drought_end_year",
    "drought_end_doy",
]

PHASES = ("pre30", "prepeak", "onset", "shock", "postpeak30", "postpeak60", "recoverywin")

PHASE_TO_DAY_OFFSETS = {
    "pre30": (-30, -1),
    "prepeak": ("onset", "peak"),
    "onset": ("onset", "drought_start"),
    "shock": ("drought_start", "peak"),
    "postpeak30": ("peak", 30),
    "postpeak60": ("peak", 60),
    "recoverywin": ("peak", "recover"),
}

WINDOW_STATS = {
    "temperature_2m": {"pre30": ("mean", "max"), "prepeak": ("mean",), "onset": ("mean",), "shock": ("mean", "max"), "postpeak30": ("mean",), "postpeak60": ("mean",), "recoverywin": ("mean",)},
    "total_precipitation": {"pre30": ("mean", "sum"), "prepeak": ("mean",), "onset": ("sum",), "shock": ("sum", "mean"), "postpeak30": ("sum",), "postpeak60": ("sum",), "recoverywin": ("sum", "mean")},
    "total_evaporation": {"pre30": ("sum",), "prepeak": ("mean",), "onset": ("sum",), "shock": ("sum", "mean"), "postpeak30": ("sum",), "postpeak60": ("sum",), "recoverywin": ("sum", "mean")},
    "ssrd": {"pre30": ("mean",), "prepeak": ("mean",), "onset": ("mean",), "shock": ("mean",), "postpeak30": ("mean",), "recoverywin": ("mean",)},
    "strd": {"pre30": ("mean",), "prepeak": ("mean",), "shock": ("mean",), "postpeak30": ("mean",), "recoverywin": ("mean",)},
    "surface_pressure": {"pre30": ("mean",), "recoverywin": ("mean",)},
    "wind_u_10m": {"pre30": ("mean",), "prepeak": ("mean",), "shock": ("mean",), "postpeak30": ("mean",), "recoverywin": ("mean",)},
    "wind_v_10m": {"pre30": ("mean",), "prepeak": ("mean",), "shock": ("mean",), "postpeak30": ("mean",), "recoverywin": ("mean",)},
    "soil_temperature_level_1": {"pre30": ("mean",), "shock": ("mean",), "postpeak30": ("mean",), "recoverywin": ("mean",)},
    "soil_temperature_level_2": {"shock": ("mean",), "recoverywin": ("mean",)},
    "soil_temperature_level_3": {"shock": ("mean",), "recoverywin": ("mean",)},
    "soil_temperature_level_4": {"shock": ("mean",), "recoverywin": ("mean",)},
    "leaf_area_index_high_vegetation": {"pre30": ("mean",), "prepeak": ("mean",), "shock": ("mean",), "postpeak30": ("mean",), "recoverywin": ("mean",)},
    "leaf_area_index_low_vegetation": {"pre30": ("mean",), "prepeak": ("mean",), "shock": ("mean",), "postpeak30": ("mean",), "recoverywin": ("mean",)},
    "dewpoint_temperature": {"pre30": ("mean",), "prepeak": ("mean",), "onset": ("mean",), "shock": ("mean",), "postpeak30": ("mean",), "recoverywin": ("mean",)},
    "SMrz": {"pre30": ("mean", "min"), "prepeak": ("mean",), "onset": ("min", "delta"), "shock": ("mean", "min"), "postpeak30": ("mean", "delta"), "postpeak60": ("mean",), "recoverywin": ("mean", "delta")},
    "SMs": {"pre30": ("mean", "min"), "prepeak": ("mean",), "onset": ("min", "delta"), "shock": ("mean", "min"), "postpeak30": ("mean", "delta"), "postpeak60": ("mean",), "recoverywin": ("mean", "delta")},
}

DERIVED_FEATURE_NAMES = (
    "pre30_wind_speed_mean",
    "prepeak_wind_speed_mean",
    "shock_wind_speed_mean",
    "postpeak30_wind_speed_mean",
    "recoverywin_wind_speed_mean",
    "pre30_p_minus_et",
    "shock_p_minus_et",
    "postpeak30_p_minus_et",
    "recoverywin_p_minus_et",
    "pre30_lai_total_mean",
    "prepeak_lai_total_mean",
    "shock_lai_total_mean",
    "postpeak30_lai_total_mean",
    "recoverywin_lai_total_mean",
    "shock_soil_temp_gradient",
    "recoverywin_soil_temperature_weighted_mean",
    "pre30_VPD_mean",
    "prepeak_VPD_mean",
    "shock_VPD_mean",
    "postpeak30_VPD_mean",
    "recoverywin_VPD_mean",
)

SOIL_TEMPERATURE_LAYER_WEIGHTS = {
    "recoverywin_soil_temperature_level_1_mean": 7.0,
    "recoverywin_soil_temperature_level_2_mean": 21.0,
    "recoverywin_soil_temperature_level_3_mean": 72.0,
    "recoverywin_soil_temperature_level_4_mean": 189.0,
}

FEATURE_SCOPE_PREFIXES: Dict[str, Tuple[str, ...]] = {
    "predictive": ("event_", "pre30_", "prepeak_", "onset_", "shock_"),
    "prepeak_event": ("event_", "prepeak_"),
    "shock_event": ("event_", "shock_"),
    "process": ("postpeak30_", "postpeak60_", "recoverywin_"),
    "process_recoverywin": ("recoverywin_",),
    "all": ("event_", "pre30_", "prepeak_", "onset_", "shock_", "postpeak30_", "postpeak60_", "recoverywin_"),
}


@dataclass(frozen=True)
class TargetSpec:
    metric: str
    code_id: str
    drought_type: str
    soil_layer: str
    path: Path


def get_target_specs() -> List[TargetSpec]:
    return [
        TargetSpec("GPP", "code1", "flash", "SMrz", PROCESS_DIR / "GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        TargetSpec("GPP", "code2", "flash", "SMs", PROCESS_DIR / "GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        TargetSpec("GPP", "code3", "nonflash", "SMrz", PROCESS_DIR / "GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        TargetSpec("GPP", "code4", "nonflash", "SMs", PROCESS_DIR / "GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        TargetSpec("NEE", "code1", "flash", "SMrz", PROCESS_DIR / "NEE-draught-analysis/code1SMrz/result/nee_response_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        TargetSpec("NEE", "code2", "flash", "SMs", PROCESS_DIR / "NEE-draught-analysis/code2SMs/result/nee_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        TargetSpec("NEE", "code3", "nonflash", "SMrz", PROCESS_DIR / "NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        TargetSpec("NEE", "code4", "nonflash", "SMs", PROCESS_DIR / "NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        TargetSpec("RECO", "code1", "flash", "SMrz", PROCESS_DIR / "RECO-draught-analysis/code1/results/reco_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        TargetSpec("RECO", "code2", "flash", "SMs", PROCESS_DIR / "RECO-draught-analysis/code2_SMs/results/reco_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        TargetSpec("RECO", "code3", "nonflash", "SMrz", PROCESS_DIR / "RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
        TargetSpec("RECO", "code4", "nonflash", "SMs", PROCESS_DIR / "RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    ]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_feature_scope(scope: Optional[str]) -> str:
    normalized = "all" if scope is None else str(scope).strip().lower()
    if normalized not in FEATURE_SCOPE_PREFIXES:
        valid = ", ".join(sorted(FEATURE_SCOPE_PREFIXES))
        raise ValueError(f"Unsupported feature scope: {scope!r}. Expected one of: {valid}")
    return normalized


def column_allowed_by_scope(column: str, scope: Optional[str]) -> bool:
    normalized = normalize_feature_scope(scope)
    return column.startswith(FEATURE_SCOPE_PREFIXES[normalized])


def build_event_uid(df: pd.DataFrame) -> pd.Series:
    uid_frame = pd.DataFrame(
        {
            "metric": df["metric"].astype("string"),
            "code_id": df["code_id"].astype("string"),
            "lat": pd.to_numeric(df["lat"], errors="coerce").round(5),
            "lon": pd.to_numeric(df["lon"], errors="coerce").round(5),
            "event_id": pd.to_numeric(df["event_id"], errors="coerce"),
        }
    )
    return pd.util.hash_pandas_object(uid_frame, index=False).astype("int64")


def get_event_file_path(soil_layer: str, drought_type: str) -> Path:
    return DROUGHT_EVENT_SPECS[(soil_layer, drought_type)]


def biome_from_igbp(igbp_class: int) -> str:
    return IGBP_TO_BIOME.get(int(igbp_class), "Other")


def load_landuse_raster(tif_path: Path = LAND_USE_TIF):
    with rasterio.open(tif_path) as src:
        data = src.read(1)
        transform = src.transform
        nodata = src.nodata
    return data, transform, nodata


def assign_igbp_class(
    lats: Sequence[float],
    lons: Sequence[float],
    lu_data: np.ndarray,
    lu_transform,
    lu_nodata,
) -> np.ndarray:
    igbp_classes = np.full(len(lats), 255, dtype=np.uint16)
    lat_arr = np.asarray(lats, dtype=np.float64)
    lon_arr = np.asarray(lons, dtype=np.float64)
    valid = np.isfinite(lat_arr) & np.isfinite(lon_arr)
    if not valid.any():
        return igbp_classes
    rows, cols = rowcol(lu_transform, lon_arr[valid], lat_arr[valid])
    rows = np.asarray(rows)
    cols = np.asarray(cols)
    height, width = lu_data.shape
    in_bounds = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
    valid_idx = np.where(valid)[0]
    for local_i, (row_i, col_i, ok) in enumerate(zip(rows, cols, in_bounds)):
        if not ok:
            continue
        value = lu_data[row_i, col_i]
        if lu_nodata is not None and value == lu_nodata:
            continue
        igbp_classes[valid_idx[local_i]] = value
    return igbp_classes


def assign_igbp_class_by_unique_coords(
    lats: Sequence[float],
    lons: Sequence[float],
    lu_data: np.ndarray,
    lu_transform,
    lu_nodata,
    max_workers: int = 1,
    coord_chunk_size: int = 200000,
) -> np.ndarray:
    coord_df = pd.DataFrame({"lat": lats, "lon": lons})
    unique_coords = coord_df.drop_duplicates(ignore_index=True)
    if unique_coords.empty:
        return np.full(len(coord_df), 255, dtype=np.uint16)

    chunks = []
    for start in range(0, len(unique_coords), coord_chunk_size):
        stop = min(start + coord_chunk_size, len(unique_coords))
        chunks.append(unique_coords.iloc[start:stop].copy())

    def process_chunk(chunk_df: pd.DataFrame) -> pd.DataFrame:
        chunk_df = chunk_df.copy()
        chunk_df["igbp_class"] = assign_igbp_class(
            chunk_df["lat"].values,
            chunk_df["lon"].values,
            lu_data,
            lu_transform,
            lu_nodata,
        )
        return chunk_df

    if max_workers and max_workers > 1 and len(chunks) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            mapped_parts = list(executor.map(process_chunk, chunks))
    else:
        mapped_parts = [process_chunk(chunk) for chunk in chunks]

    mapped_unique = pd.concat(mapped_parts, ignore_index=True)
    merged = coord_df.merge(mapped_unique, on=["lat", "lon"], how="left")
    return merged["igbp_class"].fillna(255).astype(np.uint16).values


def optimize_event_frame_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce", downcast="float")
        elif pd.api.types.is_integer_dtype(out[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce", downcast="integer")
    for col in ("metric", "code_id", "drought_type", "soil_layer", "biome"):
        if col in out.columns:
            out[col] = out[col].astype("category")
    return out


def year_doy_to_timestamp(year: float, doy: float) -> pd.Timestamp:
    if not np.isfinite(year) or not np.isfinite(doy):
        return pd.NaT
    return pd.Timestamp(int(year), 1, 1) + pd.Timedelta(days=int(doy) - 1)


def add_event_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["onset_start_date"] = [
        year_doy_to_timestamp(y, d) for y, d in zip(out["onset_year"], out["onset_doy"])
    ]
    out["drought_start_date"] = [
        year_doy_to_timestamp(y, d)
        for y, d in zip(out["drought_start_year"], out["drought_start_doy"])
    ]
    return out


def compute_stage_dates(row: Mapping[str, object]) -> Dict[str, Tuple[pd.Timestamp, pd.Timestamp]]:
    onset_date = pd.Timestamp(row["onset_start_date"])
    drought_start = pd.Timestamp(row["drought_start_date"])
    peak_offset = row.get("t_peak_abs", np.nan)
    recovery_offset = row.get("t_recover_to_baseline_abs_peak", np.nan)
    if pd.isna(onset_date) or pd.isna(drought_start) or not np.isfinite(peak_offset):
        return {}
    peak_date = drought_start + pd.Timedelta(days=int(float(peak_offset)))
    windows = {
        "pre30": (onset_date - pd.Timedelta(days=30), onset_date - pd.Timedelta(days=1)),
        "prepeak": (onset_date, peak_date),
        "onset": (onset_date, drought_start),
        "shock": (drought_start, peak_date),
        "postpeak30": (peak_date, peak_date + pd.Timedelta(days=30)),
        "postpeak60": (peak_date, peak_date + pd.Timedelta(days=60)),
    }
    if np.isfinite(recovery_offset) and float(recovery_offset) >= 0:
        windows["recoverywin"] = (
            peak_date,
            peak_date + pd.Timedelta(days=int(float(recovery_offset))),
        )
    return windows


def nearest_index(values: np.ndarray, target: float) -> int:
    values = np.asarray(values)
    if values[0] <= values[-1]:
        idx = int(np.abs(values - target).argmin())
    else:
        idx = int(np.abs(values - target).argmin())
    return idx


def summarize_window(values: np.ndarray, stat: str) -> float:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return np.nan
    if stat == "mean":
        return float(arr.mean())
    if stat == "sum":
        return float(arr.sum())
    if stat == "min":
        return float(arr.min())
    if stat == "max":
        return float(arr.max())
    if stat == "std":
        return float(arr.std(ddof=0))
    if stat == "delta":
        return float(arr[-1] - arr[0]) if arr.size >= 2 else np.nan
    raise ValueError(f"Unsupported stat: {stat}")


def slice_time_window(
    time_values: np.ndarray,
    series: np.ndarray,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> np.ndarray:
    if pd.isna(start) or pd.isna(end):
        return np.array([], dtype=np.float64)
    time_arr = np.asarray(time_values).astype("datetime64[ns]")
    start64 = np.datetime64(start.to_datetime64())
    end64 = np.datetime64(end.to_datetime64())
    mask = (time_arr >= start64) & (time_arr <= end64)
    return np.asarray(series)[mask]


def metric_specific_rename_map(metric: str) -> Dict[str, str]:
    return dict(zip(METRIC_FIELDS[metric], UNIFIED_METRIC_COLUMNS))


def read_subset_filters(
    df: pd.DataFrame,
    metric: Optional[str] = None,
    code_id: Optional[str] = None,
    biome: Optional[str] = None,
) -> pd.DataFrame:
    out = df
    if metric:
        out = out[out["metric"] == metric].copy()
    if code_id:
        out = out[out["code_id"] == code_id].copy()
    if biome:
        out = out[out["biome"] == biome].copy()
    return out.reset_index(drop=True)


def feature_chunk_name(prefix: str, metric: Optional[str], code_id: Optional[str], biome: Optional[str]) -> str:
    parts = [prefix]
    if metric:
        parts.append(metric)
    if code_id:
        parts.append(code_id)
    if biome:
        parts.append(biome)
    return "_".join(parts)


def finalize_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "wind_u_10m" in "".join(out.columns) or "wind_v_10m" in "".join(out.columns):
        for phase in ("pre30", "prepeak", "shock", "postpeak30", "recoverywin"):
            u_col = f"{phase}_wind_u_10m_mean"
            v_col = f"{phase}_wind_v_10m_mean"
            if u_col in out and v_col in out:
                out[f"{phase}_wind_speed_mean"] = np.sqrt(out[u_col] ** 2 + out[v_col] ** 2)
    for phase in ("pre30", "shock", "postpeak30", "recoverywin"):
        p_col = f"{phase}_total_precipitation_sum"
        et_col = f"{phase}_total_evaporation_sum"
        if p_col in out and et_col in out:
            out[f"{phase}_p_minus_et"] = out[p_col] - out[et_col]

    recovery_days_col = "t_recover_to_baseline_abs_peak"
    if recovery_days_col in out:
        recovery_days = pd.to_numeric(out[recovery_days_col], errors="coerce")
        # Recovery window is sliced inclusively from peak day to recovery day.
        recovery_counts = recovery_days + 1.0
        valid_counts = recovery_counts > 0
        for var_name in ("total_precipitation", "total_evaporation"):
            sum_col = f"recoverywin_{var_name}_sum"
            mean_col = f"recoverywin_{var_name}_mean"
            if sum_col in out and mean_col not in out:
                numerator = pd.to_numeric(out[sum_col], errors="coerce")
                out[mean_col] = np.divide(
                    numerator,
                    recovery_counts,
                    out=np.full(len(out), np.nan, dtype=float),
                    where=valid_counts & numerator.notna(),
                )
    for phase in ("pre30", "prepeak", "shock", "postpeak30", "recoverywin"):
        hi = f"{phase}_leaf_area_index_high_vegetation_mean"
        lo = f"{phase}_leaf_area_index_low_vegetation_mean"
        if hi in out and lo in out:
            out[f"{phase}_lai_total_mean"] = out[hi] + out[lo]
    st1 = "shock_soil_temperature_level_1_mean"
    st4 = "shock_soil_temperature_level_4_mean"
    if st1 in out and st4 in out:
        out["shock_soil_temp_gradient"] = out[st1] - out[st4]
    recoverywin_soil_temp_cols = list(SOIL_TEMPERATURE_LAYER_WEIGHTS.keys())
    if any(col in out for col in recoverywin_soil_temp_cols):
        available = [col for col in recoverywin_soil_temp_cols if col in out]
        weights = np.array([SOIL_TEMPERATURE_LAYER_WEIGHTS[col] for col in available], dtype=float)
        values = out[available].to_numpy(dtype=float)
        mask = ~np.isnan(values)
        weighted_sum = (np.where(mask, values, 0.0) * weights).sum(axis=1)
        total_weight = (mask * weights).sum(axis=1)
        out["recoverywin_soil_temperature_weighted_mean"] = np.divide(
            weighted_sum,
            total_weight,
            out=np.full(weighted_sum.shape, np.nan, dtype=float),
            where=total_weight > 0,
        )
        
    # Calculate VPD (hPa) using Magnus formula
    for phase in ("pre30", "prepeak", "shock", "postpeak30", "recoverywin"):
        t2m_col = f"{phase}_temperature_2m_mean"
        d2m_col = f"{phase}_dewpoint_temperature_mean"
        if t2m_col in out and d2m_col in out:
            tc = out[t2m_col] - 273.15
            tdc = out[d2m_col] - 273.15
            es = 6.1078 * np.exp((17.27 * tc) / (tc + 237.3))
            ea = 6.1078 * np.exp((17.27 * tdc) / (tdc + 237.3))
            out[f"{phase}_VPD_mean"] = es - ea
            
    return out


def resolve_event_slot(ds, lat_idx: int, lon_idx: int, row: Mapping[str, object]) -> Optional[int]:
    event_id = int(row["event_id"])
    max_events = ds.sizes["max_events"]
    candidate_slots = []
    if 0 <= event_id < max_events:
        candidate_slots.append(event_id)

    count = int(ds["event_count"].isel(lat=lat_idx, lon=lon_idx).item())
    if count <= 0:
        return None

    onset_year = int(row["onset_year"])
    onset_doy = int(row["onset_doy"])
    drought_start_year = int(row["drought_start_year"])
    drought_start_doy = int(row["drought_start_doy"])

    for slot in range(count):
        if slot not in candidate_slots:
            candidate_slots.append(slot)

    for slot in candidate_slots:
        oy = int(ds["onset_start_year"].isel(max_events=slot, lat=lat_idx, lon=lon_idx).item())
        od = int(ds["onset_start_doy"].isel(max_events=slot, lat=lat_idx, lon=lon_idx).item())
        dy = int(ds["drought_start_year"].isel(max_events=slot, lat=lat_idx, lon=lon_idx).item())
        dd = int(ds["drought_start_doy"].isel(max_events=slot, lat=lat_idx, lon=lon_idx).item())
        if oy == onset_year and od == onset_doy and dy == drought_start_year and dd == drought_start_doy:
            return slot
    return candidate_slots[0] if candidate_slots else None
