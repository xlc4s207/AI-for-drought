#!/usr/bin/env python3
"""Standardized absolute-metric augmentation for v20260316 results."""

import argparse
import os
from functools import lru_cache

import netCDF4 as nc
import numpy as np

from response_standardization_v20260316 import build_year_offsets, compute_absolute_metrics_from_segment


BASE_DIR = "/home/xulc/flash_drought"
START_YEAR = 1982
END_YEAR = 2022
WINDOW_BEFORE = 60
WINDOW_AFTER_FLASH = 180
BASELINE_TOLERANCE_MULTIPLIER = 0.5
BASELINE_TOLERANCE_FLOOR_FRACTION = 0.02
BASELINE_RECOVERY_CONSECUTIVE_DAYS = 3

DEFAULT_DATA_FILES = {
    "gpp": os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_result/BESS_GPP_1982_2022.nc"),
    "reco": "/data/BESS_V2/BESS_RECO_1982-2022_0.1deg.nc",
    "nee": "/data/BESS_V2/NEE_1982-2022_0.1deg.nc",
}

OUTPUT_FIELDS = (
    "value_baseline_abs",
    "value_baseline_std_abs",
    "value_min_abs",
    "value_max_abs",
    "value_mean_abs",
    "value_trend_abs",
    "value_drop_abs",
    "value_rise_abs",
    "value_change_to_peak_abs",
    "value_recovery_rate_abs",
    "t_recover_to_baseline",
    "recovery_rate_to_baseline",
    "legacy_duration",
    "legacy_integral",
    "cross_zero_after_onset",
    "t_to_source",
    "source_days",
    "source_integral",
)


def infer_metric_type(input_file, var_name=None):
    name = os.path.basename(input_file).lower()
    if "gpp" in name:
        return "gpp", "GPP"
    if "reco" in name:
        return "reco", "RECO"
    if "nee" in name:
        return "nee", "NEE"
    if var_name is not None:
        upper = str(var_name).upper()
        if upper == "GPP":
            return "gpp", "GPP"
        if upper == "RECO":
            return "reco", "RECO"
        if upper == "NEE":
            return "nee", "NEE"
    raise ValueError(f"Cannot infer metric type from file name: {input_file}")


