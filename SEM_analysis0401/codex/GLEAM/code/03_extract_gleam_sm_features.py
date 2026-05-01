#!/usr/bin/env python
"""Extract GLEAM soil-moisture event-window features with tile-based parallelism."""

from __future__ import annotations

import argparse
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
    GLEAM_SM_SPECS,
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
WORKER_TIME_VALS: np.ndarray | None = None
WORKER_GRID_SHAPE: tuple[int, int] = (0, 0)
ACTIVE_GLEAM_SM_SPECS: dict[str, Path] = dict(GLEAM_SM_SPECS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metric", default=None)
    parser.add_argument("--code-id", default=None)
    parser.add_argument("--biome", default=None)
    parser.add_argument("--drought-type", default=None)
    parser.add_argument("--soil-layer", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=200000)
    parser.add_argument("--tile-lat-size", type=int, default=32)
    parser.add_argument("--tile-lon-size", type=int, default=32)
    parser.add_argument("--output", default=None)
    parser.add_argument("--resume-existing-work-root", action="store_true")
    parser.add_argument("--keep-work-root", action="store_true")
    return parser.parse_args()


def resolve_active_gleam_sm_specs(candidate_groups: list[tuple[str, str]]) -> dict[str, Path]:
    soil_layers = {str(soil_layer) for soil_layer, _ in candidate_groups}
    return {name: path for name, path in GLEAM_SM_SPECS.items() if name in soil_layers}


def expected_feature_columns(active_var_names: list[str]) -> list[str]:
    columns = ["event_uid"]
    for var_name in active_var_names:
        stats_cfg = WINDOW_STATS[var_name]
        for phase, stats in stats_cfg.items():
            for stat in stats:
                columns.append(f"{phase}_{var_name}_{stat}")
    return columns


def feature_file_matches_expected_schema(feature_path: Path, expected_columns: list[str]) -> bool:
    if not feature_path.exists():
        return False
    schema = pq.read_schema(feature_path)
    return schema.names == expected_columns


def compute_stage_dates_from_row(row: pd.Series):
    onset_date = pd.Timestamp(row["onset_start_date"])
    drought_start = pd.Timestamp(row["drought_start_date"])
    peak_offset = row["t_peak_abs"]
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


def assign_chunk_indices(
    events: pd.DataFrame,
    lat_vals: np.ndarray,
    lon_vals: np.ndarray,
    lat_chunk_size: int,
    lon_chunk_size: int,
) -> pd.DataFrame:
    work = events.copy()
    work["lat_idx"] = [nearest_index(lat_vals, v) for v in work["lat"].to_numpy()]
    work["lon_idx"] = [nearest_index(lon_vals, v) for v in work["lon"].to_numpy()]
    work["lat_chunk_id"] = work["lat_idx"] // lat_chunk_size
    work["lon_chunk_id"] = work["lon_idx"] // lon_chunk_size
    work["lat_local_idx"] = work["lat_idx"] % lat_chunk_size
    work["lon_local_idx"] = work["lon_idx"] % lon_chunk_size
    return work


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
    group_label: str,
    stage: str,
    batch_idx: int,
    scanned_rows: int,
    matched_rows: int,
    cumulative_rows: int,
    elapsed_seconds: float,
) -> str:
    return (
        f"[{stage}][{group_label}] "
        f"batch={batch_idx} scanned={scanned_rows} matched={matched_rows} "
        f"cumulative={cumulative_rows} elapsed_s={elapsed_seconds:.1f}"
    )


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
            prefix_sum = np.concatenate([[0.0], np.cumsum(clean_series)])
            prefix_count = np.concatenate([[0], np.cumsum(valid_series)])

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
                    else:
                        values = batch_slice_stat(segment_series, phase_left, phase_right, stat)
                    results[f"{phase}_{var_name}_{stat}"][row_idx] = values
    return pd.DataFrame(results)


def init_worker_datasets() -> None:
    global WORKER_DATASETS, WORKER_TIME_VALS, WORKER_GRID_SHAPE
    WORKER_DATASETS = {name: xr.open_dataset(path, cache=False) for name, path in ACTIVE_GLEAM_SM_SPECS.items()}
    ref_name = next(iter(WORKER_DATASETS))
    ref_ds = WORKER_DATASETS[ref_name]
    WORKER_TIME_VALS = np.asarray(ref_ds["time"].values).astype("datetime64[D]")
    WORKER_GRID_SHAPE = (int(ref_ds.sizes["lat"]), int(ref_ds.sizes["lon"]))


