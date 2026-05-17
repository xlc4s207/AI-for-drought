#!/usr/bin/env python
"""Python ERA5 rechunker with bounded parallel reads and single-process writes."""

from __future__ import annotations

import argparse
import os
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Iterable

import netCDF4 as nc
import numpy as np


def infer_primary_variable_name(ds: nc.Dataset) -> str:
    candidates: list[str] = []
    for name, var in ds.variables.items():
        if tuple(var.dimensions) == ("time", "lat", "lon"):
            candidates.append(name)
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one primary variable, found {candidates}")
    return candidates[0]


def build_time_slices(total_time: int, time_chunk: int) -> list[tuple[int, int]]:
    if total_time < 0:
        raise ValueError("total_time must be non-negative")
    if time_chunk <= 0:
        raise ValueError("time_chunk must be positive")
    return [(start, min(start + time_chunk, total_time)) for start in range(0, total_time, time_chunk)]


def _copy_dimensions(src: nc.Dataset, dst: nc.Dataset) -> None:
    for name, dim in src.dimensions.items():
        size = None if dim.isunlimited() else len(dim)
        dst.createDimension(name, size)


def _copy_fixed_variables(src: nc.Dataset, dst: nc.Dataset, data_var_name: str) -> None:
    for name, var in src.variables.items():
        if name == data_var_name:
            continue
        out = dst.createVariable(name, var.datatype, var.dimensions)
        out.setncatts({attr: var.getncattr(attr) for attr in var.ncattrs()})
        out[:] = var[:]


def _create_output_data_variable(
    src: nc.Dataset,
    dst: nc.Dataset,
    data_var_name: str,
    target_time_chunk: int,
    target_lat_chunk: int,
    target_lon_chunk: int,
):
    src_var = src.variables[data_var_name]
    out = dst.createVariable(
        data_var_name,
        src_var.datatype,
        src_var.dimensions,
        zlib=True,
        complevel=1,
        shuffle=True,
        chunksizes=(target_time_chunk, target_lat_chunk, target_lon_chunk),
    )
    out.setncatts({attr: src_var.getncattr(attr) for attr in src_var.ncattrs() if attr != "_FillValue"})
    return out


def _copy_global_attributes(src: nc.Dataset, dst: nc.Dataset) -> None:
    dst.setncatts({attr: src.getncattr(attr) for attr in src.ncattrs()})


def _read_time_slice(input_path: str, data_var_name: str, start: int, stop: int) -> tuple[int, int, np.ndarray]:
    with nc.Dataset(input_path, "r") as ds:
        var = ds.variables[data_var_name]
        if hasattr(var, "set_auto_mask"):
            var.set_auto_mask(False)
        values = np.asarray(var[start:stop, :, :])
    return start, stop, values


def _iter_completed(futures: dict, max_pending: int, executor: ProcessPoolExecutor, pending_iter: Iterable[tuple[int, int]], input_path: Path, data_var_name: str):
    while futures:
        done, _ = wait(futures, return_when=FIRST_COMPLETED)
        for future in done:
            time_slice = futures.pop(future)
            yield future.result()
            for _ in range(max_pending - len(futures)):
                try:
                    next_slice = next(pending_iter)
                except StopIteration:
                    break
                futures[executor.submit(_read_time_slice, str(input_path), data_var_name, *next_slice)] = next_slice


