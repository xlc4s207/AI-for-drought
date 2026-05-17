#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Plot BESS 0401 vs FluxSat fixlon spatial comparison for recovery mean."""

from __future__ import annotations

import math
import os
import csv
from dataclasses import dataclass
from typing import Iterable

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
    "fluxsat_compare_analysis2/bess0401_vs_fluxsat_fixlon_spatial_compare"
)
OUT_SUMMARY_CSV = os.path.join(OUT_DIR, "bess_fluxsat_spatial_consistency_summary.csv")
START_YEAR = 2001
END_YEAR = 2018


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    bess_event_file: str
    fluxsat_event_file: str
    out_png: str


SCENARIOS = [
    Scenario(
        key="SMrz",
        title="SMrz Recovery Mean",
        bess_event_file=(
            f"{BASE_DIR}/process/GPP-draught-analysis/code1/results/"
            "gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_"
            "rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
        fluxsat_event_file=(
            f"{BASE_DIR}/process/fluxsat-draught-analysis/code1/results/"
            "fluxsat_gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_"
            "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426.nc"
        ),
        out_png=os.path.join(OUT_DIR, "smrz_recovery_mean_bess0401_vs_fluxsat_fixlon.png"),
    ),
    Scenario(
        key="SMs",
        title="SMs Recovery Mean",
        bess_event_file=(
            f"{BASE_DIR}/process/GPP-draught-analysis/code2_SMs/results/"
            "gpp_response_SMs_events_global_v20260401_growingseason_recovery_gsdays_"
            "rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
        fluxsat_event_file=(
            f"{BASE_DIR}/process/fluxsat-draught-analysis/code2_SMs/results/"
            "fluxsat_gpp_response_SMs_events_global_v20260401_growingseason_recovery_gsdays_"
            "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426.nc"
        ),
        out_png=os.path.join(OUT_DIR, "sms_recovery_mean_bess0401_vs_fluxsat_fixlon.png"),
    ),
]


def setup_font() -> None:
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


def aggregate_event_recovery_mean(event_file: str) -> dict[str, np.ndarray]:
    with nc.Dataset(event_file, "r") as ds:
        lat_evt = to_numpy(ds.variables["lat"]).astype(np.float64)
        lon_evt = to_numpy(ds.variables["lon"]).astype(np.float64)
        onset_year = to_numpy(ds.variables["onset_year"]).astype(np.float64)
        t_recover = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))

    valid_evt = (
        np.isfinite(lat_evt)
        & np.isfinite(lon_evt)
        & np.isfinite(onset_year)
        & (onset_year >= START_YEAR)
        & (onset_year <= END_YEAR)
    )
    lat_vals = np.unique(lat_evt[valid_evt])
    lon_vals = np.unique(lon_evt[valid_evt])
    lat_vals.sort()
    lon_vals.sort()
    if lat_vals.size == 0 or lon_vals.size == 0:
        raise RuntimeError(
            f"No valid events remain in {event_file} for onset_year {START_YEAR}-{END_YEAR}."
        )
    nlat = len(lat_vals)
    nlon = len(lon_vals)

    lat_idx = np.searchsorted(lat_vals, lat_evt[valid_evt])
    lon_idx = np.searchsorted(lon_vals, lon_evt[valid_evt])
    flat_idx = lat_idx * nlon + lon_idx
    ncell = nlat * nlon

    recover_valid = np.isfinite(t_recover[valid_evt])
    recovery_count = np.bincount(flat_idx[recover_valid], minlength=ncell).astype(np.int32)
    recovery_sum = np.bincount(
        flat_idx[recover_valid],
        weights=t_recover[valid_evt][recover_valid],
        minlength=ncell,
    )
    recovery_mean = np.full(ncell, np.nan, dtype=np.float64)
    ok = recovery_count > 0
    recovery_mean[ok] = recovery_sum[ok] / recovery_count[ok]
    return {
        "lat": lat_vals,
        "lon": lon_vals,
        "recovery_mean_days": recovery_mean.reshape(nlat, nlon),
    }


