#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
import pandas as pd
from scipy.stats import t as student_t


BASE_DIR = "/home/xulc/flash_drought"
OUTPUT_DIR = os.path.join(BASE_DIR, "process/result_analysis/GPP_trend")
NC_OUT_DIR = os.path.join(OUTPUT_DIR, "pixel_trend_maps")
PLOT_DIR = os.path.join(OUTPUT_DIR, "plots_pixel_trend")
os.makedirs(NC_OUT_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

YEARS = np.arange(1980, 2025, dtype=np.int32)
YEAR_MIN = int(YEARS[0])
YEAR_MAX = int(YEARS[-1])
MIN_YEARS_FOR_TREND = 5
CHUNK_SIZE = 1_500_000
COORD_SCALE = 1000
BIT_MASK_32 = np.int64(0xFFFFFFFF)
ABS_SCALE_FACTOR = 0.01


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    drought_type: str
    soil_layer: str
    path: str


DATASETS: List[DatasetSpec] = [
    DatasetSpec(
        key="flash_SMrz",
        drought_type="flash",
        soil_layer="SMrz",
        path=os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v11_with_abs.nc",
        ),
    ),
    DatasetSpec(
        key="flash_SMs",
        drought_type="flash",
        soil_layer="SMs",
        path=os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v11_with_abs.nc",
        ),
    ),
    DatasetSpec(
        key="nonflash_SMrz",
        drought_type="nonflash",
        soil_layer="SMrz",
        path=os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v11_global_with_abs.nc",
        ),
    ),
    DatasetSpec(
        key="nonflash_SMs",
        drought_type="nonflash",
        soil_layer="SMs",
        path=os.path.join(
            BASE_DIR,
            "process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v11_global_with_abs.nc",
        ),
    ),
]

SCENARIO_LABELS = {
    "flash_SMrz": "Flash-SMrz",
    "flash_SMs": "Flash-SMs",
    "nonflash_SMrz": "Nonflash-SMrz",
    "nonflash_SMs": "Nonflash-SMs",
}

SCENARIO_ORDER = ["flash_SMrz", "flash_SMs", "nonflash_SMrz", "nonflash_SMs"]

