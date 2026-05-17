#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Build RECO-only 0401 recovery spatial and trend figures for conclusion."""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
OUT_DIR = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/conclusion/"
    "RECO_recovery_valid"
)
SPATIAL_PNG = os.path.join(OUT_DIR, "reco_0401_recovery_mean_global.png")
TREND_PNG = os.path.join(OUT_DIR, "reco_0401_recovery_trend.png")
SUMMARY_CSV = os.path.join(OUT_DIR, "reco_0401_recovery_summary.csv")
SUMMARY_MD = os.path.join(OUT_DIR, "reco_0401_recovery_summary.md")

ANNUAL_CSV = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/compare_analysis2/"
    "v20260401_growingseason_recovery_gsdays/"
    "annual_response_recovery_trends_v20260401_growingseason_recovery_gsdays.csv"
)
SUMMARY_0401 = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/compare_analysis2/"
    "v20260401_growingseason_recovery_gsdays/"
    "summary_table_v20260401_growingseason_recovery_gsdays.csv"
)


@dataclass(frozen=True)
class Panel:
    soil_layer: str
    event_file: str


PANELS = [
    Panel(
        soil_layer="SMrz",
        event_file=(
            f"{BASE_DIR}/process/RECO-draught-analysis/code1/results/"
            "reco_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_"
            "rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
    ),
    Panel(
        soil_layer="SMs",
        event_file=(
            f"{BASE_DIR}/process/RECO-draught-analysis/code2_SMs/results/"
            "reco_response_SMs_drought_v20260401_growingseason_recovery_gsdays_"
            "rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
    ),
]


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
        recovery = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))

    valid = np.isfinite(lat_evt) & np.isfinite(lon_evt)
    lat_vals = np.unique(lat_evt[valid])
    lon_vals = np.unique(lon_evt[valid])
    lat_vals.sort()
    lon_vals.sort()

    nlat = len(lat_vals)
    nlon = len(lon_vals)
    lat_idx = np.searchsorted(lat_vals, lat_evt[valid])
    lon_idx = np.searchsorted(lon_vals, lon_evt[valid])
    flat_idx = lat_idx * nlon + lon_idx
    ncell = nlat * nlon

    recovery_valid = np.isfinite(recovery[valid])
    counts = np.bincount(flat_idx[recovery_valid], minlength=ncell).astype(np.int32)
    sums = np.bincount(
        flat_idx[recovery_valid],
        weights=recovery[valid][recovery_valid],
        minlength=ncell,
    )
    mean = np.full(ncell, np.nan, dtype=np.float64)
    ok = counts > 0
    mean[ok] = sums[ok] / counts[ok]
    return {
        "lat": lat_vals,
        "lon": lon_vals,
        "recovery_mean_days": mean.reshape(nlat, nlon),
    }


def extent_from_lon_lat(lon: np.ndarray, lat: np.ndarray) -> list[float]:
    dlon = float(np.nanmedian(np.diff(lon))) if lon.size > 1 else 0.25
    dlat = float(np.nanmedian(np.diff(lat))) if lat.size > 1 else 0.25
    return [
        float(lon[0] - dlon / 2),
        float(lon[-1] + dlon / 2),
        float(lat[0] - dlat / 2),
        float(lat[-1] + dlat / 2),
    ]


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def trend_line(years: np.ndarray, values: np.ndarray) -> tuple[float, float]:
    valid = np.isfinite(years) & np.isfinite(values)
    slope, intercept = np.polyfit(years[valid], values[valid], 1)
    return float(slope), float(intercept)


