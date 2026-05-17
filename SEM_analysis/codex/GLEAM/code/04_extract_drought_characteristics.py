#!/usr/bin/env python
"""Match event-level drought morphology fields from the original GLEAM event library."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import xarray as xr

from sem_gleam_common import (
    DATA_DIR,
    EVENT_ATTRIBUTE_FIELDS,
    MASTER_VALID_PATH,
    build_event_uid,
    feature_chunk_name,
    get_event_file_path,
    nearest_index,
    read_subset_filters,
)

REQUIRED_COLUMNS = [
    "event_uid",
    "metric",
    "code_id",
    "biome",
    "soil_layer",
    "drought_type",
    "lat",
    "lon",
    "event_id",
    "onset_year",
    "onset_doy",
    "drought_start_year",
    "drought_start_doy",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metric", default=None)
    parser.add_argument("--code-id", default=None)
    parser.add_argument("--biome", default=None)
    parser.add_argument("--drought-type", default=None)
    parser.add_argument("--soil-layer", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=100000)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def build_slot_lookup_for_pixel(ds: xr.Dataset, lat_idx: int, lon_idx: int) -> dict[tuple[int, int, int, int], int]:
    count = int(ds["event_count"].isel(lat=lat_idx, lon=lon_idx).item())
    if count <= 0:
        return {}
    onset_year = ds["onset_start_year"].values[:count, lat_idx, lon_idx]
    onset_doy = ds["onset_start_doy"].values[:count, lat_idx, lon_idx]
    drought_year = ds["drought_start_year"].values[:count, lat_idx, lon_idx]
    drought_doy = ds["drought_start_doy"].values[:count, lat_idx, lon_idx]
    lookup = {}
    for slot in range(count):
        key = (
            int(onset_year[slot]),
            int(onset_doy[slot]),
            int(drought_year[slot]),
            int(drought_doy[slot]),
        )
        lookup[key] = slot
    return lookup


def assign_slots_for_pixel(pixel_df: pd.DataFrame, slot_lookup: dict[tuple[int, int, int, int], int]) -> np.ndarray:
    slots = np.full(len(pixel_df), -1, dtype=np.int32)
    event_ids = pd.to_numeric(pixel_df["event_id"], errors="coerce").fillna(-1).astype(int).to_numpy()
    for i, (_, row) in enumerate(pixel_df.iterrows()):
        key = (
            int(row["onset_year"]),
            int(row["onset_doy"]),
            int(row["drought_start_year"]),
            int(row["drought_start_doy"]),
        )
        slot = slot_lookup.get(key, -1)
        if slot < 0:
            event_id = event_ids[i]
            if event_id >= 0:
                slot = event_id
        slots[i] = slot
    return slots


def extract_field_values_for_pixel(ds: xr.Dataset, field: str, lat_idx: int, lon_idx: int, slots: np.ndarray) -> np.ndarray:
    values = np.full(len(slots), np.nan, dtype=np.float32)
    valid_mask = slots >= 0
    if not valid_mask.any():
        return values
    field_values = ds[field].values[:, lat_idx, lon_idx]
    picked = field_values[slots[valid_mask]]
    fill_value = ds[field].attrs.get("_FillValue", ds[field].encoding.get("_FillValue", None))
    picked = picked.astype(np.float32, copy=False)
    if fill_value is not None:
        picked = np.where(picked == fill_value, np.nan, picked)
    values[valid_mask] = picked
    return values


def match_single_group(events: pd.DataFrame, ds: xr.Dataset) -> pd.DataFrame:
    results = {"event_uid": events["event_uid"].values}
    for field in EVENT_ATTRIBUTE_FIELDS:
        results[f"event_{field}"] = np.full(len(events), np.nan, dtype=np.float32)

    lat_vals = ds["lat"].values
    lon_vals = ds["lon"].values
    work = events.copy()
    work["lat_idx"] = [nearest_index(lat_vals, v) for v in work["lat"].to_numpy()]
    work["lon_idx"] = [nearest_index(lon_vals, v) for v in work["lon"].to_numpy()]

    for (lat_idx, lon_idx), pixel_df in work.groupby(["lat_idx", "lon_idx"], sort=False):
        slot_lookup = build_slot_lookup_for_pixel(ds, int(lat_idx), int(lon_idx))
        if not slot_lookup:
            continue
        slots = assign_slots_for_pixel(pixel_df, slot_lookup)
        target_positions = pixel_df.index.to_numpy()
        for field in EVENT_ATTRIBUTE_FIELDS:
            values = extract_field_values_for_pixel(ds, field, int(lat_idx), int(lon_idx), slots)
            results[f"event_{field}"][target_positions] = values

    return pd.DataFrame(results)


def match_event_attributes(events: pd.DataFrame) -> pd.DataFrame:
    outputs = []
    for (soil_layer, drought_type), subset in events.groupby(["soil_layer", "drought_type"], sort=False, observed=True):
        event_path = get_event_file_path(str(soil_layer), str(drought_type))
        print(f"[INFO] Matching {soil_layer} {drought_type} from {event_path.name}")
        ds = xr.open_dataset(event_path)
        try:
            outputs.append(match_single_group(subset, ds))
        finally:
            ds.close()
    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame({"event_uid": []})


class ShardWriter:
    def __init__(self, path: Path):
        self.path = path
        self.writer = None

    def write_df(self, df: pd.DataFrame) -> None:
        if df.empty:
            return
        table = pa.Table.from_pandas(df, preserve_index=False)
        if self.writer is None:
            self.writer = pq.ParquetWriter(str(self.path), table.schema, compression="snappy")
        self.writer.write_table(table)

    def close(self) -> None:
        if self.writer is not None:
            self.writer.close()


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


def process_group_streaming_to_shard(args_tuple) -> str:
    (
        master_path,
        shard_path,
        metric,
        code_id,
        biome,
        drought_type,
        soil_layer,
        batch_size,
        limit,
    ) = args_tuple
    event_path = get_event_file_path(str(soil_layer), str(drought_type))
    ds = xr.open_dataset(event_path)
    writer = ShardWriter(shard_path)
    pf = pq.ParquetFile(master_path)
    remaining = limit
    try:
        for batch in pf.iter_batches(columns=REQUIRED_COLUMNS, batch_size=batch_size):
            batch_df = batch.to_pandas()
            batch_df = filter_master_batch(batch_df, metric, code_id, biome, drought_type, soil_layer)
            if batch_df.empty:
                continue
            if remaining is not None:
                if remaining <= 0:
                    break
                batch_df = batch_df.head(remaining).copy()
                remaining -= len(batch_df)
            matched = match_single_group(batch_df.reset_index(drop=True), ds)
            writer.write_df(matched)
            if remaining is not None and remaining <= 0:
                break
    finally:
        writer.close()
        ds.close()
    return str(shard_path)


def merge_shards(shard_paths: list[Path], output: Path) -> None:
    writer = None
    try:
        for shard_path in shard_paths:
            if not shard_path.exists():
                continue
            pf = pq.ParquetFile(shard_path)
            for batch in pf.iter_batches(batch_size=200000):
                table = pa.Table.from_batches([batch])
                if writer is None:
                    writer = pq.ParquetWriter(str(output), table.schema, compression="snappy")
                writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()


def cleanup_shards(shard_paths: list[Path]) -> None:
    for shard_path in shard_paths:
        if shard_path.exists():
            shard_path.unlink()


def main() -> None:
    args = parse_args()
    output = Path(args.output) if args.output else DATA_DIR / f"{feature_chunk_name('drought_event_features', args.metric, args.code_id, args.biome)}.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)

    group_tasks = []
    shard_paths = []
    candidate_groups = []
    if args.drought_type is not None and args.soil_layer is not None:
        candidate_groups = [(args.soil_layer, args.drought_type)]
    elif args.drought_type is not None:
        candidate_groups = [("SMrz", args.drought_type), ("SMs", args.drought_type)]
    elif args.soil_layer is not None:
        candidate_groups = [(args.soil_layer, "flash"), (args.soil_layer, "nonflash")]
    else:
        candidate_groups = [("SMrz", "flash"), ("SMrz", "nonflash"), ("SMs", "flash"), ("SMs", "nonflash")]

    if args.limit is not None:
        events = pd.read_parquet(MASTER_VALID_PATH, columns=REQUIRED_COLUMNS)
        if "event_uid" not in events.columns:
            events["event_uid"] = build_event_uid(events)
        events = read_subset_filters(events, args.metric, args.code_id, args.biome)
        events = filter_master_batch(
            events,
            None,
            None,
            None,
            args.drought_type,
            args.soil_layer,
        )
        events = events.head(args.limit).reset_index(drop=True)
        for i, ((soil_layer, drought_type), subset) in enumerate(
            events.groupby(["soil_layer", "drought_type"], sort=False, observed=True)
        ):
            shard_path = output.with_name(f"{output.stem}_shard_{i}_{soil_layer}_{drought_type}.parquet")
            shard_paths.append(shard_path)
            group_tasks.append(("INLINE", shard_path, subset.copy(), str(soil_layer), str(drought_type)))
    else:
        for i, (soil_layer, drought_type) in enumerate(candidate_groups):
            shard_path = output.with_name(f"{output.stem}_shard_{i}_{soil_layer}_{drought_type}.parquet")
            shard_paths.append(shard_path)
            group_tasks.append(
                (
                    MASTER_VALID_PATH,
                    shard_path,
                    args.metric,
                    args.code_id,
                    args.biome,
                    str(drought_type),
                    str(soil_layer),
                    args.batch_size,
                    None,
                )
            )

    for shard_path in shard_paths:
        if shard_path.exists():
            shard_path.unlink()

    if args.limit is not None:
        for task in group_tasks:
            _, shard_path, subset, soil_layer, drought_type = task
            ds = xr.open_dataset(get_event_file_path(soil_layer, drought_type))
            try:
                matched = match_single_group(subset, ds)
            finally:
                ds.close()
            matched.to_parquet(shard_path, index=False)
    elif args.workers <= 1 or len(group_tasks) <= 1:
        for task in group_tasks:
            process_group_streaming_to_shard(task)
    else:
        with ProcessPoolExecutor(max_workers=min(args.workers, len(group_tasks))) as executor:
            list(executor.map(process_group_streaming_to_shard, group_tasks))

    merge_shards(shard_paths, output)
    cleanup_shards(shard_paths)
    print(f"[DONE] saved to {output}")


if __name__ == "__main__":
    main()