METRIC_SPECS = {
    "response_ratio": {
        "label": "Response Ratio Trend",
        "unit": "1/year",
    },
    "response_speed_proxy_mean": {
        "label": "Response Speed Proxy Trend",
        "unit": "(1/day)/year",
    },
    "gpp_min_abs_mean": {
        "label": "GPP Min Abs Trend",
        "unit": "gC m^-2 day^-1 year^-1",
    },
    "t_min_mean": {
        "label": "t_min Trend",
        "unit": "day/year",
    },
    "t_response_mean": {
        "label": "t_response Trend",
        "unit": "day/year",
    },
    "t_impact_mean": {
        "label": "t_impact Trend",
        "unit": "day/year",
    },
    "t_recover_mean": {
        "label": "t_recover Trend",
        "unit": "day/year",
    },
    "gpp_drop_abs_mean": {
        "label": "GPP Drop Abs Trend",
        "unit": "gC m^-2 day^-1 year^-1",
    },
    "gpp_recovery_rate_abs_mean": {
        "label": "GPP Recovery Abs Rate Trend",
        "unit": "gC m^-2 day^-2 year^-1",
    },
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
    fill = getattr(var_obj, "_FillValue", None)
    return _to_float(var_obj[start:end], fill)


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
    lat_i = _coord_to_int(lat_all[valid])
    lon_i = _coord_to_int(lon_all[valid])
    cell_keys = np.unique(_pack_cell_key(lat_i, lon_i))

    cell_lat_i, cell_lon_i = _unpack_cell_key(cell_keys)
    lat_axis_i = np.unique(cell_lat_i)
    lon_axis_i = np.unique(cell_lon_i)

    cell_lat_idx = np.searchsorted(lat_axis_i, cell_lat_i)
    cell_lon_idx = np.searchsorted(lon_axis_i, cell_lon_i)

    return {
        "cell_keys": cell_keys,
        "cell_lat_idx": cell_lat_idx.astype(np.int32, copy=False),
        "cell_lon_idx": cell_lon_idx.astype(np.int32, copy=False),
        "lat_axis_i": lat_axis_i,
        "lon_axis_i": lon_axis_i,
        "lat_axis": (lat_axis_i.astype(np.float32) / COORD_SCALE),
        "lon_axis": (lon_axis_i.astype(np.float32) / COORD_SCALE),
    }


def _compute_trend(values: np.ndarray, years: np.ndarray, min_years: int) -> Dict[str, np.ndarray]:
    x = years.astype(np.float64)[:, None]
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
    enough = n >= float(min_years)
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


def _write_scenario_nc(
    spec: DatasetSpec,
    out_path: str,
    lat_axis: np.ndarray,
    lon_axis: np.ndarray,
    trend_results: Dict[str, Dict[str, np.ndarray]],
    cell_lat_idx: np.ndarray,
    cell_lon_idx: np.ndarray,
) -> None:
    nlat = lat_axis.size
    nlon = lon_axis.size
    with nc.Dataset(out_path, "w", format="NETCDF4") as dst:
        dst.createDimension("lat", nlat)
        dst.createDimension("lon", nlon)

        lat_var = dst.createVariable("lat", "f4", ("lat",))
        lon_var = dst.createVariable("lon", "f4", ("lon",))
        lat_var[:] = lat_axis
        lon_var[:] = lon_axis
        lat_var.units = "degrees_north"
        lon_var.units = "degrees_east"

        for metric, stat in trend_results.items():
            for suffix in ["slope", "pvalue", "r2", "n_years", "intercept"]:
                v = dst.createVariable(
                    f"{metric}_{suffix}",
                    "f4",
                    ("lat", "lon"),
                    zlib=True,
                    complevel=4,
                    fill_value=np.float32(np.nan),
                )
                grid = _to_grid(stat[suffix], cell_lat_idx, cell_lon_idx, nlat, nlon)
                v[:, :] = grid

            dst.variables[f"{metric}_slope"].units = METRIC_SPECS[metric]["unit"]
            dst.variables[f"{metric}_pvalue"].units = "1"
            dst.variables[f"{metric}_r2"].units = "1"
            dst.variables[f"{metric}_n_years"].units = "count"

        dst.title = "Per-pixel yearly-trend maps for GPP drought-response indicators"
        dst.scenario = spec.key
        dst.drought_type = spec.drought_type
        dst.soil_layer = spec.soil_layer
        dst.period = f"{YEAR_MIN}-{YEAR_MAX}"
        dst.min_years_for_trend = MIN_YEARS_FOR_TREND
        dst.notes = (
            "Indicators are annual per-pixel aggregates from event-level records; "
            "OLS trend computed against year."
        )
        dst.abs_value_scale_factor = ABS_SCALE_FACTOR


def _plot_metric_panels(metric: str, files: Dict[str, str]) -> None:
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
    if finite_all.size == 0:
        vmax = 1.0
    else:
        vmax = float(np.nanpercentile(np.abs(finite_all), 98))
        if not np.isfinite(vmax) or vmax <= 0:
            vmax = float(np.nanmax(np.abs(finite_all)))
            if not np.isfinite(vmax) or vmax <= 0:
                vmax = 1.0

    fig, axes = plt.subplots(2, 2, figsize=(14, 7), dpi=220)
    fig.subplots_adjust(left=0.06, right=0.88, bottom=0.08, top=0.92, wspace=0.16, hspace=0.2)
    axes = axes.ravel()
    im = None
    for i, sc in enumerate(SCENARIO_ORDER):
        ax = axes[i]
        arr = loaded[sc]["slope"]
        lat_ref = loaded[sc]["lat"]
        lon_ref = loaded[sc]["lon"]
        im = ax.imshow(
            arr,
            origin="lower",
            extent=[float(lon_ref.min()), float(lon_ref.max()), float(lat_ref.min()), float(lat_ref.max())],
            cmap="RdBu_r",
            vmin=-vmax,
            vmax=vmax,
            aspect="auto",
            interpolation="nearest",
        )
        ax.set_title(SCENARIO_LABELS.get(sc, sc), fontsize=10)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_xlim(float(lon_ref.min()), float(lon_ref.max()))
        ax.set_ylim(float(lat_ref.min()), float(lat_ref.max()))
        ax.grid(False)

    cax = fig.add_axes([0.9, 0.16, 0.016, 0.68])
    cbar = fig.colorbar(im, cax=cax, orientation="vertical")
    cbar.set_label(f"Slope ({METRIC_SPECS[metric]['unit']})")
    fig.suptitle(f"{METRIC_SPECS[metric]['label']} (1980-2024)", y=0.97)
    out_png = os.path.join(PLOT_DIR, f"{metric}_pixel_trend_map_2x2.png")
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def process_scenario(spec: DatasetSpec) -> Tuple[str, pd.DataFrame]:
    if not os.path.exists(spec.path):
        raise FileNotFoundError(spec.path)

    with nc.Dataset(spec.path, "r") as ds:
        n_events = len(ds.dimensions["event"])
        year_name = _year_var_name(ds)
        print(f"[{spec.key}] events={n_events} year_var={year_name}")

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
        n_year = YEARS.size
        n_slots = int(n_cells * n_year)
        print(f"[{spec.key}] used_cells={n_cells} lat={lat_axis.size} lon={lon_axis.size}")

        events_count = np.zeros(n_slots, dtype=np.float32)
        response_count = np.zeros(n_slots, dtype=np.float32)
        speed_sum = np.zeros(n_slots, dtype=np.float32)
        speed_count = np.zeros(n_slots, dtype=np.float32)
        tmin_sum = np.zeros(n_slots, dtype=np.float32)
        tmin_count = np.zeros(n_slots, dtype=np.float32)
        tresp_sum = np.zeros(n_slots, dtype=np.float32)
        tresp_count = np.zeros(n_slots, dtype=np.float32)
        timp_sum = np.zeros(n_slots, dtype=np.float32)
        timp_count = np.zeros(n_slots, dtype=np.float32)
        trec_sum = np.zeros(n_slots, dtype=np.float32)
        trec_count = np.zeros(n_slots, dtype=np.float32)
        gpp_min_sum = np.zeros(n_slots, dtype=np.float32)
        gpp_min_count = np.zeros(n_slots, dtype=np.float32)
        drop_sum = np.zeros(n_slots, dtype=np.float32)
        drop_count = np.zeros(n_slots, dtype=np.float32)
        rec_sum = np.zeros(n_slots, dtype=np.float32)
        rec_count = np.zeros(n_slots, dtype=np.float32)

        year_var = ds.variables[year_name]
        response_var = ds.variables["response_detected"]
        t_min_var = ds.variables["t_min"]
        t_resp_var = ds.variables["t_response"]
        t_imp_var = ds.variables["t_impact"]
        t_rec_var = ds.variables["t_recover"]
        gpp_min_var = ds.variables["gpp_min_abs"]
        drop_var = ds.variables["gpp_drop_abs"]
        rec_var = ds.variables["gpp_recovery_rate_abs"]
        lat_var = ds.variables["lat"]
        lon_var = ds.variables["lon"]

        for start in range(0, n_events, CHUNK_SIZE):
            end = min(start + CHUNK_SIZE, n_events)
            years_raw = _read_var_chunk(year_var, start, end)
            resp_raw = _read_var_chunk(response_var, start, end)
            lat_raw = _read_var_chunk(lat_var, start, end)
            lon_raw = _read_var_chunk(lon_var, start, end)

            valid = (
                np.isfinite(years_raw)
                & np.isfinite(lat_raw)
                & np.isfinite(lon_raw)
            )
            if not np.any(valid):
                continue

            years_i = years_raw.astype(np.int32, copy=False)
            valid &= (years_i >= YEAR_MIN) & (years_i <= YEAR_MAX)
            if not np.any(valid):
                continue

            lat_i = _coord_to_int(lat_raw[valid])
            lon_i = _coord_to_int(lon_raw[valid])
            key = _pack_cell_key(lat_i, lon_i)
            cell_idx = np.searchsorted(cell_keys, key)
            if np.any(cell_idx >= n_cells):
                ok = cell_idx < n_cells
                valid_idx = np.flatnonzero(valid)
                valid[valid_idx[~ok]] = False
                if not np.any(valid):
                    continue
                lat_i = _coord_to_int(lat_raw[valid])
                lon_i = _coord_to_int(lon_raw[valid])
                key = _pack_cell_key(lat_i, lon_i)
                cell_idx = np.searchsorted(cell_keys, key)

            year_idx = years_i[valid] - YEAR_MIN
            flat = year_idx.astype(np.int64) * n_cells + cell_idx.astype(np.int64)
            np.add.at(events_count, flat, 1.0)

            responded = valid & np.isfinite(resp_raw) & (resp_raw > 0)
            if np.any(responded):
                lat_i_r = _coord_to_int(lat_raw[responded])
                lon_i_r = _coord_to_int(lon_raw[responded])
                key_r = _pack_cell_key(lat_i_r, lon_i_r)
                cell_idx_r = np.searchsorted(cell_keys, key_r)
                year_idx_r = years_i[responded] - YEAR_MIN
                flat_r = year_idx_r.astype(np.int64) * n_cells + cell_idx_r.astype(np.int64)
                np.add.at(response_count, flat_r, 1.0)

                t_raw = _read_var_chunk(t_resp_var, start, end)
                t_resp_valid = responded & np.isfinite(t_raw) & (t_raw >= 0)
                if np.any(t_resp_valid):
                    lat_i_tr = _coord_to_int(lat_raw[t_resp_valid])
                    lon_i_tr = _coord_to_int(lon_raw[t_resp_valid])
                    key_tr = _pack_cell_key(lat_i_tr, lon_i_tr)
                    cell_idx_tr = np.searchsorted(cell_keys, key_tr)
                    year_idx_tr = years_i[t_resp_valid] - YEAR_MIN
                    flat_tr = year_idx_tr.astype(np.int64) * n_cells + cell_idx_tr.astype(np.int64)
                    t_resp_vals = t_raw[t_resp_valid].astype(np.float32, copy=False)
                    np.add.at(tresp_sum, flat_tr, t_resp_vals)
                    np.add.at(tresp_count, flat_tr, 1.0)

                speed_valid = responded & np.isfinite(t_raw) & (t_raw > 0)
                if np.any(speed_valid):
                    lat_i_s = _coord_to_int(lat_raw[speed_valid])
                    lon_i_s = _coord_to_int(lon_raw[speed_valid])
                    key_s = _pack_cell_key(lat_i_s, lon_i_s)
                    cell_idx_s = np.searchsorted(cell_keys, key_s)
                    year_idx_s = years_i[speed_valid] - YEAR_MIN
                    flat_s = year_idx_s.astype(np.int64) * n_cells + cell_idx_s.astype(np.int64)
                    speed_vals = (1.0 / t_raw[speed_valid]).astype(np.float32, copy=False)
                    np.add.at(speed_sum, flat_s, speed_vals)
                    np.add.at(speed_count, flat_s, 1.0)

                tmin_raw = _read_var_chunk(t_min_var, start, end)
                tmin_valid = responded & np.isfinite(tmin_raw) & (tmin_raw >= 0)
                if np.any(tmin_valid):
                    lat_i_tm = _coord_to_int(lat_raw[tmin_valid])
                    lon_i_tm = _coord_to_int(lon_raw[tmin_valid])
                    key_tm = _pack_cell_key(lat_i_tm, lon_i_tm)
                    cell_idx_tm = np.searchsorted(cell_keys, key_tm)
                    year_idx_tm = years_i[tmin_valid] - YEAR_MIN
                    flat_tm = year_idx_tm.astype(np.int64) * n_cells + cell_idx_tm.astype(np.int64)
                    tmin_vals = tmin_raw[tmin_valid].astype(np.float32, copy=False)
                    np.add.at(tmin_sum, flat_tm, tmin_vals)
                    np.add.at(tmin_count, flat_tm, 1.0)

                timp_raw = _read_var_chunk(t_imp_var, start, end)
                timp_valid = responded & np.isfinite(timp_raw) & (timp_raw >= 0)
                if np.any(timp_valid):
                    lat_i_ti = _coord_to_int(lat_raw[timp_valid])
                    lon_i_ti = _coord_to_int(lon_raw[timp_valid])
                    key_ti = _pack_cell_key(lat_i_ti, lon_i_ti)
                    cell_idx_ti = np.searchsorted(cell_keys, key_ti)
                    year_idx_ti = years_i[timp_valid] - YEAR_MIN
                    flat_ti = year_idx_ti.astype(np.int64) * n_cells + cell_idx_ti.astype(np.int64)
                    timp_vals = timp_raw[timp_valid].astype(np.float32, copy=False)
                    np.add.at(timp_sum, flat_ti, timp_vals)
                    np.add.at(timp_count, flat_ti, 1.0)

                trec_raw = _read_var_chunk(t_rec_var, start, end)
                trec_valid = responded & np.isfinite(trec_raw) & (trec_raw >= 0)
                if np.any(trec_valid):
                    lat_i_trec = _coord_to_int(lat_raw[trec_valid])
                    lon_i_trec = _coord_to_int(lon_raw[trec_valid])
                    key_trec = _pack_cell_key(lat_i_trec, lon_i_trec)
                    cell_idx_trec = np.searchsorted(cell_keys, key_trec)
                    year_idx_trec = years_i[trec_valid] - YEAR_MIN
                    flat_trec = year_idx_trec.astype(np.int64) * n_cells + cell_idx_trec.astype(np.int64)
                    trec_vals = trec_raw[trec_valid].astype(np.float32, copy=False)
                    np.add.at(trec_sum, flat_trec, trec_vals)
                    np.add.at(trec_count, flat_trec, 1.0)

                gpp_min_raw = _read_var_chunk(gpp_min_var, start, end)
                gpp_min_valid = responded & np.isfinite(gpp_min_raw)
                if np.any(gpp_min_valid):
                    lat_i_gmin = _coord_to_int(lat_raw[gpp_min_valid])
                    lon_i_gmin = _coord_to_int(lon_raw[gpp_min_valid])
                    key_gmin = _pack_cell_key(lat_i_gmin, lon_i_gmin)
                    cell_idx_gmin = np.searchsorted(cell_keys, key_gmin)
                    year_idx_gmin = years_i[gpp_min_valid] - YEAR_MIN
                    flat_gmin = year_idx_gmin.astype(np.int64) * n_cells + cell_idx_gmin.astype(np.int64)
                    gpp_min_vals = (gpp_min_raw[gpp_min_valid] * ABS_SCALE_FACTOR).astype(np.float32, copy=False)
                    np.add.at(gpp_min_sum, flat_gmin, gpp_min_vals)
                    np.add.at(gpp_min_count, flat_gmin, 1.0)

                drop_raw = _read_var_chunk(drop_var, start, end)
                drop_valid = responded & np.isfinite(drop_raw)
                if np.any(drop_valid):
                    lat_i_d = _coord_to_int(lat_raw[drop_valid])
                    lon_i_d = _coord_to_int(lon_raw[drop_valid])
                    key_d = _pack_cell_key(lat_i_d, lon_i_d)
                    cell_idx_d = np.searchsorted(cell_keys, key_d)
                    year_idx_d = years_i[drop_valid] - YEAR_MIN
                    flat_d = year_idx_d.astype(np.int64) * n_cells + cell_idx_d.astype(np.int64)
                    drop_vals = (drop_raw[drop_valid] * ABS_SCALE_FACTOR).astype(np.float32, copy=False)
                    np.add.at(drop_sum, flat_d, drop_vals)
                    np.add.at(drop_count, flat_d, 1.0)

                rec_raw = _read_var_chunk(rec_var, start, end)
                rec_valid = responded & np.isfinite(rec_raw)
                if np.any(rec_valid):
                    lat_i_rc = _coord_to_int(lat_raw[rec_valid])
                    lon_i_rc = _coord_to_int(lon_raw[rec_valid])
                    key_rc = _pack_cell_key(lat_i_rc, lon_i_rc)
                    cell_idx_rc = np.searchsorted(cell_keys, key_rc)
                    year_idx_rc = years_i[rec_valid] - YEAR_MIN
                    flat_rc = year_idx_rc.astype(np.int64) * n_cells + cell_idx_rc.astype(np.int64)
                    rec_vals = (rec_raw[rec_valid] * ABS_SCALE_FACTOR).astype(np.float32, copy=False)
                    np.add.at(rec_sum, flat_rc, rec_vals)
                    np.add.at(rec_count, flat_rc, 1.0)

            if (start // CHUNK_SIZE) % 4 == 0:
                print(f"[{spec.key}] processed events {start:,}-{end:,} / {n_events:,}")

    events_2d = events_count.reshape(YEARS.size, n_cells)
    resp_2d = response_count.reshape(YEARS.size, n_cells)
    speed_sum_2d = speed_sum.reshape(YEARS.size, n_cells)
    speed_cnt_2d = speed_count.reshape(YEARS.size, n_cells)
    tmin_sum_2d = tmin_sum.reshape(YEARS.size, n_cells)
    tmin_cnt_2d = tmin_count.reshape(YEARS.size, n_cells)
    tresp_sum_2d = tresp_sum.reshape(YEARS.size, n_cells)
    tresp_cnt_2d = tresp_count.reshape(YEARS.size, n_cells)
    timp_sum_2d = timp_sum.reshape(YEARS.size, n_cells)
    timp_cnt_2d = timp_count.reshape(YEARS.size, n_cells)
    trec_sum_2d = trec_sum.reshape(YEARS.size, n_cells)
    trec_cnt_2d = trec_count.reshape(YEARS.size, n_cells)
    gpp_min_sum_2d = gpp_min_sum.reshape(YEARS.size, n_cells)
    gpp_min_cnt_2d = gpp_min_count.reshape(YEARS.size, n_cells)
    drop_sum_2d = drop_sum.reshape(YEARS.size, n_cells)
    drop_cnt_2d = drop_count.reshape(YEARS.size, n_cells)
    rec_sum_2d = rec_sum.reshape(YEARS.size, n_cells)
    rec_cnt_2d = rec_count.reshape(YEARS.size, n_cells)

    with np.errstate(invalid="ignore", divide="ignore"):
        response_ratio = np.full(events_2d.shape, np.nan, dtype=np.float32)
        np.divide(resp_2d, events_2d, out=response_ratio, where=events_2d > 0)

        speed_mean = np.full(speed_sum_2d.shape, np.nan, dtype=np.float32)
        np.divide(speed_sum_2d, speed_cnt_2d, out=speed_mean, where=speed_cnt_2d > 0)

        tmin_mean = np.full(tmin_sum_2d.shape, np.nan, dtype=np.float32)
        np.divide(tmin_sum_2d, tmin_cnt_2d, out=tmin_mean, where=tmin_cnt_2d > 0)

        t_response_mean = np.full(tresp_sum_2d.shape, np.nan, dtype=np.float32)
        np.divide(tresp_sum_2d, tresp_cnt_2d, out=t_response_mean, where=tresp_cnt_2d > 0)

        t_impact_mean = np.full(timp_sum_2d.shape, np.nan, dtype=np.float32)
        np.divide(timp_sum_2d, timp_cnt_2d, out=t_impact_mean, where=timp_cnt_2d > 0)

        t_recover_mean = np.full(trec_sum_2d.shape, np.nan, dtype=np.float32)
        np.divide(trec_sum_2d, trec_cnt_2d, out=t_recover_mean, where=trec_cnt_2d > 0)

        gpp_min_mean = np.full(gpp_min_sum_2d.shape, np.nan, dtype=np.float32)
        np.divide(gpp_min_sum_2d, gpp_min_cnt_2d, out=gpp_min_mean, where=gpp_min_cnt_2d > 0)

        drop_mean = np.full(drop_sum_2d.shape, np.nan, dtype=np.float32)
        np.divide(drop_sum_2d, drop_cnt_2d, out=drop_mean, where=drop_cnt_2d > 0)

        rec_mean = np.full(rec_sum_2d.shape, np.nan, dtype=np.float32)
        np.divide(rec_sum_2d, rec_cnt_2d, out=rec_mean, where=rec_cnt_2d > 0)

    yearly_metrics = {
        "response_ratio": response_ratio,
        "response_speed_proxy_mean": speed_mean,
        "gpp_min_abs_mean": gpp_min_mean,
        "t_min_mean": tmin_mean,
        "t_response_mean": t_response_mean,
        "t_impact_mean": t_impact_mean,
        "t_recover_mean": t_recover_mean,
        "gpp_drop_abs_mean": drop_mean,
        "gpp_recovery_rate_abs_mean": rec_mean,
    }

    trend_results = {
        metric: _compute_trend(values=arr, years=YEARS, min_years=MIN_YEARS_FOR_TREND)
        for metric, arr in yearly_metrics.items()
    }

    out_nc = os.path.join(NC_OUT_DIR, f"gpp_response_pixel_trends_{spec.key}_1980_2024.nc")
    _write_scenario_nc(
        spec=spec,
        out_path=out_nc,
        lat_axis=map_info["lat_axis"],
        lon_axis=map_info["lon_axis"],
        trend_results=trend_results,
        cell_lat_idx=map_info["cell_lat_idx"],
        cell_lon_idx=map_info["cell_lon_idx"],
    )

    summary_rows = []
    for metric, stat in trend_results.items():
        slope = stat["slope"]
        pval = stat["pvalue"]
        finite = np.isfinite(slope)
        if np.any(finite):
            slope_valid = slope[finite]
            sig_mask = finite & np.isfinite(pval) & (pval < 0.05)
            summary_rows.append(
                {
                    "scenario": spec.key,
                    "label": SCENARIO_LABELS.get(spec.key, spec.key),
                    "drought_type": spec.drought_type,
                    "soil_layer": spec.soil_layer,
                    "metric": metric,
                    "n_pixels": int(finite.sum()),
                    "mean_slope": float(np.nanmean(slope_valid)),
                    "median_slope": float(np.nanmedian(slope_valid)),
                    "p05_slope": float(np.nanpercentile(slope_valid, 5)),
                    "p95_slope": float(np.nanpercentile(slope_valid, 95)),
                    "frac_significant_p005": float(sig_mask.sum() / max(1, finite.sum())),
                }
            )
        else:
            summary_rows.append(
                {
                    "scenario": spec.key,
                    "label": SCENARIO_LABELS.get(spec.key, spec.key),
                    "drought_type": spec.drought_type,
                    "soil_layer": spec.soil_layer,
                    "metric": metric,
                    "n_pixels": 0,
                    "mean_slope": np.nan,
                    "median_slope": np.nan,
                    "p05_slope": np.nan,
                    "p95_slope": np.nan,
                    "frac_significant_p005": np.nan,
                }
            )

    return out_nc, pd.DataFrame(summary_rows)


def write_summary_md(df: pd.DataFrame, out_md: str) -> None:
    lines: List[str] = []
    lines.append("# Pixel-Level GPP Response Trend Summary (1980-2024)")
    lines.append("")
    lines.append("Indicators:")
    for metric in METRIC_SPECS:
        lines.append(f"- {metric}")
    lines.append(f"- absolute GPP metrics use scale factor `{ABS_SCALE_FACTOR}` (DN -> flux)")
    lines.append("")
    lines.append("Trend method:")
    lines.append(f"- OLS slope against year for each pixel (minimum {MIN_YEARS_FOR_TREND} valid years).")
    lines.append("")
    lines.append("## Spatial Summary")

    if df.empty:
        lines.append("- No valid pixel trend results.")
    else:
        for _, r in df.sort_values(["metric", "scenario"]).iterrows():
            lines.append(
                "- {label} | {metric}: mean_slope={mean:.6g}, median={median:.6g}, p05={p05:.6g}, p95={p95:.6g}, sig_frac={sig:.3f}".format(
                    label=r["label"],
                    metric=r["metric"],
                    mean=r["mean_slope"],
                    median=r["median_slope"],
                    p05=r["p05_slope"],
                    p95=r["p95_slope"],
                    sig=r["frac_significant_p005"],
                )
            )

    lines.append("")
    lines.append("## Outputs")
    lines.append("- pixel trend nc: `pixel_trend_maps/gpp_response_pixel_trends_<scenario>_1980_2024.nc`")
    for metric in METRIC_SPECS:
        lines.append(f"- map plot: `plots_pixel_trend/{metric}_pixel_trend_map_2x2.png`")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    out_files: Dict[str, str] = {}
    summary_frames: List[pd.DataFrame] = []

    for spec in DATASETS:
        out_nc, summary_df = process_scenario(spec)
        out_files[spec.key] = out_nc
        summary_frames.append(summary_df)
        print(f"[DONE] {spec.key} -> {out_nc}")

    summary_all = pd.concat(summary_frames, ignore_index=True)
    summary_csv = os.path.join(OUTPUT_DIR, "gpp_pixel_trend_spatial_summary_1980_2024.csv")
    summary_all.to_csv(summary_csv, index=False, encoding="utf-8")

    for metric in METRIC_SPECS:
        _plot_metric_panels(metric, out_files)
        print(f"[PLOT] {metric}")

    summary_md = os.path.join(OUTPUT_DIR, "gpp_pixel_trend_spatial_summary_1980_2024.md")
    write_summary_md(summary_all, summary_md)

    print("[DONE] summary_csv =", summary_csv)
    print("[DONE] summary_md =", summary_md)
    print("[DONE] map_dir =", PLOT_DIR)


if __name__ == "__main__":
    main()
