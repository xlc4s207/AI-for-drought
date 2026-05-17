#!/usr/bin/env python3
"""Shared compact carbon-response helpers for v20260322_lu_025deg scripts."""

import gc
import json
import os
import shutil
import warnings
from datetime import datetime
from multiprocessing import Pool

import netCDF4 as nc
import numpy as np
from tqdm import tqdm

try:
    from scipy.interpolate import UnivariateSpline
except ImportError:  # pragma: no cover - exercised in runtime environment
    UnivariateSpline = None

warnings.filterwarnings("ignore")


_CONFIG = None
_DATA_DS = None
_EVENT_DS = None
_LON_ARR = None
_YEAR_OFFSETS = None
_DOY_IDX = None
_EVENT_LAT_ARR = None
_EVENT_TO_DATA_LON_IDX = None
_LAT_INDEX_MODE = "same"
_DATA_NLAT = 0
_TEMP_DS = None
_TEMP_EVENT_TO_DATA_LON_IDX = None
_TEMP_LAT_INDEX_MODE = "same"
_TEMP_NLAT = 0
_TEMP_TIME_SLICE = None
_YEAR_SLICES = None
_DATA_TIME_SLICE = None


def _init_drop_reason_stats():
    return {
        "events_chunk_total": 0,
        "events_pass_min_valid_values": 0,
        "events_drop_min_valid_values": 0,
        "events_drop_low_abs_at_drought_start": 0,
        "events_iterated": 0,
        "events_drop_invalid_event_time": 0,
        "events_drop_window_out_of_range": 0,
        "events_drop_insufficient_z_segment": 0,
        "events_drop_insufficient_post": 0,
        "events_drop_insufficient_pre_raw": 0,
        "events_written": 0,
        "events_no_response_detected": 0,
        "events_response_detected": 0,
        "events_lu_valid": 0,
        "events_not_lu_valid": 0,
        "events_excluded_from_baseline_recovery": 0,
        "events_recovery_detected": 0,
        "events_response_valid_but_no_recovery": 0,
        "events_drop_recovery_over_max_valid_days": 0,
        "events_drop_not_growing_season": 0,
        "chunk_errors": 0,
    }


def _merge_drop_reason_stats(total_stats, chunk_stats):
    for key, value in chunk_stats.items():
        total_stats[key] = int(total_stats.get(key, 0)) + int(value)
    return total_stats


def infer_direction(metric_name, direction=None):
    if direction is not None:
        return direction
    return "positive" if str(metric_name).lower() == "nee" else "negative"


def metric_field_names(metric_name, direction=None):
    metric_name = str(metric_name).lower()
    direction = infer_direction(metric_name, direction)
    extremum = f"{metric_name}_max_abs" if direction == "positive" else f"{metric_name}_min_abs"
    return {
        "baseline": f"{metric_name}_baseline_abs",
        "baseline_std": f"{metric_name}_baseline_std_abs",
        "extremum": extremum,
        "change": f"{metric_name}_change_to_peak_abs",
        "loss_total": f"{metric_name}_loss_total_abs",
        "loss_drought_phase": f"{metric_name}_loss_drought_phase_abs",
        "loss_post_drought_phase": f"{metric_name}_loss_post_drought_phase_abs",
        "peak_deficit": f"{metric_name}_peak_deficit_abs",
    }


def auxiliary_response_field_names(prefix):
    prefix = str(prefix).strip()
    if not prefix:
        raise ValueError("auxiliary response prefix cannot be empty")
    return {
        "response_detected": f"response_detected_{prefix}",
        "t_response_onset_start": f"t_response_onset_start_{prefix}",
        "t_response_drought_start": f"t_response_drought_start_{prefix}",
        "t_response_drought_start_from_onset": f"t_response_drought_start_from_onset_{prefix}",
        "t_peak": f"t_peak_{prefix}",
        "t_peak_abs": f"t_peak_abs_{prefix}",
        "amp_max": f"amp_max_{prefix}",
    }


def build_year_offsets(start_year, end_year):
    offsets = {}
    cumsum = 0
    for year in range(start_year, end_year + 1):
        offsets[year] = cumsum
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        cumsum += 366 if leap else 365
    return offsets


def build_year_slices(start_year, end_year):
    slices = []
    cumsum = 0
    for year in range(start_year, end_year + 1):
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        year_len = 366 if leap else 365
        slices.append((year, cumsum, cumsum + year_len))
        cumsum += year_len
    return slices


def detect_growing_season_bounds(temp_series, threshold_k=278.15, min_consecutive_days=5):
    temp = np.asarray(temp_series, dtype=np.float32)
    n = int(len(temp))
    if n == 0:
        return -1, -1
    min_consecutive_days = max(1, int(min_consecutive_days))
    warm_mask = np.isfinite(temp) & (temp > float(threshold_k))
    cold_mask = np.isfinite(temp) & (temp < float(threshold_k))
    start_idx = _first_sustained_true_index(warm_mask, start_idx=0, n_consecutive=min_consecutive_days)
    if start_idx < 0:
        return -1, -1
    cold_start_idx = _first_sustained_true_index(
        cold_mask,
        start_idx=start_idx + min_consecutive_days,
        n_consecutive=min_consecutive_days,
    )
    end_idx = n - 1 if cold_start_idx < 0 else cold_start_idx - 1
    if end_idx < start_idx:
        return -1, -1
    return int(start_idx), int(end_idx)


def build_growing_season_mask(temp_series, year_slices, threshold_k=278.15, min_consecutive_days=5):
    temp = np.asarray(temp_series, dtype=np.float32)
    mask = np.zeros(temp.shape[0], dtype=bool)
    for _, year_start, year_end in year_slices:
        start_idx, end_idx = detect_growing_season_bounds(
            temp[year_start:year_end],
            threshold_k=threshold_k,
            min_consecutive_days=min_consecutive_days,
        )
        if start_idx >= 0 and end_idx >= start_idx:
            mask[year_start + start_idx : year_start + end_idx + 1] = True
    return mask


def is_growing_season_event(growing_season_mask, drought_start_idx, drought_end_idx, min_fraction=0.5):
    mask = np.asarray(growing_season_mask, dtype=bool)
    if mask.size == 0:
        return False
    if drought_start_idx is None or drought_end_idx is None:
        return False
    drought_start_idx = int(drought_start_idx)
    drought_end_idx = int(drought_end_idx)
    if drought_end_idx < drought_start_idx:
        return False
    start_idx = max(0, drought_start_idx)
    end_idx = min(mask.size - 1, drought_end_idx)
    if end_idx < start_idx:
        return False
    duration = end_idx - start_idx + 1
    overlap = int(np.count_nonzero(mask[start_idx : end_idx + 1]))
    return float(overlap) / float(duration) > float(min_fraction)


def count_growing_season_recovery_days(post_growing_season_mask, peak_idx, recover_idx):
    mask = np.asarray(post_growing_season_mask, dtype=bool)
    if mask.size == 0:
        return 0.0
    peak_idx = int(peak_idx)
    recover_idx = int(recover_idx)
    if recover_idx <= peak_idx:
        return 0.0
    lo = max(0, peak_idx + 1)
    hi = min(mask.size, recover_idx + 1)
    if hi <= lo:
        return 0.0
    return float(np.count_nonzero(mask[lo:hi]))


def compute_recovery_day_count(peak_idx, recover_idx, recovery_day_count_mode="elapsed_days", post_growing_season_mask=None):
    elapsed_days = float(max(0, int(recover_idx) - int(peak_idx)))
    if str(recovery_day_count_mode).lower() != "growing_season_only" or post_growing_season_mask is None:
        return elapsed_days
    return count_growing_season_recovery_days(post_growing_season_mask, peak_idx, recover_idx)


def build_doy_index(start_year, end_year):
    idx = []
    for year in range(start_year, end_year + 1):
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        for day in range(366 if leap else 365):
            doy_idx = day if leap else (day if day < 59 else day + 1)
            idx.append(doy_idx)
    return np.array(idx, dtype=np.int16)


def apply_data_scale(values, data_scale=1.0):
    arr = np.asarray(values, dtype=np.float32)
    scale = float(data_scale)
    if not np.isfinite(scale) or np.isclose(scale, 1.0):
        return arr
    return arr * np.float32(scale)


def _time_slice_for_year_range(time_var, start_year, end_year):
    units = getattr(time_var, "units", None)
    if units is None:
        raise ValueError("Temperature time variable is missing units.")
    calendar = getattr(time_var, "calendar", "standard")
    dates = nc.num2date(
        time_var[:],
        units=units,
        calendar=calendar,
        only_use_cftime_datetimes=False,
        only_use_python_datetimes=True,
    )
    valid_idx = np.array(
        [idx for idx, item in enumerate(dates) if start_year <= item.year <= end_year],
        dtype=np.int64,
    )
    if valid_idx.size == 0:
        raise ValueError(f"No temperature time steps overlap {start_year}-{end_year}.")
    return int(valid_idx[0]), int(valid_idx[-1] + 1)


def smooth_causal(x, window=7):
    x = np.asarray(x, dtype=np.float32)
    n = len(x)
    if n == 0:
        return np.array([], dtype=np.float32)
    window = max(1, int(window))
    finite = np.isfinite(x)
    values = np.where(finite, x, 0.0).astype(np.float64, copy=False)
    value_csum = np.cumsum(values, dtype=np.float64)
    count_csum = np.cumsum(finite.astype(np.int32), dtype=np.int64)

    idx = np.arange(n, dtype=np.int64)
    starts = np.maximum(0, idx - window + 1)
    sums = value_csum.copy()
    counts = count_csum.copy()
    valid_start = starts > 0
    if np.any(valid_start):
        start_minus_one = starts[valid_start] - 1
        sums[valid_start] -= value_csum[start_minus_one]
        counts[valid_start] -= count_csum[start_minus_one]

    result = np.full(n, np.nan, dtype=np.float32)
    valid = counts > 0
    if np.any(valid):
        result[valid] = (sums[valid] / counts[valid]).astype(np.float32)
    return result


def calc_climatology_components(data_matrix, doy_idx):
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
        z_matrix = (data_matrix - full_mean) / full_std
    return z_matrix, full_mean, full_std


def calc_climatology_zscore(data_matrix, doy_idx):
    z_matrix, _, _ = calc_climatology_components(data_matrix, doy_idx)
    return z_matrix