def prepare_group_tile_tasks(
    master_path: Path,
    metric: str | None,
    code_id: str | None,
    biome: str | None,
    drought_type: str,
    soil_layer: str,
    batch_size: int,
    limit: int | None,
    tile_lat_size: int,
    tile_lon_size: int,
    lat_vals: np.ndarray,
    lon_vals: np.ndarray,
    work_root: Path,
    resume_existing_work_root: bool = False,
) -> dict[str, object]:
    group_label = f"{soil_layer}-{drought_type}"
    start_time = time.time()
    group_dir = work_root / group_label
    events_dir = group_dir / "events"
    features_dir = group_dir / "features"
    if resume_existing_work_root and events_dir.exists():
        tile_tasks, feature_shards = discover_existing_group_tile_tasks(
            events_dir=events_dir,
            features_dir=features_dir,
            tile_lat_size=tile_lat_size,
            tile_lon_size=tile_lon_size,
            group_label=group_label,
        )
        if tile_tasks:
            group_output = work_root / f"{group_label}_merged.parquet"
            print(f"[PREP_RESUME][{group_label}] reuse_events={len(tile_tasks)}", flush=True)
            return {
                "group_label": group_label,
                "tile_tasks": tile_tasks,
                "feature_shards": feature_shards,
                "group_output": group_output,
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
        f"[PREP_START][{group_label}] batch_size={batch_size} tile={tile_lat_size}x{tile_lon_size} limit={limit}",
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
                        group_label=group_label,
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
                group_label=group_label,
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
        print(f"[PREP_DONE][{group_label}] no matched events", flush=True)
        return {
            "group_label": group_label,
            "tile_tasks": [],
            "feature_shards": [],
            "group_output": None,
        }

    group_df = pd.concat(pieces, ignore_index=True)
    group_df.sort_values(["tile_row", "tile_col", "lat_idx", "lon_idx"], inplace=True, ignore_index=True)
    unique_tiles = int(group_df.groupby(["tile_row", "tile_col"], sort=False).ngroups)
    unique_pixels = int(group_df.groupby(["lat_idx", "lon_idx"], sort=False).ngroups)

    if group_dir.exists():
        shutil.rmtree(group_dir)
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
                group_label,
            )
        )
        feature_shards.append(feature_path)
        if tile_idx % 100 == 0:
            print(
                f"[PREP_TILE][{group_label}] tiles_written={tile_idx} elapsed_s={time.time() - start_time:.1f}",
                flush=True,
            )

    group_output = work_root / f"{group_label}_merged.parquet"
    print(
        f"[PREP_DONE][{group_label}] scanned={scanned_total} matched={matched_total} "
        f"unique_pixels={unique_pixels} unique_tiles={unique_tiles} elapsed_s={time.time() - start_time:.1f}",
        flush=True,
    )
    return {
        "group_label": group_label,
        "tile_tasks": tile_tasks,
        "feature_shards": feature_shards,
        "group_output": group_output,
        "matched_total": matched_total,
        "unique_tiles": unique_tiles,
        "unique_pixels": unique_pixels,
    }


def discover_existing_group_tile_tasks(
    events_dir: Path,
    features_dir: Path,
    tile_lat_size: int,
    tile_lon_size: int,
    group_label: str,
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
                group_label,
            )
        )
        feature_shards.append(feature_path)
    return tile_tasks, feature_shards


def process_tile_task(task: tuple[str, str, int, int, int, int, str]) -> dict[str, object]:
    event_path_str, feature_path_str, tile_row, tile_col, tile_lat_size, tile_lon_size, group_label = task
    event_path = Path(event_path_str)
    feature_path = Path(feature_path_str)
    events = pd.read_parquet(event_path)
    if events.empty:
        pd.DataFrame({"event_uid": []}).to_parquet(feature_path, index=False)
        return {"group_label": group_label, "rows": 0, "tile": (tile_row, tile_col), "path": str(feature_path)}

    lat_start = int(tile_row) * int(tile_lat_size)
    lon_start = int(tile_col) * int(tile_lon_size)
    lat_stop = min(lat_start + int(tile_lat_size), WORKER_GRID_SHAPE[0])
    lon_stop = min(lon_start + int(tile_lon_size), WORKER_GRID_SHAPE[1])

    base = events[["event_uid"]].copy()
    parts: list[pd.DataFrame] = []
    assert WORKER_TIME_VALS is not None
    for name, ds in WORKER_DATASETS.items():
        block = ds[name].isel(lat=slice(lat_start, lat_stop), lon=slice(lon_start, lon_stop)).values.astype(np.float64, copy=False)
        parts.append(extract_features_for_var_from_block(events.reset_index(drop=True), block, WORKER_TIME_VALS, name))
    merged = merge_feature_frames(base, parts)
    merged.to_parquet(feature_path, index=False)
    return {
        "group_label": group_label,
        "rows": int(len(merged)),
        "tile": (int(tile_row), int(tile_col)),
        "path": str(feature_path),
    }


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


