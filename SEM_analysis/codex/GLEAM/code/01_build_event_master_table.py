#!/usr/bin/env python
"""Build the unified GLEAM event master table with chunked, low-memory I/O."""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import xarray as xr

from sem_gleam_common import (
    COMMON_EVENT_FIELDS,
    EVENT_COUNT_SUMMARY_PATH,
    EXCLUDE_IGBP,
    MASTER_ALL_PATH,
    MASTER_VALID_PATH,
    METRIC_FIELDS,
    UNIFIED_METRIC_COLUMNS,
    add_event_dates,
    assign_igbp_class_by_unique_coords,
    biome_from_igbp,
    build_event_uid,
    get_target_specs,
    load_landuse_raster,
    optimize_event_frame_dtypes,
)

ANTI_ALL_PATH = Path("/home/xulc/flash_drought/process/SEM_analysis/anti/GLEAM/data/event_master_table_all.parquet")
ANTI_VALID_PATH = Path("/home/xulc/flash_drought/process/SEM_analysis/anti/GLEAM/data/event_master_table_valid.parquet")
ANTI_SUMMARY_PATH = Path("/home/xulc/flash_drought/process/SEM_analysis/anti/GLEAM/data/event_count_summary.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-anti", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=250000)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def iter_event_frame_chunks(spec, chunk_size: int):
    ds = xr.open_dataset(spec.path)
    total = ds.sizes["event"]
    available_common = [field for field in COMMON_EVENT_FIELDS if field in ds]
    available_metric = {
        raw_name: unified_name
        for raw_name, unified_name in zip(METRIC_FIELDS[spec.metric], UNIFIED_METRIC_COLUMNS)
    }
    try:
        for start in range(0, total, chunk_size):
            stop = min(start + chunk_size, total)
            sl = slice(start, stop)
            data = {}
            for field in available_common:
                data[field] = ds[field].isel(event=sl).values
            for raw_name, unified_name in available_metric.items():
                if raw_name in ds:
                    data[unified_name] = ds[raw_name].isel(event=sl).values
                else:
                    data[unified_name] = np.full(stop - start, np.nan, dtype=np.float32)
            df = pd.DataFrame(data)
            df["metric"] = spec.metric
            df["code_id"] = spec.code_id
            df["drought_type"] = spec.drought_type
            df["soil_layer"] = spec.soil_layer
            yield df
    finally:
        ds.close()


def enrich_chunk(df: pd.DataFrame, lu_data, lu_transform, lu_nodata, workers: int) -> pd.DataFrame:
    out = df.copy()
    out["igbp_class"] = assign_igbp_class_by_unique_coords(
        out["lat"].values,
        out["lon"].values,
        lu_data,
        lu_transform,
        lu_nodata,
        max_workers=workers,
    )
    out["biome"] = [biome_from_igbp(v) for v in out["igbp_class"].values]
    out["event_uid"] = build_event_uid(out)
    out = add_event_dates(out)
    out = optimize_event_frame_dtypes(out)
    return out


def compute_valid_mask(df: pd.DataFrame) -> pd.Series:
    mask_lu = df["lu_event_valid"] == 1
    mask_igbp = ~df["igbp_class"].isin(EXCLUDE_IGBP)
    mask_resp = df["response_detected"] == 1
    mask_rec = np.isfinite(df["t_recover_to_baseline_abs_peak"]) & (
        df["t_recover_to_baseline_abs_peak"] >= 0
    )
    mask_coord = np.isfinite(df["lat"]) & np.isfinite(df["lon"])
    return mask_lu & mask_igbp & mask_resp & mask_rec & mask_coord


def write_chunk(writer, df: pd.DataFrame):
    table = pa.Table.from_pandas(df, preserve_index=False)
    if writer is None:
        writer = pq.ParquetWriter(writer.path, table.schema, compression="snappy")
    writer.write_table(table)
    return writer


class WriterBox:
    def __init__(self, path: Path):
        self.path = str(path)
        self.writer = None

    def write(self, df: pd.DataFrame):
        table = pa.Table.from_pandas(df, preserve_index=False)
        if self.writer is None:
            self.writer = pq.ParquetWriter(self.path, table.schema, compression="snappy")
        self.writer.write_table(table)

    def close(self):
        if self.writer is not None:
            self.writer.close()


def prepare_tmp_path(path: Path) -> Path:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if tmp.exists():
        tmp.unlink()
    if path.exists():
        path.unlink()
    return tmp


def finalize_tmp_path(tmp_path: Path, final_path: Path) -> None:
    if tmp_path.exists():
        tmp_path.replace(final_path)


