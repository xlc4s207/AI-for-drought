#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import argparse
import math
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from glob import glob
from pathlib import Path

import netCDF4 as nc
import numpy as np
from scipy import sparse


FILE_RE = re.compile(r"GPP_FluxSat_daily_v2_(\d{4})(\d{2})\.nc4$")
DEFAULT_INPUT_DIR = "/data/Fluxsat"
DEFAULT_OUTPUT_DIR = (
    "/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results/monthly_025deg"
)
GLEAM_EVENT_FILE = (
    "/home/xulc/flash_drought/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/"
    "flash_lt20_drought_events_v5.4.nc"
)


@dataclass(frozen=True)
class MonthlyFile:
    year: int
    month: int
    path: str


@dataclass(frozen=True)
class GridSpec:
    lat: np.ndarray
    lon: np.ndarray


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def discover_monthly_files(input_dir: str, start_year: int, end_year: int) -> list[MonthlyFile]:
    items: list[MonthlyFile] = []
    for path in sorted(glob(os.path.join(input_dir, "GPP_FluxSat_daily_v2_*.nc4"))):
        m = FILE_RE.search(os.path.basename(path))
        if not m:
            continue
        year = int(m.group(1))
        month = int(m.group(2))
        if start_year <= year <= end_year:
            items.append(MonthlyFile(year=year, month=month, path=path))
    if not items:
        raise FileNotFoundError(f"no FluxSat monthly files found in {input_dir} for {start_year}-{end_year}")
    return items


def output_path_for(output_dir: str, year: int, month: int) -> str:
    return os.path.join(output_dir, f"FluxSat_GPP_{year}{month:02d}_0.25deg.nc")


def centers_to_edges(centers: np.ndarray) -> np.ndarray:
    deltas = np.diff(centers)
    edges = np.empty(centers.size + 1, dtype=np.float64)
    edges[1:-1] = centers[:-1] + deltas / 2.0
    edges[0] = centers[0] - deltas[0] / 2.0
    edges[-1] = centers[-1] + deltas[-1] / 2.0
    return edges


def build_overlap_matrix(src_edges: np.ndarray, dst_edges: np.ndarray, area_weighted: bool) -> sparse.csr_matrix:
    src_lo = src_edges[:-1]
    src_hi = src_edges[1:]
    dst_lo = dst_edges[:-1]
    dst_hi = dst_edges[1:]
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    i = 0
    j = 0
    eps = 1.0e-12
    while i < src_lo.size and j < dst_lo.size:
        overlap_lo = max(src_lo[i], dst_lo[j])
        overlap_hi = min(src_hi[i], dst_hi[j])
        if overlap_hi > overlap_lo + eps:
            if area_weighted:
                weight = math.sin(math.radians(overlap_hi)) - math.sin(math.radians(overlap_lo))
            else:
                weight = overlap_hi - overlap_lo
            rows.append(i)
            cols.append(j)
            data.append(weight)
        if src_hi[i] <= dst_hi[j] + eps:
            i += 1
        else:
            j += 1
    return sparse.csr_matrix(
        (np.asarray(data, dtype=np.float32), (rows, cols)),
        shape=(src_lo.size, dst_lo.size),
        dtype=np.float32,
    )


def load_target_grid() -> GridSpec:
    with nc.Dataset(GLEAM_EVENT_FILE, "r") as ds:
        lat = np.asarray(ds.variables["lat"][:], dtype=np.float32)
        lon = np.asarray(ds.variables["lon"][:], dtype=np.float32)
    return GridSpec(lat=lat, lon=lon)


def build_weight_matrices(src_lat: np.ndarray, src_lon: np.ndarray, dst_grid: GridSpec):
    src_lat_edges = centers_to_edges(np.asarray(src_lat, dtype=np.float64))
    src_lon_edges = centers_to_edges(np.asarray(src_lon, dtype=np.float64))
    dst_lat_edges = centers_to_edges(np.asarray(dst_grid.lat, dtype=np.float64))
    dst_lon_edges = centers_to_edges(np.asarray(dst_grid.lon, dtype=np.float64))
    w_lat = build_overlap_matrix(src_lat_edges, dst_lat_edges, area_weighted=True)
    w_lon = build_overlap_matrix(src_lon_edges, dst_lon_edges, area_weighted=False)
    return w_lat, w_lon