def align_common_grid(
    bess: dict[str, np.ndarray],
    fluxsat: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    lat_b = np.asarray(bess["lat"], dtype=np.float64)
    lon_b = np.asarray(bess["lon"], dtype=np.float64)
    lat_f = np.asarray(fluxsat["lat"], dtype=np.float64)
    lon_f = np.asarray(fluxsat["lon"], dtype=np.float64)
    common_lat = np.intersect1d(np.round(lat_b, 6), np.round(lat_f, 6))
    common_lon = np.intersect1d(np.round(lon_b, 6), np.round(lon_f, 6))
    idx_b_lat = np.nonzero(np.isin(np.round(lat_b, 6), common_lat))[0]
    idx_f_lat = np.nonzero(np.isin(np.round(lat_f, 6), common_lat))[0]
    idx_b_lon = np.nonzero(np.isin(np.round(lon_b, 6), common_lon))[0]
    idx_f_lon = np.nonzero(np.isin(np.round(lon_f, 6), common_lon))[0]
    b = np.asarray(bess["recovery_mean_days"], dtype=np.float64)[np.ix_(idx_b_lat, idx_b_lon)]
    f = np.asarray(fluxsat["recovery_mean_days"], dtype=np.float64)[np.ix_(idx_f_lat, idx_f_lon)]
    lat = lat_b[idx_b_lat]
    lon = lon_b[idx_b_lon]
    return lat, lon, b, f


def summarize_pair(scenario: Scenario) -> dict[str, object]:
    bess = aggregate_event_recovery_mean(scenario.bess_event_file)
    fluxsat = aggregate_event_recovery_mean(scenario.fluxsat_event_file)
    lat, lon, bess_grid, fluxsat_grid = align_common_grid(bess, fluxsat)
    mask = np.isfinite(bess_grid) & np.isfinite(fluxsat_grid)
    bess_vals = bess_grid[mask]
    fluxsat_vals = fluxsat_grid[mask]
    corr = float(np.corrcoef(bess_vals, fluxsat_vals)[0, 1]) if mask.sum() > 1 else float("nan")
    diff = float(np.nanmean(bess_vals - fluxsat_vals))
    lat2d = np.repeat(lat[:, None], len(lon), axis=1)
    weights = np.cos(np.deg2rad(lat2d))[mask]
    bess_weighted = float(np.sum(bess_vals * weights) / np.sum(weights))
    fluxsat_weighted = float(np.sum(fluxsat_vals * weights) / np.sum(weights))
    bess_hotspot_threshold = float(np.nanquantile(bess_vals, 0.8))
    fluxsat_hotspot_threshold = float(np.nanquantile(fluxsat_vals, 0.8))
    bess_hotspot = bess_vals >= bess_hotspot_threshold
    fluxsat_hotspot = fluxsat_vals >= fluxsat_hotspot_threshold
    hotspot_intersection = int(np.count_nonzero(bess_hotspot & fluxsat_hotspot))
    hotspot_union = int(np.count_nonzero(bess_hotspot | fluxsat_hotspot))
    hotspot_jaccard = float(hotspot_intersection / hotspot_union) if hotspot_union > 0 else float("nan")
    return {
        "scenario": scenario.key,
        "start_year": START_YEAR,
        "end_year": END_YEAR,
        "shared_valid_pixels": int(mask.sum()),
        "bess_area_weighted_recovery_mean_days": bess_weighted,
        "fluxsat_area_weighted_recovery_mean_days": fluxsat_weighted,
        "spatial_correlation": corr,
        "mean_difference_bess_minus_fluxsat_days": diff,
        "hotspot_definition": "top20pct_within_shared_valid_each_product",
        "bess_hotspot_threshold_days": bess_hotspot_threshold,
        "fluxsat_hotspot_threshold_days": fluxsat_hotspot_threshold,
        "hotspot_jaccard_overlap": hotspot_jaccard,
        "hotspot_intersection_pixels": hotspot_intersection,
        "hotspot_union_pixels": hotspot_union,
    }


def plot_pair(scenario: Scenario) -> None:
    bess = aggregate_event_recovery_mean(scenario.bess_event_file)
    fluxsat = aggregate_event_recovery_mean(scenario.fluxsat_event_file)

    vals = []
    for arr in [bess["recovery_mean_days"], fluxsat["recovery_mean_days"]]:
        finite = arr[np.isfinite(arr)]
        if finite.size:
            vals.append(finite)
    joined = np.concatenate(vals)
    vmin = float(np.nanpercentile(joined, 2))
    vmax = float(np.nanpercentile(joined, 98))

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.8), constrained_layout=True)
    ims = []
    for ax, data, label in [
        (axes[0], bess, "BESS"),
        (axes[1], fluxsat, "Fluxsat"),
    ]:
        lon = data["lon"]
        lat = data["lat"]
        dlon = float(np.nanmedian(np.diff(lon))) if lon.size > 1 else 0.25
        dlat = float(np.nanmedian(np.diff(lat))) if lat.size > 1 else 0.25
        extent = [
            float(lon[0] - dlon / 2),
            float(lon[-1] + dlon / 2),
            float(lat[0] - dlat / 2),
            float(lat[-1] + dlat / 2),
        ]
        im = ax.imshow(
            data["recovery_mean_days"],
            origin="lower",
            extent=extent,
            aspect="auto",
            cmap="RdYlGn_r",
            vmin=vmin,
            vmax=vmax,
        )
        ims.append(im)
        ax.set_title(f"{label}")
        ax.set_xlabel("Lon")
        ax.set_ylabel("Lat")
        ax.set_xlim(-180, 180)

    fig.suptitle(
        f"{scenario.title}: BESS vs Fluxsat ({START_YEAR}-{END_YEAR})",
        fontsize=16,
    )
    fig.colorbar(ims[-1], ax=axes[:], shrink=0.95, pad=0.02, label="days")
    fig.savefig(scenario.out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    setup_font()
    summary_rows = []
    for scenario in SCENARIOS:
        plot_pair(scenario)
        summary_rows.append(summarize_pair(scenario))
        print(f"Wrote {scenario.out_png}")
    with open(OUT_SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scenario",
                "start_year",
                "end_year",
                "shared_valid_pixels",
                "bess_area_weighted_recovery_mean_days",
                "fluxsat_area_weighted_recovery_mean_days",
                "spatial_correlation",
                "mean_difference_bess_minus_fluxsat_days",
                "hotspot_definition",
                "bess_hotspot_threshold_days",
                "fluxsat_hotspot_threshold_days",
                "hotspot_jaccard_overlap",
                "hotspot_intersection_pixels",
                "hotspot_union_pixels",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Wrote {OUT_SUMMARY_CSV}")


if __name__ == "__main__":
    main()
