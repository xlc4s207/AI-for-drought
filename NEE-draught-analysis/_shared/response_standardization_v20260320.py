#!/usr/bin/env python3
"""Shared compact GPP response helpers for v20260320 scripts."""

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
        if len(vals) >= 1:
            result[i] = np.float32(np.mean(vals))
    return result


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


def _first_nonpositive(x, start_idx, max_search=None):
    n = len(x)
    if max_search is not None:
        n = min(n, int(max_search))
    start_idx = max(0, int(start_idx))
    for i in range(start_idx, n):
        if np.isfinite(x[i]) and x[i] <= 0:
            return i
    return -1


def _baseline_recovery_index(raw_post, start_idx, threshold_value, n_consecutive):
    if raw_post is None:
        return -1
    start_idx = max(0, int(start_idx))
    n_consecutive = max(1, int(n_consecutive))
    for i in range(start_idx, len(raw_post) - n_consecutive + 1):
        window = raw_post[i : i + n_consecutive]
        if np.all(np.isfinite(window)) and np.all(window >= threshold_value):
            return i
    return -1


def compute_compact_absolute_metrics(segment, window_before, t_peak):
    metrics = {
        "gpp_baseline_abs": np.nan,
        "gpp_baseline_std_abs": np.nan,
        "gpp_min_abs": np.nan,
        "gpp_change_to_peak_abs": np.nan,
    }
    if len(segment) <= window_before:
        return metrics
    pre = segment[:window_before]
    post = segment[window_before:]
    if np.sum(np.isfinite(pre)) < 5 or np.sum(np.isfinite(post)) < 3:
        return metrics
    baseline = float(np.nanmean(pre))
    baseline_std = float(np.nanstd(pre))
    metrics["gpp_baseline_abs"] = baseline
    metrics["gpp_baseline_std_abs"] = baseline_std
    if 0 <= int(t_peak) < len(post) and np.isfinite(post[int(t_peak)]):
        peak_val = float(post[int(t_peak)])
        metrics["gpp_min_abs"] = peak_val
        metrics["gpp_change_to_peak_abs"] = peak_val - baseline
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
):
    metrics = {
        "response_detected": 0,
        "t_response_onset_start": -1,
        "t_response_drought_start": -1,
        "t_peak": -1,
        "t_impact": -1,
        "amp_max": np.nan,
        "legacy_duration": np.nan,
        "t_recover_to_baseline": np.nan,
        "recovery_rate_to_baseline": np.nan,
    }

    if np.sum(np.isfinite(post)) < 3:
        return metrics

    onset_response = _first_nonpositive(post, 0, max_search=search_len)
    if onset_response >= 0:
        metrics["t_response_onset_start"] = int(onset_response)

    drought_response = _first_nonpositive(post, threshold_offset, max_search=search_len)
    if drought_response < 0:
        return metrics

    metrics["response_detected"] = 1
    metrics["t_response_drought_start"] = int(drought_response)

    valid = np.where(np.isfinite(post[drought_response:]))[0]
    if len(valid) == 0:
        return metrics
    rel_peak = int(valid[np.argmin(post[drought_response:][valid])])
    peak_idx = drought_response + rel_peak
    metrics["t_peak"] = int(peak_idx)
    metrics["t_impact"] = int(peak_idx - drought_response)
    metrics["amp_max"] = float(post[peak_idx])

    if (
        exclude_from_baseline_recovery
        or raw_post is None
        or baseline is None
        or not np.isfinite(baseline)
        or baseline_tolerance is None
        or not np.isfinite(baseline_tolerance)
    ):
        return metrics

    recovery_threshold = float(baseline) - float(baseline_tolerance)
    recover_idx = _baseline_recovery_index(
        raw_post,
        start_idx=peak_idx + 1,
        threshold_value=recovery_threshold,
        n_consecutive=n_consecutive,
    )
    if recover_idx < 0:
        return metrics

    metrics["t_recover_to_baseline"] = float(recover_idx - peak_idx)
    metrics["legacy_duration"] = float(recover_idx - drought_response + 1)
    if metrics["t_recover_to_baseline"] > 0 and np.isfinite(raw_post[peak_idx]):
        metrics["recovery_rate_to_baseline"] = float(
            (float(baseline) - float(raw_post[peak_idx])) / metrics["t_recover_to_baseline"]
        )
    return metrics


