#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Build SMrz GPP/RECO BESS-vs-FluxSat comparison figures for conclusion."""

from __future__ import annotations

import csv
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
    "BESS_Fluxsat_valid"
)
SPATIAL_PNG = os.path.join(
    OUT_DIR, "smrz_gpp_reco_recovery_mean_bess_fluxsat_compare.png"
)
TREND_PNG = os.path.join(
    OUT_DIR, "smrz_gpp_reco_recovery_trend_bess_fluxsat_compare.png"
)
TREND_WITH_BAR_PNG = os.path.join(
    OUT_DIR, "smrz_gpp_reco_recovery_trend_bess_fluxsat_compare_with_bar.png"
)

ANNUAL_FLUXSAT_CSV = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/fluxsat_compare_analysis2/"
    "fluxsat_0401_sensitivity_compare/fluxsat_0401_sensitivity_annual.csv"
)
ANNUAL_0401_CSV = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/compare_analysis2/"
    "v20260401_growingseason_recovery_gsdays/"
    "annual_response_recovery_trends_v20260401_growingseason_recovery_gsdays.csv"
)

START_YEAR = 2001
END_YEAR = 2018


@dataclass(frozen=True)
class SpatialPanel:
    row: int
    col: int
    title: str
    event_file: str | None
    letter: str


