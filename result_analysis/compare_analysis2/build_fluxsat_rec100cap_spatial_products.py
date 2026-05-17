#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Build gridded spatial products for FluxSat 0401 rec100cap outputs."""

from __future__ import annotations

import csv
import math
import os
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
OUT_DIR = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/"
    "fluxsat_compare_analysis2/fluxsat_rec100cap_spatial"
)
SUMMARY_CSV = os.path.join(OUT_DIR, "fluxsat_rec100cap_spatial_summary.csv")
SUMMARY_MD = os.path.join(OUT_DIR, "fluxsat_rec100cap_spatial_summary.md")
OVERVIEW_PNG = os.path.join(OUT_DIR, "fluxsat_rec100cap_spatial_overview.png")


@dataclass(frozen=True)
class Item:
    scenario: str
    file_path: str
    out_nc: str


ITEMS: List[Item] = [
    Item(
        scenario="SMrz",
        file_path=(
            f"{BASE_DIR}/process/fluxsat-draught-analysis/code1/results/"
            "fluxsat_gpp_response_SMrz_events_global_"
            "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426.nc"
        ),
        out_nc=os.path.join(OUT_DIR, "fluxsat_rec100cap_spatial_SMrz.nc"),
    ),
    Item(
        scenario="SMs",
        file_path=(
            f"{BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/results/"
            "fluxsat_gpp_response_SMs_events_global_"
            "v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426.nc"
        ),
        out_nc=os.path.join(OUT_DIR, "fluxsat_rec100cap_spatial_SMs.nc"),
    ),
]