def build_result_dtype(event_mode):
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
        ("overlap_with_prev", "i1"),
        ("overlap_with_next", "i1"),
        ("exclude_from_baseline_recovery", "i1"),
        ("response_detected", "i1"),
        ("t_response_onset_start", "i2"),
        ("t_response_drought_start", "i2"),
        ("t_peak", "i2"),
        ("t_impact", "i2"),
        ("amp_max", "f4"),
        ("gpp_baseline_abs", "f4"),
        ("gpp_baseline_std_abs", "f4"),
        ("gpp_min_abs", "f4"),
        ("gpp_change_to_peak_abs", "f4"),
        ("legacy_duration", "f4"),
        ("t_recover_to_baseline", "f4"),
        ("recovery_rate_to_baseline", "f4"),
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
                "drought_duration": duration if duration > 0 else drought_end_idx - drought_start_idx + 1,
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


def _metric_tuple(lat_val, lon_val, event_id, event_info, overlap_flags, metrics, abs_metrics):
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
            int(overlap_flags["overlap_with_prev"]),
            int(overlap_flags["overlap_with_next"]),
            int(overlap_flags["exclude_from_baseline_recovery"]),
            int(metrics["response_detected"]),
            int(metrics["t_response_onset_start"]),
            int(metrics["t_response_drought_start"]),
            int(metrics["t_peak"]),
            int(metrics["t_impact"]),
            float(metrics["amp_max"]),
            float(abs_metrics["gpp_baseline_abs"]),
            float(abs_metrics["gpp_baseline_std_abs"]),
            float(abs_metrics["gpp_min_abs"]),
            float(abs_metrics["gpp_change_to_peak_abs"]),
            float(metrics["legacy_duration"]),
            float(metrics["t_recover_to_baseline"]),
            float(metrics["recovery_rate_to_baseline"]),
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
        ec_chunk = _fill_array(_EVENT_DS.variables["event_count"][lat_start:lat_end, :], 0)
        max_ec = int(np.max(ec_chunk))
        if max_ec == 0:
            return chunk_id, np.array([], dtype=build_result_dtype(_CONFIG["event_mode"]))

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
                raw_series = good_data[:, idx]
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
                    z_segment = z_series[ws : we + 1]
                    raw_segment = raw_series[ws : we + 1]
                    if np.sum(np.isfinite(z_segment)) < 3:
                        continue
                    smoothed = smooth_causal(z_segment, _CONFIG["smooth_window"])
                    post = smoothed[_CONFIG["window_before"] :]
                    raw_post = raw_segment[_CONFIG["window_before"] :]
                    if np.sum(np.isfinite(post)) < 3:
                        continue
                    pre_raw = raw_segment[: _CONFIG["window_before"]]
                    if np.sum(np.isfinite(pre_raw)) < 5:
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
                    search_len = (
                        _CONFIG["response_search_window"]
                        if _CONFIG["event_mode"] == "flash"
                        else event_info["actual_window_after"]
                    )
                    metrics = compute_event_metrics_from_post(
                        post=post,
                        threshold_offset=threshold_offset,
                        n_consecutive=_CONFIG["baseline_recovery_consecutive_days"],
                        baseline=baseline,
                        baseline_tolerance=baseline_tolerance,
                        exclude_from_baseline_recovery=bool(overlap_flags["exclude_from_baseline_recovery"]),
                        raw_post=raw_post,
                        search_len=search_len,
                    )
                    abs_metrics = compute_compact_absolute_metrics(
                        segment=raw_segment,
                        window_before=_CONFIG["window_before"],
                        t_peak=metrics["t_peak"],
                    )
                    results.append(
                        _metric_tuple(lat_val, lon_val, event_id, event_info, overlap_flags, metrics, abs_metrics)
                    )
        dtype = build_result_dtype(_CONFIG["event_mode"])
        if results:
            return chunk_id, np.array(results, dtype=dtype)
        return chunk_id, np.array([], dtype=dtype)
    except Exception as exc:
        print(f"Chunk {chunk_id} error: {exc}")
        return chunk_id, np.array([], dtype=build_result_dtype(_CONFIG["event_mode"]))


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

    with Pool(config["n_workers"], initializer=worker_init, initargs=(config,)) as pool:
        for chunk_id, result in tqdm(pool.imap_unordered(process_chunk, chunks), total=len(chunks), desc="Processing"):
            if len(result) > 0:
                np.save(os.path.join(config["temp_dir"], f"chunk_{chunk_id:04d}.npy"), result)
            del result
            gc.collect()

    all_results = []
    for name in sorted(os.listdir(config["temp_dir"])):
        if name.endswith(".npy"):
            all_results.append(np.load(os.path.join(config["temp_dir"], name)))
    dtype = build_result_dtype(config["event_mode"])
    merged = np.concatenate(all_results) if all_results else np.array([], dtype=dtype)
    save_results_to_netcdf(merged, config, config["relative_output_file"])
    shutil.rmtree(config["temp_dir"])
    print(f"Saved {len(merged):,} compact events to {config['relative_output_file']}")
    return config["relative_output_file"]
