#!/usr/bin/env python3
"""Hybrid shared response standardization helpers for v20260316_3 scripts."""

import gc
import os
import shutil
from multiprocessing import Pool

import numpy as np
from tqdm import tqdm

import response_standardization_v20260316_2 as timing_base


calc_daily_climatology_mean = timing_base.calc_daily_climatology_mean
classify_timing_phase_from_climatology = timing_base.classify_timing_phase_from_climatology
smooth_centered_cycle = timing_base.smooth_centered_cycle


def worker_init(config):
    timing_base.worker_init(config)


def process_chunk(chunk_info):
    chunk_id, lat_start, lat_end = chunk_info
    results = []

    try:
        lat_arr = timing_base._DATA_DS.variables["lat"][lat_start:lat_end]
        data_chunk = timing_base._DATA_DS.variables[timing_base._CONFIG["data_var"]][:, lat_start:lat_end, :]
        timing_chunk = timing_base._TIMING_DS.variables[timing_base._CONFIG["timing_reference_var"]][:, lat_start:lat_end, :]
        if hasattr(data_chunk, "filled"):
            data_chunk = data_chunk.filled(np.nan).astype(np.float32)
        else:
            data_chunk = np.array(data_chunk, dtype=np.float32)
        if hasattr(timing_chunk, "filled"):
            timing_chunk = timing_chunk.filled(np.nan).astype(np.float32)
        else:
            timing_chunk = np.array(timing_chunk, dtype=np.float32)

        ec_chunk = timing_base._EVENT_DS.variables["event_count"][lat_start:lat_end, :]
        ec_chunk = timing_base._fill_array(ec_chunk, 0)
        max_ec = int(np.max(ec_chunk))
        if max_ec == 0:
            return chunk_id, np.array([], dtype=timing_base.build_result_dtype(timing_base._CONFIG["metric_name"], timing_base._CONFIG["event_mode"]))

        event_arrays = timing_base._get_event_arrays(lat_start, lat_end, max_ec)
        for rel_lat in range(lat_end - lat_start):
            lat_val = float(lat_arr[rel_lat])
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            if len(lon_with_events) == 0:
                continue

            row = data_chunk[:, rel_lat, lon_with_events]
            valid_count = np.sum(np.isfinite(row), axis=0)
            good_mask = valid_count >= timing_base._CONFIG["min_valid_values"]
            if not np.any(good_mask):
                continue

            good_lon_indices = lon_with_events[good_mask]
            good_data = row[:, good_mask]
            good_timing = timing_chunk[:, rel_lat, good_lon_indices]
            z_matrix = timing_base.calc_climatology_zscore(good_data, timing_base._DOY_IDX)
            timing_clim = timing_base.calc_daily_climatology_mean(good_timing, timing_base._DOY_IDX)

            for idx, lon_idx in enumerate(good_lon_indices):
                ec = int(ec_chunk[rel_lat, lon_idx])
                z_series = z_matrix[:, idx]
                timing_climatology = timing_clim[:, idx]
                lon_val = float(timing_base._LON_ARR[lon_idx])
                for event_id in range(ec):
                    event_info = timing_base._event_indices(event_arrays, event_id, rel_lat, lon_idx)
                    if event_info is None:
                        continue
                    prev_event_info = None
                    next_event_info = None
                    if event_id > 0:
                        prev_event_info = timing_base._event_indices(event_arrays, event_id - 1, rel_lat, lon_idx)
                    if event_id + 1 < ec:
                        next_event_info = timing_base._event_indices(event_arrays, event_id + 1, rel_lat, lon_idx)
                    overlap_flags = timing_base.compute_event_overlap_flags(
                        event_info=event_info,
                        prev_event_info=prev_event_info,
                        next_event_info=next_event_info,
                        window_before=timing_base._CONFIG["window_before"],
                    )
                    timing_info = timing_base.classify_timing_phase_from_climatology(
                        timing_climatology,
                        event_info["onset_doy"],
                    )

                    window = timing_base._build_window(event_info, len(z_series))
                    if window is None:
                        continue
                    ws, we, threshold_offset = window
                    segment = z_series[ws : we + 1]
                    if np.sum(np.isfinite(segment)) < 30:
                        continue

                    smoothed = timing_base.smooth_causal(segment, timing_base._CONFIG["smooth_window"])
                    pre = smoothed[: timing_base._CONFIG["window_before"]]
                    if np.sum(np.isfinite(pre)) < 5:
                        continue

                    post = smoothed[timing_base._CONFIG["window_before"] :]
                    metrics = timing_base.compute_event_metrics_from_post(
                        post=post,
                        threshold_offset=threshold_offset,
                        response_threshold=timing_base._CONFIG["response_threshold"],
                        recover_threshold=timing_base._CONFIG["recover_threshold"],
                        n_consecutive=timing_base._CONFIG["consecutive_days"],
                        primary_search_window=timing_base._primary_search_window(event_info),
                        supplemental_search_window=timing_base._supplemental_search_window(event_info, threshold_offset),
                        direction=timing_base._CONFIG["direction"],
                    )
                    results.append(
                        timing_base._metric_tuple(
                            timing_base._CONFIG["metric_name"],
                            timing_base._CONFIG["event_mode"],
                            lat_val,
                            lon_val,
                            event_id,
                            event_info,
                            overlap_flags,
                            timing_info,
                            metrics,
                        )
                    )

        dtype = timing_base.build_result_dtype(timing_base._CONFIG["metric_name"], timing_base._CONFIG["event_mode"])
        if results:
            return chunk_id, np.array(results, dtype=dtype)
        return chunk_id, np.array([], dtype=dtype)
    except Exception as exc:
        print(f"Chunk {chunk_id} error: {exc}")
        return chunk_id, np.array([], dtype=timing_base.build_result_dtype(timing_base._CONFIG["metric_name"], timing_base._CONFIG["event_mode"]))


def run_relative_analysis(config):
    os.makedirs(config["output_dir"], exist_ok=True)
    if os.path.exists(config["temp_dir"]):
        shutil.rmtree(config["temp_dir"])
    os.makedirs(config["temp_dir"], exist_ok=True)

    chunks, total_events = timing_base._create_chunks(config)
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
    dtype = timing_base.build_result_dtype(config["metric_name"], config["event_mode"])
    merged = np.concatenate(all_results) if all_results else np.array([], dtype=dtype)
    timing_base.save_results_to_netcdf(merged, config, config["relative_output_file"])
    shutil.rmtree(config["temp_dir"])
    print(f"Saved {len(merged):,} standardized events to {config['relative_output_file']}")
    return config["relative_output_file"]