def setup_chinese_font() -> None:
    candidates = [
        "Noto Sans CJK SC",
        "Noto Sans CJK",
        "Source Han Sans SC",
        "Source Han Sans CN",
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
        "Microsoft YaHei",
        "SimHei",
        "PingFang SC",
        "Arial Unicode MS",
    ]
    installed = {f.name for f in fm.fontManager.ttflist}
    selected = None
    for name in candidates:
        if name in installed:
            selected = name
            break
    rcParams["font.sans-serif"] = [selected, "DejaVu Sans"] if selected else ["DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False


def to_numpy(var) -> np.ndarray:
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        arr = arr.filled(np.nan)
    arr = np.asarray(arr)
    if np.issubdtype(arr.dtype, np.integer):
        arr = arr.astype(np.float64)
    fill_value = getattr(var, "_FillValue", None)
    if fill_value is not None:
        arr = arr.astype(np.float64, copy=False)
        arr[np.isclose(arr, float(fill_value), equal_nan=False)] = np.nan
    return arr


def clean_nonnegative(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    arr[~np.isfinite(arr)] = np.nan
    arr[arr < 0] = np.nan
    return arr


def fmt(value: object, decimals: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return "-"
        return f"{float(value):,.{decimals}f}"
    return str(value)


def metadata_match(
    out_event_id: int,
    out_onset_year: int,
    out_onset_doy: int,
    out_drought_start_year: int,
    out_drought_start_doy: int,
    src_event_id: int,
    src_onset_year: int,
    src_onset_doy: int,
    src_drought_start_year: int,
    src_drought_start_doy: int,
) -> bool:
    return (
        int(out_event_id) == int(src_event_id)
        and int(out_onset_year) == int(src_onset_year)
        and int(out_onset_doy) == int(src_onset_doy)
        and int(out_drought_start_year) == int(src_drought_start_year)
        and int(out_drought_start_doy) == int(src_drought_start_doy)
    )


def reconstruct_true_lon(
    source_event_file: str,
    lat_evt: np.ndarray,
    lon_evt: np.ndarray,
    event_id_evt: np.ndarray,
    onset_year_evt: np.ndarray,
    onset_doy_evt: np.ndarray,
    drought_start_year_evt: np.ndarray,
    drought_start_doy_evt: np.ndarray,
) -> np.ndarray:
    lon_valid = lon_evt[np.isfinite(lon_evt)]
    if lon_valid.size == 0:
        return lon_evt
    if np.nanmin(lon_valid) < -170.0 and np.nanmax(lon_valid) > 170.0:
        return lon_evt

    with nc.Dataset(source_event_file, "r") as ds:
        src_lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
        src_lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
        src_ec = np.asarray(ds.variables["event_count"][:], dtype=np.int32)
        fixed_lon = np.full(lon_evt.shape, np.nan, dtype=np.float64)
        lat_buckets: dict[int, np.ndarray] = defaultdict(list)
        rounded_lat_evt = np.rint(lat_evt * 1_000_000.0).astype(np.int64)
        rounded_src_lat = np.rint(src_lat * 1_000_000.0).astype(np.int64)
        for idx, lat_key in enumerate(rounded_lat_evt):
            lat_buckets[int(lat_key)].append(idx)

        for lat_idx, lat_key in enumerate(rounded_src_lat):
            out_rows = lat_buckets.get(int(lat_key))
            if not out_rows:
                continue
            out_rows = np.asarray(out_rows, dtype=np.int64)
            needed_keys = {
                (
                    int(event_id_evt[out_idx]),
                    int(onset_year_evt[out_idx]),
                    int(onset_doy_evt[out_idx]),
                    int(drought_start_year_evt[out_idx]),
                    int(drought_start_doy_evt[out_idx]),
                )
                for out_idx in out_rows
            }
            lon_nonzero = np.where(src_ec[lat_idx, :] > 0)[0]
            if lon_nonzero.size == 0:
                continue
            max_ec = int(np.max(src_ec[lat_idx, lon_nonzero]))
            onset_year_src = np.asarray(ds.variables["onset_start_year"][:max_ec, lat_idx, lon_nonzero])
            onset_doy_src = np.asarray(ds.variables["onset_start_doy"][:max_ec, lat_idx, lon_nonzero])
            drought_start_year_src = np.asarray(ds.variables["drought_start_year"][:max_ec, lat_idx, lon_nonzero])
            drought_start_doy_src = np.asarray(ds.variables["drought_start_doy"][:max_ec, lat_idx, lon_nonzero])
            lon_queues = defaultdict(deque)
            for j, lon_idx in enumerate(lon_nonzero):
                ec = int(src_ec[lat_idx, lon_idx])
                for src_event_id in range(ec):
                    key = (
                        src_event_id,
                        onset_year_src[src_event_id, j],
                        onset_doy_src[src_event_id, j],
                        drought_start_year_src[src_event_id, j],
                        drought_start_doy_src[src_event_id, j],
                    )
                    if key in needed_keys:
                        lon_queues[key].append(float(src_lon[lon_idx]))

            for out_idx in out_rows:
                key = (
                    int(event_id_evt[out_idx]),
                    int(onset_year_evt[out_idx]),
                    int(onset_doy_evt[out_idx]),
                    int(drought_start_year_evt[out_idx]),
                    int(drought_start_doy_evt[out_idx]),
                )
                queue = lon_queues.get(key)
                if queue:
                    fixed_lon[out_idx] = queue.popleft()

        unresolved = np.sum(~np.isfinite(fixed_lon) & np.isfinite(lat_evt))
        if unresolved > 0:
            raise RuntimeError(
                f"Failed to reconstruct longitude for {int(unresolved)} events from {source_event_file}"
            )
        return fixed_lon


def aggregate_item(item: Item) -> dict:
    with nc.Dataset(item.file_path, "r") as ds:
        lat_evt = to_numpy(ds.variables["lat"]).astype(np.float64)
        lon_evt = to_numpy(ds.variables["lon"]).astype(np.float64)
        event_id_evt = np.asarray(ds.variables["event_id"][:], dtype=np.int32)
        onset_year_evt = np.asarray(ds.variables["onset_year"][:], dtype=np.int32)
        onset_doy_evt = np.asarray(ds.variables["onset_doy"][:], dtype=np.int32)
        drought_start_year_evt = np.asarray(ds.variables["drought_start_year"][:], dtype=np.int32)
        drought_start_doy_evt = np.asarray(ds.variables["drought_start_doy"][:], dtype=np.int32)
        t_response = clean_nonnegative(to_numpy(ds.variables["t_response_drought_start"]))
        t_recover = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))
        source_event_file = getattr(ds, "source_event_file", "")

    lon_evt = reconstruct_true_lon(
        source_event_file=source_event_file,
        lat_evt=lat_evt,
        lon_evt=lon_evt,
        event_id_evt=event_id_evt,
        onset_year_evt=onset_year_evt,
        onset_doy_evt=onset_doy_evt,
        drought_start_year_evt=drought_start_year_evt,
        drought_start_doy_evt=drought_start_doy_evt,
    )

    lat_vals = np.unique(lat_evt[np.isfinite(lat_evt)])
    lon_vals = np.unique(lon_evt[np.isfinite(lon_evt)])
    lat_vals.sort()
    lon_vals.sort()
    nlat = len(lat_vals)
    nlon = len(lon_vals)

    lat_idx = np.searchsorted(lat_vals, lat_evt)
    lon_idx = np.searchsorted(lon_vals, lon_evt)
    flat_idx = lat_idx * nlon + lon_idx
    ncell = nlat * nlon

    event_total = np.bincount(flat_idx, minlength=ncell).astype(np.int32)

    response_valid = np.isfinite(t_response)
    recovery_valid = np.isfinite(t_recover)
    response_count = np.bincount(flat_idx[response_valid], minlength=ncell).astype(np.int32)
    recovery_count = np.bincount(flat_idx[recovery_valid], minlength=ncell).astype(np.int32)
    response_sum = np.bincount(flat_idx[response_valid], weights=t_response[response_valid], minlength=ncell)
    recovery_sum = np.bincount(flat_idx[recovery_valid], weights=t_recover[recovery_valid], minlength=ncell)

    response_mean = np.full(ncell, np.nan, dtype=np.float64)
    recovery_mean = np.full(ncell, np.nan, dtype=np.float64)
    ok_resp = response_count > 0
    ok_rec = recovery_count > 0
    response_mean[ok_resp] = response_sum[ok_resp] / response_count[ok_resp]
    recovery_mean[ok_rec] = recovery_sum[ok_rec] / recovery_count[ok_rec]

    event_total_2d = event_total.reshape(nlat, nlon)
    response_count_2d = response_count.reshape(nlat, nlon)
    recovery_count_2d = recovery_count.reshape(nlat, nlon)
    response_mean_2d = response_mean.reshape(nlat, nlon)
    recovery_mean_2d = recovery_mean.reshape(nlat, nlon)

    with nc.Dataset(item.out_nc, "w") as ds:
        ds.createDimension("lat", nlat)
        ds.createDimension("lon", nlon)
        lat_var = ds.createVariable("lat", "f4", ("lat",))
        lon_var = ds.createVariable("lon", "f4", ("lon",))
        lat_var[:] = lat_vals.astype(np.float32)
        lon_var[:] = lon_vals.astype(np.float32)

        def write_var(name: str, data: np.ndarray, units: str) -> None:
            var = ds.createVariable(name, "f4", ("lat", "lon"), fill_value=np.float32(np.nan), zlib=True)
            var[:, :] = data.astype(np.float32)
            var.units = units

        write_var("event_total_count", event_total_2d, "count")
        write_var("response_valid_count", response_count_2d, "count")
        write_var("recovery_valid_count", recovery_count_2d, "count")
        write_var("response_mean_days", response_mean_2d, "days")
        write_var("recovery_mean_days", recovery_mean_2d, "days")
        ds.description = f"FluxSat 0401 rec100cap gridded spatial summary for {item.scenario}"

    return {
        "scenario": item.scenario,
        "lat": lat_vals,
        "lon": lon_vals,
        "event_total_count": event_total_2d,
        "response_valid_count": response_count_2d,
        "recovery_valid_count": recovery_count_2d,
        "response_mean_days": response_mean_2d,
        "recovery_mean_days": recovery_mean_2d,
        "event_total_sum": int(np.nansum(event_total_2d)),
        "response_valid_sum": int(np.nansum(response_count_2d)),
        "recovery_valid_sum": int(np.nansum(recovery_count_2d)),
        "response_mean_gridmean": float(np.nanmean(response_mean_2d)),
        "recovery_mean_gridmean": float(np.nanmean(recovery_mean_2d)),
        "out_nc": item.out_nc,
    }


def write_summary(rows: List[dict]) -> None:
    fieldnames = [
        "scenario",
        "event_total_sum",
        "response_valid_sum",
        "recovery_valid_sum",
        "response_mean_gridmean",
        "recovery_mean_gridmean",
        "out_nc",
    ]
    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})

    lines = [
        "# FluxSat rec100cap 空间聚合结果",
        "",
        "| 情景 | 总事件数 | 响应有效数 | 恢复有效数 | 响应均值(格点平均,d) | 恢复均值(格点平均,d) | 输出NC |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["scenario"],
                    fmt(row["event_total_sum"], 0),
                    fmt(row["response_valid_sum"], 0),
                    fmt(row["recovery_valid_sum"], 0),
                    fmt(row["response_mean_gridmean"]),
                    fmt(row["recovery_mean_gridmean"]),
                    os.path.basename(row["out_nc"]),
                ]
            )
            + " |"
        )
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def plot_overview(rows: List[dict]) -> None:
    response_arrays = [row["response_mean_days"] for row in rows]
    recovery_arrays = [row["recovery_mean_days"] for row in rows]
    count_arrays = [row["recovery_valid_count"] for row in rows]
    resp_vmin = float(np.nanpercentile(np.concatenate([a[np.isfinite(a)] for a in response_arrays]), 2))
    resp_vmax = float(np.nanpercentile(np.concatenate([a[np.isfinite(a)] for a in response_arrays]), 98))
    rec_vmin = float(np.nanpercentile(np.concatenate([a[np.isfinite(a)] for a in recovery_arrays]), 2))
    rec_vmax = float(np.nanpercentile(np.concatenate([a[np.isfinite(a)] for a in recovery_arrays]), 98))
    cnt_vmin = float(np.nanpercentile(np.concatenate([a[np.isfinite(a)] for a in count_arrays]), 5))
    cnt_vmax = float(np.nanpercentile(np.concatenate([a[np.isfinite(a)] for a in count_arrays]), 98))

    fig, axes = plt.subplots(3, 2, figsize=(14, 11), constrained_layout=True)
    top_im = None
    mid_im = None
    bot_im = None
    for col, row in enumerate(rows):
        lon = row["lon"]
        lat = row["lat"]
        dlon = float(np.nanmedian(np.diff(lon))) if lon.size > 1 else 0.25
        dlat = float(np.nanmedian(np.diff(lat))) if lat.size > 1 else 0.25
        extent = [float(lon[0] - dlon / 2), float(lon[-1] + dlon / 2), float(lat[0] - dlat / 2), float(lat[-1] + dlat / 2)]
        top_im = axes[0, col].imshow(
            row["response_mean_days"],
            origin="lower",
            extent=extent,
            aspect="auto",
            cmap="YlGnBu",
            vmin=resp_vmin,
            vmax=resp_vmax,
        )
        axes[0, col].set_title(f"{row['scenario']} Response Mean")
        mid_im = axes[1, col].imshow(
            row["recovery_mean_days"],
            origin="lower",
            extent=extent,
            aspect="auto",
            cmap="YlOrRd",
            vmin=rec_vmin,
            vmax=rec_vmax,
        )
        axes[1, col].set_title(f"{row['scenario']} Recovery Mean")
        bot_im = axes[2, col].imshow(
            row["recovery_valid_count"],
            origin="lower",
            extent=extent,
            aspect="auto",
            cmap="PuBu",
            vmin=cnt_vmin,
            vmax=cnt_vmax,
        )
        axes[2, col].set_title(f"{row['scenario']} Recovery Count")
        for r in range(3):
            axes[r, col].set_xlabel("Lon")
            axes[r, col].set_ylabel("Lat")
            axes[r, col].set_xlim(-180, 180)

    fig.colorbar(top_im, ax=axes[0, :], shrink=0.92, pad=0.02, label="days")
    fig.colorbar(mid_im, ax=axes[1, :], shrink=0.92, pad=0.02, label="days")
    fig.colorbar(bot_im, ax=axes[2, :], shrink=0.92, pad=0.02, label="count")
    fig.savefig(OVERVIEW_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    setup_chinese_font()
    rows = [aggregate_item(item) for item in ITEMS]
    write_summary(rows)
    plot_overview(rows)
    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {SUMMARY_MD}")
    print(f"Wrote {OVERVIEW_PNG}")
    for row in rows:
        print(f"Wrote {row['out_nc']}")


if __name__ == "__main__":
    main()
