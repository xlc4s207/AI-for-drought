#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Plot GLEAM vs ERA5 flash-drought maps for SMrz only."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
OUT_DIR = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/conclusion/"
    "gleam_era5_flash_frequency_intensity_spatial"
)
OUT_FREQ_PNG = os.path.join(OUT_DIR, "gleam_vs_era5_flash_frequency_global_smrz_only.png")
OUT_INTENSITY_PNG = os.path.join(OUT_DIR, "gleam_vs_era5_flash_intensity_global_smrz_only.png")
OUT_SUMMARY_CSV = os.path.join(OUT_DIR, "gleam_vs_era5_flash_frequency_intensity_summary_smrz_only.csv")


@dataclass(frozen=True)
class Scenario:
    dataset: str
    soil_layer: str
    event_file: str


SCENARIOS = [
    Scenario(
        dataset="GLEAM",
        soil_layer="SMrz",
        event_file=(
            f"{BASE_DIR}/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/"
            "flash_lt20_drought_events_v5.4.nc"
        ),
    ),
    Scenario(
        dataset="ERA5",
        soil_layer="SMrz",
        event_file=(
            f"{BASE_DIR}/era5/clip_result/ERA5L_root_result_v5.4_0p25deg_no_ice_desert/"
            "flash_lt20_drought_events_v5.4.nc"
        ),
    ),
]


def to_numpy(var) -> np.ndarray:
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        if np.issubdtype(arr.dtype, np.integer):
            arr = arr.astype(np.float64).filled(np.nan)
        else:
            arr = arr.filled(np.nan)
    arr = np.asarray(arr)
    if np.issubdtype(arr.dtype, np.integer):
        arr = arr.astype(np.float64)
    fill_value = getattr(var, "_FillValue", None)
    if fill_value is not None:
        arr = arr.astype(np.float64, copy=False)
        arr[np.isclose(arr, float(fill_value), equal_nan=False)] = np.nan
    return arr


