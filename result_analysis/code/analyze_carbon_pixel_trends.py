#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
import pandas as pd
from scipy.stats import t as student_t


BASE_DIR = "/home/xulc/flash_drought"
YEARS = np.arange(1980, 2025, dtype=np.int32)
YEAR_MIN = int(YEARS[0])
YEAR_MAX = int(YEARS[-1])
MIN_YEARS_FOR_TREND = 5
CHUNK_SIZE = 1_500_000
COORD_SCALE = 1000
BIT_MASK_32 = np.int64(0xFFFFFFFF)


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    drought_type: str
    soil_layer: str
    path: str


@dataclass(frozen=True)
class TargetConfig:
    key: str
    display: str
    output_dir: str
    event_prefix: str
    abs_scale_factor: float
    abs_unit: str
    abs_rate_unit: str
    plot_lat_sign: float
    datasets: List[DatasetSpec]


SCENARIO_LABELS = {
    "flash_SMrz": "Flash-SMrz",
    "flash_SMs": "Flash-SMs",
    "nonflash_SMrz": "Nonflash-SMrz",
    "nonflash_SMs": "Nonflash-SMs",
}

SCENARIO_ORDER = ["flash_SMrz", "flash_SMs", "nonflash_SMrz", "nonflash_SMs"]

TARGET_CONFIGS: Dict[str, TargetConfig] = {
    "nee": TargetConfig(
        key="nee",
        display="NEE",
        output_dir=os.path.join(BASE_DIR, "process/result_analysis/NEE_trend"),
        event_prefix="nee",
        abs_scale_factor=0.01,
        abs_unit="gC m^-2 day^-1",
        abs_rate_unit="gC m^-2 day^-2",
        plot_lat_sign=-1.0,
        datasets=[
            DatasetSpec("flash_SMrz", "flash", "SMrz", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code1SMrz/result/nee_response_events_global_v11_with_abs.nc")),
            DatasetSpec("flash_SMs", "flash", "SMs", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code2SMs/result/nee_response_SMs_events_global_v11_with_abs.nc")),
            DatasetSpec("nonflash_SMrz", "nonflash", "SMrz", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v11_global_with_abs.nc")),
            DatasetSpec("nonflash_SMs", "nonflash", "SMs", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v11_global_with_abs.nc")),
        ],
    ),
    "reco": TargetConfig(
        key="reco",
        display="RECO",
        output_dir=os.path.join(BASE_DIR, "process/result_analysis/RECO_trend"),
        event_prefix="reco",
        abs_scale_factor=0.01,
        abs_unit="gC m^-2 day^-1",
        abs_rate_unit="gC m^-2 day^-2",
        plot_lat_sign=1.0,
        datasets=[
            DatasetSpec("flash_SMrz", "flash", "SMrz", os.path.join(BASE_DIR, "process/RECO-draught-analysis/code1/results/reco_response_events_global_v11_with_abs.nc")),
            DatasetSpec("flash_SMs", "flash", "SMs", os.path.join(BASE_DIR, "process/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_events_global_v11_with_abs.nc")),
            DatasetSpec("nonflash_SMrz", "nonflash", "SMrz", os.path.join(BASE_DIR, "process/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v11_global_with_abs.nc")),
            DatasetSpec("nonflash_SMs", "nonflash", "SMs", os.path.join(BASE_DIR, "process/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v11_global_with_abs.nc")),
        ],
    ),
}


def build_metric_specs(cfg: TargetConfig) -> Dict[str, Dict[str, str]]:
    return {
        "response_ratio": {"label": "Response Ratio Trend", "unit": "1/year"},
        "response_speed_proxy_mean": {"label": "Response Speed Proxy Trend", "unit": "(1/day)/year"},
        f"{cfg.event_prefix}_min_abs_mean": {"label": f"{cfg.display} Min Abs Trend", "unit": f"{cfg.abs_unit} year^-1"},
        "t_min_mean": {"label": "t_min Trend", "unit": "day/year"},
        "t_response_mean": {"label": "t_response Trend", "unit": "day/year"},
        "t_impact_mean": {"label": "t_impact Trend", "unit": "day/year"},
        "t_recover_mean": {"label": "t_recover Trend", "unit": "day/year"},
        f"{cfg.event_prefix}_drop_abs_mean": {"label": f"{cfg.display} Drop Abs Trend", "unit": f"{cfg.abs_unit} year^-1"},
        f"{cfg.event_prefix}_recovery_rate_abs_mean": {"label": f"{cfg.display} Recovery Abs Rate Trend", "unit": f"{cfg.abs_rate_unit} year^-1"},
    }


def _to_float(arr, fill_value) -> np.ndarray:
    if isinstance(arr, np.ma.MaskedArray):
        data = arr.filled(np.nan).astype(np.float64, copy=False)
    else:
        data = np.asarray(arr, dtype=np.float64)
    if fill_value is not None:
        data[data == fill_value] = np.nan
    return data


def _read_var_chunk(var_obj, start: int, end: int) -> np.ndarray:
    return _to_float(var_obj[start:end], getattr(var_obj, "_FillValue", None))


def _year_var_name(ds: nc.Dataset) -> str:
    if "drought_start_year" in ds.variables:
        return "drought_start_year"
    if "onset_year" in ds.variables:
        return "onset_year"
    raise KeyError("Neither drought_start_year nor onset_year is available.")


def _coord_to_int(coord_arr: np.ndarray) -> np.ndarray:
    return np.rint(coord_arr * COORD_SCALE).astype(np.int32, copy=False)


def _pack_cell_key(lat_i: np.ndarray, lon_i: np.ndarray) -> np.ndarray:
    return ((lat_i.astype(np.int64) & BIT_MASK_32) << 32) | (lon_i.astype(np.int64) & BIT_MASK_32)


def _unpack_cell_key(cell_keys: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    lat_u = ((cell_keys >> 32) & BIT_MASK_32).astype(np.uint32).view(np.int32)
    lon_u = (cell_keys & BIT_MASK_32).astype(np.uint32).view(np.int32)
    return lat_u, lon_u


def _build_cell_index(lat_all: np.ndarray, lon_all: np.ndarray) -> Dict[str, np.ndarray]:
    valid = np.isfinite(lat_all) & np.isfinite(lon_all)
    cell_keys = np.unique(_pack_cell_key(_coord_to_int(lat_all[valid]), _coord_to_int(lon_all[valid])))
    cell_lat_i, cell_lon_i = _unpack_cell_key(cell_keys)
    lat_axis_i = np.unique(cell_lat_i)
    lon_axis_i = np.unique(cell_lon_i)
    return {
        "cell_keys": cell_keys,
        "cell_lat_idx": np.searchsorted(lat_axis_i, cell_lat_i).astype(np.int32, copy=False),
        "cell_lon_idx": np.searchsorted(lon_axis_i, cell_lon_i).astype(np.int32, copy=False),
        "lat_axis": lat_axis_i.astype(np.float32) / COORD_SCALE,
        "lon_axis": lon_axis_i.astype(np.float32) / COORD_SCALE,
    }


def _compute_trend(values: np.ndarray) -> Dict[str, np.ndarray]:
    x = YEARS.astype(np.float64)[:, None]
    y = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(y)
    n = valid.sum(axis=0).astype(np.float64)
    y0 = np.where(valid, y, 0.0)
    x0 = np.where(valid, x, 0.0)
    sx = x0.sum(axis=0)
    sy = y0.sum(axis=0)
    sxx = (x0 * x0).sum(axis=0)
    syy = (y0 * y0).sum(axis=0)
    sxy = (x0 * y0).sum(axis=0)
    denom = n * sxx - sx * sx
    enough = n >= float(MIN_YEARS_FOR_TREND)
    ok = enough & np.isfinite(denom) & (np.abs(denom) > 0.0)

    slope = np.full(n.shape, np.nan, dtype=np.float64)
    intercept = np.full(n.shape, np.nan, dtype=np.float64)
    slope[ok] = (n[ok] * sxy[ok] - sx[ok] * sy[ok]) / denom[ok]
    intercept[ok] = (sy[ok] - slope[ok] * sx[ok]) / n[ok]

    r_num = n * sxy - sx * sy
    r_den = (n * sxx - sx * sx) * (n * syy - sy * sy)
    r = np.full(n.shape, np.nan, dtype=np.float64)
    good_r = ok & np.isfinite(r_den) & (r_den > 0.0)
    r[good_r] = r_num[good_r] / np.sqrt(r_den[good_r])
    r = np.clip(r, -1.0, 1.0, out=r)
    r2 = r * r
    pvalue = np.full(n.shape, np.nan, dtype=np.float64)
    df = n - 2.0
    good_p = good_r & np.isfinite(df) & (df > 0.0) & (r2 < 1.0)
    t_stat = np.full(n.shape, np.nan, dtype=np.float64)
    t_stat[good_p] = r[good_p] * np.sqrt(df[good_p] / (1.0 - r2[good_p]))
    pvalue[good_p] = 2.0 * student_t.sf(np.abs(t_stat[good_p]), df[good_p])

    return {
        "slope": slope.astype(np.float32, copy=False),
        "intercept": intercept.astype(np.float32, copy=False),
        "r2": r2.astype(np.float32, copy=False),
        "pvalue": pvalue.astype(np.float32, copy=False),
        "n_years": n.astype(np.float32, copy=False),
    }


def _to_grid(flat_cell: np.ndarray, cell_lat_idx: np.ndarray, cell_lon_idx: np.ndarray, nlat: int, nlon: int) -> np.ndarray:
    out = np.full((nlat, nlon), np.nan, dtype=np.float32)
    out[cell_lat_idx, cell_lon_idx] = flat_cell
    return out


def _prepare_plot_grid(data: np.ndarray, lat: np.ndarray, lon: np.ndarray, lat_sign: float = 1.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    plot_data = np.asarray(data, dtype=np.float32)
    plot_lat = np.asarray(lat, dtype=np.float32)
    plot_lon = np.asarray(lon, dtype=np.float32)
    if plot_data.shape != (plot_lat.size, plot_lon.size):
        raise ValueError(f"Grid shape {plot_data.shape} does not match lat/lon sizes {(plot_lat.size, plot_lon.size)}")
    if lat_sign not in (-1.0, 1.0):
        raise ValueError(f"lat_sign must be -1.0 or 1.0, got {lat_sign}")
    if lat_sign < 0:
        plot_data = plot_data[::-1, :]
        plot_lat = (-plot_lat[::-1]).astype(np.float32, copy=False)
    if plot_lat.size > 1 and plot_lat[0] > plot_lat[-1]:
        plot_data = plot_data[::-1, :]
        plot_lat = plot_lat[::-1]
    if plot_lon.size > 1 and plot_lon[0] > plot_lon[-1]:
        plot_data = plot_data[:, ::-1]
        plot_lon = plot_lon[::-1]
    return plot_data, plot_lat, plot_lon


def _coord_edges(coord: np.ndarray) -> np.ndarray:
    coord = np.asarray(coord, dtype=np.float32)
    if coord.ndim != 1 or coord.size == 0:
        raise ValueError("Coordinate must be a non-empty 1D array")
    if coord.size == 1:
        delta = np.float32(0.5)
        return np.array([coord[0] - delta, coord[0] + delta], dtype=np.float32)
    mid = (coord[1:] + coord[:-1]) / 2.0
    first = coord[0] - (mid[0] - coord[0])
    last = coord[-1] + (coord[-1] - mid[-1])
    return np.concatenate(([first], mid, [last])).astype(np.float32, copy=False)


def _write_scenario_nc(
    cfg: TargetConfig,
    spec: DatasetSpec,
    out_path: str,
    lat_axis: np.ndarray,
    lon_axis: np.ndarray,
    trend_results: Dict[str, Dict[str, np.ndarray]],
    metric_specs: Dict[str, Dict[str, str]],
    cell_lat_idx: np.ndarray,
    cell_lon_idx: np.ndarray,
) -> None:
    with nc.Dataset(out_path, "w", format="NETCDF4") as dst:
        dst.createDimension("lat", lat_axis.size)
        dst.createDimension("lon", lon_axis.size)
        lat_var = dst.createVariable("lat", "f4", ("lat",))
        lon_var = dst.createVariable("lon", "f4", ("lon",))
        lat_var[:] = lat_axis
        lon_var[:] = lon_axis
        lat_var.units = "degrees_north"
        lon_var.units = "degrees_east"

        for metric, stat in trend_results.items():
            for suffix in ["slope", "pvalue", "r2", "n_years", "intercept"]:
                v = dst.createVariable(f"{metric}_{suffix}", "f4", ("lat", "lon"), zlib=True, complevel=4, fill_value=np.float32(np.nan))
                v[:, :] = _to_grid(stat[suffix], cell_lat_idx, cell_lon_idx, lat_axis.size, lon_axis.size)
            dst.variables[f"{metric}_slope"].units = metric_specs[metric]["unit"]
            dst.variables[f"{metric}_pvalue"].units = "1"
            dst.variables[f"{metric}_r2"].units = "1"
            dst.variables[f"{metric}_n_years"].units = "count"

        dst.title = f"Per-pixel yearly-trend maps for {cfg.display} drought-response indicators"
        dst.scenario = spec.key
        dst.drought_type = spec.drought_type
        dst.soil_layer = spec.soil_layer
        dst.period = f"{YEAR_MIN}-{YEAR_MAX}"
        dst.min_years_for_trend = MIN_YEARS_FOR_TREND
        dst.abs_value_scale_factor = cfg.abs_scale_factor


def _plot_metric_panels(cfg: TargetConfig, metric: str, files: Dict[str, str], plot_dir: str, metric_specs: Dict[str, Dict[str, str]]) -> None:
    arrays = []
    loaded = {}
    for sc in SCENARIO_ORDER:
        with nc.Dataset(files[sc], "r") as ds:
            arr = np.asarray(ds.variables[f"{metric}_slope"][:], dtype=np.float32)
            arrays.append(arr[np.isfinite(arr)])
            loaded[sc] = {
                "slope": arr,
                "lat": np.asarray(ds.variables["lat"][:], dtype=np.float32),
                "lon": np.asarray(ds.variables["lon"][:], dtype=np.float32),
            }
    finite_all = np.concatenate([a for a in arrays if a.size > 0]) if arrays else np.array([], dtype=np.float32)
    vmax = float(np.nanpercentile(np.abs(finite_all), 98)) if finite_all.size else 1.0
    if not np.isfinite(vmax) or vmax <= 0:
        vmax = 1.0

    fig, axes = plt.subplots(2, 2, figsize=(14, 7), dpi=220)
    fig.subplots_adjust(left=0.06, right=0.88, bottom=0.08, top=0.92, wspace=0.16, hspace=0.2)
    axes = axes.ravel()
    im = None
    for idx, sc in enumerate(SCENARIO_ORDER):
        ax = axes[idx]
        item = loaded[sc]
        plot_data, plot_lat, plot_lon = _prepare_plot_grid(item["slope"], item["lat"], item["lon"], lat_sign=cfg.plot_lat_sign)
        im = ax.pcolormesh(
            _coord_edges(plot_lon),
            _coord_edges(plot_lat),
            plot_data,
            cmap="RdBu_r",
            vmin=-vmax,
            vmax=vmax,
            shading="auto",
        )
        ax.set_title(SCENARIO_LABELS.get(sc, sc), fontsize=10)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_xlim(float(plot_lon[0]), float(plot_lon[-1]))
        ax.set_ylim(float(plot_lat[0]), float(plot_lat[-1]))
    cax = fig.add_axes([0.9, 0.16, 0.016, 0.68])
    cbar = fig.colorbar(im, cax=cax, orientation="vertical")
    cbar.set_label(f"Slope ({metric_specs[metric]['unit']})")
    fig.suptitle(f"{metric_specs[metric]['label']} (1980-2024)", y=0.97)
    fig.savefig(os.path.join(plot_dir, f"{metric}_pixel_trend_map_2x2.png"), bbox_inches="tight")
    plt.close(fig)


def process_scenario(cfg: TargetConfig, spec: DatasetSpec, metric_specs: Dict[str, Dict[str, str]], nc_out_dir: str) -> Tuple[str, pd.DataFrame]:
    if not os.path.exists(spec.path):
        raise FileNotFoundError(spec.path)

    prefix = cfg.event_prefix
    abs_min_var = f"{prefix}_min_abs"
    abs_drop_var = f"{prefix}_drop_abs"
    abs_rec_var = f"{prefix}_recovery_rate_abs"

    with nc.Dataset(spec.path, "r") as ds:
        n_events = len(ds.dimensions["event"])
        year_name = _year_var_name(ds)
        print(f"[{cfg.key}:{spec.key}] events={n_events} year_var={year_name}")

        lat_all = _read_var_chunk(ds.variables["lat"], 0, n_events).astype(np.float32, copy=False)
        lon_all = _read_var_chunk(ds.variables["lon"], 0, n_events).astype(np.float32, copy=False)
        map_info = _build_cell_index(lat_all, lon_all)
        del lat_all, lon_all

        cell_keys = map_info["cell_keys"]
        cell_lat_idx = map_info["cell_lat_idx"]
        cell_lon_idx = map_info["cell_lon_idx"]
        lat_axis = map_info["lat_axis"]
        lon_axis = map_info["lon_axis"]
        n_cells = cell_keys.size
        n_slots = int(n_cells * YEARS.size)

        sums = {name: np.zeros(n_slots, dtype=np.float32) for name in ["speed", "tmin", "tresp", "timp", "trec", "abs_min", "drop", "rec"]}
        counts = {name: np.zeros(n_slots, dtype=np.float32) for name in ["events", "response", "speed", "tmin", "tresp", "timp", "trec", "abs_min", "drop", "rec"]}

        year_var = ds.variables[year_name]
        response_var = ds.variables["response_detected"]
        lat_var = ds.variables["lat"]
        lon_var = ds.variables["lon"]

        t_min_var = ds.variables["t_min"]
        t_resp_var = ds.variables["t_response"]
        t_imp_var = ds.variables["t_impact"]
        t_rec_var = ds.variables["t_recover"]
        abs_min_obj = ds.variables[abs_min_var]
        drop_var = ds.variables[abs_drop_var]
        rec_var = ds.variables[abs_rec_var]

        for start in range(0, n_events, CHUNK_SIZE):
            end = min(start + CHUNK_SIZE, n_events)
            years_raw = _read_var_chunk(year_var, start, end)
            response_raw = _read_var_chunk(response_var, start, end)
            lat_raw = _read_var_chunk(lat_var, start, end)
            lon_raw = _read_var_chunk(lon_var, start, end)

            valid = np.isfinite(years_raw) & np.isfinite(lat_raw) & np.isfinite(lon_raw)
            if not np.any(valid):
                continue
            years_i = years_raw.astype(np.int32, copy=False)
            valid &= (years_i >= YEAR_MIN) & (years_i <= YEAR_MAX)
            if not np.any(valid):
                continue

            key = _pack_cell_key(_coord_to_int(lat_raw[valid]), _coord_to_int(lon_raw[valid]))
            cell_idx = np.searchsorted(cell_keys, key)
            year_idx = years_i[valid] - YEAR_MIN
            flat = year_idx.astype(np.int64) * n_cells + cell_idx.astype(np.int64)
            np.add.at(counts["events"], flat, 1.0)

            responded = valid & np.isfinite(response_raw) & (response_raw > 0)
            if not np.any(responded):
                continue

            key_r = _pack_cell_key(_coord_to_int(lat_raw[responded]), _coord_to_int(lon_raw[responded]))
            cell_idx_r = np.searchsorted(cell_keys, key_r)
            year_idx_r = years_i[responded] - YEAR_MIN
            flat_r = year_idx_r.astype(np.int64) * n_cells + cell_idx_r.astype(np.int64)
            np.add.at(counts["response"], flat_r, 1.0)

            def add_metric(name: str, values: np.ndarray, responded_mask: np.ndarray, scale: float = 1.0, positive_only: bool = False) -> None:
                mask = responded_mask & np.isfinite(values)
                if positive_only:
                    mask &= values > 0
                else:
                    mask &= values >= 0
                if not np.any(mask):
                    return
                key_m = _pack_cell_key(_coord_to_int(lat_raw[mask]), _coord_to_int(lon_raw[mask]))
                cell_idx_m = np.searchsorted(cell_keys, key_m)
                year_idx_m = years_i[mask] - YEAR_MIN
                flat_m = year_idx_m.astype(np.int64) * n_cells + cell_idx_m.astype(np.int64)
                vals = (values[mask] * scale).astype(np.float32, copy=False)
                np.add.at(sums[name], flat_m, vals)
                np.add.at(counts[name], flat_m, 1.0)

            t_resp_vals = _read_var_chunk(t_resp_var, start, end)
            add_metric("tresp", t_resp_vals, responded)
            speed_vals = np.full(t_resp_vals.shape, np.nan, dtype=np.float64)
            valid_speed = np.isfinite(t_resp_vals) & (t_resp_vals > 0)
            np.divide(1.0, t_resp_vals, out=speed_vals, where=valid_speed)
            add_metric("speed", speed_vals, responded & valid_speed, positive_only=True)
            add_metric("tmin", _read_var_chunk(t_min_var, start, end), responded)
            add_metric("timp", _read_var_chunk(t_imp_var, start, end), responded)
            add_metric("trec", _read_var_chunk(t_rec_var, start, end), responded)
            add_metric("abs_min", _read_var_chunk(abs_min_obj, start, end), responded, scale=cfg.abs_scale_factor, positive_only=False)
            add_metric("drop", _read_var_chunk(drop_var, start, end), responded, scale=cfg.abs_scale_factor, positive_only=False)
            add_metric("rec", _read_var_chunk(rec_var, start, end), responded, scale=cfg.abs_scale_factor, positive_only=False)

            if (start // CHUNK_SIZE) % 4 == 0:
                print(f"[{cfg.key}:{spec.key}] processed events {start:,}-{end:,} / {n_events:,}")

    events_2d = counts["events"].reshape(YEARS.size, n_cells)
    response_2d = counts["response"].reshape(YEARS.size, n_cells)
    metrics_2d = {name: sums[name].reshape(YEARS.size, n_cells) for name in sums}
    counts_2d = {name: counts[name].reshape(YEARS.size, n_cells) for name in counts if name not in {"events", "response"}}

    yearly_metrics = {
        "response_ratio": np.divide(response_2d, events_2d, out=np.full(events_2d.shape, np.nan, dtype=np.float32), where=events_2d > 0),
        "response_speed_proxy_mean": np.divide(metrics_2d["speed"], counts_2d["speed"], out=np.full(events_2d.shape, np.nan, dtype=np.float32), where=counts_2d["speed"] > 0),
        f"{prefix}_min_abs_mean": np.divide(metrics_2d["abs_min"], counts_2d["abs_min"], out=np.full(events_2d.shape, np.nan, dtype=np.float32), where=counts_2d["abs_min"] > 0),
        "t_min_mean": np.divide(metrics_2d["tmin"], counts_2d["tmin"], out=np.full(events_2d.shape, np.nan, dtype=np.float32), where=counts_2d["tmin"] > 0),
        "t_response_mean": np.divide(metrics_2d["tresp"], counts_2d["tresp"], out=np.full(events_2d.shape, np.nan, dtype=np.float32), where=counts_2d["tresp"] > 0),
        "t_impact_mean": np.divide(metrics_2d["timp"], counts_2d["timp"], out=np.full(events_2d.shape, np.nan, dtype=np.float32), where=counts_2d["timp"] > 0),
        "t_recover_mean": np.divide(metrics_2d["trec"], counts_2d["trec"], out=np.full(events_2d.shape, np.nan, dtype=np.float32), where=counts_2d["trec"] > 0),
        f"{prefix}_drop_abs_mean": np.divide(metrics_2d["drop"], counts_2d["drop"], out=np.full(events_2d.shape, np.nan, dtype=np.float32), where=counts_2d["drop"] > 0),
        f"{prefix}_recovery_rate_abs_mean": np.divide(metrics_2d["rec"], counts_2d["rec"], out=np.full(events_2d.shape, np.nan, dtype=np.float32), where=counts_2d["rec"] > 0),
    }

    trend_results = {metric: _compute_trend(values) for metric, values in yearly_metrics.items()}
    out_nc = os.path.join(nc_out_dir, f"{cfg.key}_response_pixel_trends_{spec.key}_1980_2024.nc")
    _write_scenario_nc(cfg, spec, out_nc, lat_axis, lon_axis, trend_results, metric_specs, cell_lat_idx, cell_lon_idx)

    rows = []
    for metric, stat in trend_results.items():
        slope = stat["slope"]
        pvalue = stat["pvalue"]
        finite = np.isfinite(slope)
        if np.any(finite):
            sv = slope[finite]
            sig = finite & np.isfinite(pvalue) & (pvalue < 0.05)
            rows.append(
                {
                    "scenario": spec.key,
                    "label": SCENARIO_LABELS.get(spec.key, spec.key),
                    "drought_type": spec.drought_type,
                    "soil_layer": spec.soil_layer,
                    "metric": metric,
                    "n_pixels": int(finite.sum()),
                    "mean_slope": float(np.nanmean(sv)),
                    "median_slope": float(np.nanmedian(sv)),
                    "p05_slope": float(np.nanpercentile(sv, 5)),
                    "p95_slope": float(np.nanpercentile(sv, 95)),
                    "frac_significant_p005": float(sig.sum() / max(1, finite.sum())),
                }
            )
    return out_nc, pd.DataFrame(rows)


def write_summary_md(cfg: TargetConfig, df: pd.DataFrame, out_md: str, metric_specs: Dict[str, Dict[str, str]]) -> None:
    lines = [
        f"# Pixel-Level {cfg.display} Response Trend Summary (1980-2024)",
        "",
        "Indicators:",
    ]
    lines.extend([f"- {metric}" for metric in metric_specs])
    lines.append(f"- absolute {cfg.display} metrics use scale factor `{cfg.abs_scale_factor}`")
    lines.extend(["", f"Trend method: OLS slope against year for each pixel (minimum {MIN_YEARS_FOR_TREND} valid years).", "", "## Spatial Summary"])
    if df.empty:
        lines.append("- No valid pixel trend results.")
    else:
        for _, row in df.sort_values(["metric", "scenario"]).iterrows():
            lines.append(
                "- {label} | {metric}: mean_slope={mean:.6g}, median={median:.6g}, p05={p05:.6g}, p95={p95:.6g}, sig_frac={sig:.3f}".format(
                    label=row["label"], metric=row["metric"], mean=row["mean_slope"], median=row["median_slope"], p05=row["p05_slope"], p95=row["p95_slope"], sig=row["frac_significant_p005"]
                )
            )
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze per-pixel trends for NEE or RECO.")
    parser.add_argument("--target", choices=sorted(TARGET_CONFIGS), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = TARGET_CONFIGS[args.target]
    metric_specs = build_metric_specs(cfg)
    output_dir = cfg.output_dir
    nc_out_dir = os.path.join(output_dir, "pixel_trend_maps")
    plot_dir = os.path.join(output_dir, "plots_pixel_trend")
    os.makedirs(nc_out_dir, exist_ok=True)
    os.makedirs(plot_dir, exist_ok=True)

    out_files: Dict[str, str] = {}
    frames: List[pd.DataFrame] = []
    for spec in cfg.datasets:
        out_nc, summary_df = process_scenario(cfg, spec, metric_specs, nc_out_dir)
        out_files[spec.key] = out_nc
        frames.append(summary_df)
        print(f"[DONE] {cfg.key}:{spec.key} -> {out_nc}")

    summary_df = pd.concat(frames, ignore_index=True)
    summary_csv = os.path.join(output_dir, f"{cfg.key}_pixel_trend_spatial_summary_1980_2024.csv")
    summary_md = os.path.join(output_dir, f"{cfg.key}_pixel_trend_spatial_summary_1980_2024.md")
    summary_df.to_csv(summary_csv, index=False, encoding="utf-8")
    write_summary_md(cfg, summary_df, summary_md, metric_specs)

    for metric in metric_specs:
        _plot_metric_panels(cfg, metric, out_files, plot_dir, metric_specs)
        print(f"[PLOT] {cfg.key}:{metric}")

    print("[DONE] summary_csv =", summary_csv)
    print("[DONE] summary_md =", summary_md)
    print("[DONE] map_dir =", plot_dir)


if __name__ == "__main__":
    main()