def weighted_remap(values: np.ndarray, valid: np.ndarray, w_lat: sparse.csr_matrix, w_lon: sparse.csr_matrix) -> np.ndarray:
    time_size, src_lat_size, src_lon_size = values.shape
    filled = np.where(valid, values, 0.0).astype(np.float32, copy=False)
    weights = valid.astype(np.float32, copy=False)

    num_lon = (filled.reshape(time_size * src_lat_size, src_lon_size) @ w_lon).reshape(
        time_size, src_lat_size, w_lon.shape[1]
    )
    den_lon = (weights.reshape(time_size * src_lat_size, src_lon_size) @ w_lon).reshape(
        time_size, src_lat_size, w_lon.shape[1]
    )

    num_lat = (
        np.transpose(num_lon, (0, 2, 1)).reshape(time_size * w_lon.shape[1], src_lat_size) @ w_lat
    ).reshape(time_size, w_lon.shape[1], w_lat.shape[1]).transpose(0, 2, 1)
    den_lat = (
        np.transpose(den_lon, (0, 2, 1)).reshape(time_size * w_lon.shape[1], src_lat_size) @ w_lat
    ).reshape(time_size, w_lon.shape[1], w_lat.shape[1]).transpose(0, 2, 1)

    output = np.full((time_size, w_lat.shape[1], w_lon.shape[1]), np.nan, dtype=np.float32)
    np.divide(num_lat, den_lat, out=output, where=den_lat > 0.0)
    return output


def copy_attrs(src_var, dst_var, skip: set[str] | None = None) -> None:
    skip = skip or set()
    for attr in src_var.ncattrs():
        if attr in skip:
            continue
        dst_var.setncattr(attr, src_var.getncattr(attr))


def create_output_dataset(
    src_ds: nc.Dataset,
    output_path: str,
    dst_grid: GridSpec,
    chunk_size: int,
    complevel: int,
) -> tuple[nc.Dataset, dict[str, nc.Variable]]:
    dst_ds = nc.Dataset(output_path, "w", format="NETCDF4")
    dst_ds.createDimension("time", None)
    dst_ds.createDimension("lat", len(dst_grid.lat))
    dst_ds.createDimension("lon", len(dst_grid.lon))

    time_var = dst_ds.createVariable("time", src_ds.variables["time"].dtype, ("time",))
    lat_var = dst_ds.createVariable("lat", "f4", ("lat",))
    lon_var = dst_ds.createVariable("lon", "f4", ("lon",))
    gpp_var = dst_ds.createVariable(
        "GPP",
        "f4",
        ("time", "lat", "lon"),
        zlib=complevel > 0,
        complevel=complevel,
        fill_value=np.float32(np.nan),
        chunksizes=(max(1, min(chunk_size, 16)), len(dst_grid.lat), len(dst_grid.lon)),
    )
    unc_var = dst_ds.createVariable(
        "GPP_uncertainty",
        "f4",
        ("time", "lat", "lon"),
        zlib=complevel > 0,
        complevel=complevel,
        fill_value=np.float32(np.nan),
        chunksizes=(max(1, min(chunk_size, 16)), len(dst_grid.lat), len(dst_grid.lon)),
    )
    brdf_var = dst_ds.createVariable(
        "BRDF_Quality",
        "f4",
        ("time", "lat", "lon"),
        zlib=complevel > 0,
        complevel=complevel,
        fill_value=np.float32(np.nan),
        chunksizes=(max(1, min(chunk_size, 16)), len(dst_grid.lat), len(dst_grid.lon)),
    )
    pct_var = dst_ds.createVariable(
        "Percent_Inputs",
        "f4",
        ("time", "lat", "lon"),
        zlib=complevel > 0,
        complevel=complevel,
        fill_value=np.float32(np.nan),
        chunksizes=(max(1, min(chunk_size, 16)), len(dst_grid.lat), len(dst_grid.lon)),
    )

    copy_attrs(src_ds.variables["time"], time_var)
    copy_attrs(src_ds.variables["GPP"], gpp_var, skip={"_FillValue"})
    copy_attrs(src_ds.variables["GPP_uncertainty"], unc_var, skip={"_FillValue"})
    lat_var.units = "degrees_north"
    lon_var.units = "degrees_east"
    lat_var[:] = dst_grid.lat
    lon_var[:] = dst_grid.lon

    for attr in src_ds.ncattrs():
        dst_ds.setncattr(attr, src_ds.getncattr(attr))
    dst_ds.title = "FluxSat monthly resampled GPP (0.25 degree aligned to GLEAM drought grid)"
    dst_ds.source = f"Resampled from {os.path.basename(src_ds.filepath())} using area-weighted aggregation"
    return dst_ds, {
        "time": time_var,
        "GPP": gpp_var,
        "GPP_uncertainty": unc_var,
        "BRDF_Quality": brdf_var,
        "Percent_Inputs": pct_var,
    }