def rechunk_file(
    input_path: Path,
    output_path: Path,
    time_chunk: int,
    read_workers: int,
    max_pending: int,
    target_time_chunk: int,
    target_lat_chunk: int,
    target_lon_chunk: int,
) -> None:
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(f"{output_path}.lock")
    tmp_output_path = Path(f"{output_path}.tmp")

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError as exc:
        raise RuntimeError(f"lock exists, output may already be in progress: {lock_path}") from exc

    try:
        with nc.Dataset(input_path, "r") as src:
            data_var_name = infer_primary_variable_name(src)
            total_time = len(src.dimensions["time"])
            _copy_template_to_output(
                src=src,
                output_path=tmp_output_path,
                data_var_name=data_var_name,
                target_time_chunk=target_time_chunk,
                target_lat_chunk=target_lat_chunk,
                target_lon_chunk=target_lon_chunk,
            )

        time_slices = build_time_slices(total_time, time_chunk)
        print(
            f"[RECHUNK] input={input_path} output={output_path} total_time={total_time} "
            f"time_chunk={time_chunk} read_workers={read_workers} max_pending={max_pending} "
            f"target_chunk={target_time_chunk}x{target_lat_chunk}x{target_lon_chunk}",
            flush=True,
        )
        completed = 0

        with nc.Dataset(tmp_output_path, "r+") as dst:
            out_var = dst.variables[data_var_name]
            if read_workers <= 1:
                for start, stop in time_slices:
                    _, _, values = _read_time_slice(str(input_path), data_var_name, start, stop)
                    out_var[start:stop, :, :] = values
                    completed += 1
                    print(f"[RECHUNK] completed_slices={completed}/{len(time_slices)} stop={stop}", flush=True)
            else:
                pending_iter = iter(time_slices)
                futures = {}
                max_pending = max(1, int(max_pending))
                with ProcessPoolExecutor(max_workers=read_workers) as executor:
                    for _ in range(min(max_pending, len(time_slices))):
                        time_slice = next(pending_iter, None)
                        if time_slice is None:
                            break
                        futures[executor.submit(_read_time_slice, str(input_path), data_var_name, *time_slice)] = time_slice
                    for start, stop, values in _iter_completed(
                        futures=futures,
                        max_pending=max_pending,
                        executor=executor,
                        pending_iter=pending_iter,
                        input_path=input_path,
                        data_var_name=data_var_name,
                    ):
                        out_var[start:stop, :, :] = values
                        completed += 1
                        print(f"[RECHUNK] completed_slices={completed}/{len(time_slices)} stop={stop}", flush=True)

        if output_path.exists():
            output_path.unlink()
        tmp_output_path.replace(output_path)
        print(f"[RECHUNK] done output={output_path}", flush=True)
    finally:
        if tmp_output_path.exists():
            tmp_output_path.unlink()
        if lock_path.exists():
            lock_path.unlink()


def _copy_template_to_output(
    src: nc.Dataset,
    output_path: Path,
    data_var_name: str,
    target_time_chunk: int,
    target_lat_chunk: int,
    target_lon_chunk: int,
) -> None:
    if output_path.exists():
        output_path.unlink()
    with nc.Dataset(output_path, "w", format="NETCDF4_CLASSIC") as dst:
        _copy_dimensions(src, dst)
        _copy_fixed_variables(src, dst, data_var_name)
        _create_output_data_variable(
            src=src,
            dst=dst,
            data_var_name=data_var_name,
            target_time_chunk=target_time_chunk,
            target_lat_chunk=target_lat_chunk,
            target_lon_chunk=target_lon_chunk,
        )
        _copy_global_attributes(src, dst)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--time-chunk", type=int, default=64)
    parser.add_argument("--read-workers", type=int, default=2)
    parser.add_argument("--max-pending", type=int, default=2)
    parser.add_argument("--target-time-chunk", type=int, default=256)
    parser.add_argument("--target-lat-chunk", type=int, default=32)
    parser.add_argument("--target-lon-chunk", type=int, default=32)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rechunk_file(
        input_path=Path(args.input),
        output_path=Path(args.output),
        time_chunk=args.time_chunk,
        read_workers=args.read_workers,
        max_pending=args.max_pending,
        target_time_chunk=args.target_time_chunk,
        target_lat_chunk=args.target_lat_chunk,
        target_lon_chunk=args.target_lon_chunk,
    )


if __name__ == "__main__":
    main()