def aggregate_mean_1d(values, agg_days):
    values = np.asarray(values, dtype=np.float64)
    agg_days = max(1, int(agg_days))
    n = len(values)
    n_bins = (n + agg_days - 1) // agg_days
    x_agg = np.full(n_bins, np.nan, dtype=np.float64)
    y_agg = np.full(n_bins, np.nan, dtype=np.float64)
    for idx in range(n_bins):
        start = idx * agg_days
        end = min(n, start + agg_days)
        seg = values[start:end]
        seg = seg[np.isfinite(seg)]
        if seg.size == 0:
            continue
        x_agg[idx] = 0.5 * (start + end - 1)
        y_agg[idx] = float(np.nanmean(seg))
    return x_agg, y_agg


def calc_spline_baseline_and_anomaly_1d(
    values,
    agg_days=8,
    smooth_factor_multiplier=0.5,
    min_valid_points=120,
):
    values = np.asarray(values, dtype=np.float64)
    baseline = np.full(values.shape, np.nan, dtype=np.float32)
    anomaly = np.full(values.shape, np.nan, dtype=np.float32)
    finite = np.isfinite(values)
    if finite.sum() < max(8, int(min_valid_points)):
        return baseline, anomaly
    if UnivariateSpline is None:
        raise ImportError("SciPy is required for spline anomaly calculation but is not available.")

    x_agg, y_agg = aggregate_mean_1d(values, agg_days=agg_days)
    valid = np.isfinite(x_agg) & np.isfinite(y_agg)
    if np.sum(valid) < 8:
        return baseline, anomaly

    xv = x_agg[valid]
    yv = y_agg[valid]
    if np.unique(xv).size < 8:
        return baseline, anomaly

    diff_scale = np.nanmedian(np.abs(np.diff(yv)))
    if not np.isfinite(diff_scale) or diff_scale < 1e-6:
        diff_scale = np.nanstd(yv) * 0.05
    if not np.isfinite(diff_scale) or diff_scale < 1e-6:
        diff_scale = 1.0

    s_val = float(max(0.0, smooth_factor_multiplier)) * float(len(yv)) * float(diff_scale ** 2)
    spline = UnivariateSpline(xv, yv, k=3, s=s_val)
    x_full = np.arange(len(values), dtype=np.float64)
    baseline_full = spline(x_full).astype(np.float32, copy=False)
    baseline[finite] = baseline_full[finite]
    anomaly[finite] = (values[finite] - baseline_full[finite]).astype(np.float32, copy=False)
    return baseline, anomaly


def calc_spline_baseline_and_anomaly_matrix(
    data_matrix,
    agg_days=8,
    smooth_factor_multiplier=0.5,
    min_valid_points=120,
):
    data_matrix = np.asarray(data_matrix, dtype=np.float32)
    n_time, n_pixels = data_matrix.shape
    baseline_matrix = np.full((n_time, n_pixels), np.nan, dtype=np.float32)
    anomaly_matrix = np.full((n_time, n_pixels), np.nan, dtype=np.float32)
    for idx in range(n_pixels):
        baseline, anomaly = calc_spline_baseline_and_anomaly_1d(
            data_matrix[:, idx],
            agg_days=agg_days,
            smooth_factor_multiplier=smooth_factor_multiplier,
            min_valid_points=min_valid_points,
        )
        baseline_matrix[:, idx] = baseline
        anomaly_matrix[:, idx] = anomaly
    return anomaly_matrix, baseline_matrix


def calc_auxiliary_anomaly_series_1d(values, aux_response_config, doy_idx):
    aux_response_config = aux_response_config or {}
    anomaly_source = str(aux_response_config.get("anomaly_source", "spline_residual")).lower()
    if anomaly_source == "spline_residual":
        _, anomaly = calc_spline_baseline_and_anomaly_1d(
            values,
            agg_days=aux_response_config.get("spline_agg_days", 5),
            smooth_factor_multiplier=aux_response_config.get("spline_smooth_factor_multiplier", 0.5),
            min_valid_points=aux_response_config.get("spline_min_valid_points", 120),
        )
        return anomaly
    data_matrix = np.asarray(values, dtype=np.float32).reshape(-1, 1)
    anomaly_matrix, _, _ = calc_climatology_components(data_matrix, doy_idx)
    return anomaly_matrix[:, 0]


def compute_cumulative_loss_metrics(
    raw_post,
    baseline_post,
    response_idx,
    recover_idx,
    drought_end_idx=None,
    direction="negative",
):
    out = {
        "loss_total": np.nan,
        "loss_drought_phase": np.nan,
        "loss_post_drought_phase": np.nan,
        "peak_deficit": np.nan,
    }
    if raw_post is None or baseline_post is None:
        return out
    raw_post = np.asarray(raw_post, dtype=np.float64)
    baseline_post = np.asarray(baseline_post, dtype=np.float64)
    if not np.isfinite(response_idx) or not np.isfinite(recover_idx):
        return out
    start_idx = max(0, int(response_idx))
    end_idx = min(len(raw_post) - 1, int(recover_idx))
    if end_idx < start_idx:
        return out

    if infer_direction(None, direction) == "positive":
        deficits = np.maximum(0.0, raw_post - baseline_post)
    else:
        deficits = np.maximum(0.0, baseline_post - raw_post)
    deficits[~np.isfinite(deficits)] = 0.0
    window_deficits = deficits[start_idx : end_idx + 1]
    if window_deficits.size == 0:
        return out
    out["loss_total"] = float(np.sum(window_deficits))
    out["peak_deficit"] = float(np.max(window_deficits))

    if drought_end_idx is None or not np.isfinite(drought_end_idx):
        return out
    drought_end_idx = min(end_idx, max(start_idx, int(drought_end_idx)))
    out["loss_drought_phase"] = float(np.sum(deficits[start_idx : drought_end_idx + 1]))
    if drought_end_idx + 1 <= end_idx:
        out["loss_post_drought_phase"] = float(np.sum(deficits[drought_end_idx + 1 : end_idx + 1]))
    else:
        out["loss_post_drought_phase"] = 0.0
    return out


def compute_post_drought_recovery_days(
    recover_onset_idx,
    drought_end_from_onset,
    recovery_day_count_mode="elapsed_days",
    post_growing_season_mask=None,
):
    if not np.isfinite(recover_onset_idx) or not np.isfinite(drought_end_from_onset):
        return np.nan
    return compute_recovery_day_count(
        peak_idx=int(drought_end_from_onset),
        recover_idx=int(recover_onset_idx),
        recovery_day_count_mode=recovery_day_count_mode,
        post_growing_season_mask=post_growing_season_mask,
    )


def _is_affected(value, direction):
    if not np.isfinite(value):
        return False
    if direction == "positive":
        return value >= 0
    return value <= 0


def _first_affected(x, start_idx, direction, max_search=None):
    n = len(x)
    if max_search is not None:
        n = min(n, int(max_search))
    start_idx = max(0, int(start_idx))
    if start_idx >= n:
        return -1
    x_arr = np.asarray(x[:n])
    finite = np.isfinite(x_arr)
    if direction == "positive":
        mask = finite & (x_arr >= 0)
    else:
        mask = finite & (x_arr <= 0)
    hits = np.flatnonzero(mask[start_idx:])
    if hits.size > 0:
        return int(start_idx + hits[0])
    return -1


def _is_recovered_anomaly(value, direction, threshold=0.0):
    if not np.isfinite(value):
        return False
    if direction == "positive":
        return value < threshold
    return value > threshold


def _anomaly_recovery_index(post, start_idx, direction, n_consecutive, threshold=0.0):
    post_arr = np.asarray(post)
    finite = np.isfinite(post_arr)
    if direction == "positive":
        mask = finite & (post_arr < threshold)
    else:
        mask = finite & (post_arr > threshold)
    return _first_sustained_true_index(mask, start_idx=start_idx, n_consecutive=n_consecutive)


def _first_sustained_true_index(mask, start_idx, n_consecutive, max_search=None):
    mask = np.asarray(mask, dtype=bool)
    start_idx = max(0, int(start_idx))
    n_consecutive = max(1, int(n_consecutive))
    n = len(mask)
    if max_search is not None:
        n = min(n, int(max_search))
    if start_idx >= n or start_idx > n - n_consecutive:
        return -1
    mask_int = mask[:n].astype(np.int8, copy=False)
    csum = np.cumsum(mask_int, dtype=np.int32)
    window_sums = csum[n_consecutive - 1 :].copy()
    if n_consecutive < n:
        window_sums[1:] -= csum[: n - n_consecutive]
    candidate_idx = np.flatnonzero(window_sums[start_idx:] == n_consecutive)
    if candidate_idx.size == 0:
        return -1
    return int(start_idx + candidate_idx[0])


def _has_sustained_directional_trend(x, start_idx, search_days, n_consecutive, direction):
    x = np.asarray(x, dtype=np.float64)
    start_idx = max(0, int(start_idx))
    search_days = max(1, int(search_days))
    n_consecutive = max(1, int(n_consecutive))
    direction = infer_direction(None, direction)
    end_idx = min(len(x), start_idx + search_days)
    if end_idx - start_idx < n_consecutive + 1:
        return False
    seg = x[start_idx:end_idx]
    finite_pair = np.isfinite(seg[1:]) & np.isfinite(seg[:-1])
    if direction == "positive":
        trend_mask = finite_pair & (seg[1:] > seg[:-1])
    else:
        trend_mask = finite_pair & (seg[1:] < seg[:-1])
    return _first_sustained_true_index(trend_mask, start_idx=0, n_consecutive=n_consecutive) >= 0


def _has_sustained_decline(x, start_idx, search_days, n_consecutive):
    return _has_sustained_directional_trend(
        x,
        start_idx=start_idx,
        search_days=search_days,
        n_consecutive=n_consecutive,
        direction="negative",
    )


def _first_threshold_crossing(post, start_idx, direction, threshold, n_consecutive, max_search=None):
    post_arr = np.asarray(post)
    n = len(post_arr)
    if max_search is not None:
        n = min(n, int(max_search))
    finite = np.isfinite(post_arr[:n])
    if direction == "positive":
        mask = finite & (post_arr[:n] >= threshold)
    else:
        mask = finite & (post_arr[:n] <= threshold)
    return _first_sustained_true_index(mask, start_idx=start_idx, n_consecutive=n_consecutive)


def _threshold_recovery_index(post, start_idx, direction, threshold, n_consecutive):
    post_arr = np.asarray(post)
    finite = np.isfinite(post_arr)
    if direction == "positive":
        mask = finite & (post_arr < threshold)
    else:
        mask = finite & (post_arr > threshold)
    return _first_sustained_true_index(mask, start_idx=start_idx, n_consecutive=n_consecutive)


