#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

import numpy as np
import rasterio
from netCDF4 import Dataset


def _create_var_with_encoding(ds_out, src_var):
    fill_value = getattr(src_var, "_FillValue", None)
    kwargs = {}
    filters = src_var.filters()
    if isinstance(filters, dict):
        for key in ["zlib", "complevel", "shuffle", "fletcher32", "contiguous"]:
            if key in filters and filters[key] is not None:
                kwargs[key] = filters[key]
        chunksizes = filters.get("chunksizes")
        if chunksizes is not None and not kwargs.get("contiguous", False):
            kwargs["chunksizes"] = chunksizes
    if fill_value is not None:
        kwargs["fill_value"] = fill_value
    return ds_out.createVariable(src_var.name, src_var.datatype, src_var.dimensions, **kwargs)


def flip_nc_lat(src_nc: Path, dst_nc: Path, lat_name: str = "lat", time_chunk: int = 24):
    dst_nc.parent.mkdir(parents=True, exist_ok=True)
    with Dataset(src_nc, "r") as ds_in, Dataset(dst_nc, "w", format="NETCDF4") as ds_out:
        for dname, dim in ds_in.dimensions.items():
            ds_out.createDimension(dname, (len(dim) if not dim.isunlimited() else None))

        for aname in ds_in.ncattrs():
            ds_out.setncattr(aname, ds_in.getncattr(aname))

        out_vars = {}
        for vname, vsrc in ds_in.variables.items():
            vdst = _create_var_with_encoding(ds_out, vsrc)
            for attr in vsrc.ncattrs():
                if attr == "_FillValue":
                    continue
                vdst.setncattr(attr, vsrc.getncattr(attr))
            out_vars[vname] = vdst

        for vname, vsrc in ds_in.variables.items():
            vdst = out_vars[vname]
            dims = vsrc.dimensions

            if lat_name not in dims:
                if vsrc.ndim == 0:
                    vdst.assignValue(vsrc.getValue())
                else:
                    vdst[:] = vsrc[:]
                continue

            lat_axis = dims.index(lat_name)
            if vsrc.ndim == 1 and lat_axis == 0:
                vdst[:] = vsrc[::-1]
                continue

            if vsrc.ndim > 0 and dims[0] in ds_in.dimensions and len(ds_in.dimensions[dims[0]]) > time_chunk:
                n0 = vsrc.shape[0]
                for start in range(0, n0, time_chunk):
                    end = min(start + time_chunk, n0)
                    sl = [slice(None)] * vsrc.ndim
                    sl[0] = slice(start, end)
                    arr = vsrc[tuple(sl)]
                    arr = np.flip(arr, axis=lat_axis)
                    vdst[tuple(sl)] = arr
            else:
                arr = vsrc[:]
                arr = np.flip(arr, axis=lat_axis)
                vdst[:] = arr


def flip_tif_lat(src_tif: Path, dst_tif: Path):
    dst_tif.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(src_tif) as src:
        data = src.read()
        data_flipped = data[:, ::-1, :]
        profile = src.profile.copy()
        with rasterio.open(dst_tif, "w", **profile) as dst:
            dst.write(data_flipped)


def process_one_dir(src_dir: Path, dst_dir: Path, lat_name: str, time_chunk: int):
    dst_dir.mkdir(parents=True, exist_ok=True)
    files = sorted([p for p in src_dir.iterdir() if p.is_file()])

    nc_files = [p for p in files if p.suffix.lower() in {".nc", ".nc4"}]
    tif_files = [p for p in files if p.suffix.lower() in {".tif", ".tiff"}]

    for nc in nc_files:
        out_nc = dst_dir / nc.name
        print(f"[NC ] flip lat: {nc} -> {out_nc}")
        flip_nc_lat(nc, out_nc, lat_name=lat_name, time_chunk=time_chunk)

    for tif in tif_files:
        out_tif = dst_dir / tif.name
        print(f"[TIF] flip lat: {tif} -> {out_tif}")
        flip_tif_lat(tif, out_tif)

    print(f"Done: {src_dir} -> {dst_dir} | nc={len(nc_files)}, tif={len(tif_files)}")


def main():
    parser = argparse.ArgumentParser(description="Flip latitude direction for NetCDF and GeoTIFF files in two MERRA2 result folders.")
    parser.add_argument("--smrz-in", default="/home/xulc/flash_drought/gleam/result/SMrz_MERRA2_1")
    parser.add_argument("--smrz-out", default="/home/xulc/flash_drought/gleam/result/SMrz_MERRA2_1_latflip")
    parser.add_argument("--sms-in", default="/home/xulc/flash_drought/gleam/result/SMs_MERRA2_1")
    parser.add_argument("--sms-out", default="/home/xulc/flash_drought/gleam/result/SMs_MERRA2_1_latflip")
    parser.add_argument("--lat-name", default="lat")
    parser.add_argument("--time-chunk", type=int, default=24)
    args = parser.parse_args()

    process_one_dir(Path(args.sms_in), Path(args.sms_out), lat_name=args.lat_name, time_chunk=args.time_chunk)
    process_one_dir(Path(args.smrz_in), Path(args.smrz_out), lat_name=args.lat_name, time_chunk=args.time_chunk)


if __name__ == "__main__":
    main()