def main() -> None:
    global ACTIVE_GLEAM_SM_SPECS
    args = parse_args()
    output = Path(args.output) if args.output else DATA_DIR / f"{feature_chunk_name('gleam_sm_features', args.metric, args.code_id, args.biome)}.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)

    candidate_groups = []
    if args.drought_type is not None and args.soil_layer is not None:
        candidate_groups = [(args.soil_layer, args.drought_type)]
    elif args.drought_type is not None:
        candidate_groups = [("SMrz", args.drought_type), ("SMs", args.drought_type)]
    elif args.soil_layer is not None:
        candidate_groups = [(args.soil_layer, "flash"), (args.soil_layer, "nonflash")]
    else:
        candidate_groups = [("SMrz", "flash"), ("SMrz", "nonflash"), ("SMs", "flash"), ("SMs", "nonflash")]
    ACTIVE_GLEAM_SM_SPECS = resolve_active_gleam_sm_specs(candidate_groups)
    expected_columns = expected_feature_columns(sorted(ACTIVE_GLEAM_SM_SPECS))

    with xr.open_dataset(GLEAM_SM_SPECS["SMrz"], cache=False) as grid_ds:
        lat_vals = grid_ds["lat"].values
        lon_vals = grid_ds["lon"].values

    work_root = output.parent / f"{output.stem}_tile_work"
    if work_root.exists() and not args.resume_existing_work_root:
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, exist_ok=True)

    print(
        f"[MAIN] groups={candidate_groups} workers={args.workers} tile={args.tile_lat_size}x{args.tile_lon_size} output={output}",
        flush=True,
    )

    group_infos: list[dict[str, object]] = []
    all_tile_tasks: list[tuple[str, str, int, int, int, int, str]] = []
    for soil_layer, drought_type in candidate_groups:
        info = prepare_group_tile_tasks(
            master_path=MASTER_VALID_PATH,
            metric=args.metric,
            code_id=args.code_id,
            biome=args.biome,
            drought_type=str(drought_type),
            soil_layer=str(soil_layer),
            batch_size=args.batch_size,
            limit=args.limit,
            tile_lat_size=args.tile_lat_size,
            tile_lon_size=args.tile_lon_size,
            lat_vals=lat_vals,
            lon_vals=lon_vals,
            work_root=work_root,
            resume_existing_work_root=args.resume_existing_work_root,
        )
        group_infos.append(info)
        all_tile_tasks.extend(info["tile_tasks"])

    if not all_tile_tasks:
        print("[MAIN] no tile tasks to process", flush=True)
        return

    pending_tile_tasks = []
    for task in all_tile_tasks:
        feature_path = Path(task[1])
        if args.resume_existing_work_root and feature_file_matches_expected_schema(feature_path, expected_columns):
            continue
        pending_tile_tasks.append(task)
    total_tiles = len(all_tile_tasks)
    worker_count = max(1, min(args.workers, total_tiles))
    print(
        f"[MAIN] prepared total_tiles={total_tiles} pending_tiles={len(pending_tile_tasks)} "
        f"worker_count={worker_count} active_layers={sorted(ACTIVE_GLEAM_SM_SPECS)}",
        flush=True,
    )

    completed_tiles = 0
    completed_rows = 0
    tile_start_time = time.time()
    if not pending_tile_tasks:
        print("[TILE] no pending tile tasks; reusing existing feature shards", flush=True)
    elif worker_count == 1:
        init_worker_datasets()
        for task in pending_tile_tasks:
            result = process_tile_task(task)
            completed_tiles += 1
            completed_rows += int(result["rows"])
            if completed_tiles % 25 == 0 or completed_tiles == len(pending_tile_tasks):
                print(
                    f"[TILE] completed={completed_tiles}/{len(pending_tile_tasks)} rows={completed_rows} elapsed_s={time.time() - tile_start_time:.1f}",
                    flush=True,
                )
    else:
        with ProcessPoolExecutor(max_workers=worker_count, initializer=init_worker_datasets) as executor:
            futures = {executor.submit(process_tile_task, task): task for task in pending_tile_tasks}
            for future in as_completed(futures):
                result = future.result()
                completed_tiles += 1
                completed_rows += int(result["rows"])
                if completed_tiles % 25 == 0 or completed_tiles == len(pending_tile_tasks):
                    print(
                        f"[TILE] completed={completed_tiles}/{len(pending_tile_tasks)} rows={completed_rows} elapsed_s={time.time() - tile_start_time:.1f}",
                        flush=True,
                    )

    group_outputs: list[Path] = []
    for info in group_infos:
        feature_shards = info["feature_shards"]
        group_output = info["group_output"]
        group_label = info["group_label"]
        if not feature_shards or group_output is None:
            continue
        print(f"[MERGE][{group_label}] shard_count={len(feature_shards)} output={group_output}", flush=True)
        merge_shards(feature_shards, group_output)
        group_outputs.append(group_output)

    print(f"[MAIN] merge_final outputs={len(group_outputs)} target={output}", flush=True)
    merge_shards(group_outputs, output)
    if args.keep_work_root:
        print(f"[KEEP_WORK_ROOT] preserved={work_root}", flush=True)
    else:
        shutil.rmtree(work_root, ignore_errors=True)
    print(f"[DONE] saved to {output}", flush=True)


if __name__ == "__main__":
    main()