def _is_recovered_absolute(value, direction, baseline):
    if not np.isfinite(value) or not np.isfinite(baseline):
        return False
    if direction == "positive":
        return value <= baseline
    return value >= baseline


def _absolute_recovery_index(post_abs, start_idx, direction, baseline, n_consecutive, max_search=None):
    post_abs_arr = np.asarray(post_abs)
    n = len(post_abs_arr)
    if max_search is not None:
        n = min(n, int(max_search))
    finite = np.isfinite(post_abs_arr[:n])
    if direction == "positive":
        mask = finite & (post_abs_arr[:n] <= baseline)
    else:
        mask = finite & (post_abs_arr[:n] >= baseline)
    return _first_sustained_true_index(mask, start_idx=start_idx, n_consecutive=n_consecutive)


def _find_peak_index_bounded(post, start_idx, end_idx, direction):
    start_idx = max(0, int(start_idx))
    end_idx = len(post) if end_idx is None else min(len(post), int(end_idx))
    if end_idx <= start_idx:
        return -1
    valid = np.where(np.isfinite(post[start_idx:end_idx]))[0]
    if len(valid) == 0:
        return -1
    rel_valid = post[start_idx:end_idx][valid]
    if direction == "positive":
        rel_peak = int(valid[np.argmax(rel_valid)])
    else:
        rel_peak = int(valid[np.argmin(rel_valid)])
    return start_idx + rel_peak


def _find_peak_index(post, start_idx, direction):
    valid = np.where(np.isfinite(post[start_idx:]))[0]
    if len(valid) == 0:
        return -1
    rel_valid = post[start_idx:][valid]
    if direction == "positive":
        rel_peak = int(valid[np.argmax(rel_valid)])
    else:
        rel_peak = int(valid[np.argmin(rel_valid)])
    return start_idx + rel_peak


def compute_compact_absolute_metrics(
    segment,
    window_before,
    t_peak,
    metric_name,
    direction=None,
    clim_segment=None,
    absolute_baseline_mode="pre_window_raw",
    absolute_baseline_days=10,
    absolute_baseline_scale=1.0,
):
    direction = infer_direction(metric_name, direction)
    names = metric_field_names(metric_name, direction)
    metrics = {
        names["baseline"]: np.nan,
        names["baseline_std"]: np.nan,
        names["extremum"]: np.nan,
        names["change"]: np.nan,
    }
    if len(segment) <= window_before:
        return metrics
    absolute_baseline_days = max(1, int(absolute_baseline_days))
    pre = segment[:window_before]
    post = segment[window_before:]
    if np.sum(np.isfinite(pre)) < 5 or np.sum(np.isfinite(post)) < 3:
        return metrics
    baseline_slice_start = max(0, window_before - absolute_baseline_days)
    baseline = np.nan
    baseline_std = np.nan
    if str(absolute_baseline_mode).lower() == "climatology_pre_days" and clim_segment is not None:
        pre_clim = clim_segment[baseline_slice_start:window_before]
        if np.sum(np.isfinite(pre_clim)) >= 3:
            baseline = float(np.nanmean(pre_clim))
            baseline_std = float(np.nanstd(pre_clim))
    elif str(absolute_baseline_mode).lower() == "pre_days_raw":
        pre_days = pre[baseline_slice_start:window_before]
        if np.sum(np.isfinite(pre_days)) >= 3:
            baseline = float(np.nanmean(pre_days))
            baseline_std = float(np.nanstd(pre_days))
    if not np.isfinite(baseline):
        baseline = float(np.nanmean(pre))
        baseline_std = float(np.nanstd(pre))
    baseline_scale = float(absolute_baseline_scale)
    if np.isfinite(baseline_scale):
        baseline = baseline * baseline_scale
    metrics[names["baseline"]] = baseline
    metrics[names["baseline_std"]] = baseline_std
    if 0 <= int(t_peak) < len(post) and np.isfinite(post[int(t_peak)]):
        peak_val = float(post[int(t_peak)])
        metrics[names["extremum"]] = peak_val
        metrics[names["change"]] = peak_val - baseline
    return metrics


def compute_event_metrics_from_post(
    post,
    threshold_offset,
    n_consecutive,
    baseline,
    baseline_tolerance,
    exclude_from_baseline_recovery,
    raw_post=None,
    search_len=None,
    direction="negative",
    min_affected_days=5,
    recovery_anomaly_threshold=0.0,
    exclude_if_onset_already_affected=True,
    response_logic="lu_anomaly",
    legacy_response_threshold=-0.5,
    legacy_recovery_threshold=-0.25,
    legacy_consecutive_days=3,
    legacy_ignore_overlap_exclusion=False,
    baseline_for_recovery_rate=None,
    raw_post_smoothed=None,
    baseline_for_absolute_recovery=None,
    legacy_peak_mode="relative_anomaly",
    legacy_recovery_mode="threshold_anomaly",
    require_post_drought_decline=False,
    post_drought_decline_search_days=30,
    post_drought_decline_consecutive_days=5,
    max_valid_recovery_days=None,
    ignore_overlap_exclusion=False,
    recovery_day_count_mode="elapsed_days",
    post_growing_season_mask=None,
):
    direction = infer_direction(None, direction)
    metrics = _empty_event_metrics()
    if np.sum(np.isfinite(post)) < 3:
        return metrics

    if str(response_logic).lower() == "legacy_relative":
        legacy_peak_mode = str(legacy_peak_mode).lower()
        legacy_recovery_mode = str(legacy_recovery_mode).lower()
        if bool(require_post_drought_decline):
            decline_source = raw_post_smoothed if raw_post_smoothed is not None else raw_post
            if decline_source is None or not _has_sustained_directional_trend(
                decline_source,
                start_idx=threshold_offset,
                search_days=post_drought_decline_search_days,
                n_consecutive=post_drought_decline_consecutive_days,
                direction=direction,
            ):
                return metrics
        onset_response = _first_threshold_crossing(
            post=post,
            start_idx=0,
            direction=direction,
            threshold=float(legacy_response_threshold),
            n_consecutive=int(legacy_consecutive_days),
            max_search=search_len,
        )
        if onset_response >= 0:
            metrics["t_response_onset_start"] = int(onset_response)
        drought_response_from_onset = _first_threshold_crossing(
            post=post,
            start_idx=threshold_offset,
            direction=direction,
            threshold=float(legacy_response_threshold),
            n_consecutive=int(legacy_consecutive_days),
            max_search=search_len,
        )
        if drought_response_from_onset < 0:
            return metrics

        metrics["lu_event_valid"] = 1
        metrics["response_detected"] = 1
        metrics["t_response_drought_start_from_onset"] = int(drought_response_from_onset)
        metrics["t_response_drought_start"] = int(max(0, drought_response_from_onset - int(threshold_offset)))

        abs_source = None
        if raw_post_smoothed is not None and np.sum(np.isfinite(raw_post_smoothed)) >= 3:
            abs_source = raw_post_smoothed
        elif raw_post is not None and np.sum(np.isfinite(raw_post)) >= 3:
            abs_source = raw_post

        peak_idx = -1
        peak_abs_idx = -1
        if legacy_peak_mode in {"smoothed_absolute_min", "smoothed_absolute_max"} and abs_source is not None:
            peak_search_start = max(0, int(threshold_offset))
            peak_search_end = len(abs_source) if search_len is None else min(len(abs_source), int(search_len))
            if (
                legacy_recovery_mode == "absolute_baseline"
                and baseline_for_absolute_recovery is not None
                and np.isfinite(baseline_for_absolute_recovery)
            ):
                candidate_recover_idx = _absolute_recovery_index(
                    post_abs=abs_source,
                    start_idx=peak_search_start,
                    direction=direction,
                    baseline=float(baseline_for_absolute_recovery),
                    n_consecutive=int(legacy_consecutive_days),
                    max_search=peak_search_end,
                )
                if candidate_recover_idx > peak_search_start:
                    peak_search_end = candidate_recover_idx
            peak_abs_idx = _find_peak_index_bounded(
                abs_source,
                start_idx=peak_search_start,
                end_idx=peak_search_end,
                direction=direction,
            )
            if peak_abs_idx >= 0:
                peak_idx = peak_abs_idx

        if peak_idx < 0:
            peak_idx = _find_peak_index(post, drought_response_from_onset, direction)
        if peak_idx < 0:
            return metrics

        metrics["t_peak"] = int(peak_idx)
        metrics["t_peak_drought_start"] = int(max(0, peak_idx - int(threshold_offset)))
        metrics["t_impact"] = int(peak_idx - drought_response_from_onset)
        if 0 <= int(peak_idx) < len(post) and np.isfinite(post[int(peak_idx)]):
            metrics["amp_max"] = float(post[int(peak_idx)])

        if peak_abs_idx < 0 and raw_post is not None and np.sum(np.isfinite(raw_post)) >= 3:
            peak_abs_idx = _find_peak_index(raw_post, drought_response_from_onset, direction)
        if peak_abs_idx < 0:
            peak_abs_idx = peak_idx
        if peak_abs_idx >= 0:
            metrics["t_peak_abs"] = int(peak_abs_idx)
            metrics["t_peak_abs_drought_start"] = int(max(0, peak_abs_idx - int(threshold_offset)))

        if bool(exclude_from_baseline_recovery) and not bool(legacy_ignore_overlap_exclusion):
            return metrics

        recover_idx = -1
        if (
            legacy_recovery_mode == "absolute_baseline"
            and abs_source is not None
            and baseline_for_absolute_recovery is not None
            and np.isfinite(baseline_for_absolute_recovery)
        ):
            recover_idx = _absolute_recovery_index(
                post_abs=abs_source,
                start_idx=peak_idx + 1,
                direction=direction,
                baseline=float(baseline_for_absolute_recovery),
                n_consecutive=int(legacy_consecutive_days),
                max_search=search_len,
            )
        else:
            recover_idx = _threshold_recovery_index(
                post=post,
                start_idx=peak_idx + 1,
                direction=direction,
                threshold=float(legacy_recovery_threshold),
                n_consecutive=int(legacy_consecutive_days),
            )
        if recover_idx < 0:
            return metrics

        recovery_days = compute_recovery_day_count(
            peak_idx=peak_idx,
            recover_idx=recover_idx,
            recovery_day_count_mode=recovery_day_count_mode,
            post_growing_season_mask=post_growing_season_mask,
        )
        if (
            max_valid_recovery_days is not None
            and np.isfinite(max_valid_recovery_days)
            and recovery_days > float(max_valid_recovery_days)
        ):
            metrics["recovery_exceeds_max_valid_days"] = 1
            return metrics

        metrics["t_recover_to_baseline"] = recovery_days
        if metrics["t_peak_abs"] >= 0 and recover_idx > metrics["t_peak_abs"]:
            metrics["t_recover_to_baseline_abs_peak"] = compute_recovery_day_count(
                peak_idx=int(metrics["t_peak_abs"]),
                recover_idx=recover_idx,
                recovery_day_count_mode=recovery_day_count_mode,
                post_growing_season_mask=post_growing_season_mask,
            )
        metrics["t_recover_onset_start"] = float(recover_idx)
        metrics["t_recover_drought_start"] = float(max(0, recover_idx - int(threshold_offset)))
        metrics["legacy_duration"] = float(recover_idx - drought_response_from_onset + 1)

        effective_baseline = baseline_for_recovery_rate
        if (
            legacy_recovery_mode == "absolute_baseline"
            and (effective_baseline is None or not np.isfinite(effective_baseline))
            and baseline_for_absolute_recovery is not None
            and np.isfinite(baseline_for_absolute_recovery)
        ):
            effective_baseline = baseline_for_absolute_recovery
        if effective_baseline is None or not np.isfinite(effective_baseline):
            effective_baseline = baseline
        rate_source = raw_post
        if legacy_peak_mode == "smoothed_absolute_min" or legacy_recovery_mode == "absolute_baseline":
            rate_source = abs_source
        if rate_source is None or effective_baseline is None or not np.isfinite(effective_baseline):
            return metrics
        if metrics["t_recover_to_baseline"] > 0 and np.isfinite(rate_source[peak_idx]):
            if direction == "positive":
                metrics["recovery_rate_to_baseline"] = float(
                    (float(rate_source[peak_idx]) - float(effective_baseline)) / metrics["t_recover_to_baseline"]
                )
            else:
                metrics["recovery_rate_to_baseline"] = float(
                    (float(effective_baseline) - float(rate_source[peak_idx])) / metrics["t_recover_to_baseline"]
                )
        return metrics

    if str(response_logic).lower() in {"zhao_spline_negative", "spline_negative"}:
        finite = np.isfinite(post)
        if direction == "positive":
            affected_mask = finite & (post >= 0)
        else:
            affected_mask = finite & (post <= 0)
        onset_response = _first_sustained_true_index(
            affected_mask,
            start_idx=0,
            n_consecutive=int(max(1, legacy_consecutive_days)),
            max_search=search_len,
        )
        if onset_response >= 0:
            metrics["t_response_onset_start"] = int(onset_response)
        if exclude_if_onset_already_affected and onset_response == 0:
            return metrics

        drought_response_from_onset = _first_sustained_true_index(
            affected_mask,
            start_idx=threshold_offset,
            n_consecutive=int(max(1, legacy_consecutive_days)),
            max_search=search_len,
        )
        if drought_response_from_onset < 0:
            return metrics

        n_search = len(post) if search_len is None else min(len(post), int(search_len))
        post_search = post[threshold_offset:n_search]
        affected_days = int(np.sum([_is_affected(v, direction) for v in post_search if np.isfinite(v)]))
        if affected_days < int(min_affected_days):
            return metrics

        metrics["lu_event_valid"] = 1
        metrics["response_detected"] = 1
        metrics["t_response_drought_start_from_onset"] = int(drought_response_from_onset)
        metrics["t_response_drought_start"] = int(max(0, drought_response_from_onset - int(threshold_offset)))

        peak_idx = _find_peak_index(post, drought_response_from_onset, direction)
        if peak_idx < 0:
            return metrics

        metrics["t_peak"] = int(peak_idx)
        metrics["t_peak_drought_start"] = int(max(0, peak_idx - int(threshold_offset)))
        metrics["t_impact"] = int(peak_idx - drought_response_from_onset)
        metrics["amp_max"] = float(post[peak_idx])

        if raw_post is not None and np.sum(np.isfinite(raw_post)) >= 3:
            peak_abs_idx = _find_peak_index(raw_post, drought_response_from_onset, direction)
            if peak_abs_idx >= 0:
                metrics["t_peak_abs"] = int(peak_abs_idx)
                metrics["t_peak_abs_drought_start"] = int(max(0, peak_abs_idx - int(threshold_offset)))

        if exclude_from_baseline_recovery and not bool(ignore_overlap_exclusion):
            return metrics

        recover_idx = _anomaly_recovery_index(
            post,
            start_idx=peak_idx + 1,
            n_consecutive=n_consecutive,
            direction=direction,
            threshold=float(recovery_anomaly_threshold),
        )
        if recover_idx < 0:
            return metrics

        recovery_days = compute_recovery_day_count(
            peak_idx=peak_idx,
            recover_idx=recover_idx,
            recovery_day_count_mode=recovery_day_count_mode,
            post_growing_season_mask=post_growing_season_mask,
        )
        if (
            max_valid_recovery_days is not None
            and np.isfinite(max_valid_recovery_days)
            and recovery_days > float(max_valid_recovery_days)
        ):
            metrics["recovery_exceeds_max_valid_days"] = 1
            return metrics

        metrics["t_recover_to_baseline"] = recovery_days
        if metrics["t_peak_abs"] >= 0 and recover_idx > metrics["t_peak_abs"]:
            metrics["t_recover_to_baseline_abs_peak"] = compute_recovery_day_count(
                peak_idx=int(metrics["t_peak_abs"]),
                recover_idx=recover_idx,
                recovery_day_count_mode=recovery_day_count_mode,
                post_growing_season_mask=post_growing_season_mask,
            )
        metrics["t_recover_onset_start"] = float(recover_idx)
        metrics["t_recover_drought_start"] = float(max(0, recover_idx - int(threshold_offset)))
        metrics["legacy_duration"] = float(recover_idx - drought_response_from_onset + 1)

        effective_baseline = baseline_for_recovery_rate
        if effective_baseline is None or not np.isfinite(effective_baseline):
            effective_baseline = baseline
        if raw_post is None or effective_baseline is None or not np.isfinite(effective_baseline):
            return metrics
        if metrics["t_recover_to_baseline"] > 0 and np.isfinite(raw_post[peak_idx]):
            if direction == "positive":
                metrics["recovery_rate_to_baseline"] = float(
                    (float(raw_post[peak_idx]) - float(effective_baseline)) / metrics["t_recover_to_baseline"]
                )
            else:
                metrics["recovery_rate_to_baseline"] = float(
                    (float(effective_baseline) - float(raw_post[peak_idx])) / metrics["t_recover_to_baseline"]
                )
        return metrics

    onset_response = _first_affected(post, 0, direction, max_search=search_len)
    if onset_response >= 0:
        metrics["t_response_onset_start"] = int(onset_response)
    if exclude_if_onset_already_affected and onset_response == 0:
        return metrics

    drought_response_from_onset = _first_affected(post, threshold_offset, direction, max_search=search_len)
    if drought_response_from_onset < 0:
        return metrics

    n_search = len(post) if search_len is None else min(len(post), int(search_len))
    post_search = post[threshold_offset:n_search]
    affected_days = int(np.sum([_is_affected(v, direction) for v in post_search if np.isfinite(v)]))
    if affected_days < int(min_affected_days):
        return metrics

    metrics["lu_event_valid"] = 1
    metrics["response_detected"] = 1
    metrics["t_response_drought_start_from_onset"] = int(drought_response_from_onset)
    metrics["t_response_drought_start"] = int(max(0, drought_response_from_onset - int(threshold_offset)))

    peak_idx = _find_peak_index(post, drought_response_from_onset, direction)
    if peak_idx < 0:
        return metrics

    metrics["t_peak"] = int(peak_idx)
    metrics["t_peak_drought_start"] = int(max(0, peak_idx - int(threshold_offset)))
    metrics["t_impact"] = int(peak_idx - drought_response_from_onset)
    metrics["amp_max"] = float(post[peak_idx])

    if raw_post is not None and np.sum(np.isfinite(raw_post)) >= 3:
        peak_abs_idx = _find_peak_index(raw_post, drought_response_from_onset, direction)
        if peak_abs_idx >= 0:
            metrics["t_peak_abs"] = int(peak_abs_idx)
            metrics["t_peak_abs_drought_start"] = int(max(0, peak_abs_idx - int(threshold_offset)))

    if exclude_from_baseline_recovery and not bool(ignore_overlap_exclusion):
        return metrics

    recover_idx = _anomaly_recovery_index(
        post,
        start_idx=peak_idx + 1,
        n_consecutive=n_consecutive,
        direction=direction,
        threshold=float(recovery_anomaly_threshold),
    )
    if recover_idx < 0:
        return metrics

    recovery_days = compute_recovery_day_count(
        peak_idx=peak_idx,
        recover_idx=recover_idx,
        recovery_day_count_mode=recovery_day_count_mode,
        post_growing_season_mask=post_growing_season_mask,
    )
    if (
        max_valid_recovery_days is not None
        and np.isfinite(max_valid_recovery_days)
        and recovery_days > float(max_valid_recovery_days)
    ):
        metrics["recovery_exceeds_max_valid_days"] = 1
        return metrics

    metrics["t_recover_to_baseline"] = recovery_days
    if metrics["t_peak_abs"] >= 0 and recover_idx > metrics["t_peak_abs"]:
        metrics["t_recover_to_baseline_abs_peak"] = compute_recovery_day_count(
            peak_idx=int(metrics["t_peak_abs"]),
            recover_idx=recover_idx,
            recovery_day_count_mode=recovery_day_count_mode,
            post_growing_season_mask=post_growing_season_mask,
        )
    metrics["t_recover_onset_start"] = float(recover_idx)
    metrics["t_recover_drought_start"] = float(max(0, recover_idx - int(threshold_offset)))
    metrics["legacy_duration"] = float(recover_idx - drought_response_from_onset + 1)

    effective_baseline = baseline_for_recovery_rate
    if effective_baseline is None or not np.isfinite(effective_baseline):
        effective_baseline = baseline
    if raw_post is None or effective_baseline is None or not np.isfinite(effective_baseline):
        return metrics
    if metrics["t_recover_to_baseline"] > 0 and np.isfinite(raw_post[peak_idx]):
        if direction == "positive":
            metrics["recovery_rate_to_baseline"] = float(
                (float(raw_post[peak_idx]) - float(effective_baseline)) / metrics["t_recover_to_baseline"]
            )
        else:
            metrics["recovery_rate_to_baseline"] = float(
                (float(effective_baseline) - float(raw_post[peak_idx])) / metrics["t_recover_to_baseline"]
            )
    return metrics


