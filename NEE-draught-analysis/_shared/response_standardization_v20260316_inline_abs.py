#!/usr/bin/env python3
"""Inline-absolute shared response standardization helpers for v20260316 scripts."""

import gc
import os
import shutil
from datetime import datetime
from multiprocessing import Pool

import netCDF4 as nc
import numpy as np
from tqdm import tqdm

import response_standardization_v20260316 as base


ABSOLUTE_FIELDS = (
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


def build_result_dtype(metric_name, event_mode):
    base_dtype = base.build_result_dtype(metric_name, event_mode)
    fields = [(name, base_dtype.fields[name][0]) for name in base_dtype.names]
    fields.extend((name, "f4") for name in ABSOLUTE_FIELDS)
    return np.dtype(fields)


def _metric_tuple_with_abs(metric_name, event_mode, lat_val, lon_val, event_id, event_info, overlap_flags, metrics, abs_metrics):
    values = list(
        base._metric_tuple(
            metric_name,
            event_mode,
            lat_val,
            lon_val,
            event_id,
            event_info,
            overlap_flags,
            metrics,
        )
    )
    values.extend(float(abs_metrics[name]) for name in ABSOLUTE_FIELDS)
    return tuple(values)


def worker_init(config):
    base.worker_init(config)


def process_chunk(chunk_info):
    chunk_id, lat_start, lat_end = chunk_info
    results = []

    try:
        lat_arr = base._DATA_DS.variables["lat"][lat_start:lat_end]
        data_chunk = base._DATA_DS.variables[base._CONFIG["data_var"]][:, lat_start:lat_end, :]
        if hasattr(data_chunk, "filled"):
            data_chunk = data_chunk.filled(np.nan).astype(np.float32)
        else:
            data_chunk = np.array(data_chunk, dtype=np.float32)

        ec_chunk = base._EVENT_DS.variables["event_count"][lat_start:lat_end, :]
        ec_chunk = base._fill_array(ec_chunk, 0)
        max_ec = int(np.max(ec_chunk))
        dtype = build_result_dtype(base._CONFIG["metric_name"], base._CONFIG["event_mode"])
        if max_ec == 0:
            return chunk_id, np.array([], dtype=dtype)

        event_arrays = base._get_event_arrays(lat_start, lat_end, max_ec)
        for rel_lat in range(lat_end - lat_start):
            lat_val = float(lat_arr[rel_lat])
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            if len(lon_with_events) == 0:
                continue

            row = data_chunk[:, rel_lat, lon_with_events]
            valid_count = np.sum(np.isfinite(row), axis=0)
            good_mask = valid_count >= base._CONFIG["min_valid_values"]
            if not np.any(good_mask):
                continue

            good_lon_indices = lon_with_events[good_mask]
            good_data = row[:, good_mask]
            z_matrix = base.calc_climatology_zscore(good_data, base._DOY_IDX)

            for idx, lon_idx in enumerate(good_lon_indices):
                ec = int(ec_chunk[rel_lat, lon_idx])
                z_series = z_matrix[:, idx]
                abs_series = good_data[:, idx]
                lon_val = float(base._LON_ARR[lon_idx])
                for event_id in range(ec):
                    event_info = base._event_indices(event_arrays, event_id, rel_lat, lon_idx)
                    if event_info is None:
                        continue
                    prev_event_info = None
                    next_event_info = None
                    if event_id > 0:
                        prev_event_info = base._event_indices(event_arrays, event_id - 1, rel_lat, lon_idx)
                    if event_id + 1 < ec:
                        next_event_info = base._event_indices(event_arrays, event_id + 1, rel_lat, lon_idx)
                    overlap_flags = base.compute_event_overlap_flags(
                        event_info=event_info,
                        prev_event_info=prev_event_info,
                        next_event_info=next_event_info,
                        window_before=base._CONFIG["window_before"],
                    )

                    window = base._build_window(event_info, len(z_series))
                    if window is None:
                        continue
                    ws, we, threshold_offset = window
                    segment = z_series[ws : we + 1]
                    if np.sum(np.isfinite(segment)) < 30:
                        continue

                    smoothed = base.smooth_causal(segment, base._CONFIG["smooth_window"])
                    pre = smoothed[: base._CONFIG["window_before"]]
                    if np.sum(np.isfinite(pre)) < 5:
                        continue

                    post = smoothed[base._CONFIG["window_before"] :]
                    metrics = base.compute_event_metrics_from_post(
                        post=post,
                        threshold_offset=threshold_offset,
                        response_threshold=base._CONFIG["response_threshold"],
                        recover_threshold=base._CONFIG["recover_threshold"],
                        n_consecutive=base._CONFIG["consecutive_days"],
                        primary_search_window=base._primary_search_window(event_info),
                        supplemental_search_window=base._supplemental_search_window(event_info, threshold_offset),
                        direction=base._CONFIG["direction"],
                    )

                    abs_segment = abs_series[ws : we + 1]
                    event_end_offset = None
                    if base._CONFIG["event_mode"] == "nonflash":
                        event_end_offset = int(event_info["drought_end_idx"] - event_info["onset_idx"])
                    abs_metrics = base.compute_absolute_metrics_from_segment(
                        segment=abs_segment,
                        window_before=base._CONFIG["window_before"],
                        t_peak=metrics["t_peak"],
                        t_recover=metrics["t_recover"],
                        direction=base._CONFIG["direction"],
                        n_consecutive=base._CONFIG["baseline_recovery_consecutive_days"],
                        threshold_offset=threshold_offset,
                        event_end_offset=event_end_offset,
                        baseline_tolerance_multiplier=base._CONFIG["baseline_tolerance_multiplier"],
                        baseline_tolerance_floor_fraction=base._CONFIG["baseline_tolerance_floor_fraction"],
                        enable_sink_source=(base._CONFIG["metric_name"] == "nee"),
                    )

                    results.append(
                        _metric_tuple_with_abs(
                            base._CONFIG["metric_name"],
                            base._CONFIG["event_mode"],
                            lat_val,
                            lon_val,
                            event_id,
                            event_info,
                            overlap_flags,
                            metrics,
                            abs_metrics,
                        )
                    )

        if results:
            return chunk_id, np.array(results, dtype=dtype)
        return chunk_id, np.array([], dtype=dtype)
    except Exception as exc:
        print(f"Chunk {chunk_id} error: {exc}")
        return chunk_id, np.array([], dtype=build_result_dtype(base._CONFIG["metric_name"], base._CONFIG["event_mode"]))


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
        ds.absolute_metrics_version = "v20260316_inline_abs"


def run_relative_analysis(config):
    os.makedirs(config["output_dir"], exist_ok=True)
    if os.path.exists(config["temp_dir"]):
        shutil.rmtree(config["temp_dir"])
    os.makedirs(config["temp_dir"], exist_ok=True)

    chunks, total_events = base._create_chunks(config)
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
    dtype = build_result_dtype(config["metric_name"], config["event_mode"])
    merged = np.concatenate(all_results) if all_results else np.array([], dtype=dtype)
    save_results_to_netcdf(merged, config, config["relative_output_file"])
    shutil.rmtree(config["temp_dir"])
    print(f"Saved {len(merged):,} standardized events to {config['relative_output_file']}")
    return config["relative_output_file"]
