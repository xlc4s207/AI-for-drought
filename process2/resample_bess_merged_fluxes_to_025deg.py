#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
import argparse
import math
import os
import sys
from dataclasses import dataclass

import netCDF4 as nc
import numpy as np
from scipy import sparse


@dataclass(frozen=True)
class VariableConfig:
    name: str
    input_path: str
    output_path: str
    invalid_below: float
    title: str
    long_name: str
    source: str


SRC_LAT_SIZE = 1800
SRC_LON_SIZE = 3600
DST_LAT_SIZE = 720
DST_LON_SIZE = 1440
DST_LAT_DESC = np.linspace(89.875, -89.875, DST_LAT_SIZE, dtype=np.float32)
DST_LAT_ASC = DST_LAT_DESC[::-1].copy()
DST_LON = np.linspace(-179.875, 179.875, DST_LON_SIZE, dtype=np.float32)

CONFIGS = {
    "NEE": VariableConfig(
        name="NEE",
        input_path="/data/BESS_V2/NEE_1982-2022_0.1deg.nc",
        output_path="/data/BESS_V2/NEE_1982-2022_0.25deg.nc",
        invalid_below=-1000.0,
        title="BESS V2 Daily NEE 1982-2022 (0.25 degree resolution)",
        long_name="Net Ecosystem Exchange (0.25 degree)",
        source="Resampled from 0.1 degree merged daily file using chunked area-weighted averaging; values <= -1000 treated as invalid",
    ),
    "RECO": VariableConfig(
        name="RECO",
        input_path="/data/BESS_V2/BESS_RECO_1982-2022_0.1deg.nc",
        output_path="/data/BESS_V2/BESS_RECO_1982-2022_0.25deg.nc",
        invalid_below=0.0,
        title="BESS V2 Daily RECO 1982-2022 (0.25 degree resolution)",
        long_name="Ecosystem Respiration (0.25 degree)",
        source="Resampled from 0.1 degree merged daily file using chunked area-weighted averaging; negative values treated as invalid",
    ),
    "GPP": VariableConfig(
        name="GPP",
        input_path="/data/BESS_V2/BESS_GPP_1982_2022.nc",
        output_path="/data/BESS_V2/BESS_GPP_1982_2022_0.25deg.nc",
        invalid_below=0.0,
        title="BESS V2 Daily GPP 1982-2022 (0.25 degree resolution)",
        long_name="Gross Primary Production (0.25 degree)",
        source="Resampled from 0.1 degree merged daily file using chunked area-weighted averaging; negative values treated as invalid",
    ),
}


def log(message: str) -> None:
    print(message, flush=True)


def copy_attrs(src_var, dst_var, skip=None):
    skip = set(skip or [])
    for attr in src_var.ncattrs():
        if attr in skip:
            continue
        dst_var.setncattr(attr, src_var.getncattr(attr))


def centers_to_edges(centers: np.ndarray) -> np.ndarray:
    deltas = np.diff(centers)
    if deltas.size == 0:
        raise ValueError("centers array must have at least two values")
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

    rows = []
    cols = []
    data = []

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


def build_weight_matrices(lat_values: np.ndarray, lon_values: np.ndarray):
    lat_descending = bool(lat_values[0] > lat_values[-1])
    src_lat_asc = lat_values[::-1] if lat_descending else lat_values.copy()
    src_lon = lon_values.copy()

    src_lat_edges = centers_to_edges(src_lat_asc.astype(np.float64))
    src_lon_edges = centers_to_edges(src_lon.astype(np.float64))
    dst_lat_edges = centers_to_edges(DST_LAT_ASC.astype(np.float64))
    dst_lon_edges = centers_to_edges(DST_LON.astype(np.float64))

    w_lat = build_overlap_matrix(src_lat_edges, dst_lat_edges, area_weighted=True)
    w_lon = build_overlap_matrix(src_lon_edges, dst_lon_edges, area_weighted=False)
    return w_lat, w_lon, lat_descending


def mask_invalid(var_name: str, values: np.ndarray, invalid_below: float) -> np.ndarray:
    valid = np.isfinite(values)
    if var_name == "NEE":
        valid &= values > invalid_below
    else:
        valid &= values >= invalid_below
    return valid


def remap_chunk(values: np.ndarray, w_lat: sparse.csr_matrix, w_lon: sparse.csr_matrix) -> np.ndarray:
    time_size, src_lat_size, src_lon_size = values.shape
    valid = mask_invalid("GENERIC", values, 0.0)  # placeholder, overridden before call
    raise RuntimeError("remap_chunk should not be called directly without remap_variable")


