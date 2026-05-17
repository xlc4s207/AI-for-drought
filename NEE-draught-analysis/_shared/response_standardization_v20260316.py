#!/usr/bin/env python3
"""Shared response standardization helpers for v20260316 scripts."""

import gc
import os
import shutil
import warnings
from datetime import datetime
from multiprocessing import Pool

import netCDF4 as nc
import numpy as np
from tqdm import tqdm

warnings.filterwarnings("ignore")


_CONFIG = None
_DATA_DS = None
_EVENT_DS = None
_LON_ARR = None
_YEAR_OFFSETS = None
_DOY_IDX = None


def build_year_offsets(start_year, end_year):
    offsets = {}
    cumsum = 0
    for year in range(start_year, end_year + 1):
        offsets[year] = cumsum
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        cumsum += 366 if leap else 365
    return offsets


def build_doy_index(start_year, end_year):
    idx = []
    for year in range(start_year, end_year + 1):
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        for day in range(366 if leap else 365):
            doy_idx = day if leap else (day if day < 59 else day + 1)
            idx.append(doy_idx)
    return np.array(idx, dtype=np.int16)


def smooth_causal(x, window=7):
    n = len(x)
    result = np.full(n, np.nan, dtype=np.float32)
    for i in range(n):
        start = max(0, i - window + 1)
        vals = x[start : i + 1]
        vals = vals[np.isfinite(vals)]
        if len(vals) >= 3:
            result[i] = np.float32(np.mean(vals))
    return result


def calc_trend(y):
    mask = np.isfinite(y)
    if np.sum(mask) < 10:
        return np.nan
    x = np.arange(len(y), dtype=np.float64)[mask]
    v = y[mask].astype(np.float64)
    xm = x.mean()
    vm = v.mean()
    den = np.sum((x - xm) ** 2)
    if den <= 0:
        return np.nan
    return np.sum((x - xm) * (v - vm)) / den


def _crossing_condition(value, threshold, direction):
    if direction == "negative":
        return np.isfinite(value) and value <= threshold
    return np.isfinite(value) and value >= threshold


def _recovery_condition(value, threshold, direction):
    if direction == "negative":
        return np.isfinite(value) and value > threshold
    return np.isfinite(value) and value < threshold


def find_threshold_crossing(x, threshold, n_consecutive, max_search, direction):
    search_len = min(len(x), max_search)
    if search_len < n_consecutive:
        return -1
    for i in range(search_len - n_consecutive + 1):
        ok = True
        for j in range(i, i + n_consecutive):
            if not _crossing_condition(x[j], threshold, direction):
                ok = False
                break
        if ok:
            return i
    return -1


def find_recovery(x, start_idx, threshold, n_consecutive, direction):
    if start_idx >= len(x):
        return -1
    for i in range(start_idx, len(x) - n_consecutive + 1):
        ok = True
        for j in range(i, i + n_consecutive):
            if not _recovery_condition(x[j], threshold, direction):
                ok = False
                break
        if ok:
            return i
    return -1


def _default_metric_result():
    return {
        "effective_event": 0,
        "effective_reason_code": 0,
        "response_detected": 0,
        "summary_min": np.nan,
        "summary_mean": np.nan,
        "summary_trend": np.nan,
        "t_response": -1,
        "t_response_after_threshold": -1,
        "t_peak": -1,
        "t_impact": -1,
        "amp_peak": np.nan,
        "t_recover": np.nan,
        "recovery_rate": np.nan,
    }