def process_one(item: MonthlyFile, output_dir: str, dst_grid: GridSpec, chunk_size: int, complevel: int, force: bool) -> str:
    ensure_dir(output_dir)
    output_path = output_path_for(output_dir, item.year, item.month)
    if os.path.exists(output_path):
        if not force:
            print(f"[skip] {item.year}-{item.month:02d} -> {output_path}", flush=True)
            return output_path
        os.remove(output_path)

    print(f"[start] {item.year}-{item.month:02d} <- {item.path}", flush=True)
    with nc.Dataset(item.path, "r") as src_ds:
        src_lat = np.asarray(src_ds.variables["lat"][:], dtype=np.float32)
        src_lon = np.asarray(src_ds.variables["lon"][:], dtype=np.float32)
        w_lat, w_lon = build_weight_matrices(src_lat, src_lon, dst_grid)
        dst_ds, vars_out = create_output_dataset(src_ds, output_path, dst_grid, chunk_size, complevel)
        try:
            time_size = int(src_ds.dimensions["time"].size)
            vars_out["time"][:] = src_ds.variables["time"][:]
            for t0 in range(0, time_size, chunk_size):
                t1 = min(t0 + chunk_size, time_size)
                gpp = np.asarray(src_ds.variables["GPP"][t0:t1, :, :], dtype=np.float32)
                unc = np.asarray(src_ds.variables["GPP_uncertainty"][t0:t1, :, :], dtype=np.float32)
                brdf = np.asarray(src_ds.variables["BRDF_Quality"][t0:t1, :, :], dtype=np.float32)
                pct = np.asarray(src_ds.variables["Percent_Inputs"][t0:t1, :, :], dtype=np.float32)

                gpp[gpp <= -9999.0] = np.nan
                unc[unc <= -9999.0] = np.nan

                vars_out["GPP"][t0:t1, :, :] = weighted_remap(gpp, np.isfinite(gpp), w_lat, w_lon)
                vars_out["GPP_uncertainty"][t0:t1, :, :] = weighted_remap(unc, np.isfinite(unc), w_lat, w_lon)
                vars_out["BRDF_Quality"][t0:t1, :, :] = weighted_remap(brdf, brdf >= 0.0, w_lat, w_lon)
                vars_out["Percent_Inputs"][t0:t1, :, :] = weighted_remap(pct, pct >= 0.0, w_lat, w_lon)
            dst_ds.sync()
        finally:
            dst_ds.close()
    print(f"[done] {item.year}-{item.month:02d} -> {output_path}", flush=True)
    return output_path


def process_one_from_args(args: tuple[MonthlyFile, str, GridSpec, int, int, bool]) -> str:
    return process_one(*args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resample FluxSat monthly files directly to 0.25 degree.")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2019)
    parser.add_argument("--chunk-size", type=int, default=4)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--complevel", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.chunk_size < 1:
        raise SystemExit("--chunk-size must be >= 1")
    if args.jobs < 1:
        raise SystemExit("--jobs must be >= 1")
    items = discover_monthly_files(args.input_dir, args.start_year, args.end_year)
    dst_grid = load_target_grid()
    complevel = max(0, min(args.complevel, 9))

    if args.jobs == 1:
        for item in items:
            process_one(item, args.output_dir, dst_grid, args.chunk_size, complevel, args.force)
        return

    job_args = [
        (item, args.output_dir, dst_grid, args.chunk_size, complevel, args.force)
        for item in items
    ]
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures = [executor.submit(process_one_from_args, one_job) for one_job in job_args]
        for future in as_completed(futures):
            future.result()


if __name__ == "__main__":
    main()