def stream_copy_parquet(source: Path, target: Path, batch_size: int) -> None:
    pf = pq.ParquetFile(source)
    writer = WriterBox(target)
    try:
        for batch in pf.iter_batches(batch_size=batch_size):
            df = batch.to_pandas()
            if "event_uid" not in df.columns:
                df["event_uid"] = build_event_uid(df)
            if "onset_start_date" not in df.columns or "drought_start_date" not in df.columns:
                df = add_event_dates(df)
            df = optimize_event_frame_dtypes(df)
            writer.write(df)
    finally:
        writer.close()


def build_from_anti_streaming(chunk_size: int) -> None:
    all_tmp = prepare_tmp_path(MASTER_ALL_PATH)
    valid_tmp = prepare_tmp_path(MASTER_VALID_PATH)
    stream_copy_parquet(ANTI_ALL_PATH, all_tmp, chunk_size)
    stream_copy_parquet(ANTI_VALID_PATH, valid_tmp, chunk_size)
    shutil.copy2(ANTI_SUMMARY_PATH, EVENT_COUNT_SUMMARY_PATH)
    finalize_tmp_path(all_tmp, MASTER_ALL_PATH)
    finalize_tmp_path(valid_tmp, MASTER_VALID_PATH)


def main() -> None:
    args = parse_args()
    t0 = time.time()

    if args.reuse_anti:
        print("[INFO] Streaming anti/GLEAM parquet into codex output")
        build_from_anti_streaming(args.chunk_size)
        print(f"[DONE] all table  : {MASTER_ALL_PATH}")
        print(f"[DONE] valid table: {MASTER_VALID_PATH}")
        print(f"[DONE] summary    : {EVENT_COUNT_SUMMARY_PATH}")
        print(f"[DONE] elapsed    : {time.time() - t0:.1f}s")
        return

    lu_data, lu_transform, lu_nodata = load_landuse_raster()
    all_tmp = prepare_tmp_path(MASTER_ALL_PATH)
    valid_tmp = prepare_tmp_path(MASTER_VALID_PATH)
    all_writer = WriterBox(all_tmp)
    valid_writer = WriterBox(valid_tmp)
    summary_rows = []
    total_all = 0
    total_valid = 0

    try:
        for spec in get_target_specs():
            if not spec.path.exists():
                print(f"[WARN] Missing file: {spec.path}")
                continue
            print(f"[INFO] Processing {spec.metric} {spec.code_id} -> {spec.path.name}")
            group_value_store = {}
            for chunk_i, chunk in enumerate(iter_event_frame_chunks(spec, args.chunk_size), start=1):
                enriched = enrich_chunk(chunk, lu_data, lu_transform, lu_nodata, args.workers)
                total_all += len(enriched)
                all_writer.write(enriched)

                valid = enriched.loc[compute_valid_mask(enriched)].copy()
                if not valid.empty:
                    total_valid += len(valid)
                    valid_writer.write(valid)
                    for biome, values in valid.groupby("biome", observed=True)["t_recover_to_baseline_abs_peak"]:
                        group_value_store.setdefault(str(biome), []).append(values.to_numpy(dtype=np.float32))

                print(
                    f"  [chunk {chunk_i}] all={len(enriched):,} valid={len(valid):,} "
                    f"running_all={total_all:,} running_valid={total_valid:,}"
                )

            for biome, arrays in group_value_store.items():
                values = np.concatenate(arrays) if arrays else np.array([], dtype=np.float32)
                if values.size == 0:
                    continue
                summary_rows.append(
                    {
                        "biome": biome,
                        "metric": spec.metric,
                        "code_id": spec.code_id,
                        "drought_type": spec.drought_type,
                        "soil_layer": spec.soil_layer,
                        "n_events": int(values.size),
                        "mean_recovery_time": float(values.mean()),
                        "median_recovery_time": float(np.median(values)),
                    }
                )
    finally:
        all_writer.close()
        valid_writer.close()

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(EVENT_COUNT_SUMMARY_PATH, index=False)
    finalize_tmp_path(all_tmp, MASTER_ALL_PATH)
    finalize_tmp_path(valid_tmp, MASTER_VALID_PATH)

    print(f"[DONE] all rows   : {total_all:,}")
    print(f"[DONE] valid rows : {total_valid:,}")
    print(f"[DONE] all table  : {MASTER_ALL_PATH}")
    print(f"[DONE] valid table: {MASTER_VALID_PATH}")
    print(f"[DONE] summary    : {EVENT_COUNT_SUMMARY_PATH}")
    print(f"[DONE] elapsed    : {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