def compute_auxiliary_response_metrics_from_post(
    post,
    raw_post,
    threshold_offset,
    direction,
    response_logic,
    prefix="spline5",
    legacy_consecutive_days=5,
    search_len=None,
    min_affected_days=5,
    exclude_if_onset_already_affected=False,
):
    names = auxiliary_response_field_names(prefix)
    out = {
        names["response_detected"]: 0,
        names["t_response_onset_start"]: -1,
        names["t_response_drought_start"]: -1,
        names["t_response_drought_start_from_onset"]: -1,
        names["t_peak"]: -1,
        names["t_peak_abs"]: -1,
        names["amp_max"]: np.nan,
    }
    metrics = compute_event_metrics_from_post(
        post=post,
        threshold_offset=threshold_offset,
        n_consecutive=max(1, int(legacy_consecutive_days)),
        baseline=np.nan,
        baseline_tolerance=np.nan,
        exclude_from_baseline_recovery=True,
        raw_post=raw_post,
        search_len=search_len,
        direction=direction,
        min_affected_days=min_affected_days,
        recovery_anomaly_threshold=0.0,
        exclude_if_onset_already_affected=exclude_if_onset_already_affected,
        response_logic=response_logic,
        legacy_consecutive_days=legacy_consecutive_days,
        ignore_overlap_exclusion=False,
    )
    out[names["response_detected"]] = int(metrics["response_detected"])
    out[names["t_response_onset_start"]] = int(metrics["t_response_onset_start"])
    out[names["t_response_drought_start"]] = int(metrics["t_response_drought_start"])
    out[names["t_response_drought_start_from_onset"]] = int(metrics["t_response_drought_start_from_onset"])
    out[names["t_peak"]] = int(metrics["t_peak"])
    out[names["t_peak_abs"]] = int(metrics["t_peak_abs"])
    out[names["amp_max"]] = float(metrics["amp_max"])
    return out


def _empty_event_metrics():
    return {
        "lu_event_valid": 0,
        "response_detected": 0,
        "t_response_onset_start": -1,
        "t_response_drought_start": -1,
        "t_response_drought_start_from_onset": -1,
        "t_peak": -1,
        "t_peak_drought_start": -1,
        "t_peak_abs": -1,
        "t_peak_abs_drought_start": -1,
        "t_impact": -1,
        "amp_max": np.nan,
        "legacy_duration": np.nan,
        "t_recover_to_baseline": np.nan,
        "t_recover_to_baseline_abs_peak": np.nan,
        "t_recover_onset_start": np.nan,
        "t_recover_drought_start": np.nan,
        "recovery_rate_to_baseline": np.nan,
        "recovery_exceeds_max_valid_days": 0,
        "t_recover_post_drought": np.nan,
        "loss_total": np.nan,
        "loss_drought_phase": np.nan,
        "loss_post_drought_phase": np.nan,
        "peak_deficit": np.nan,
    }


def _auxiliary_metric_fields(aux_response_config):
    if not aux_response_config:
        return []
    names = auxiliary_response_field_names(aux_response_config["prefix"])
    return [
        (names["response_detected"], "i1"),
        (names["t_response_onset_start"], "i2"),
        (names["t_response_drought_start"], "i2"),
        (names["t_response_drought_start_from_onset"], "i2"),
        (names["t_peak"], "i2"),
        (names["t_peak_abs"], "i2"),
        (names["amp_max"], "f4"),
    ]


def build_result_dtype(event_mode, metric_name, direction=None, aux_response_config=None):
    names = metric_field_names(metric_name, direction)
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
        ("lu_event_valid", "i1"),
        ("overlap_with_prev", "i1"),
        ("overlap_with_next", "i1"),
        ("exclude_from_baseline_recovery", "i1"),
        ("response_detected", "i1"),
        ("t_response_onset_start", "i2"),
        ("t_response_drought_start", "i2"),
        ("t_response_drought_start_from_onset", "i2"),
        ("t_peak", "i2"),
        ("t_peak_drought_start", "i2"),
        ("t_peak_abs", "i2"),
        ("t_peak_abs_drought_start", "i2"),
        ("t_impact", "i2"),
        ("amp_max", "f4"),
        (names["baseline"], "f4"),
        (names["baseline_std"], "f4"),
        (names["extremum"], "f4"),
        (names["change"], "f4"),
        ("legacy_duration", "f4"),
        ("t_recover_to_baseline", "f4"),
        ("t_recover_to_baseline_abs_peak", "f4"),
        ("t_recover_onset_start", "f4"),
        ("t_recover_drought_start", "f4"),
        ("t_recover_post_drought", "f4"),
        ("recovery_rate_to_baseline", "f4"),
        (names["loss_total"], "f4"),
        (names["loss_drought_phase"], "f4"),
        (names["loss_post_drought_phase"], "f4"),
        (names["peak_deficit"], "f4"),
    ]
    return np.dtype(core_fields + metric_fields + _auxiliary_metric_fields(aux_response_config))


def _fill_array(values, fill_value):
    if hasattr(values, "filled"):
        return values.filled(fill_value)
    return np.array(values)


def _to_float32_with_nan(values):
    if np.ma.isMaskedArray(values):
        return np.ma.asarray(values, dtype=np.float32).filled(np.nan)
    return np.asarray(values, dtype=np.float32)


def _axis_mode(event_axis, data_axis, axis_name, atol=1e-6):
    event_axis = np.asarray(event_axis, dtype=np.float64)
    data_axis = np.asarray(data_axis, dtype=np.float64)
    if event_axis.ndim != 1 or data_axis.ndim != 1:
        raise ValueError(f"{axis_name} axis must be 1D.")
    if len(event_axis) != len(data_axis):
        raise ValueError(
            f"{axis_name} size mismatch: event={len(event_axis)} vs data={len(data_axis)}"
        )
    if np.allclose(event_axis, data_axis, atol=atol, rtol=0.0):
        return "same"
    if np.allclose(event_axis, data_axis[::-1], atol=atol, rtol=0.0):
        return "reversed"
    return "mismatch"


def _normalize_lon_360(values):
    return np.mod(np.asarray(values, dtype=np.float64), 360.0)


def _build_event_to_data_lon_index(event_lon, data_lon, atol=1e-6):
    event_lon = np.asarray(event_lon, dtype=np.float64)
    data_lon = np.asarray(data_lon, dtype=np.float64)
    if len(event_lon) != len(data_lon):
        raise ValueError(f"lon size mismatch: event={len(event_lon)} vs data={len(data_lon)}")

    if np.allclose(event_lon, data_lon, atol=atol, rtol=0.0):
        return np.arange(len(event_lon), dtype=np.int32), "same"
    if np.allclose(event_lon, data_lon[::-1], atol=atol, rtol=0.0):
        return np.arange(len(event_lon) - 1, -1, -1, dtype=np.int32), "reversed"

    event_lon_norm = _normalize_lon_360(event_lon)
    data_lon_norm = _normalize_lon_360(data_lon)
    if np.allclose(event_lon_norm, data_lon_norm, atol=atol, rtol=0.0):
        return np.arange(len(event_lon), dtype=np.int32), "same_norm360"
    if np.allclose(event_lon_norm, data_lon_norm[::-1], atol=atol, rtol=0.0):
        return np.arange(len(event_lon) - 1, -1, -1, dtype=np.int32), "reversed_norm360"

    sort_idx = np.argsort(data_lon_norm)
    sorted_lon = data_lon_norm[sort_idx]
    pos = np.searchsorted(sorted_lon, event_lon_norm)
    pos = np.clip(pos, 0, len(sorted_lon) - 1)
    candidate = sort_idx[pos]
    diff = np.abs(data_lon_norm[candidate] - event_lon_norm)
    unresolved = diff > atol
    if np.any(unresolved):
        return None, "mismatch"
    return candidate.astype(np.int32), "mapped_norm360"