def compute_event_metrics_from_post(
    post,
    threshold_offset,
    response_threshold,
    recover_threshold,
    n_consecutive,
    primary_search_window,
    supplemental_search_window,
    direction,
):
    metrics = _default_metric_result()

    if np.sum(np.isfinite(post)) < 10:
        return metrics

    metrics["summary_min"] = float(np.nanmin(post))
    metrics["summary_mean"] = float(np.nanmean(post))
    metrics["summary_trend"] = float(calc_trend(post))

    metrics["t_response"] = find_threshold_crossing(
        post, response_threshold, n_consecutive, primary_search_window, direction
    )

    threshold_offset = int(max(0, threshold_offset))
    if threshold_offset < len(post):
        local = find_threshold_crossing(
            post[threshold_offset:],
            response_threshold,
            n_consecutive,
            supplemental_search_window,
            direction,
        )
        if local >= 0:
            metrics["t_response_after_threshold"] = int(local)

    if metrics["t_response"] < 0:
        return metrics

    metrics["effective_event"] = 1
    metrics["effective_reason_code"] = 1
    metrics["response_detected"] = 1
    response_idx = metrics["t_response"]
    if direction == "negative":
        valid = np.where(np.isfinite(post[response_idx:]))[0]
        if len(valid) == 0:
            return metrics
        rel_peak = int(valid[np.argmin(post[response_idx:][valid])])
    else:
        valid = np.where(np.isfinite(post[response_idx:]))[0]
        if len(valid) == 0:
            return metrics
        rel_peak = int(valid[np.argmax(post[response_idx:][valid])])

    metrics["t_peak"] = int(response_idx + rel_peak)
    metrics["t_impact"] = int(metrics["t_peak"] - metrics["t_response"])
    metrics["amp_peak"] = float(post[metrics["t_peak"]])

    t_recover_idx = find_recovery(
        post, metrics["t_peak"] + 1, recover_threshold, n_consecutive, direction
    )
    if t_recover_idx >= 0:
        metrics["t_recover"] = float(t_recover_idx - metrics["t_peak"])
        if metrics["t_recover"] > 0:
            if direction == "negative":
                metrics["recovery_rate"] = float(
                    (recover_threshold - metrics["amp_peak"]) / metrics["t_recover"]
                )
            else:
                metrics["recovery_rate"] = float(
                    (metrics["amp_peak"] - recover_threshold) / metrics["t_recover"]
                )

    return metrics


def _baseline_recovery_condition(value, baseline, tolerance, direction):
    if not np.isfinite(value):
        return False
    if direction == "negative":
        return value >= (baseline - tolerance)
    return value <= (baseline + tolerance)


def find_recovery_to_baseline(post, start_idx, baseline, tolerance, n_consecutive, direction):
    if start_idx >= len(post):
        return -1
    for i in range(start_idx, len(post) - n_consecutive + 1):
        ok = True
        for j in range(i, i + n_consecutive):
            if not _baseline_recovery_condition(post[j], baseline, tolerance, direction):
                ok = False
                break
        if ok:
            return i
    return -1