SPATIAL_PANELS = [
    SpatialPanel(
        row=0,
        col=0,
        title="GPP - BESS",
        letter="a",
        event_file=(
            f"{BASE_DIR}/process/GPP-draught-analysis/code1/results/"
            "gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_"
            "rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
    ),
    SpatialPanel(
        row=0,
        col=2,
        title="GPP - FluxSat",
        letter="b",
        event_file=(
            f"{BASE_DIR}/process/fluxsat-draught-analysis/code1/results/"
            "fluxsat_gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_"
            "rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100cap_fixlon_v20260426.nc"
        ),
    ),
    SpatialPanel(
        row=1,
        col=1,
        title="RECO - BESS",
        letter="c",
        event_file=(
            f"{BASE_DIR}/process/RECO-draught-analysis/code1/results/"
            "reco_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_"
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


def extent_from_lon_lat(lon: np.ndarray, lat: np.ndarray) -> list[float]:
    dlon = float(np.nanmedian(np.diff(lon))) if lon.size > 1 else 0.25
    dlat = float(np.nanmedian(np.diff(lat))) if lat.size > 1 else 0.25
    return [
        float(lon[0] - dlon / 2),
        float(lon[-1] + dlon / 2),
        float(lat[0] - dlat / 2),
        float(lat[-1] + dlat / 2),
    ]


def aggregate_event_recovery_mean(event_file: str) -> dict[str, np.ndarray]:
    with nc.Dataset(event_file, "r") as ds:
        lat_evt = to_numpy(ds.variables["lat"]).astype(np.float64)
        lon_evt = to_numpy(ds.variables["lon"]).astype(np.float64)
        onset_year = to_numpy(ds.variables["onset_year"]).astype(np.float64)
        recovery = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))

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
        raise RuntimeError(f"No valid events remain in {event_file}")

    nlat = len(lat_vals)
    nlon = len(lon_vals)
    lat_idx = np.searchsorted(lat_vals, lat_evt[valid_evt])
    lon_idx = np.searchsorted(lon_vals, lon_evt[valid_evt])
    flat_idx = lat_idx * nlon + lon_idx
    ncell = nlat * nlon

    rec = recovery[valid_evt]
    rec_valid = np.isfinite(rec)
    counts = np.bincount(flat_idx[rec_valid], minlength=ncell).astype(np.int32)
    sums = np.bincount(flat_idx[rec_valid], weights=rec[rec_valid], minlength=ncell)
    mean = np.full(ncell, np.nan, dtype=np.float64)
    ok = counts > 0
    mean[ok] = sums[ok] / counts[ok]
    return {
        "lat": lat_vals,
        "lon": lon_vals,
        "recovery_mean_days": mean.reshape(nlat, nlon),
    }


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def add_trend_line(ax: plt.Axes, years: np.ndarray, values: np.ndarray, color: str) -> None:
    valid = np.isfinite(years) & np.isfinite(values)
    if np.count_nonzero(valid) < 2:
        return
    slope, intercept = np.polyfit(years[valid], values[valid], 1)
    ax.plot(
        years[valid],
        intercept + slope * years[valid],
        linestyle="--",
        linewidth=1.7,
        color=color,
        alpha=0.78,
    )


def plot_spatial() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    loaded: dict[tuple[int, int], dict[str, np.ndarray]] = {}
    finite_values = []
    for panel in SPATIAL_PANELS:
        if panel.event_file is None:
            continue
        data = aggregate_event_recovery_mean(panel.event_file)
        loaded[(panel.row, panel.col)] = data
        arr = data["recovery_mean_days"]
        finite_values.append(arr[np.isfinite(arr)])

    joined = np.concatenate([arr for arr in finite_values if arr.size > 0])
    vmin = float(np.nanpercentile(joined, 2))
    vmax = float(np.nanpercentile(joined, 98))

    fig = plt.figure(figsize=(17.4, 9.5), constrained_layout=False)
    gs = fig.add_gridspec(
        2,
        4,
        width_ratios=[1, 1, 1, 1],
        height_ratios=[1, 1],
        left=0.055,
        right=0.90,
        bottom=0.08,
        top=0.89,
        wspace=0.17,
        hspace=0.16,
    )
    axes = {
        (0, 0): fig.add_subplot(gs[0, 0:2]),
        (0, 2): fig.add_subplot(gs[0, 2:4]),
        (1, 1): fig.add_subplot(gs[1, 1:3]),
    }
    im = None
    for panel in SPATIAL_PANELS:
        ax = axes[(panel.row, panel.col)]
        ax.set_title(panel.title, fontsize=16)
        data = loaded[(panel.row, panel.col)]
        im = ax.imshow(
            data["recovery_mean_days"],
            origin="lower",
            extent=extent_from_lon_lat(data["lon"], data["lat"]),
            aspect="auto",
            cmap="RdYlGn_r",
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_xlim(-180, 180)
        ax.set_xlabel("Longitude", fontsize=12)
        ax.set_ylabel("Latitude", fontsize=12)
        ax.tick_params(labelsize=10.5)
        if panel.letter == "b":
            ax.set_ylabel("")
            ax.tick_params(axis="y", labelleft=False)
        ax.text(
            0.03,
            0.97,
            panel.letter,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=16,
            fontweight="bold",
            color="#111111",
            bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 0.15},
        )

    fig.suptitle(
        f"SMrz Recovery Time Mean After Flash Drought ({START_YEAR}-{END_YEAR})",
        fontsize=22,
    )
    if im is not None:
        cbar = fig.colorbar(im, ax=list(axes.values()), shrink=0.90, pad=0.02, fraction=0.028)
        cbar.set_label("Recovery Time Mean (days)", fontsize=12.5)
        cbar.ax.tick_params(labelsize=10.5)
    fig.savefig(SPATIAL_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_trend() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    flux_rows = read_csv(ANNUAL_FLUXSAT_CSV)
    all_rows = read_csv(ANNUAL_0401_CSV)

    gpp_rows = [
        row
        for row in flux_rows
        if row["code"] == "code1"
        and row["soil_layer"] == "SMrz"
        and row["dataset"] in {"BESS 0401", "FluxSat 0401 rec100cap"}
    ]
    reco_rows = [
        row
        for row in all_rows
        if row["variable"] == "RECO"
        and row["code"] == "code1"
        and row["soil_layer"] == "SMrz"
    ]

    fig = plt.figure(figsize=(15.2, 8.4), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, width_ratios=[3.25, 1.0], height_ratios=[1, 1])
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[1, 0])]
    bar_ax = fig.add_subplot(gs[:, 1])
    styles = {
        "BESS 0401": {"color": "#CC6677", "marker": "o", "label": "BESS"},
        "FluxSat 0401 rec100cap": {"color": "#0072B2", "marker": "s", "label": "FluxSat"},
    }
    bar_values: list[tuple[str, float, str]] = []

    ax = axes[0]
    for dataset in ["BESS 0401", "FluxSat 0401 rec100cap"]:
        rows = sorted([row for row in gpp_rows if row["dataset"] == dataset], key=lambda r: int(r["year"]))
        years = np.array([int(row["year"]) for row in rows], dtype=np.float64)
        values = np.array([float(row["recovery_mean"]) for row in rows], dtype=np.float64)
        if dataset.startswith("FluxSat"):
            keep = years != 2000
            years = years[keep]
            values = values[keep]
        style = styles[dataset]
        ax.plot(
            years,
            values,
            color=style["color"],
            marker=style["marker"],
            markersize=6.4,
            linewidth=2.45,
            label=style["label"],
        )
        add_trend_line(ax, years, values, style["color"])
        bar_label = "BESS-GPP" if dataset == "BESS 0401" else "FluxSat-GPP"
        bar_values.append((bar_label, float(np.nanmean(values)), style["color"]))
    ax.set_title("GPP - SMrz: BESS vs FluxSat", fontsize=19)
    ax.set_ylabel("Recovery Time Mean (days)", fontsize=15)
    ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
    ax.legend(frameon=False, fontsize=14, ncol=2, loc="best")
    ax.tick_params(axis="both", labelsize=12.5)

    ax = axes[1]
    reco_rows = sorted(reco_rows, key=lambda r: int(r["year"]))
    years = np.array([int(row["year"]) for row in reco_rows], dtype=np.float64)
    values = np.array([float(row["recovery_mean"]) for row in reco_rows], dtype=np.float64)
    ax.plot(
        years,
        values,
        color="#CC6677",
        marker="o",
        markersize=6.4,
        linewidth=2.45,
        label="BESS RECO",
    )
    add_trend_line(ax, years, values, "#CC6677")
    bar_values.append(("BESS-RECO", float(np.nanmean(values)), "#882255"))
    ax.set_title("RECO - SMrz: BESS", fontsize=19)
    ax.set_ylabel("Recovery Time Mean (days)", fontsize=15)
    ax.set_xlabel("Year", fontsize=15)
    ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
    ax.legend(frameon=False, fontsize=14, loc="best")
    ax.tick_params(axis="both", labelsize=12.5)

    axes[0].set_xlim(1981.5, 2021.5)
    axes[1].set_xlim(1981.5, 2021.5)

    bar_labels = [item[0] for item in bar_values]
    bar_heights = np.array([item[1] for item in bar_values], dtype=np.float64)
    bar_colors = [item[2] for item in bar_values]
    x = np.arange(len(bar_labels))
    bar_ax.bar(x, bar_heights, color=bar_colors, width=0.68, edgecolor="#333333", linewidth=0.6)
    bar_ax.set_title("Mean recovery time", fontsize=17)
    bar_ax.set_ylabel("Recovery Time Mean (days)", fontsize=14)
    bar_ax.set_xticks(x)
    bar_ax.set_xticklabels(bar_labels, rotation=30, ha="right", fontsize=12)
    bar_ax.tick_params(axis="y", labelsize=12)
    bar_ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.30)
    if np.isfinite(bar_heights).any():
        ymax = float(np.nanmax(bar_heights)) * 1.22
        bar_ax.set_ylim(0, ymax)
        for xi, yi in zip(x, bar_heights, strict=True):
            bar_ax.text(xi, yi + ymax * 0.025, f"{yi:.1f}", ha="center", va="bottom", fontsize=12)

    fig.suptitle("SMrz Recovery Time Trend Following Flash Drought", fontsize=22)
    fig.savefig(TREND_WITH_BAR_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    plot_spatial()
    plot_trend()
    print(f"Wrote {SPATIAL_PNG}")
    print(f"Wrote {TREND_WITH_BAR_PNG}")


if __name__ == "__main__":
    main()