def _data_lat_slice_for_event_chunk(lat_start, lat_end):
    if _LAT_INDEX_MODE == "same":
        return lat_start, lat_end, False
    data_start = _DATA_NLAT - lat_end
    data_end = _DATA_NLAT - lat_start
    return data_start, data_end, True


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
    if "drought_end_year" in _EVENT_DS.variables and "drought_end_doy" in _EVENT_DS.variables:
        arrays["drought_end_year"] = _fill_array(
            _EVENT_DS.variables["drought_end_year"][:max_ec, lat_start:lat_end, :], -1
        )
        arrays["drought_end_doy"] = _fill_array(
            _EVENT_DS.variables["drought_end_doy"][:max_ec, lat_start:lat_end, :], -1
        )
    if _CONFIG["event_mode"] == "nonflash":
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
    if "drought_end_year" in event_arrays and "drought_end_doy" in event_arrays:
        drought_end_year = int(event_arrays["drought_end_year"][event_id, rel_lat, lon_idx])
        drought_end_doy = int(event_arrays["drought_end_doy"][event_id, rel_lat, lon_idx])
        if not _valid_year_doy(drought_end_year, drought_end_doy):
            drought_end_idx = -1
        else:
            drought_end_idx = _YEAR_OFFSETS[drought_end_year] + drought_end_doy - 1
        result.update(
            {
                "drought_end_year": drought_end_year,
                "drought_end_doy": drought_end_doy,
                "drought_end_idx": drought_end_idx,
            }
        )
    if _CONFIG["event_mode"] == "nonflash":
        duration = int(event_arrays["duration"][event_id, rel_lat, lon_idx])
        drought_end_idx = int(result.get("drought_end_idx", -1))
        if drought_end_idx < 0:
            return None
        if _CONFIG.get("window_after_from_drought_start") is not None:
            drought_offset = max(0, drought_start_idx - onset_idx)
            actual_window_after = min(
                drought_offset + int(_CONFIG["window_after_from_drought_start"]),
                _CONFIG["max_window_after"],
            )
        else:
            actual_window_after = min(
                drought_end_idx + _CONFIG["recovery_window"] - onset_idx,
                _CONFIG["max_window_after"],
            )
        result.update(
            {
                "drought_duration": duration if duration > 0 else drought_end_idx - drought_start_idx + 1,
                "actual_window_after": int(actual_window_after),
            }
        )
    else:
        if _CONFIG.get("window_after_from_drought_start") is not None:
            drought_offset = max(0, drought_start_idx - onset_idx)
            result["actual_window_after"] = int(
                min(
                    drought_offset + int(_CONFIG["window_after_from_drought_start"]),
                    int(_CONFIG["max_window_after"]),
                )
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


def build_pixel_series_cache(z_series, raw_series, smooth_window):
    return {
        "smoothed_z_series": smooth_causal(z_series, smooth_window),
        "smoothed_raw_series": smooth_causal(raw_series, smooth_window),
    }


def build_pixel_event_contexts(event_arrays, rel_lat, lon_idx, event_count, series_len, window_before):
    del window_before
    event_infos = []
    for event_id in range(int(event_count)):
        event_infos.append(_event_indices(event_arrays, event_id, rel_lat, lon_idx))

    contexts = []
    for event_id, event_info in enumerate(event_infos):
        prev_event_info = event_infos[event_id - 1] if event_id > 0 else None
        next_event_info = event_infos[event_id + 1] if event_id + 1 < len(event_infos) else None
        overlap_flags = (
            compute_event_overlap_flags(
                event_info=event_info,
                prev_event_info=prev_event_info,
                next_event_info=next_event_info,
                window_before=_CONFIG["window_before"],
            )
            if event_info is not None
            else {
                "overlap_with_prev": 0,
                "overlap_with_next": 0,
                "exclude_from_baseline_recovery": 0,
            }
        )
        window = _build_window(event_info, series_len) if event_info is not None else None
        contexts.append(
            {
                "event_id": int(event_id),
                "event_info": event_info,
                "prev_event_info": prev_event_info,
                "next_event_info": next_event_info,
                "overlap_flags": overlap_flags,
                "window": window,
            }
        )
    return contexts


def _metric_tuple(lat_val, lon_val, event_id, event_info, overlap_flags, metrics, abs_metrics, aux_metrics=None):
    names = metric_field_names(_CONFIG["metric_name"], _CONFIG["direction"])
    values = [
        lat_val,
        lon_val,
        event_id,
        event_info["onset_year"],
        event_info["onset_doy"],
        event_info["drought_start_year"],
        event_info["drought_start_doy"],
    ]
    if _CONFIG["event_mode"] == "nonflash":
        values.extend(
            [
                event_info["drought_end_year"],
                event_info["drought_end_doy"],
                int(min(event_info["drought_duration"], 32767)),
                int(min(event_info["actual_window_after"], 32767)),
            ]
        )
    else:
        values.append(int(min(event_info["actual_window_after"], 32767)))
    values.extend(
        [
            int(metrics["lu_event_valid"]),
            int(overlap_flags["overlap_with_prev"]),
            int(overlap_flags["overlap_with_next"]),
            int(overlap_flags["exclude_from_baseline_recovery"]),
            int(metrics["response_detected"]),
            int(metrics["t_response_onset_start"]),
            int(metrics["t_response_drought_start"]),
            int(metrics["t_response_drought_start_from_onset"]),
            int(metrics["t_peak"]),
            int(metrics["t_peak_drought_start"]),
            int(metrics["t_peak_abs"]),
            int(metrics["t_peak_abs_drought_start"]),
            int(metrics["t_impact"]),
            float(metrics["amp_max"]),
            float(abs_metrics[names["baseline"]]),
            float(abs_metrics[names["baseline_std"]]),
            float(abs_metrics[names["extremum"]]),
            float(abs_metrics[names["change"]]),
            float(metrics["legacy_duration"]),
            float(metrics["t_recover_to_baseline"]),
            float(metrics["t_recover_to_baseline_abs_peak"]),
            float(metrics["t_recover_onset_start"]),
            float(metrics["t_recover_drought_start"]),
            float(metrics["t_recover_post_drought"]),
            float(metrics["recovery_rate_to_baseline"]),
            float(metrics["loss_total"]),
            float(metrics["loss_drought_phase"]),
            float(metrics["loss_post_drought_phase"]),
            float(metrics["peak_deficit"]),
        ]
    )
    if _CONFIG.get("aux_response_config"):
        aux_names = auxiliary_response_field_names(_CONFIG["aux_response_config"]["prefix"])
        aux_metrics = aux_metrics or {
            aux_names["response_detected"]: 0,
            aux_names["t_response_onset_start"]: -1,
            aux_names["t_response_drought_start"]: -1,
            aux_names["t_response_drought_start_from_onset"]: -1,
            aux_names["t_peak"]: -1,
            aux_names["t_peak_abs"]: -1,
            aux_names["amp_max"]: np.nan,
        }
        values.extend(
            [
                int(aux_metrics[aux_names["response_detected"]]),
                int(aux_metrics[aux_names["t_response_onset_start"]]),
                int(aux_metrics[aux_names["t_response_drought_start"]]),
                int(aux_metrics[aux_names["t_response_drought_start_from_onset"]]),
                int(aux_metrics[aux_names["t_peak"]]),
                int(aux_metrics[aux_names["t_peak_abs"]]),
                float(aux_metrics[aux_names["amp_max"]]),
            ]
        )
    return tuple(values)


def worker_init(config):
    global _CONFIG, _DATA_DS, _EVENT_DS, _LON_ARR, _YEAR_OFFSETS, _DOY_IDX
    global _EVENT_LAT_ARR, _EVENT_TO_DATA_LON_IDX, _LAT_INDEX_MODE, _DATA_NLAT
    global _TEMP_DS, _TEMP_EVENT_TO_DATA_LON_IDX, _TEMP_LAT_INDEX_MODE, _TEMP_NLAT, _TEMP_TIME_SLICE, _YEAR_SLICES, _DATA_TIME_SLICE
    _CONFIG = config
    _DATA_DS = nc.Dataset(config["data_file"], "r")
    _EVENT_DS = nc.Dataset(config["event_file"], "r")
    event_lat = np.asarray(_EVENT_DS.variables["lat"][:], dtype=np.float64)
    data_lat = np.asarray(_DATA_DS.variables["lat"][:], dtype=np.float64)
    _EVENT_LAT_ARR = event_lat.astype(np.float32)
    _DATA_NLAT = int(len(data_lat))
    lat_mode = _axis_mode(event_lat, data_lat, "lat")
    if lat_mode == "mismatch":
        raise ValueError(
            "Lat grids are incompatible between event and data files: "
            f"event(lat0,latN)=({event_lat[0]:.6f},{event_lat[-1]:.6f}) vs "
            f"data(lat0,latN)=({data_lat[0]:.6f},{data_lat[-1]:.6f})"
        )
    _LAT_INDEX_MODE = lat_mode

    event_lon = np.asarray(_EVENT_DS.variables["lon"][:], dtype=np.float64)
    data_lon = np.asarray(_DATA_DS.variables["lon"][:], dtype=np.float64)
    lon_map, lon_mode = _build_event_to_data_lon_index(event_lon, data_lon)
    if lon_map is None or lon_mode == "mismatch":
        raise ValueError(
            "Lon grids are incompatible between event and data files and could not be mapped."
        )
    _EVENT_TO_DATA_LON_IDX = lon_map
    _LON_ARR = event_lon.astype(np.float32)
    _YEAR_OFFSETS = build_year_offsets(config["start_year"], config["end_year"])
    _YEAR_SLICES = build_year_slices(config["start_year"], config["end_year"])
    _DOY_IDX = build_doy_index(config["start_year"], config["end_year"])
    _DATA_TIME_SLICE = _time_slice_for_year_range(
        _DATA_DS.variables["time"],
        config["start_year"],
        config["end_year"],
    )

    _TEMP_DS = None
    _TEMP_EVENT_TO_DATA_LON_IDX = None
    _TEMP_LAT_INDEX_MODE = "same"
    _TEMP_NLAT = 0
    _TEMP_TIME_SLICE = None
    if config.get("growing_season_enabled", False):
        _TEMP_DS = nc.Dataset(config["growing_season_temp_file"], "r")
        temp_lat = np.asarray(_TEMP_DS.variables["lat"][:], dtype=np.float64)
        temp_lon = np.asarray(_TEMP_DS.variables["lon"][:], dtype=np.float64)
        _TEMP_NLAT = int(len(temp_lat))
        temp_lat_mode = _axis_mode(event_lat, temp_lat, "temp_lat")
        if temp_lat_mode == "mismatch":
            raise ValueError("Lat grids are incompatible between event and temperature files.")
        _TEMP_LAT_INDEX_MODE = temp_lat_mode
        temp_lon_map, temp_lon_mode = _build_event_to_data_lon_index(event_lon, temp_lon)
        if temp_lon_map is None or temp_lon_mode == "mismatch":
            raise ValueError("Lon grids are incompatible between event and temperature files.")
        _TEMP_EVENT_TO_DATA_LON_IDX = temp_lon_map
        _TEMP_TIME_SLICE = _time_slice_for_year_range(
            _TEMP_DS.variables["time"],
            config["start_year"],
            config["end_year"],
        )


def process_chunk(chunk_info):
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    drop_stats = _init_drop_reason_stats()
    dtype = build_result_dtype(
        _CONFIG["event_mode"],
        _CONFIG["metric_name"],
        _CONFIG["direction"],
        _CONFIG.get("aux_response_config"),
    )
    try:
        lat_arr = _EVENT_LAT_ARR[lat_start:lat_end]
        data_lat_start, data_lat_end, flip_lat = _data_lat_slice_for_event_chunk(lat_start, lat_end)
        dt0, dt1 = _DATA_TIME_SLICE
        data_chunk = _DATA_DS.variables[_CONFIG["data_var"]][dt0:dt1, data_lat_start:data_lat_end, :]
        data_chunk = _to_float32_with_nan(data_chunk)
        data_chunk = apply_data_scale(data_chunk, _CONFIG.get("data_scale", 1.0))
        if flip_lat:
            data_chunk = data_chunk[:, ::-1, :]
        if _CONFIG.get("growing_season_enabled", False):
            if _TEMP_LAT_INDEX_MODE == "same":
                temp_lat_start, temp_lat_end, temp_flip_lat = lat_start, lat_end, False
            else:
                temp_lat_start = _TEMP_NLAT - lat_end
                temp_lat_end = _TEMP_NLAT - lat_start
                temp_flip_lat = True
            tt0, tt1 = _TEMP_TIME_SLICE
            temp_chunk = _TEMP_DS.variables[_CONFIG["growing_season_temp_var"]][tt0:tt1, temp_lat_start:temp_lat_end, :]
            temp_chunk = _to_float32_with_nan(temp_chunk)
            if temp_flip_lat:
                temp_chunk = temp_chunk[:, ::-1, :]
        else:
            temp_chunk = None
        ec_chunk = _fill_array(_EVENT_DS.variables["event_count"][lat_start:lat_end, :], 0)
        drop_stats["events_chunk_total"] = int(np.sum(ec_chunk))
        max_ec = int(np.max(ec_chunk))
        if max_ec == 0:
            return chunk_id, np.array([], dtype=dtype), drop_stats

        event_arrays = _get_event_arrays(lat_start, lat_end, max_ec)
        for rel_lat in range(lat_end - lat_start):
            lat_val = float(lat_arr[rel_lat])
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            if len(lon_with_events) == 0:
                continue
            data_lon_with_events = _EVENT_TO_DATA_LON_IDX[lon_with_events]
            row = data_chunk[:, rel_lat, data_lon_with_events]
            valid_count = np.sum(np.isfinite(row), axis=0)
            good_mask = valid_count >= _CONFIG["min_valid_values"]
            bad_mask = ~good_mask
            if np.any(bad_mask):
                drop_stats["events_drop_min_valid_values"] += int(
                    np.sum(ec_chunk[rel_lat, lon_with_events[bad_mask]])
                )
            if not np.any(good_mask):
                continue
            good_lon_indices = lon_with_events[good_mask]
            drop_stats["events_pass_min_valid_values"] += int(
                np.sum(ec_chunk[rel_lat, good_lon_indices])
            )
            good_data = row[:, good_mask]
            if temp_chunk is not None:
                temp_data_lon_with_events = _TEMP_EVENT_TO_DATA_LON_IDX[lon_with_events]
                temp_row = temp_chunk[:, rel_lat, temp_data_lon_with_events]
                good_temp = temp_row[:, good_mask]
            else:
                good_temp = None
            anomaly_source = str(_CONFIG.get("anomaly_source", "climatology_zscore")).lower()
            if anomaly_source == "spline_residual":
                z_matrix, clim_matrix = calc_spline_baseline_and_anomaly_matrix(
                    good_data,
                    agg_days=_CONFIG.get("spline_agg_days", 8),
                    smooth_factor_multiplier=_CONFIG.get("spline_smooth_factor_multiplier", 0.5),
                    min_valid_points=_CONFIG.get("spline_min_valid_points", 120),
                )
            else:
                z_matrix, clim_matrix, _ = calc_climatology_components(good_data, _DOY_IDX)
            aux_response_config = _CONFIG.get("aux_response_config")

            for idx, lon_idx in enumerate(good_lon_indices):
                ec = int(ec_chunk[rel_lat, lon_idx])
                z_series = z_matrix[:, idx]
                raw_series = good_data[:, idx]
                clim_series = clim_matrix[:, idx]
                if good_temp is not None:
                    temp_series = good_temp[:, idx]
                    growing_season_mask = build_growing_season_mask(
                        temp_series,
                        _YEAR_SLICES,
                        threshold_k=_CONFIG.get("growing_season_temp_threshold_k", 278.15),
                        min_consecutive_days=_CONFIG.get("growing_season_min_consecutive_days", 5),
                    )
                else:
                    growing_season_mask = None
                lon_val = float(_LON_ARR[lon_idx])
                series_cache = build_pixel_series_cache(
                    z_series=z_series,
                    raw_series=raw_series,
                    smooth_window=_CONFIG["smooth_window"],
                )
                smoothed_z_series = series_cache["smoothed_z_series"]
                smoothed_raw_series = series_cache["smoothed_raw_series"]
                event_contexts = build_pixel_event_contexts(
                    event_arrays=event_arrays,
                    rel_lat=rel_lat,
                    lon_idx=lon_idx,
                    event_count=ec,
                    series_len=len(z_series),
                    window_before=_CONFIG["window_before"],
                )
                aux_z_series = None
                for context in event_contexts:
                    event_id = context["event_id"]
                    drop_stats["events_iterated"] += 1
                    event_info = context["event_info"]
                    if event_info is None:
                        drop_stats["events_drop_invalid_event_time"] += 1
                        continue
                    if growing_season_mask is not None:
                        if not is_growing_season_event(
                            growing_season_mask,
                            drought_start_idx=event_info.get("drought_start_idx"),
                            drought_end_idx=event_info.get("drought_end_idx"),
                            min_fraction=_CONFIG.get("growing_season_min_fraction", 0.5),
                        ):
                            drop_stats["events_drop_not_growing_season"] += 1
                            continue
                    overlap_flags = context["overlap_flags"]
                    window = context["window"]
                    if window is None:
                        drop_stats["events_drop_window_out_of_range"] += 1
                        continue
                    ws, we, threshold_offset = window
                    z_segment = z_series[ws : we + 1]
                    raw_segment = raw_series[ws : we + 1]
                    clim_segment = clim_series[ws : we + 1]
                    if np.sum(np.isfinite(z_segment)) < 3:
                        drop_stats["events_drop_insufficient_z_segment"] += 1
                        continue
                    smoothed = smoothed_z_series[ws : we + 1]
                    smoothed_raw_segment = smoothed_raw_series[ws : we + 1]
                    post = smoothed[_CONFIG["window_before"] :]
                    raw_post = raw_segment[_CONFIG["window_before"] :]
                    raw_post_smoothed = smoothed_raw_segment[_CONFIG["window_before"] :]
                    post_growing_season_mask = None
                    if growing_season_mask is not None:
                        post_growing_season_mask = growing_season_mask[int(event_info["onset_idx"]) : we + 1]
                        if len(post_growing_season_mask) != len(post):
                            post_growing_season_mask = None
                    if np.sum(np.isfinite(post)) < 3:
                        drop_stats["events_drop_insufficient_post"] += 1
                        continue
                    baseline_scale = float(_CONFIG.get("absolute_baseline_scale", 1.0))
                    if not np.isfinite(baseline_scale):
                        baseline_scale = 1.0
                    min_abs = _CONFIG.get("min_abs_at_drought_start_for_response")
                    if min_abs is not None and np.isfinite(min_abs):
                        drought_offset = int(max(0, threshold_offset))
                        if drought_offset < len(raw_post):
                            drought_val = raw_post[drought_offset]
                            if np.isfinite(drought_val) and np.abs(float(drought_val)) < float(min_abs):
                                drop_stats["events_drop_low_abs_at_drought_start"] += 1
                                metrics = _empty_event_metrics()
                                abs_metrics = compute_compact_absolute_metrics(
                                    segment=raw_segment,
                                    window_before=_CONFIG["window_before"],
                                    t_peak=metrics["t_peak"],
                                    metric_name=_CONFIG["metric_name"],
                                    direction=_CONFIG["direction"],
                                    clim_segment=clim_segment,
                                    absolute_baseline_mode=_CONFIG.get("absolute_baseline_mode", "pre_window_raw"),
                                    absolute_baseline_days=_CONFIG.get("absolute_baseline_days", 10),
                                    absolute_baseline_scale=baseline_scale,
                                )
                                results.append(
                                    _metric_tuple(
                                        lat_val,
                                        lon_val,
                                        event_id,
                                        event_info,
                                        overlap_flags,
                                        metrics,
                                        abs_metrics,
                                    )
                                )
                                drop_stats["events_no_response_detected"] += 1
                                drop_stats["events_not_lu_valid"] += 1
                                if int(overlap_flags["exclude_from_baseline_recovery"]) == 1:
                                    drop_stats["events_excluded_from_baseline_recovery"] += 1
                                drop_stats["events_written"] += 1
                                continue
                    pre_raw = raw_segment[: _CONFIG["window_before"]]
                    if np.sum(np.isfinite(pre_raw)) < 5:
                        drop_stats["events_drop_insufficient_pre_raw"] += 1
                        continue
                    baseline = float(np.nanmean(pre_raw))
                    baseline_std = float(np.nanstd(pre_raw))
                    tolerance_floor = max(
                        abs(baseline) * float(_CONFIG["baseline_tolerance_floor_fraction"]),
                        float(_CONFIG["baseline_tolerance_floor_fraction"]),
                    )
                    baseline_tolerance = max(
                        baseline_std * float(_CONFIG["baseline_tolerance_multiplier"]),
                        tolerance_floor,
                    )
                    baseline_days = max(1, int(_CONFIG.get("absolute_baseline_days", 10)))
                    baseline_slice_start = max(0, int(_CONFIG["window_before"]) - baseline_days)
                    baseline_for_rate = baseline
                    baseline_for_abs_recovery = baseline
                    rate_mode = str(_CONFIG.get("recovery_rate_baseline_mode", "pre_window_raw")).lower()
                    if rate_mode == "climatology_pre_days":
                        pre_clim = clim_segment[baseline_slice_start : _CONFIG["window_before"]]
                        if np.sum(np.isfinite(pre_clim)) >= 3:
                            baseline_for_rate = float(np.nanmean(pre_clim))
                    elif rate_mode == "pre_days_raw":
                        pre_days = smoothed_raw_segment[baseline_slice_start : _CONFIG["window_before"]]
                        if np.sum(np.isfinite(pre_days)) >= 3:
                            baseline_for_rate = float(np.nanmean(pre_days))
                    abs_mode = str(_CONFIG.get("absolute_baseline_mode", "pre_window_raw")).lower()
                    if abs_mode == "climatology_pre_days":
                        pre_clim = clim_segment[baseline_slice_start : _CONFIG["window_before"]]
                        if np.sum(np.isfinite(pre_clim)) >= 3:
                            baseline_for_abs_recovery = float(np.nanmean(pre_clim))
                    elif abs_mode == "pre_days_raw":
                        pre_days_abs = smoothed_raw_segment[baseline_slice_start : _CONFIG["window_before"]]
                        if np.sum(np.isfinite(pre_days_abs)) >= 3:
                            baseline_for_abs_recovery = float(np.nanmean(pre_days_abs))
                    baseline_for_rate = float(baseline_for_rate) * baseline_scale
                    baseline_for_abs_recovery = float(baseline_for_abs_recovery) * baseline_scale
                    search_len = (
                        _CONFIG["response_search_window"]
                        if _CONFIG["event_mode"] == "flash"
                        else event_info["actual_window_after"]
                    )
                    metrics = compute_event_metrics_from_post(
                        post=post,
                        threshold_offset=threshold_offset,
                        n_consecutive=_CONFIG["anomaly_recovery_consecutive_days"],
                        baseline=baseline,
                        baseline_tolerance=baseline_tolerance,
                        exclude_from_baseline_recovery=bool(overlap_flags["exclude_from_baseline_recovery"]),
                        raw_post=raw_post,
                        search_len=search_len,
                        direction=_CONFIG["direction"],
                        min_affected_days=_CONFIG["min_affected_days_for_event"],
                        recovery_anomaly_threshold=_CONFIG["recovery_anomaly_threshold"],
                        exclude_if_onset_already_affected=_CONFIG["exclude_if_onset_already_affected"],
                        response_logic=_CONFIG.get("response_logic", "lu_anomaly"),
                        legacy_response_threshold=_CONFIG.get("legacy_response_threshold", -0.5),
                        legacy_recovery_threshold=_CONFIG.get("legacy_recovery_threshold", -0.25),
                        legacy_consecutive_days=_CONFIG.get("legacy_consecutive_days", 3),
                        legacy_ignore_overlap_exclusion=_CONFIG.get("legacy_ignore_overlap_exclusion", False),
                        baseline_for_recovery_rate=baseline_for_rate,
                        raw_post_smoothed=raw_post_smoothed,
                        baseline_for_absolute_recovery=baseline_for_abs_recovery,
                        legacy_peak_mode=_CONFIG.get("legacy_peak_mode", "relative_anomaly"),
                        legacy_recovery_mode=_CONFIG.get("legacy_recovery_mode", "threshold_anomaly"),
                        require_post_drought_decline=_CONFIG.get("require_post_drought_decline", False),
                        post_drought_decline_search_days=_CONFIG.get("post_drought_decline_search_days", 30),
                        post_drought_decline_consecutive_days=_CONFIG.get(
                            "post_drought_decline_consecutive_days", 5
                        ),
                        max_valid_recovery_days=_CONFIG.get("max_valid_recovery_days"),
                        ignore_overlap_exclusion=_CONFIG.get("ignore_overlap_exclusion", False),
                        recovery_day_count_mode=_CONFIG.get("recovery_day_count_mode", "elapsed_days"),
                        post_growing_season_mask=post_growing_season_mask,
                    )
                    if np.isfinite(metrics.get("t_recover_onset_start", np.nan)):
                        drought_end_idx = event_info.get("drought_end_idx", -1)
                        if drought_end_idx is not None and int(drought_end_idx) >= int(event_info["onset_idx"]):
                            drought_end_from_onset = int(drought_end_idx - event_info["onset_idx"])
                            metrics["t_recover_post_drought"] = compute_post_drought_recovery_days(
                                metrics["t_recover_onset_start"],
                                drought_end_from_onset,
                                recovery_day_count_mode=_CONFIG.get("recovery_day_count_mode", "elapsed_days"),
                                post_growing_season_mask=post_growing_season_mask,
                            )
                    if (
                        anomaly_source == "spline_residual"
                        and int(metrics["response_detected"]) == 1
                        and np.isfinite(metrics["t_response_onset_start"])
                        and np.isfinite(metrics["t_recover_onset_start"])
                    ):
                        drought_end_idx = event_info.get("drought_end_idx", -1)
                        drought_end_from_onset = (
                            max(0, int(drought_end_idx - event_info["onset_idx"]))
                            if int(drought_end_idx) >= int(event_info["onset_idx"])
                            else None
                        )
                        loss_metrics = compute_cumulative_loss_metrics(
                            raw_post=raw_post,
                            baseline_post=clim_segment[_CONFIG["window_before"] :],
                            response_idx=metrics["t_response_onset_start"],
                            recover_idx=metrics["t_recover_onset_start"],
                            drought_end_idx=drought_end_from_onset,
                            direction=_CONFIG["direction"],
                        )
                        metrics.update(loss_metrics)
                    if int(metrics["response_detected"]) == 1:
                        drop_stats["events_response_detected"] += 1
                    else:
                        drop_stats["events_no_response_detected"] += 1
                    if int(metrics["lu_event_valid"]) == 1:
                        drop_stats["events_lu_valid"] += 1
                    else:
                        drop_stats["events_not_lu_valid"] += 1
                    if int(overlap_flags["exclude_from_baseline_recovery"]) == 1:
                        drop_stats["events_excluded_from_baseline_recovery"] += 1
                    if int(metrics.get("recovery_exceeds_max_valid_days", 0)) == 1:
                        drop_stats["events_drop_recovery_over_max_valid_days"] += 1
                        drop_stats["events_response_valid_but_no_recovery"] += 1
                    elif np.isfinite(metrics["t_recover_to_baseline"]):
                        drop_stats["events_recovery_detected"] += 1
                    elif int(metrics["response_detected"]) == 1 and int(metrics["lu_event_valid"]) == 1:
                        drop_stats["events_response_valid_but_no_recovery"] += 1
                    abs_metrics = compute_compact_absolute_metrics(
                        segment=raw_segment,
                        window_before=_CONFIG["window_before"],
                        t_peak=metrics["t_peak"],
                        metric_name=_CONFIG["metric_name"],
                        direction=_CONFIG["direction"],
                        clim_segment=clim_segment,
                        absolute_baseline_mode=_CONFIG.get("absolute_baseline_mode", "pre_window_raw"),
                        absolute_baseline_days=_CONFIG.get("absolute_baseline_days", 10),
                        absolute_baseline_scale=baseline_scale,
                    )
                    aux_metrics = None
                    if aux_response_config:
                        if aux_z_series is None:
                            aux_z_series = calc_auxiliary_anomaly_series_1d(
                                raw_series,
                                aux_response_config,
                                _DOY_IDX,
                            )
                        aux_z_segment = aux_z_series[ws : we + 1]
                    else:
                        aux_z_segment = None
                    if aux_response_config and aux_z_segment is not None and np.sum(np.isfinite(aux_z_segment)) >= 3:
                        aux_smoothed = smooth_causal(
                            aux_z_segment,
                            aux_response_config.get("smooth_window", _CONFIG["smooth_window"]),
                        )
                        aux_post = aux_smoothed[_CONFIG["window_before"] :]
                        if np.sum(np.isfinite(aux_post)) >= 3:
                            aux_metrics = compute_auxiliary_response_metrics_from_post(
                                post=aux_post,
                                raw_post=raw_post,
                                threshold_offset=threshold_offset,
                                direction=aux_response_config.get("direction", _CONFIG["direction"]),
                                response_logic=aux_response_config.get(
                                    "response_logic", "zhao_spline_negative"
                                ),
                                prefix=aux_response_config.get("prefix", "spline5"),
                                legacy_consecutive_days=aux_response_config.get("legacy_consecutive_days", 5),
                                search_len=(
                                    aux_response_config.get("response_search_window", search_len)
                                    if _CONFIG["event_mode"] == "flash"
                                    else event_info["actual_window_after"]
                                ),
                                min_affected_days=aux_response_config.get("min_affected_days_for_event", 5),
                                exclude_if_onset_already_affected=aux_response_config.get(
                                    "exclude_if_onset_already_affected", False
                                ),
                            )
                    results.append(
                        _metric_tuple(
                            lat_val,
                            lon_val,
                            event_id,
                            event_info,
                            overlap_flags,
                            metrics,
                            abs_metrics,
                            aux_metrics=aux_metrics,
                        )
                    )
                    drop_stats["events_written"] += 1
        if results:
            return chunk_id, np.array(results, dtype=dtype), drop_stats
        return chunk_id, np.array([], dtype=dtype), drop_stats
    except Exception as exc:
        print(f"Chunk {chunk_id} error: {exc}")
        drop_stats["chunk_errors"] += 1
        return chunk_id, np.array([], dtype=dtype), drop_stats


def save_results_to_netcdf(results, config, output_file):
    with nc.Dataset(output_file, "w", format="NETCDF4") as ds:
        ds.createDimension("event", len(results))
        for field in results.dtype.names:
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

    total_drop_stats = _init_drop_reason_stats()
    total_drop_stats["events_from_event_file_total"] = int(total_events)

    with Pool(config["n_workers"], initializer=worker_init, initargs=(config,)) as pool:
        for item in tqdm(pool.imap_unordered(process_chunk, chunks), total=len(chunks), desc="Processing"):
            if len(item) == 3:
                chunk_id, result, chunk_drop_stats = item
                _merge_drop_reason_stats(total_drop_stats, chunk_drop_stats)
            else:
                chunk_id, result = item
            if len(result) > 0:
                np.save(os.path.join(config["temp_dir"], f"chunk_{chunk_id:04d}.npy"), result)
            del result
            gc.collect()

    all_results = []
    for name in sorted(os.listdir(config["temp_dir"])):
        if name.endswith(".npy"):
            all_results.append(np.load(os.path.join(config["temp_dir"], name)))
    dtype = build_result_dtype(
        config["event_mode"],
        config["metric_name"],
        config["direction"],
        config.get("aux_response_config"),
    )
    merged = np.concatenate(all_results) if all_results else np.array([], dtype=dtype)
    save_results_to_netcdf(merged, config, config["relative_output_file"])

    total_drop_stats["events_output_written_total"] = int(len(merged))
    if len(merged) > 0 and "response_detected" in merged.dtype.names:
        total_drop_stats["events_output_response_detected"] = int(np.sum(merged["response_detected"] == 1))
    if len(merged) > 0 and "lu_event_valid" in merged.dtype.names:
        total_drop_stats["events_output_lu_valid"] = int(np.sum(merged["lu_event_valid"] == 1))
    if len(merged) > 0 and "exclude_from_baseline_recovery" in merged.dtype.names:
        total_drop_stats["events_output_excluded_from_baseline_recovery"] = int(
            np.sum(merged["exclude_from_baseline_recovery"] == 1)
        )
    if len(merged) > 0 and "t_recover_to_baseline" in merged.dtype.names:
        total_drop_stats["events_output_recovery_detected"] = int(np.sum(np.isfinite(merged["t_recover_to_baseline"])))

    diagnostic_output_file = config.get("diagnostic_output_file")
    if not diagnostic_output_file:
        base = os.path.splitext(config["relative_output_file"])[0]
        diagnostic_output_file = f"{base}_drop_reason_stats.json"
    with open(diagnostic_output_file, "w", encoding="utf-8") as fp:
        json.dump(total_drop_stats, fp, ensure_ascii=False, indent=2, sort_keys=True)

    shutil.rmtree(config["temp_dir"])
    print(f"Saved {len(merged):,} compact events to {config['relative_output_file']}")
    print(f"Saved drop-reason stats to {diagnostic_output_file}")
    return config["relative_output_file"]