def plot_spatial() -> list[dict[str, float]]:
    aggregated = [aggregate_event_recovery_mean(panel.event_file) for panel in PANELS]
    finite_values = [
        item["recovery_mean_days"][np.isfinite(item["recovery_mean_days"])] for item in aggregated
    ]
    finite_values = [arr for arr in finite_values if arr.size > 0]
    joined = np.concatenate(finite_values)
    vmin = float(np.nanpercentile(joined, 2))
    vmax = float(np.nanpercentile(joined, 98))

    fig, axes = plt.subplots(1, 2, figsize=(15.5, 6.0), constrained_layout=True)
    summaries: list[dict[str, float]] = []
    im = None
    for ax, panel, data in zip(axes, PANELS, aggregated):
        arr = data["recovery_mean_days"]
        im = ax.imshow(
            arr,
            origin="lower",
            extent=extent_from_lon_lat(data["lon"], data["lat"]),
            aspect="auto",
            cmap="RdYlGn_r",
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_title(panel.soil_layer, fontsize=18)
        ax.set_xlabel("Longitude", fontsize=13)
        ax.set_ylabel("Latitude", fontsize=13)
        ax.set_xlim(-180, 180)
        ax.tick_params(labelsize=11)
        finite = arr[np.isfinite(arr)]
        summaries.append(
            {
                "soil_layer": panel.soil_layer,
                "spatial_mean_days": float(np.nanmean(finite)),
                "spatial_median_days": float(np.nanmedian(finite)),
                "spatial_p95_days": float(np.nanpercentile(finite, 95)),
            }
        )

    fig.suptitle("RECO Recovery Time Mean After Flash Drought", fontsize=22)
    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.95, pad=0.02)
    cbar.set_label("Recovery Time Mean (days)", fontsize=13)
    cbar.ax.tick_params(labelsize=11)
    fig.savefig(SPATIAL_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return summaries


def plot_trend() -> list[dict[str, float]]:
    rows = read_csv(ANNUAL_CSV)
    summary_rows = read_csv(SUMMARY_0401)
    selected = [
        row for row in rows if row["variable"] == "RECO" and row["code"] in {"code1", "code2"}
    ]
    fig, axes = plt.subplots(2, 1, figsize=(11.2, 8.2), sharex=True, constrained_layout=True)
    colors = {"SMrz": "#CC6677", "SMs": "#0072B2"}
    out_summary: list[dict[str, float]] = []

    for ax, code, soil in zip(axes, ["code1", "code2"], ["SMrz", "SMs"]):
        soil_rows = sorted(
            [row for row in selected if row["code"] == code and row["soil_layer"] == soil],
            key=lambda r: int(r["year"]),
        )
        years = np.array([int(r["year"]) for r in soil_rows], dtype=np.float64)
        values = np.array([float(r["recovery_mean"]) for r in soil_rows], dtype=np.float64)
        ax.plot(
            years,
            values,
            color=colors[soil],
            marker="o",
            markersize=6.5,
            linewidth=2.6,
        )
        slope, intercept = trend_line(years, values)
        ax.plot(
            years,
            intercept + slope * years,
            linestyle="--",
            linewidth=1.8,
            color=colors[soil],
            alpha=0.8,
        )
        ax.set_title(soil, fontsize=20)
        ax.set_ylabel("Recovery Time Mean (days)", fontsize=16)
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
        ax.tick_params(axis="both", labelsize=13)

        summary_row = next(
            row for row in summary_rows if row["variable"] == "RECO" and row["code"] == code
        )
        out_summary.append(
            {
                "soil_layer": soil,
                "global_mean_days": float(summary_row["recovery_mean_days"]),
                "global_median_days": float(summary_row["recovery_median_days"]),
                "global_p25_days": float(summary_row["recovery_p25_days"]),
                "global_p75_days": float(summary_row["recovery_p75_days"]),
                "trend_days_per_decade": float(summary_row["recovery_mean_slope_days_per_decade"]),
                "first_year": int(years[0]),
                "last_year": int(years[-1]),
                "first_year_mean": float(values[0]),
                "last_year_mean": float(values[-1]),
            }
        )

    axes[-1].set_xlabel("Year", fontsize=16)
    fig.suptitle("Temporal Trend of RECO Recovery Time After Flash Drought", fontsize=24)
    fig.savefig(TREND_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out_summary


def write_summary(spatial_rows: list[dict[str, float]], trend_rows: list[dict[str, float]]) -> None:
    merged = []
    for spatial in spatial_rows:
        trend = next(row for row in trend_rows if row["soil_layer"] == spatial["soil_layer"])
        merged.append({**spatial, **trend})

    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "soil_layer",
                "spatial_mean_days",
                "spatial_median_days",
                "spatial_p95_days",
                "global_mean_days",
                "global_median_days",
                "global_p25_days",
                "global_p75_days",
                "trend_days_per_decade",
                "first_year",
                "last_year",
                "first_year_mean",
                "last_year_mean",
            ],
        )
        writer.writeheader()
        writer.writerows(merged)

    lines = [
        "# RECO 0401 Recovery Summary",
        "",
        "| Soil layer | Global mean (d) | Median (d) | P25 (d) | P75 (d) | Trend (d/10a) | Spatial mean (d) | Spatial p95 (d) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in merged:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["soil_layer"],
                    f"{row['global_mean_days']:.2f}",
                    f"{row['global_median_days']:.2f}",
                    f"{row['global_p25_days']:.2f}",
                    f"{row['global_p75_days']:.2f}",
                    f"{row['trend_days_per_decade']:.2f}",
                    f"{row['spatial_mean_days']:.2f}",
                    f"{row['spatial_p95_days']:.2f}",
                ]
            )
            + " |"
        )
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    spatial_rows = plot_spatial()
    trend_rows = plot_trend()
    write_summary(spatial_rows, trend_rows)
    print(f"Wrote {SPATIAL_PNG}")
    print(f"Wrote {TREND_PNG}")
    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {SUMMARY_MD}")


if __name__ == "__main__":
    main()