def augment_absolute_metrics(
    input_file,
    data_file,
    var_name,
    output_file,
    window_before=WINDOW_BEFORE,
    window_after_flash=WINDOW_AFTER_FLASH,
    direction=None,
    baseline_tolerance_multiplier=BASELINE_TOLERANCE_MULTIPLIER,
    baseline_tolerance_floor_fraction=BASELINE_TOLERANCE_FLOOR_FRACTION,
    baseline_recovery_consecutive_days=BASELINE_RECOVERY_CONSECUTIVE_DAYS,
):
    year_offsets = build_year_offsets(START_YEAR, END_YEAR)
    with nc.Dataset(input_file, "r") as res_ds, nc.Dataset(data_file, "r") as data_ds:
        n_event = len(res_ds.dimensions["event"])
        lat_arr = data_ds.variables["lat"][:].astype(np.float32)
        lon_arr = data_ds.variables["lon"][:].astype(np.float32)
        data_var = data_ds.variables[var_name]
        data_time = len(data_ds.dimensions["time"])

        event_lat = res_ds.variables["lat"][:]
        event_lon = res_ds.variables["lon"][:]
        event_year = res_ds.variables["onset_year"][:]
        event_doy = res_ds.variables["onset_doy"][:]
        drought_start_year = res_ds.variables["drought_start_year"][:] if "drought_start_year" in res_ds.variables else event_year
        drought_start_doy = res_ds.variables["drought_start_doy"][:] if "drought_start_doy" in res_ds.variables else event_doy
        drought_end_year = res_ds.variables["drought_end_year"][:] if "drought_end_year" in res_ds.variables else None
        drought_end_doy = res_ds.variables["drought_end_doy"][:] if "drought_end_doy" in res_ds.variables else None
        t_peak = res_ds.variables["t_peak"][:] if "t_peak" in res_ds.variables else np.full(n_event, -1, dtype=np.int16)
        t_recover = res_ds.variables["t_recover"][:] if "t_recover" in res_ds.variables else np.full(n_event, np.nan, dtype=np.float32)
        if "actual_window_after" in res_ds.variables:
            event_win_after = res_ds.variables["actual_window_after"][:]
        else:
            event_win_after = np.full(n_event, window_after_flash, dtype=np.int16)

        lat_idx = np.array([int(np.argmin(np.abs(lat_arr - v))) for v in event_lat], dtype=np.int32)
        lon_idx = np.array([int(np.argmin(np.abs(lon_arr - v))) for v in event_lon], dtype=np.int32)

        @lru_cache(maxsize=2048)
        def get_pixel_series(i_lat, i_lon):
            raw = data_var[:, int(i_lat), int(i_lon)]
            arr = raw.astype(np.float32)
            if np.ma.isMaskedArray(arr):
                arr = np.ma.filled(arr, np.nan).astype(np.float32)
            return arr

        outputs = {name: np.full(n_event, np.nan, dtype=np.float32) for name in OUTPUT_FIELDS}
        metric_type = infer_metric_type(input_file, var_name=var_name)[0]
        metric_direction = direction or ("positive" if metric_type == "nee" else "negative")
        for idx in range(n_event):
            year = int(event_year[idx])
            doy = int(event_doy[idx])
            if year not in year_offsets or doy < 1 or doy > 366:
                continue

            onset = year_offsets[year] + doy - 1
            win_after = int(event_win_after[idx]) if np.isfinite(event_win_after[idx]) else window_after_flash
            if win_after <= 0:
                win_after = window_after_flash
            ws = onset - window_before
            we = onset + win_after
            if ws < 0 or we >= data_time:
                continue

            threshold_offset = 0
            start_year = int(drought_start_year[idx]) if idx < len(drought_start_year) else year
            start_doy = int(drought_start_doy[idx]) if idx < len(drought_start_doy) else doy
            if start_year in year_offsets and 1 <= start_doy <= 366:
                threshold_offset = (year_offsets[start_year] + start_doy - 1) - onset
            threshold_offset = max(0, int(threshold_offset))

            event_end_offset = None
            if drought_end_year is not None and drought_end_doy is not None:
                end_year = int(drought_end_year[idx])
                end_doy = int(drought_end_doy[idx])
                if end_year in year_offsets and 1 <= end_doy <= 366:
                    event_end_offset = (year_offsets[end_year] + end_doy - 1) - onset

            segment = get_pixel_series(int(lat_idx[idx]), int(lon_idx[idx]))[ws : we + 1]
            metrics = compute_absolute_metrics_from_segment(
                segment=segment,
                window_before=window_before,
                t_peak=int(t_peak[idx]) if idx < len(t_peak) else -1,
                t_recover=float(t_recover[idx]) if idx < len(t_recover) else np.nan,
                direction=metric_direction,
                n_consecutive=baseline_recovery_consecutive_days,
                threshold_offset=threshold_offset,
                event_end_offset=event_end_offset,
                baseline_tolerance_multiplier=baseline_tolerance_multiplier,
                baseline_tolerance_floor_fraction=baseline_tolerance_floor_fraction,
                enable_sink_source=(metric_type == "nee"),
            )
            for field in OUTPUT_FIELDS:
                outputs[field][idx] = metrics[field]

    with nc.Dataset(input_file, "r") as src, nc.Dataset(output_file, "w", format="NETCDF4") as dst:
        for dim_name, dim in src.dimensions.items():
            dst.createDimension(dim_name, None if dim.isunlimited() else len(dim))
        for name, var in src.variables.items():
            fill_value = getattr(var, "_FillValue", None)
            if fill_value is not None:
                out_var = dst.createVariable(name, var.datatype, var.dimensions, fill_value=fill_value, zlib=True, complevel=4)
            else:
                out_var = dst.createVariable(name, var.datatype, var.dimensions, zlib=True, complevel=4)
            out_var[:] = var[:]
            for attr in var.ncattrs():
                if attr != "_FillValue":
                    setattr(out_var, attr, getattr(var, attr))
        for field in OUTPUT_FIELDS:
            out_var = dst.createVariable(field, "f4", ("event",), fill_value=np.nan, zlib=True, complevel=4)
            out_var[:] = outputs[field]
        for attr in src.ncattrs():
            setattr(dst, attr, getattr(src, attr))
        dst.absolute_metrics_version = "v20260316"


def main():
    parser = argparse.ArgumentParser(description="Standardized absolute metrics augmentation for v20260316 results")
    parser.add_argument("--input", required=True)
    parser.add_argument("--data", default=None)
    parser.add_argument("--var", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    metric_type, inferred_var = infer_metric_type(args.input, var_name=args.var)
    data_file = args.data or DEFAULT_DATA_FILES[metric_type]
    var_name = args.var or inferred_var
    augment_absolute_metrics(args.input, data_file, var_name, args.output)


if __name__ == "__main__":
    main()
