#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Build BESS 0401 SMrz-only GPP/RECO recovery-time global spatial maps."""

from __future__ import annotations

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
OUT_PNG = os.path.join(OUT_DIR, "bess_0401_gpp_reco_recovery_mean_smrz_flash.png")


@dataclass(frozen=True)
class Panel:
    title: str
    event_file: str


PANELS = [
    Panel(
        title="GPP | SMrz Flash",
        event_file=(
            f"{BASE_DIR}/process/GPP-draught-analysis/code1/results/"
            "gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_"
            "rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc"
        ),
    ),
    Panel(
        title="RECO | SMrz Flash",
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


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    aggregated = [aggregate_event_recovery_mean(panel.event_file) for panel in PANELS]
    finite_values = [
        item["recovery_mean_days"][np.isfinite(item["recovery_mean_days"])] for item in aggregated
    ]
    joined = np.concatenate([arr for arr in finite_values if arr.size > 0])
    vmin = float(np.nanpercentile(joined, 2))
    vmax = float(np.nanpercentile(joined, 98))

    fig, axes = plt.subplots(1, 2, figsize=(16, 5.6), constrained_layout=True)
    im = None
    for ax, panel, data in zip(axes, PANELS, aggregated):
        im = ax.imshow(
            data["recovery_mean_days"],
            origin="lower",
            extent=extent_from_lon_lat(data["lon"], data["lat"]),
            aspect="auto",
            cmap="RdYlGn_r",
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_title(panel.title, fontsize=16)
        ax.set_xlabel("Longitude", fontsize=12)
        ax.set_ylabel("Latitude", fontsize=12)
        ax.set_xlim(-180, 180)
        ax.tick_params(labelsize=10)

    fig.suptitle("BESS Recovery Time Mean After SMrz Flash Drought", fontsize=20)
    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.95, pad=0.02)
    cbar.set_label("Recovery Time Mean (days)", fontsize=13)
    cbar.ax.tick_params(labelsize=11)
    fig.savefig(OUT_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