def load_scenario(scenario: Scenario) -> dict[str, np.ndarray | str]:
    with nc.Dataset(scenario.event_file, "r") as ds:
        lat = to_numpy(ds.variables["lat"]).astype(np.float64)
        lon = to_numpy(ds.variables["lon"]).astype(np.float64)
        event_count = to_numpy(ds.variables["event_count"]).astype(np.float64)
        intensity = to_numpy(ds.variables["intensity"]).astype(np.float64)

    valid = np.isfinite(event_count) & (event_count >= 0)
    event_count = np.where(valid, event_count, np.nan)
    intensity = np.where(np.isfinite(intensity) & (intensity > -9000), intensity, np.nan)

    mean_intensity = np.full(event_count.shape, np.nan, dtype=np.float64)
    count_int = np.sum(np.isfinite(intensity), axis=0)
    sum_int = np.nansum(intensity, axis=0)
    ok = count_int > 0
    mean_intensity[ok] = sum_int[ok] / count_int[ok]

    return {
        "dataset": scenario.dataset,
        "soil_layer": scenario.soil_layer,
        "lat": lat,
        "lon": lon,
        "frequency": event_count,
        "mean_intensity": mean_intensity,
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


def plot_two_panels(
    items: list[dict[str, np.ndarray | str]],
    key: str,
    out_png: str,
    title: str,
    cbar_label: str,
    cmap: str,
    vmin_override: float | None = None,
    vmax_override: float | None = None,
) -> None:
    values = []
    for item in items:
        arr = np.asarray(item[key], dtype=np.float64)
        if key == "frequency":
            arr = np.where(arr > 0, arr, np.nan)
        finite = arr[np.isfinite(arr)]
        if finite.size:
            values.append(finite)
    joined = np.concatenate(values)
    vmin = vmin_override if vmin_override is not None else float(np.nanpercentile(joined, 2))
    vmax = vmax_override if vmax_override is not None else float(np.nanpercentile(joined, 98))

    base_cmap = plt.get_cmap(cmap)
    plot_cmap = base_cmap.copy() if hasattr(base_cmap, "copy") else plt.get_cmap(cmap)
    plot_cmap.set_bad(color="white", alpha=0.0)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), constrained_layout=True)
    im = None
    for ax, item in zip(axes, items):
        lat = np.asarray(item["lat"], dtype=np.float64)
        lon = np.asarray(item["lon"], dtype=np.float64)
        arr = np.asarray(item[key], dtype=np.float64)
        if key == "frequency":
            arr = np.where(arr > 0, arr, np.nan)
        im = ax.imshow(
            arr,
            origin="lower",
            extent=extent_from_lon_lat(lon, lat),
            aspect="auto",
            cmap=plot_cmap,
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_title(f"{item['dataset']} | {item['soil_layer']}", fontsize=15)
        ax.set_xlabel("Longitude", fontsize=12)
        ax.set_ylabel("Latitude", fontsize=12)
        ax.set_xlim(-180, 180)
        ax.tick_params(labelsize=10)

    fig.suptitle(title, fontsize=20)
    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.95, pad=0.02)
    cbar.set_label(cbar_label, fontsize=13)
    cbar.ax.tick_params(labelsize=11)
    fig.savefig(out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_summary_csv(items: list[dict[str, np.ndarray | str]]) -> None:
    gleam = next(x for x in items if x["dataset"] == "GLEAM" and x["soil_layer"] == "SMrz")
    era5 = next(x for x in items if x["dataset"] == "ERA5" and x["soil_layer"] == "SMrz")

    gleam_freq = np.asarray(gleam["frequency"], dtype=np.float64)
    era5_freq = np.asarray(era5["frequency"], dtype=np.float64)
    valid = np.isfinite(gleam_freq) & np.isfinite(era5_freq)
    gleam_valid = gleam_freq[valid]
    era5_valid = era5_freq[valid]
    freq_corr = float(np.corrcoef(gleam_valid, era5_valid)[0, 1]) if valid.sum() > 1 else float("nan")
    gleam_positive = gleam_valid > 0
    era5_positive = era5_valid > 0
    union = int(np.count_nonzero(gleam_positive | era5_positive))
    intersection = int(np.count_nonzero(gleam_positive & era5_positive))
    positive_jaccard = float(intersection / union) if union > 0 else float("nan")

    rows = []
    for item in items:
        freq = np.asarray(item["frequency"], dtype=np.float64)
        intensity = np.asarray(item["mean_intensity"], dtype=np.float64)
        rows.append(
            {
                "dataset": str(item["dataset"]),
                "soil_layer": str(item["soil_layer"]),
                "mean_frequency_1980_2024": float(np.nanmean(freq)),
                "median_frequency_1980_2024": float(np.nanmedian(freq)),
                "max_frequency_1980_2024": float(np.nanmax(freq)),
                "mean_intensity": float(np.nanmean(intensity)),
                "median_intensity": float(np.nanmedian(intensity)),
                "max_intensity": float(np.nanmax(intensity)),
                "frequency_spatial_correlation_gleam_vs_era5": freq_corr,
                "positive_frequency_jaccard_overlap": positive_jaccard,
                "positive_frequency_intersection_pixels": intersection,
                "positive_frequency_union_pixels": union,
                "shared_valid_pixels": int(valid.sum()),
            }
        )

    with open(OUT_SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset",
                "soil_layer",
                "mean_frequency_1980_2024",
                "median_frequency_1980_2024",
                "max_frequency_1980_2024",
                "mean_intensity",
                "median_intensity",
                "max_intensity",
                "frequency_spatial_correlation_gleam_vs_era5",
                "positive_frequency_jaccard_overlap",
                "positive_frequency_intersection_pixels",
                "positive_frequency_union_pixels",
                "shared_valid_pixels",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    items = [load_scenario(s) for s in SCENARIOS]
    plot_two_panels(
        items=items,
        key="frequency",
        out_png=OUT_FREQ_PNG,
        title="Flash Drought Frequency (1980-2024): GLEAM vs ERA5 | SMrz",
        cbar_label="Event Count",
        cmap="RdYlGn_r",
        vmin_override=0.0,
        vmax_override=90.0,
    )
    plot_two_panels(
        items=items,
        key="mean_intensity",
        out_png=OUT_INTENSITY_PNG,
        title="Flash Drought Mean Intensity (1980-2024): GLEAM vs ERA5 | SMrz",
        cbar_label="Mean Intensity",
        cmap="RdYlGn_r",
    )
    write_summary_csv(items)
    print(f"Wrote {OUT_FREQ_PNG}")
    print(f"Wrote {OUT_INTENSITY_PNG}")
    print(f"Wrote {OUT_SUMMARY_CSV}")


if __name__ == "__main__":
    main()
