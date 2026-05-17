#!/usr/bin/env python
"""Extract ERA5 event-window features with tile-based parallelism."""

from __future__ import annotations

import argparse
import os
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import xarray as xr

from sem_gleam_common import (
    DATA_DIR,
    ERA5_VARIABLE_SPECS,
    MASTER_VALID_PATH,
    WINDOW_STATS,
    feature_chunk_name,
    finalize_feature_table,
    nearest_index,
    summarize_window,
)

FILTER_COLUMNS = [
    "event_uid",
    "metric",
    "code_id",
    "biome",
    "soil_layer",
    "drought_type",
    "lat",
    "lon",
    "onset_start_date",
    "drought_start_date",
    "t_peak_abs",
    "t_recover_to_baseline_abs_peak",
]

EVENT_TILE_COLUMNS = [
    "event_uid",
    "onset_start_date",
    "drought_start_date",
    "t_peak_abs",
    "t_recover_to_baseline_abs_peak",
    "lat_idx",
    "lon_idx",
    "tile_row",
    "tile_col",
    "lat_local_idx",
    "lon_local_idx",
]

WORKER_DATASETS: dict[str, xr.Dataset] = {}
WORKER_DATA_VARS: dict[str, str] = {}
WORKER_TIME_VALS: np.ndarray | None = None
WORKER_GRID_SHAPE: tuple[int, int] = (0, 0)
ACTIVE_ERA5_VARIABLE_SPECS: dict[str, Path] = dict(ERA5_VARIABLE_SPECS)
DEFAULT_RECHUNK_ROOT_NAME = "rechunked_spatial_20260402"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metric", default=None)
    parser.add_argument("--code-id", default=None)
    parser.add_argument("--biome", default=None)
    parser.add_argument("--drought-type", default=None)
    parser.add_argument("--soil-layer", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--concurrent-era5-tasks", type=int, default=1)
    parser.add_argument("--reserve-cpus", type=int, default=8)
    parser.add_argument("--max-workers-cap", type=int, default=None)
    parser.add_argument("--progress-every", type=int, default=None)
    parser.add_argument("--vars-per-task", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=200000)
    parser.add_argument("--tile-lat-size", type=int, default=32)
    parser.add_argument("--tile-lon-size", type=int, default=32)
    parser.add_argument("--era5-root-dir", default=None)
    parser.add_argument("--era5-file-suffix", default="_spatialchunks_py.nc")
    parser.add_argument("--total-precipitation-path", default=None)
    parser.add_argument("--total-evaporation-path", default=None)
    parser.add_argument("--variables", nargs="+", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--resume-existing-work-root", action="store_true")
    parser.add_argument("--keep-work-root", action="store_true")
    return parser.parse_args()


def resolve_era5_variable_specs(
    era5_root_dir: str | None,
    era5_file_suffix: str,
    total_precipitation_path: str | None = None,
    total_evaporation_path: str | None = None,
) -> dict[str, Path]:
    auto_root = discover_default_rechunk_root(era5_file_suffix)
    effective_root = era5_root_dir or (str(auto_root) if auto_root is not None else None)
    if not effective_root:
        resolved = dict(ERA5_VARIABLE_SPECS)
    else:
        root = Path(effective_root)
        resolved: dict[str, Path] = {}
        for var_name, original_path in ERA5_VARIABLE_SPECS.items():
            candidate = root / f"{original_path.stem}{era5_file_suffix}"
            if not candidate.exists():
                raise FileNotFoundError(f"Missing rechunked ERA5 file for {var_name}: {candidate}")
            resolved[var_name] = candidate

    if total_precipitation_path:
        resolved["total_precipitation"] = Path(total_precipitation_path)
    if total_evaporation_path:
        resolved["total_evaporation"] = Path(total_evaporation_path)

    for var_name, path in resolved.items():
        if not Path(path).exists():
            raise FileNotFoundError(f"Missing ERA5 input for {var_name}: {path}")
    return resolved


def discover_default_rechunk_root(era5_file_suffix: str) -> Path | None:
    yearly_root = next(iter(ERA5_VARIABLE_SPECS.values())).parent
    candidate_root = yearly_root.parent / DEFAULT_RECHUNK_ROOT_NAME
    if not candidate_root.exists():
        return None
    for original_path in ERA5_VARIABLE_SPECS.values():
        candidate = candidate_root / f"{original_path.stem}{era5_file_suffix}"
        if not candidate.exists():
            return None
    return candidate_root


def resolve_dataset_variable_name(ds: xr.Dataset, requested_name: str) -> str:
    if requested_name in ds.data_vars:
        return requested_name
    candidates = [
        name
        for name, var in ds.data_vars.items()
        if tuple(var.dims) == ("time", "lat", "lon")
    ]
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError(
        f"Could not resolve dataset variable for requested name {requested_name!r}. "
        f"Available data_vars={list(ds.data_vars)} candidates={candidates}"
    )


def build_phase_windows(onset_dates, drought_dates, peak_offsets_days, recovery_offsets_days=None):
    peak_dates = drought_dates + peak_offsets_days.astype("timedelta64[D]")
    windows = {
        "pre30": (onset_dates - np.timedelta64(30, "D"), onset_dates - np.timedelta64(1, "D")),
        "prepeak": (onset_dates, peak_dates),
        "onset": (onset_dates, drought_dates),
        "shock": (drought_dates, peak_dates),
        "postpeak30": (peak_dates, peak_dates + np.timedelta64(30, "D")),
        "postpeak60": (peak_dates, peak_dates + np.timedelta64(60, "D")),
    }
    if recovery_offsets_days is not None:
        windows["recoverywin"] = (
            peak_dates,
            peak_dates + recovery_offsets_days.astype("timedelta64[D]"),
        )
    return windows


def compute_window_indices(time_vals, start_dates, end_dates):
    left = np.searchsorted(time_vals, start_dates, side="left")
    right = np.searchsorted(time_vals, end_dates, side="right")
    return left, right


def batch_mean_from_prefix(prefix_sum, prefix_count, left, right):
    sums = prefix_sum[right] - prefix_sum[left]
    counts = prefix_count[right] - prefix_count[left]
    out = np.full(len(left), np.nan, dtype=np.float32)
    valid = counts > 0
    out[valid] = (sums[valid] / counts[valid]).astype(np.float32)
    return out


def batch_sum_from_prefix(prefix_sum, prefix_count, left, right):
    sums = prefix_sum[right] - prefix_sum[left]
    counts = prefix_count[right] - prefix_count[left]
    out = np.full(len(left), np.nan, dtype=np.float32)
    valid = counts > 0
    out[valid] = sums[valid].astype(np.float32)
    return out


def batch_slice_stat(series, left, right, stat: str):
    out = np.full(len(left), np.nan, dtype=np.float32)
    for i, (l_idx, r_idx) in enumerate(zip(left, right)):
        if r_idx <= l_idx:
            continue
        out[i] = summarize_window(series[l_idx:r_idx], stat)
    return out


def vectorized_nearest_indices(values: np.ndarray, targets: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    targets = np.asarray(targets, dtype=np.float64)
    if targets.size == 0:
        return np.empty(0, dtype=np.int32)
    if values.size == 0:
        raise ValueError("values cannot be empty")
    if values[0] > values[-1]:
        flipped = values[::-1]
        rev_idx = vectorized_nearest_indices(flipped, targets)
        return (len(values) - 1 - rev_idx).astype(np.int32, copy=False)

    idx = np.searchsorted(values, targets, side="left")
    idx = np.clip(idx, 1, len(values) - 1)
    left = values[idx - 1]
    right = values[idx]
    choose_right = np.abs(right - targets) < np.abs(targets - left)
    out = idx - 1
    out[choose_right] = idx[choose_right]
    return out.astype(np.int32, copy=False)


def group_event_windows(starts: np.ndarray, ends: np.ndarray) -> list[list[int]]:
    if len(starts) == 0:
        return []
    order = np.argsort(starts, kind="stable")
    groups: list[list[int]] = [[int(order[0])]]
    current_end = ends[int(order[0])]
    for raw_idx in order[1:]:
        idx = int(raw_idx)
        if starts[idx] <= current_end:
            groups[-1].append(idx)
            if ends[idx] > current_end:
                current_end = ends[idx]
        else:
            groups.append([idx])
            current_end = ends[idx]
    return groups


def format_progress_line(
    label: str,
    stage: str,
    batch_idx: int,
    scanned_rows: int,
    matched_rows: int,
    cumulative_rows: int,
    elapsed_seconds: float,
) -> str:
    return (
        f"[{stage}][{label}] "
        f"batch={batch_idx} scanned={scanned_rows} matched={matched_rows} "
        f"cumulative={cumulative_rows} elapsed_s={elapsed_seconds:.1f}"
    )


def resolve_worker_count(
    requested_workers: int | None,
    total_tiles: int,
    cpu_count: int | None = None,
    concurrent_tasks: int = 1,
    reserve_cpus: int = 8,
    max_workers_cap: int | None = None,
) -> int:
    total_tiles = max(1, int(total_tiles))
    cpu_total = max(1, int(cpu_count or os.cpu_count() or 1))
    task_count = max(1, int(concurrent_tasks))
    reserved = max(0, int(reserve_cpus))
    usable_cpus = max(1, cpu_total - reserved)
    auto_workers = max(1, usable_cpus // task_count)
    if max_workers_cap is not None:
        auto_workers = min(auto_workers, max(1, int(max_workers_cap)))
    if requested_workers is None or int(requested_workers) <= 0:
        return max(1, min(total_tiles, auto_workers))
    return max(1, min(total_tiles, int(requested_workers)))


def compute_progress_every(total_tiles: int, requested_every: int | None = None) -> int:
    if requested_every is not None and int(requested_every) > 0:
        return int(requested_every)
    if total_tiles <= 20:
        return 1
    if total_tiles <= 500:
        return 10
    return 25


def build_variable_batches(variable_names: list[str], vars_per_task: int) -> list[tuple[str, ...]]:
    batch_size = max(1, int(vars_per_task))
    return [tuple(variable_names[idx : idx + batch_size]) for idx in range(0, len(variable_names), batch_size)]


def filter_master_batch(
    df: pd.DataFrame,
    metric: str | None,
    code_id: str | None,
    biome: str | None,
    drought_type: str | None,
    soil_layer: str | None,
) -> pd.DataFrame:
    out = df
    if metric is not None:
        out = out[out["metric"].astype(str) == str(metric)]
    if code_id is not None:
        out = out[out["code_id"].astype(str) == str(code_id)]
    if biome is not None:
        out = out[out["biome"].astype(str) == str(biome)]
    if drought_type is not None:
        out = out[out["drought_type"].astype(str) == str(drought_type)]
    if soil_layer is not None:
        out = out[out["soil_layer"].astype(str) == str(soil_layer)]
    return out


def merge_feature_frames(base_df: pd.DataFrame, parts: list[pd.DataFrame]) -> pd.DataFrame:
    merged = base_df
    for part in parts:
        merged = merged.merge(part, on="event_uid", how="left")
    return finalize_feature_table(merged)


def extract_features_for_var_from_block(
    events: pd.DataFrame,
    block: np.ndarray,
    time_vals: np.ndarray,
    var_name: str,
) -> pd.DataFrame:
    stats_cfg = WINDOW_STATS[var_name]
    results = {"event_uid": events["event_uid"].to_numpy()}
    for phase, stats in stats_cfg.items():
        for stat in stats:
            results[f"{phase}_{var_name}_{stat}"] = np.full(len(events), np.nan, dtype=np.float32)

    for (lat_local_idx, lon_local_idx), pixel_df in events.groupby(["lat_local_idx", "lon_local_idx"], sort=False):
        row_idx_all = pixel_df.index.to_numpy()
        onset_dates = pixel_df["onset_start_date"].to_numpy().astype("datetime64[D]")
        drought_dates = pixel_df["drought_start_date"].to_numpy().astype("datetime64[D]")
        peak_offsets = pd.to_numeric(pixel_df["t_peak_abs"], errors="coerce").fillna(-9999).astype(np.int32).to_numpy()
        recovery_offsets = pd.to_numeric(
            pixel_df["t_recover_to_baseline_abs_peak"],
            errors="coerce",
        ).fillna(-9999).astype(np.int32).to_numpy()
        valid_events = (peak_offsets >= 0) & (recovery_offsets >= 0)
        if not valid_events.any():
            continue

        series = block[:, int(lat_local_idx), int(lon_local_idx)]
        valid_row_idx = row_idx_all[valid_events]
        valid_onset_dates = onset_dates[valid_events]
        valid_drought_dates = drought_dates[valid_events]
        valid_peak_offsets = peak_offsets[valid_events]
        valid_recovery_offsets = recovery_offsets[valid_events]
        valid_peak_dates = valid_drought_dates + valid_peak_offsets.astype("timedelta64[D]")
        valid_window_starts = valid_onset_dates - np.timedelta64(30, "D")
        valid_window_ends = np.maximum(
            valid_peak_dates + np.timedelta64(60, "D"),
            valid_peak_dates + valid_recovery_offsets.astype("timedelta64[D]"),
        )

        for group in group_event_windows(valid_window_starts, valid_window_ends):
            group_idx = np.asarray(group, dtype=np.int32)
            segment_start = valid_window_starts[group_idx].min()
            segment_end = valid_window_ends[group_idx].max()
            left = int(np.searchsorted(time_vals, segment_start, side="left"))
            right = int(np.searchsorted(time_vals, segment_end, side="right"))
            if right <= left:
                continue

            segment_series = series[left:right]
            local_time_vals = time_vals[left:right]
            clean_series = np.where(np.isfinite(segment_series), segment_series, 0.0)
            valid_series = np.isfinite(segment_series).astype(np.int32)
            prefix_sum = np.concatenate([[0.0], np.cumsum(clean_series, dtype=np.float64)])
            prefix_count = np.concatenate([[0], np.cumsum(valid_series, dtype=np.int64)])

            row_idx = valid_row_idx[group_idx]
            phase_windows = build_phase_windows(
                valid_onset_dates[group_idx],
                valid_drought_dates[group_idx],
                valid_peak_offsets[group_idx],
                valid_recovery_offsets[group_idx],
            )

            for phase, stats in stats_cfg.items():
                start_dates, end_dates = phase_windows[phase]
                phase_left, phase_right = compute_window_indices(local_time_vals, start_dates, end_dates)
                phase_right = np.maximum(phase_right, phase_left)
                for stat in stats:
                    if stat == "mean":
                        values = batch_mean_from_prefix(prefix_sum, prefix_count, phase_left, phase_right)
                    elif stat == "sum":
                        values = batch_sum_from_prefix(prefix_sum, prefix_count, phase_left, phase_right)
                    else:
                        values = batch_slice_stat(segment_series, phase_left, phase_right, stat)
                    results[f"{phase}_{var_name}_{stat}"][row_idx] = values
    return pd.DataFrame(results)


def init_worker_datasets() -> None:
    global WORKER_DATASETS, WORKER_DATA_VARS, WORKER_TIME_VALS, WORKER_GRID_SHAPE
    WORKER_DATASETS = {}
    WORKER_DATA_VARS = {}
    ref_name = next(iter(ACTIVE_ERA5_VARIABLE_SPECS))
    ref_ds = xr.open_dataset(ACTIVE_ERA5_VARIABLE_SPECS[ref_name], cache=False)
    WORKER_DATASETS[ref_name] = ref_ds
    WORKER_DATA_VARS[ref_name] = resolve_dataset_variable_name(ref_ds, ref_name)
    WORKER_TIME_VALS = np.asarray(ref_ds["time"].values).astype("datetime64[D]")
    WORKER_GRID_SHAPE = (int(ref_ds.sizes["lat"]), int(ref_ds.sizes["lon"]))


def get_worker_dataset(var_name: str) -> xr.Dataset:
    ds = WORKER_DATASETS.get(var_name)
    if ds is None:
        ds = xr.open_dataset(ACTIVE_ERA5_VARIABLE_SPECS[var_name], cache=False)
        WORKER_DATASETS[var_name] = ds
        WORKER_DATA_VARS[var_name] = resolve_dataset_variable_name(ds, var_name)
    return ds


def prepare_tile_tasks(
    master_path: Path,
    metric: str | None,
    code_id: str | None,
    biome: str | None,
    drought_type: str | None,
    soil_layer: str | None,
    batch_size: int,
    limit: int | None,
    tile_lat_size: int,
    tile_lon_size: int,
    lat_vals: np.ndarray,
    lon_vals: np.ndarray,
    work_root: Path,
    label: str,
    resume_existing_work_root: bool = False,
) -> dict[str, object]:
    start_time = time.time()
    events_dir = work_root / "events"
    features_dir = work_root / "features"
    if resume_existing_work_root and events_dir.exists():
        tile_tasks, feature_shards = discover_existing_tile_tasks(
            events_dir=events_dir,
            features_dir=features_dir,
            tile_lat_size=tile_lat_size,
            tile_lon_size=tile_lon_size,
            label=label,
        )
        if tile_tasks:
            print(
                f"[PREP_RESUME][{label}] reuse_events={len(tile_tasks)} work_root={work_root}",
                flush=True,
            )
            return {
                "tile_tasks": tile_tasks,
                "feature_shards": feature_shards,
                "matched_total": None,
                "unique_tiles": len(tile_tasks),
                "unique_pixels": None,
            }

    pf = pq.ParquetFile(master_path)
    pieces: list[pd.DataFrame] = []
    scanned_total = 0
    matched_total = 0
    remaining = limit

    print(
        f"[PREP_START][{label}] batch_size={batch_size} tile={tile_lat_size}x{tile_lon_size} limit={limit}",
        flush=True,
    )
    for batch_idx, batch in enumerate(pf.iter_batches(columns=FILTER_COLUMNS, batch_size=batch_size), start=1):
        raw_df = batch.to_pandas()
        scanned_rows = len(raw_df)
        scanned_total += scanned_rows
        batch_df = filter_master_batch(raw_df, metric, code_id, biome, drought_type, soil_layer)
        if batch_df.empty:
            if batch_idx % 10 == 0:
                print(
                    format_progress_line(
                        label=label,
                        stage="PREP_SCAN",
                        batch_idx=batch_idx,
                        scanned_rows=scanned_rows,
                        matched_rows=0,
                        cumulative_rows=matched_total,
                        elapsed_seconds=time.time() - start_time,
                    ),
                    flush=True,
                )
            continue
        if remaining is not None:
            if remaining <= 0:
                break
            batch_df = batch_df.head(remaining).copy()
            remaining -= len(batch_df)

        keep = batch_df[["event_uid", "lat", "lon", "onset_start_date", "drought_start_date", "t_peak_abs", "t_recover_to_baseline_abs_peak"]].copy()
        keep["lat_idx"] = vectorized_nearest_indices(lat_vals, keep["lat"].to_numpy())
        keep["lon_idx"] = vectorized_nearest_indices(lon_vals, keep["lon"].to_numpy())
        keep["tile_row"] = keep["lat_idx"] // tile_lat_size
        keep["tile_col"] = keep["lon_idx"] // tile_lon_size
        keep["lat_local_idx"] = keep["lat_idx"] % tile_lat_size
        keep["lon_local_idx"] = keep["lon_idx"] % tile_lon_size
        keep = keep[EVENT_TILE_COLUMNS]
        pieces.append(keep)
        matched_total += len(keep)
        print(
            format_progress_line(
                label=label,
                stage="PREP_MATCH",
                batch_idx=batch_idx,
                scanned_rows=scanned_rows,
                matched_rows=len(keep),
                cumulative_rows=matched_total,
                elapsed_seconds=time.time() - start_time,
            ),
            flush=True,
        )
        if remaining is not None and remaining <= 0:
            break

    if not pieces:
        print(f"[PREP_DONE][{label}] no matched events", flush=True)
        return {"tile_tasks": [], "feature_shards": [], "matched_total": 0}

    group_df = pd.concat(pieces, ignore_index=True)
    group_df.sort_values(["tile_row", "tile_col", "lat_idx", "lon_idx"], inplace=True, ignore_index=True)
    unique_tiles = int(group_df.groupby(["tile_row", "tile_col"], sort=False).ngroups)
    unique_pixels = int(group_df.groupby(["lat_idx", "lon_idx"], sort=False).ngroups)

    if work_root.exists():
        shutil.rmtree(work_root)
    events_dir.mkdir(parents=True, exist_ok=True)
    features_dir.mkdir(parents=True, exist_ok=True)

    tile_tasks: list[tuple[str, str, int, int, int, int, str]] = []
    feature_shards: list[Path] = []
    for tile_idx, ((tile_row, tile_col), tile_df) in enumerate(group_df.groupby(["tile_row", "tile_col"], sort=False), start=1):
        event_path = events_dir / f"events_r{int(tile_row):03d}_c{int(tile_col):03d}.parquet"
        feature_path = features_dir / f"features_r{int(tile_row):03d}_c{int(tile_col):03d}.parquet"
        tile_df[EVENT_TILE_COLUMNS].to_parquet(event_path, index=False)
        tile_tasks.append(
            (
                str(event_path),
                str(feature_path),
                int(tile_row),
                int(tile_col),
                int(tile_lat_size),
                int(tile_lon_size),
                label,
            )
        )
        feature_shards.append(feature_path)
        if tile_idx % 100 == 0:
            print(f"[PREP_TILE][{label}] tiles_written={tile_idx} elapsed_s={time.time() - start_time:.1f}", flush=True)

    print(
        f"[PREP_DONE][{label}] scanned={scanned_total} matched={matched_total} "
        f"unique_pixels={unique_pixels} unique_tiles={unique_tiles} elapsed_s={time.time() - start_time:.1f}",
        flush=True,
    )
    return {
        "tile_tasks": tile_tasks,
        "feature_shards": feature_shards,
        "matched_total": matched_total,
        "unique_tiles": unique_tiles,
        "unique_pixels": unique_pixels,
    }


def discover_existing_tile_tasks(
    events_dir: Path,
    features_dir: Path,
    tile_lat_size: int,
    tile_lon_size: int,
    label: str,
) -> tuple[list[tuple[str, str, int, int, int, int, str]], list[Path]]:
    tile_tasks: list[tuple[str, str, int, int, int, int, str]] = []
    feature_shards: list[Path] = []
    for event_path in sorted(events_dir.glob("events_r*_c*.parquet")):
        stem = event_path.stem
        _, row_part, col_part = stem.split("_")
        tile_row = int(row_part[1:])
        tile_col = int(col_part[1:])
        feature_path = features_dir / f"features_r{tile_row:03d}_c{tile_col:03d}.parquet"
        tile_tasks.append(
            (
                str(event_path),
                str(feature_path),
                tile_row,
                tile_col,
                int(tile_lat_size),
                int(tile_lon_size),
                label,
            )
        )
        feature_shards.append(feature_path)
    return tile_tasks, feature_shards


def build_variable_tasks(
    tile_tasks: list[tuple[str, str, int, int, int, int, str]],
    variable_batches: list[tuple[str, ...]],
    work_root: Path,
    resume_existing_work_root: bool = False,
) -> tuple[list[tuple[str, str, int, int, int, int, str, tuple[str, ...]]], dict[str, list[Path]]]:
    partial_dir = work_root / "partials"
    partial_dir.mkdir(parents=True, exist_ok=True)
    var_tasks: list[tuple[str, str, int, int, int, int, str, tuple[str, ...]]] = []
    tile_partials: dict[str, list[Path]] = {}
    for event_path_str, feature_path_str, tile_row, tile_col, tile_lat_size, tile_lon_size, label in tile_tasks:
        feature_path = Path(feature_path_str)
        tile_key = feature_path.stem
        partial_paths: list[Path] = []
        for batch_idx, variable_names in enumerate(variable_batches, start=1):
            partial_path = partial_dir / f"{tile_key}_vars{batch_idx:02d}.parquet"
            partial_paths.append(partial_path)
            if resume_existing_work_root and partial_path.exists():
                continue
            var_tasks.append(
                (
                    event_path_str,
                    str(partial_path),
                    tile_row,
                    tile_col,
                    tile_lat_size,
                    tile_lon_size,
                    label,
                    variable_names,
                )
            )
        tile_partials[tile_key] = partial_paths
    return var_tasks, tile_partials


def process_variable_task(task: tuple[str, str, int, int, int, int, str, tuple[str, ...]]) -> dict[str, object]:
    event_path_str, partial_path_str, tile_row, tile_col, tile_lat_size, tile_lon_size, label, variable_names = task
    event_path = Path(event_path_str)
    partial_path = Path(partial_path_str)
    events = pd.read_parquet(event_path)
    if events.empty:
        pd.DataFrame({"event_uid": []}).to_parquet(partial_path, index=False)
        return {"rows": 0, "tile": (tile_row, tile_col), "path": str(partial_path), "label": label, "vars": variable_names}

    lat_start = int(tile_row) * int(tile_lat_size)
    lon_start = int(tile_col) * int(tile_lon_size)
    lat_stop = min(lat_start + int(tile_lat_size), WORKER_GRID_SHAPE[0])
    lon_stop = min(lon_start + int(tile_lon_size), WORKER_GRID_SHAPE[1])

    parts: list[pd.DataFrame] = []
    assert WORKER_TIME_VALS is not None
    for name in variable_names:
        ds = get_worker_dataset(name)
        data_var_name = WORKER_DATA_VARS[name]
        block = ds[data_var_name].isel(lat=slice(lat_start, lat_stop), lon=slice(lon_start, lon_stop)).values.astype(np.float64, copy=False)
        parts.append(extract_features_for_var_from_block(events.reset_index(drop=True), block, WORKER_TIME_VALS, name))
    partial = parts[0] if len(parts) == 1 else merge_feature_frames(events[["event_uid"]].copy(), parts)
    partial.to_parquet(partial_path, index=False)
    return {"rows": int(len(partial)), "tile": (tile_row, tile_col), "path": str(partial_path), "label": label, "vars": variable_names}


def merge_tile_partial_shards(
    tile_tasks: list[tuple[str, str, int, int, int, int, str]],
    tile_partials: dict[str, list[Path]],
    progress_every: int = 100,
) -> None:
    total_tiles = len(tile_tasks)
    for tile_idx, (_, feature_path_str, _, _, _, _, label) in enumerate(tile_tasks, start=1):
        feature_path = Path(feature_path_str)
        if feature_path.exists():
            if tile_idx % max(1, progress_every) == 0 or tile_idx == total_tiles:
                print(
                    f"[TILE_MERGE][{label}] completed={tile_idx}/{total_tiles} reused_existing=1",
                    flush=True,
                )
            continue
        tile_key = feature_path.stem
        partial_paths = tile_partials.get(tile_key, [])
        base_df: pd.DataFrame | None = None
        parts: list[pd.DataFrame] = []
        for partial_path in partial_paths:
            if not partial_path.exists():
                continue
            part = pd.read_parquet(partial_path)
            if base_df is None:
                base_df = part[["event_uid"]].copy()
            parts.append(part)
        if base_df is None:
            pd.DataFrame({"event_uid": []}).to_parquet(feature_path, index=False)
            if tile_idx % max(1, progress_every) == 0 or tile_idx == total_tiles:
                print(
                    f"[TILE_MERGE][{label}] completed={tile_idx}/{total_tiles} rows=0",
                    flush=True,
                )
            continue
        merged = merge_feature_frames(base_df, parts)
        merged.to_parquet(feature_path, index=False)
        if tile_idx % max(1, progress_every) == 0 or tile_idx == total_tiles:
            print(
                f"[TILE_MERGE][{label}] completed={tile_idx}/{total_tiles} rows={len(merged)}",
                flush=True,
            )


def merge_shards(shard_paths: list[Path], output: Path) -> None:
    if output.exists():
        output.unlink()
    writer = None
    try:
        for shard_path in shard_paths:
            if not shard_path.exists():
                continue
            pf = pq.ParquetFile(shard_path)
            for batch in pf.iter_batches(batch_size=100000):
                table = pa.Table.from_batches([batch])
                if writer is None:
                    writer = pq.ParquetWriter(str(output), table.schema, compression="snappy")
                writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()


def build_label(args: argparse.Namespace) -> str:
    parts = [p for p in (args.metric, args.code_id, args.biome, args.drought_type, args.soil_layer) if p]
    return "-".join(str(p) for p in parts) if parts else "all-events"


def main() -> None:
    global ACTIVE_ERA5_VARIABLE_SPECS
    args = parse_args()
    ACTIVE_ERA5_VARIABLE_SPECS = resolve_era5_variable_specs(
        args.era5_root_dir,
        args.era5_file_suffix,
        total_precipitation_path=args.total_precipitation_path,
        total_evaporation_path=args.total_evaporation_path,
    )
    if args.variables:
        requested = [str(name) for name in args.variables]
        missing = [name for name in requested if name not in ACTIVE_ERA5_VARIABLE_SPECS]
        if missing:
            raise ValueError(
                f"Unknown --variables entries: {missing}. "
                f"Available={sorted(ACTIVE_ERA5_VARIABLE_SPECS)}"
            )
        ACTIVE_ERA5_VARIABLE_SPECS = {
            name: ACTIVE_ERA5_VARIABLE_SPECS[name] for name in requested
        }
    output = Path(args.output) if args.output else DATA_DIR / f"{feature_chunk_name('era5_features', args.metric, args.code_id, args.biome)}.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    label = build_label(args)

    with xr.open_dataset(next(iter(ACTIVE_ERA5_VARIABLE_SPECS.values())), cache=False) as grid_ds:
        lat_vals = grid_ds["lat"].values
        lon_vals = grid_ds["lon"].values

    work_root = output.parent / f"{output.stem}_tile_work"
    print(
        f"[MAIN] label={label} workers={args.workers} tile={args.tile_lat_size}x{args.tile_lon_size} output={output}",
        flush=True,
    )
    info = prepare_tile_tasks(
        master_path=MASTER_VALID_PATH,
        metric=args.metric,
        code_id=args.code_id,
        biome=args.biome,
        drought_type=args.drought_type,
        soil_layer=args.soil_layer,
        batch_size=args.batch_size,
        limit=args.limit,
        tile_lat_size=args.tile_lat_size,
        tile_lon_size=args.tile_lon_size,
        lat_vals=lat_vals,
        lon_vals=lon_vals,
        work_root=work_root,
        label=label,
        resume_existing_work_root=args.resume_existing_work_root,
    )

    tile_tasks = info["tile_tasks"]
    feature_shards = info["feature_shards"]
    if not tile_tasks:
        print("[MAIN] no tile tasks to process", flush=True)
        return

    total_tiles = len(tile_tasks)
    variable_batches = build_variable_batches(list(ACTIVE_ERA5_VARIABLE_SPECS.keys()), args.vars_per_task)
    variable_tasks, tile_partials = build_variable_tasks(
        tile_tasks,
        variable_batches,
        work_root,
        resume_existing_work_root=args.resume_existing_work_root,
    )
    worker_count = resolve_worker_count(
        requested_workers=args.workers,
        total_tiles=len(variable_tasks),
        concurrent_tasks=args.concurrent_era5_tasks,
        reserve_cpus=args.reserve_cpus,
        max_workers_cap=args.max_workers_cap,
    )
    log_every = compute_progress_every(total_tiles=len(variable_tasks), requested_every=args.progress_every)
    cpu_total = max(1, int(os.cpu_count() or 1))
    print(
        f"[MAIN] prepared total_tiles={total_tiles} total_var_tasks={len(variable_tasks)} "
        f"vars_per_task={max(1, int(args.vars_per_task))} worker_count={worker_count} "
        f"cpu_total={cpu_total} concurrent_tasks={max(1, int(args.concurrent_era5_tasks))} "
        f"reserve_cpus={max(0, int(args.reserve_cpus))} progress_every={log_every}",
        flush=True,
    )

    completed_var_tasks = 0
    completed_rows = 0
    tile_start_time = time.time()
    if variable_tasks:
        if worker_count == 1:
            init_worker_datasets()
            for task in variable_tasks:
                result = process_variable_task(task)
                completed_var_tasks += 1
                completed_rows += int(result["rows"])
                if completed_var_tasks % log_every == 0 or completed_var_tasks == len(variable_tasks):
                    print(
                        f"[VAR_TASK] completed={completed_var_tasks}/{len(variable_tasks)} rows={completed_rows} elapsed_s={time.time() - tile_start_time:.1f}",
                        flush=True,
                    )
        else:
            with ProcessPoolExecutor(max_workers=worker_count, initializer=init_worker_datasets) as executor:
                futures = {executor.submit(process_variable_task, task): task for task in variable_tasks}
                for future in as_completed(futures):
                    result = future.result()
                    completed_var_tasks += 1
                    completed_rows += int(result["rows"])
                    if completed_var_tasks % log_every == 0 or completed_var_tasks == len(variable_tasks):
                        print(
                            f"[VAR_TASK] completed={completed_var_tasks}/{len(variable_tasks)} rows={completed_rows} elapsed_s={time.time() - tile_start_time:.1f}",
                            flush=True,
                        )
    else:
        print("[VAR_TASK] no pending variable tasks; reusing existing partials", flush=True)

    print(f"[TILE_MERGE][{label}] tile_count={len(tile_tasks)} partial_task_count={len(variable_tasks)}", flush=True)
    merge_tile_partial_shards(tile_tasks, tile_partials)
    print(f"[MERGE][{label}] shard_count={len(feature_shards)} output={output}", flush=True)
    merge_shards(feature_shards, output)
    if args.keep_work_root:
        print(f"[KEEP_WORK_ROOT] preserved={work_root}", flush=True)
    else:
        shutil.rmtree(work_root, ignore_errors=True)
    print(f"[DONE] saved to {output}", flush=True)


if __name__ == "__main__":
    main()