def compute_absolute_metrics_from_segment(
    segment,
    window_before,
    t_peak,
    t_recover,
    direction=None,
    n_consecutive=3,
    threshold_offset=0,
    event_end_offset=None,
    baseline_tolerance_multiplier=0.5,
    baseline_tolerance_floor_fraction=0.02,
    enable_sink_source=False,
):
    names = (
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
    metrics = {name: np.nan for name in names}
    if len(segment) <= window_before:
        return metrics

    pre = segment[:window_before]
    post = segment[window_before:]
    if np.sum(np.isfinite(pre)) < 5 or np.sum(np.isfinite(post)) < 10:
        return metrics

    baseline = float(np.nanmean(pre))
    baseline_std = float(np.nanstd(pre))
    post_min = float(np.nanmin(post))
    post_max = float(np.nanmax(post))
    post_mean = float(np.nanmean(post))
    post_trend = float(calc_trend(post))

    metrics["value_baseline_abs"] = baseline
    metrics["value_baseline_std_abs"] = baseline_std
    metrics["value_min_abs"] = post_min
    metrics["value_max_abs"] = post_max
    metrics["value_mean_abs"] = post_mean
    metrics["value_trend_abs"] = post_trend
    metrics["value_drop_abs"] = baseline - post_min
    metrics["value_rise_abs"] = post_max - baseline

    if 0 <= int(t_peak) < len(post) and np.isfinite(post[int(t_peak)]):
        peak_val = float(post[int(t_peak)])
        metrics["value_change_to_peak_abs"] = peak_val - baseline
        if np.isfinite(t_recover) and t_recover > 0:
            recover_idx = int(t_peak) + int(round(float(t_recover)))
            if 0 <= recover_idx < len(post) and np.isfinite(post[recover_idx]):
                metrics["value_recovery_rate_abs"] = float(
                    (post[recover_idx] - peak_val) / float(t_recover)
                )

        if direction in ("negative", "positive"):
            tolerance_floor = max(abs(baseline) * float(baseline_tolerance_floor_fraction), float(baseline_tolerance_floor_fraction))
            tolerance = max(float(baseline_std) * float(baseline_tolerance_multiplier), tolerance_floor)
            anchor_offset = int(max(0, threshold_offset))
            if event_end_offset is not None and np.isfinite(event_end_offset):
                anchor_offset = int(max(anchor_offset, int(event_end_offset)))

            search_start = max(int(t_peak) + 1, anchor_offset)
            recover_to_baseline_idx = find_recovery_to_baseline(
                post=post,
                start_idx=search_start,
                baseline=baseline,
                tolerance=tolerance,
                n_consecutive=max(1, int(n_consecutive)),
                direction=direction,
            )
            if recover_to_baseline_idx >= 0:
                metrics["t_recover_to_baseline"] = float(recover_to_baseline_idx - int(t_peak))
                if metrics["t_recover_to_baseline"] > 0:
                    if direction == "negative":
                        metrics["recovery_rate_to_baseline"] = float(
                            (baseline - peak_val) / metrics["t_recover_to_baseline"]
                        )
                    else:
                        metrics["recovery_rate_to_baseline"] = float(
                            (peak_val - baseline) / metrics["t_recover_to_baseline"]
                        )

            legacy_start = min(max(anchor_offset, 0), len(post))
            legacy_end = recover_to_baseline_idx if recover_to_baseline_idx >= 0 else len(post)
            legacy_end = min(max(legacy_end, legacy_start), len(post))
            if legacy_end > legacy_start:
                legacy_slice = post[legacy_start:legacy_end]
                if direction == "negative":
                    legacy_mag = np.where(np.isfinite(legacy_slice), np.maximum(0.0, baseline - legacy_slice), 0.0)
                else:
                    legacy_mag = np.where(np.isfinite(legacy_slice), np.maximum(0.0, legacy_slice - baseline), 0.0)
                metrics["legacy_duration"] = float(legacy_end - legacy_start)
                metrics["legacy_integral"] = float(np.nansum(legacy_mag))

        if enable_sink_source:
            source_mask = np.isfinite(post) & (post > 0)
            metrics["cross_zero_after_onset"] = float(int(np.any(source_mask)))
            metrics["source_days"] = float(np.sum(source_mask))
            metrics["source_integral"] = float(np.nansum(post[source_mask])) if np.any(source_mask) else 0.0
            if np.any(source_mask):
                metrics["t_to_source"] = float(int(np.where(source_mask)[0][0]))
            else:
                metrics["t_to_source"] = np.nan
        else:
            metrics["cross_zero_after_onset"] = 0.0
            metrics["source_days"] = 0.0
            metrics["source_integral"] = 0.0

    return metrics


def calc_climatology_zscore(data_matrix, doy_idx):
    n_time, n_pixels = data_matrix.shape
    clim_mean = np.full((366, n_pixels), np.nan, dtype=np.float32)
    clim_std = np.full((366, n_pixels), np.nan, dtype=np.float32)

    for doy in range(366):
        mask = doy_idx == doy
        if np.any(mask):
            data = data_matrix[mask, :]
            clim_mean[doy, :] = np.nanmean(data, axis=0)
            clim_std[doy, :] = np.nanstd(data, axis=0, ddof=0)

    clim_std[clim_std < 0.01] = np.nan
    full_mean = clim_mean[doy_idx, :]
    full_std = clim_std[doy_idx, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        return (data_matrix - full_mean) / full_std


def build_result_dtype(metric_name, event_mode):
    core_fields = [
        ("lat", "f4"),
        ("lon", "f4"),
        ("event_id", "i2"),
        ("onset_year", "i2"),
        ("onset_doy", "i2"),
        ("drought_start_year", "i2"),
        ("drought_start_doy", "i2"),
    ]
    if event_mode == "nonflash":
        core_fields.extend(
            [
                ("drought_end_year", "i2"),
                ("drought_end_doy", "i2"),
                ("drought_duration", "i2"),
                ("actual_window_after", "i2"),
            ]
        )
    else:
        core_fields.append(("actual_window_after", "i2"))

    metric_fields = [
        ("effective_event", "i1"),
        ("effective_reason_code", "i2"),
        ("overlap_with_prev", "i1"),
        ("overlap_with_next", "i1"),
        ("exclude_from_baseline_recovery", "i1"),
        ("response_detected", "i1"),
        (f"{metric_name}_min", "f4"),
        (f"{metric_name}_mean", "f4"),
        (f"{metric_name}_trend", "f4"),
        ("t_peak", "i2"),
        ("t_response", "i2"),
        ("t_response_after_threshold", "i2"),
        ("t_impact", "i2"),
        ("amp_max", "f4"),
        ("t_recover", "f4"),
        ("recovery_rate", "f4"),
    ]
    return np.dtype(core_fields + metric_fields)


def _fill_array(values, fill_value):
    if hasattr(values, "filled"):
        return values.filled(fill_value)
    return np.array(values)


def _to_float32_with_nan(values):
    if np.ma.isMaskedArray(values):
        return np.ma.asarray(values, dtype=np.float32).filled(np.nan)
    return np.asarray(values, dtype=np.float32)


def _get_event_arrays(lat_start, lat_end, max_ec):
    arrays = {
        "onset_year": _fill_array(
            _EVENT_DS.variables["onset_start_year"][:max_ec, lat_start:lat_end, :], -1
        ),
        "onset_doy": _fill_array(
            _EVENT_DS.variables["onset_start_doy"][:max_ec, lat_start:lat_end, :], -1
        ),
        "drought_start_year": _fill_array(
            _EVENT_DS.variables["drought_start_year"][:max_ec, lat_start:lat_end, :], -1
        ),
        "drought_start_doy": _fill_array(
            _EVENT_DS.variables["drought_start_doy"][:max_ec, lat_start:lat_end, :], -1
        ),
    }
    if _CONFIG["event_mode"] == "nonflash":
        arrays["drought_end_year"] = _fill_array(
            _EVENT_DS.variables["drought_end_year"][:max_ec, lat_start:lat_end, :], -1
        )
        arrays["drought_end_doy"] = _fill_array(
            _EVENT_DS.variables["drought_end_doy"][:max_ec, lat_start:lat_end, :], -1
        )
        arrays["duration"] = _fill_array(
            _EVENT_DS.variables["duration"][:max_ec, lat_start:lat_end, :], -1
        )
    return arrays


def _valid_year_doy(year, doy):
    return year in _YEAR_OFFSETS and 1 <= doy <= 366


def _event_indices(event_arrays, event_id, rel_lat, lon_idx):
    onset_year = int(event_arrays["onset_year"][event_id, rel_lat, lon_idx])
    onset_doy = int(event_arrays["onset_doy"][event_id, rel_lat, lon_idx])
    drought_start_year = int(event_arrays["drought_start_year"][event_id, rel_lat, lon_idx])
    drought_start_doy = int(event_arrays["drought_start_doy"][event_id, rel_lat, lon_idx])

    if not _valid_year_doy(onset_year, onset_doy):
        return None
    if not _valid_year_doy(drought_start_year, drought_start_doy):
        drought_start_year = onset_year
        drought_start_doy = onset_doy

    onset_idx = _YEAR_OFFSETS[onset_year] + onset_doy - 1
    drought_start_idx = _YEAR_OFFSETS[drought_start_year] + drought_start_doy - 1

    result = {
        "onset_year": onset_year,
        "onset_doy": onset_doy,
        "drought_start_year": drought_start_year,
        "drought_start_doy": drought_start_doy,
        "onset_idx": onset_idx,
        "drought_start_idx": drought_start_idx,
    }

    if _CONFIG["event_mode"] == "nonflash":
        drought_end_year = int(event_arrays["drought_end_year"][event_id, rel_lat, lon_idx])
        drought_end_doy = int(event_arrays["drought_end_doy"][event_id, rel_lat, lon_idx])
        duration = int(event_arrays["duration"][event_id, rel_lat, lon_idx])
        if not _valid_year_doy(drought_end_year, drought_end_doy):
            return None
        drought_end_idx = _YEAR_OFFSETS[drought_end_year] + drought_end_doy - 1
        actual_window_after = min(
            drought_end_idx + _CONFIG["recovery_window"] - onset_idx,
            _CONFIG["max_window_after"],
        )
        result.update(
            {
                "drought_end_year": drought_end_year,
                "drought_end_doy": drought_end_doy,
                "drought_end_idx": drought_end_idx,
                "duration": duration if duration > 0 else drought_end_idx - drought_start_idx + 1,
                "actual_window_after": int(actual_window_after),
            }
        )
    else:
        result["actual_window_after"] = int(_CONFIG["window_after"])

    return result


def _build_window(event_info, series_len):
    ws = event_info["onset_idx"] - _CONFIG["window_before"]
    we = event_info["onset_idx"] + event_info["actual_window_after"]
    if ws < 0 or we >= series_len:
        return None
    threshold_offset = max(0, event_info["drought_start_idx"] - event_info["onset_idx"])
    return ws, we, threshold_offset


def _summary_value(metrics):
    return metrics["amp_peak"] if metrics["response_detected"] else metrics["summary_min"]


def _primary_search_window(event_info):
    if _CONFIG["event_mode"] == "flash":
        return _CONFIG["response_search_window"]
    return max(1, int(event_info["actual_window_after"]))


def _supplemental_search_window(event_info, threshold_offset):
    if _CONFIG["event_mode"] == "flash":
        return _CONFIG["response_search_window"]
    remaining = int(event_info["actual_window_after"]) - int(threshold_offset)
    return max(1, remaining)


def compute_event_overlap_flags(event_info, prev_event_info, next_event_info, window_before):
    baseline_start_idx = int(event_info["onset_idx"]) - int(window_before)
    current_window_end = int(event_info["onset_idx"]) + int(event_info["actual_window_after"])

    overlap_with_prev = 0
    overlap_with_next = 0

    if prev_event_info is not None:
        prev_window_end = int(prev_event_info["onset_idx"]) + int(prev_event_info["actual_window_after"])
        overlap_with_prev = int(prev_window_end >= baseline_start_idx)

    if next_event_info is not None:
        next_onset = int(next_event_info["onset_idx"])
        overlap_with_next = int(next_onset <= current_window_end)

    return {
        "overlap_with_prev": overlap_with_prev,
        "overlap_with_next": overlap_with_next,
        "exclude_from_baseline_recovery": int(overlap_with_prev or overlap_with_next),
    }


def _metric_tuple(metric_name, event_mode, lat_val, lon_val, event_id, event_info, overlap_flags, metrics):
    values = [
        lat_val,
        lon_val,
        event_id,
        event_info["onset_year"],
        event_info["onset_doy"],
        event_info["drought_start_year"],
        event_info["drought_start_doy"],
    ]
    if event_mode == "nonflash":
        values.extend(
            [
                event_info["drought_end_year"],
                event_info["drought_end_doy"],
                int(min(event_info["duration"], 32767)),
                int(min(event_info["actual_window_after"], 32767)),
            ]
        )
    else:
        values.append(int(min(event_info["actual_window_after"], 32767)))

    values.extend(
        [
            int(metrics["effective_event"]),
            int(metrics["effective_reason_code"]),
            int(overlap_flags["overlap_with_prev"]),
            int(overlap_flags["overlap_with_next"]),
            int(overlap_flags["exclude_from_baseline_recovery"]),
            int(metrics["response_detected"]),
            float(metrics["summary_min"]),
            float(metrics["summary_mean"]),
            float(metrics["summary_trend"]),
            int(metrics["t_peak"]) if metrics["t_peak"] >= 0 else -1,
            int(metrics["t_response"]) if metrics["t_response"] >= 0 else -1,
            int(metrics["t_response_after_threshold"])
            if metrics["t_response_after_threshold"] >= 0
            else -1,
            int(metrics["t_impact"]) if metrics["t_impact"] >= 0 else -1,
            float(_summary_value(metrics)),
            float(metrics["t_recover"]),
            float(metrics["recovery_rate"]),
        ]
    )
    return tuple(values)


def worker_init(config):
    global _CONFIG, _DATA_DS, _EVENT_DS, _LON_ARR, _YEAR_OFFSETS, _DOY_IDX
    _CONFIG = config
    _DATA_DS = nc.Dataset(config["data_file"], "r")
    _EVENT_DS = nc.Dataset(config["event_file"], "r")
    _LON_ARR = _DATA_DS.variables["lon"][:]
    _YEAR_OFFSETS = build_year_offsets(config["start_year"], config["end_year"])
    _DOY_IDX = build_doy_index(config["start_year"], config["end_year"])


def process_chunk(chunk_info):
    chunk_id, lat_start, lat_end = chunk_info
    results = []

    try:
        lat_arr = _DATA_DS.variables["lat"][lat_start:lat_end]
        data_chunk = _DATA_DS.variables[_CONFIG["data_var"]][:, lat_start:lat_end, :]
        data_chunk = _to_float32_with_nan(data_chunk)

        ec_chunk = _EVENT_DS.variables["event_count"][lat_start:lat_end, :]
        ec_chunk = _fill_array(ec_chunk, 0)
        max_ec = int(np.max(ec_chunk))
        if max_ec == 0:
            return chunk_id, np.array([], dtype=build_result_dtype(_CONFIG["metric_name"], _CONFIG["event_mode"]))

        event_arrays = _get_event_arrays(lat_start, lat_end, max_ec)
        for rel_lat in range(lat_end - lat_start):
            lat_val = float(lat_arr[rel_lat])
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            if len(lon_with_events) == 0:
                continue

            row = data_chunk[:, rel_lat, lon_with_events]
            valid_count = np.sum(np.isfinite(row), axis=0)
            good_mask = valid_count >= _CONFIG["min_valid_values"]
            if not np.any(good_mask):
                continue

            good_lon_indices = lon_with_events[good_mask]
            good_data = row[:, good_mask]
            z_matrix = calc_climatology_zscore(good_data, _DOY_IDX)

            for idx, lon_idx in enumerate(good_lon_indices):
                ec = int(ec_chunk[rel_lat, lon_idx])
                z_series = z_matrix[:, idx]
                lon_val = float(_LON_ARR[lon_idx])
                for event_id in range(ec):
                    event_info = _event_indices(event_arrays, event_id, rel_lat, lon_idx)
                    if event_info is None:
                        continue
                    prev_event_info = None
                    next_event_info = None
                    if event_id > 0:
                        prev_event_info = _event_indices(event_arrays, event_id - 1, rel_lat, lon_idx)
                    if event_id + 1 < ec:
                        next_event_info = _event_indices(event_arrays, event_id + 1, rel_lat, lon_idx)
                    overlap_flags = compute_event_overlap_flags(
                        event_info=event_info,
                        prev_event_info=prev_event_info,
                        next_event_info=next_event_info,
                        window_before=_CONFIG["window_before"],
                    )

                    window = _build_window(event_info, len(z_series))
                    if window is None:
                        continue
                    ws, we, threshold_offset = window
                    segment = z_series[ws : we + 1]
                    if np.sum(np.isfinite(segment)) < 30:
                        continue

                    smoothed = smooth_causal(segment, _CONFIG["smooth_window"])
                    pre = smoothed[: _CONFIG["window_before"]]
                    if np.sum(np.isfinite(pre)) < 5:
                        continue

                    post = smoothed[_CONFIG["window_before"] :]
                    metrics = compute_event_metrics_from_post(
                        post=post,
                        threshold_offset=threshold_offset,
                        response_threshold=_CONFIG["response_threshold"],
                        recover_threshold=_CONFIG["recover_threshold"],
                        n_consecutive=_CONFIG["consecutive_days"],
                        primary_search_window=_primary_search_window(event_info),
                        supplemental_search_window=_supplemental_search_window(event_info, threshold_offset),
                        direction=_CONFIG["direction"],
                    )
                    results.append(
                        _metric_tuple(
                            _CONFIG["metric_name"],
                            _CONFIG["event_mode"],
                            lat_val,
                            lon_val,
                            event_id,
                            event_info,
                            overlap_flags,
                            metrics,
                        )
                    )

        dtype = build_result_dtype(_CONFIG["metric_name"], _CONFIG["event_mode"])
        if results:
            return chunk_id, np.array(results, dtype=dtype)
        return chunk_id, np.array([], dtype=dtype)
    except Exception as exc:
        print(f"Chunk {chunk_id} error: {exc}")
        return chunk_id, np.array([], dtype=build_result_dtype(_CONFIG["metric_name"], _CONFIG["event_mode"]))


def save_results_to_netcdf(results, config, output_file):
    result_fields = list(results.dtype.names)
    with nc.Dataset(output_file, "w", format="NETCDF4") as ds:
        ds.createDimension("event", len(results))
        for field in result_fields:
            dtype = results.dtype[field]
            if np.issubdtype(dtype, np.floating):
                fill_value = np.nan
            elif dtype == np.int8:
                fill_value = -127
            else:
                fill_value = -9999
            var = ds.createVariable(field, dtype, ("event",), fill_value=fill_value, zlib=True, complevel=4)
            var[:] = results[field]
        ds.title = config["title"]
        ds.description = config["description"]
        ds.history = f"Created: {datetime.now()}"
        ds.source_event_file = config["event_file"]
        ds.source_data_file = config["data_file"]


def _create_chunks(config):
    with nc.Dataset(config["event_file"], "r") as ds:
        ec_all = _fill_array(ds.variables["event_count"][:], 0)
        lat_has_events = np.any(ec_all > 0, axis=1)
        valid_lat_indices = np.where(lat_has_events)[0]
        if len(valid_lat_indices) == 0:
            return [], 0
        start = int(valid_lat_indices[0])
        end = int(valid_lat_indices[-1] + 1)
        total_events = int(np.sum(ec_all))
    chunks = []
    chunk_id = 0
    for chunk_start in range(start, end, config["lat_chunk_size"]):
        chunk_end = min(chunk_start + config["lat_chunk_size"], end)
        chunks.append((chunk_id, chunk_start, chunk_end))
        chunk_id += 1
    return chunks, total_events


def run_relative_analysis(config):
    os.makedirs(config["output_dir"], exist_ok=True)
    if os.path.exists(config["temp_dir"]):
        shutil.rmtree(config["temp_dir"])
    os.makedirs(config["temp_dir"], exist_ok=True)

    chunks, total_events = _create_chunks(config)
    if not chunks:
        raise RuntimeError("No valid events found for the configured event file")

    print("=" * 70)
    print(config["title"])
    print("=" * 70)
    print(f"Event file: {config['event_file']}")
    print(f"Data file : {config['data_file']}")
    print(f"Output    : {config['relative_output_file']}")
    print(f"Chunks    : {len(chunks)}")
    print(f"Events    : {total_events:,}")

    total_saved = 0
    with Pool(config["n_workers"], initializer=worker_init, initargs=(config,)) as pool:
        for chunk_id, result in tqdm(pool.imap_unordered(process_chunk, chunks), total=len(chunks), desc="Processing"):
            if len(result) > 0:
                np.save(os.path.join(config["temp_dir"], f"chunk_{chunk_id:04d}.npy"), result)
                total_saved += len(result)
            del result
            gc.collect()

    all_results = []
    for name in sorted(os.listdir(config["temp_dir"])):
        if name.endswith(".npy"):
            all_results.append(np.load(os.path.join(config["temp_dir"], name)))
    dtype = build_result_dtype(config["metric_name"], config["event_mode"])
    merged = np.concatenate(all_results) if all_results else np.array([], dtype=dtype)
    save_results_to_netcdf(merged, config, config["relative_output_file"])
    shutil.rmtree(config["temp_dir"])
    print(f"Saved {len(merged):,} standardized events to {config['relative_output_file']}")
    return config["relative_output_file"]