def weighted_remap(values: np.ndarray, valid: np.ndarray, w_lat: sparse.csr_matrix, w_lon: sparse.csr_matrix) -> np.ndarray:
    time_size, src_lat_size, src_lon_size = values.shape

    filled = np.where(valid, values, 0.0).astype(np.float32, copy=False)
    weights = valid.astype(np.float32, copy=False)

    num_lon = (filled.reshape(time_size * src_lat_size, src_lon_size) @ w_lon).reshape(time_size, src_lat_size, DST_LON_SIZE)
    den_lon = (weights.reshape(time_size * src_lat_size, src_lon_size) @ w_lon).reshape(time_size, src_lat_size, DST_LON_SIZE)

    num_lat = (
        np.transpose(num_lon, (0, 2, 1)).reshape(time_size * DST_LON_SIZE, src_lat_size) @ w_lat
    ).reshape(time_size, DST_LON_SIZE, DST_LAT_SIZE).transpose(0, 2, 1)
    den_lat = (
        np.transpose(den_lon, (0, 2, 1)).reshape(time_size * DST_LON_SIZE, src_lat_size) @ w_lat
    ).reshape(time_size, DST_LON_SIZE, DST_LAT_SIZE).transpose(0, 2, 1)

    output = np.full((time_size, DST_LAT_SIZE, DST_LON_SIZE), np.nan, dtype=np.float32)
    np.divide(num_lat, den_lat, out=output, where=den_lat > 0.0)
    return output


def create_output_dataset(config: VariableConfig, src_ds: nc.Dataset, chunk_size: int) -> tuple[nc.Dataset, nc.Variable]:
    dst_ds = nc.Dataset(config.output_path, "w", format="NETCDF4")
    dst_ds.createDimension("time", None)
    dst_ds.createDimension("lat", DST_LAT_SIZE)
    dst_ds.createDimension("lon", DST_LON_SIZE)

    time_var_src = src_ds.variables["time"]
    lat_var_src = src_ds.variables["lat"]
    lon_var_src = src_ds.variables["lon"]

    time_var = dst_ds.createVariable("time", time_var_src.dtype, ("time",))
    lat_var = dst_ds.createVariable("lat", "f4", ("lat",))
    lon_var = dst_ds.createVariable("lon", "f4", ("lon",))
    data_var = dst_ds.createVariable(
        config.name,
        "f4",
        ("time", "lat", "lon"),
        zlib=True,
        complevel=1,
        fill_value=np.nan,
        chunksizes=(max(1, min(chunk_size, 32)), DST_LAT_SIZE, DST_LON_SIZE),
    )

    copy_attrs(time_var_src, time_var)
    copy_attrs(lat_var_src, lat_var, skip={"_FillValue"})
    copy_attrs(lon_var_src, lon_var, skip={"_FillValue"})
    copy_attrs(src_ds.variables[config.name], data_var, skip={"_FillValue", "long_name"})

    lat_var[:] = DST_LAT_DESC
    lon_var[:] = DST_LON
    data_var.long_name = config.long_name

    for attr in src_ds.ncattrs():
        dst_ds.setncattr(attr, src_ds.getncattr(attr))
    dst_ds.title = config.title
    dst_ds.source = config.source
    return dst_ds, data_var


def process_variable(config: VariableConfig, chunk_size: int, force: bool) -> None:
    if os.path.exists(config.output_path) and not force:
        log(f"skip existing output: {config.output_path}")
        return

    log(f"processing {config.name}")
    log(f"  input : {config.input_path}")
    log(f"  output: {config.output_path}")

    with nc.Dataset(config.input_path, "r") as src_ds:
        src_ds.set_auto_mask(False)
        src_ds.set_auto_scale(True)
        lat_values = np.asarray(src_ds.variables["lat"][:], dtype=np.float32)
        lon_values = np.asarray(src_ds.variables["lon"][:], dtype=np.float32)
        w_lat, w_lon, lat_descending = build_weight_matrices(lat_values, lon_values)

        time_var_src = src_ds.variables["time"]
        data_var_src = src_ds.variables[config.name]
        time_size = time_var_src.shape[0]

        with create_output_dataset(config, src_ds, chunk_size)[0] as dst_ds:
            data_var_dst = dst_ds.variables[config.name]
            dst_time = dst_ds.variables["time"]

            for start in range(0, time_size, chunk_size):
                end = min(start + chunk_size, time_size)
                log(f"  chunk {start}:{end} / {time_size}")

                values = np.asarray(data_var_src[start:end, :, :], dtype=np.float32)
                if lat_descending:
                    values = values[:, ::-1, :]

                valid = mask_invalid(config.name, values, config.invalid_below)
                output = weighted_remap(values, valid, w_lat, w_lon)
                if lat_descending:
                    output = output[:, ::-1, :]

                data_var_dst[start:end, :, :] = output
                dst_time[start:end] = time_var_src[start:end]

        log(f"finished {config.name}")


def parse_args():
    parser = argparse.ArgumentParser(description="Resample merged BESS daily flux files from 0.1 degree to 0.25 degree.")
    parser.add_argument("--only", choices=["NEE", "RECO", "GPP"], help="Only process one variable")
    parser.add_argument("--chunk-size", type=int, default=4, help="Number of days per processing chunk")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.chunk_size < 1:
        raise SystemExit("--chunk-size must be >= 1")

    names = [args.only] if args.only else ["NEE", "RECO", "GPP"]
    for name in names:
        process_variable(CONFIGS[name], args.chunk_size, args.force)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise
