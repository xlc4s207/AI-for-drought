#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import datetime as dt
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
FLUXSAT_FILE = (
    f"{BASE_DIR}/process/fluxsat-draught-analysis/preprocess/results/FluxSat_GPP_2000_2019_0.25deg.nc"
)
EVENT_FILES = {
    "SMrz": f"{BASE_DIR}/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc",
    "SMs": f"{BASE_DIR}/gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc",
}
OUT_DIR = f"{BASE_DIR}/process/fluxsat-draught-analysis/analysis/lu2025_like_recovery"

START_YEAR = 2001
END_YEAR = 2018
GROWING_MONTHS = {4, 5, 6, 7, 8, 9, 10}
LAT_CHUNK = 5


@dataclass(frozen=True)
class Slot:
    year: int
    pentad: int
    start: int
    end: int


@dataclass(frozen=True)
class ScenarioResult:
    scenario: str
    summary: Dict[str, object]
    annual_rows: List[Dict[str, object]]
    grid_nc_path: str


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


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


def load_time_and_slots(fluxsat_path: str) -> Tuple[np.ndarray, np.ndarray, List[Slot], Dict[Tuple[int, int], int]]:
    with nc.Dataset(fluxsat_path, "r") as ds:
        time_var = ds.variables["time"]
        dates = nc.num2date(
            time_var[:],
            units=time_var.units,
            calendar=getattr(time_var, "calendar", "standard"),
            only_use_cftime_datetimes=False,
            only_use_python_datetimes=True,
        )

    dates = np.asarray(dates, dtype=object)
    valid = np.array(
        [
            (START_YEAR <= d.year <= END_YEAR) and (d.month in GROWING_MONTHS)
            for d in dates
        ],
        dtype=bool,
    )
    selected_idx = np.flatnonzero(valid)
    selected_dates = dates[selected_idx]

    slots: List[Slot] = []
    slot_to_index: Dict[Tuple[int, int], int] = {}
    start = 0
    while start < selected_idx.size:
        year = selected_dates[start].year
        doy = selected_dates[start].timetuple().tm_yday
        pentad = (doy - 1) // 5 + 1
        end = start + 1
        while end < selected_idx.size:
            next_date = selected_dates[end]
            next_pentad = (next_date.timetuple().tm_yday - 1) // 5 + 1
            if next_date.year != year or next_pentad != pentad:
                break
            end += 1
        slot = Slot(year=year, pentad=pentad, start=start, end=end)
        slot_to_index[(year, pentad)] = len(slots)
        slots.append(slot)
        start = end
    return dates, selected_idx, slots, slot_to_index


def forward_three_pentad(values: np.ndarray) -> np.ndarray:
    out = np.full_like(values, np.nan, dtype=np.float32)
    n_slots, n_pixels = values.shape
    for i in range(n_slots):
        window = values[i : min(i + 3, n_slots), :]
        valid = np.isfinite(window)
        counts = valid.sum(axis=0)
        sums = np.nansum(window, axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[i, :] = np.where(counts > 0, sums / counts, np.nan).astype(np.float32)
    return out


def aggregate_to_pentads(gpp_daily: np.ndarray, slots: List[Slot]) -> np.ndarray:
    out = np.full((len(slots), gpp_daily.shape[1]), np.nan, dtype=np.float32)
    for i, slot in enumerate(slots):
        window = gpp_daily[slot.start : slot.end, :]
        valid = np.isfinite(window)
        counts = valid.sum(axis=0)
        sums = np.nansum(window, axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[i, :] = np.where(counts > 0, sums / counts, np.nan).astype(np.float32)
    return out


def build_anomaly(smoothed: np.ndarray, slots: List[Slot]) -> np.ndarray:
    out = np.full_like(smoothed, np.nan, dtype=np.float32)
    pentads = sorted({slot.pentad for slot in slots})
    for pentad in pentads:
        idx = np.array([i for i, slot in enumerate(slots) if slot.pentad == pentad], dtype=np.int64)
        values = smoothed[idx, :]
        clim_mean = np.nanmean(values, axis=0)
        clim_std = np.nanstd(values, axis=0)
        bad = (~np.isfinite(clim_std)) | np.isclose(clim_std, 0.0)
        clim_std[bad] = np.nan
        out[idx, :] = ((values - clim_mean) / clim_std).astype(np.float32)
    return out


def year_negative_segments(year_anom: np.ndarray) -> List[Tuple[int, int]]:
    neg = np.isfinite(year_anom) & (year_anom < 0.0)
    segments: List[Tuple[int, int]] = []
    i = 0
    while i < neg.size:
        if not neg[i]:
            i += 1
            continue
        j = i + 1
        while j < neg.size and neg[j]:
            j += 1
        segments.append((i, j - 1))
        i = j
    return segments


def pentad_from_year_doy(year: int, doy: int) -> int:
    try:
        date = dt.datetime.strptime(f"{year}-{int(doy):03d}", "%Y-%j").date()
    except ValueError:
        return -1
    if date.month not in GROWING_MONTHS:
        return -1
    return (date.timetuple().tm_yday - 1) // 5 + 1


def analyze_pixel_events(
    year_to_segment: Dict[int, np.ndarray],
    year_to_pentads: Dict[int, np.ndarray],
    events: List[Tuple[int, int, int]],
) -> Tuple[List[Tuple[int, float]], Dict[str, int]]:
    recovery_pentads: List[Tuple[int, float]] = []
    counters = {
        "events_total": 0,
        "events_valid": 0,
        "drop_onset_outside_growing_season": 0,
        "drop_missing_year_segment": 0,
        "drop_no_negative_segment_overlap": 0,
        "drop_negative_before_onset": 0,
        "drop_negative_only_one_pentad": 0,
        "drop_no_positive_recovery": 0,
    }

    for onset_year, onset_doy, end_doy in events:
        counters["events_total"] += 1
        onset_pentad = pentad_from_year_doy(onset_year, onset_doy)
        end_pentad = pentad_from_year_doy(onset_year, end_doy)
        if onset_pentad < 0 or end_pentad < 0:
            counters["drop_onset_outside_growing_season"] += 1
            continue
        year_anom = year_to_segment.get(onset_year)
        year_pentads = year_to_pentads.get(onset_year)
        if year_anom is None or year_anom.size == 0:
            counters["drop_missing_year_segment"] += 1
            continue
        if year_pentads is None or year_pentads.size == 0:
            counters["drop_missing_year_segment"] += 1
            continue
        pentad_to_local = {int(p): i for i, p in enumerate(year_pentads)}
        onset_local = pentad_to_local.get(int(onset_pentad))
        end_local = pentad_to_local.get(int(end_pentad))
        if onset_local is None or end_local is None:
            counters["drop_onset_outside_growing_season"] += 1
            continue

        segments = year_negative_segments(year_anom)
        matched = None
        for lo, hi in segments:
            if lo <= end_local and hi >= onset_local:
                matched = (lo, hi)
                break
        if matched is None:
            counters["drop_no_negative_segment_overlap"] += 1
            continue
        lo, hi = matched
        if lo < onset_local:
            counters["drop_negative_before_onset"] += 1
            continue
        if hi <= lo:
            counters["drop_negative_only_one_pentad"] += 1
            continue

        segment = year_anom[lo : hi + 1]
        if segment.size <= 1:
            counters["drop_negative_only_one_pentad"] += 1
            continue
        peak_rel = int(np.nanargmin(segment))
        peak_idx = lo + peak_rel
        recover_idx = -1
        for idx in range(peak_idx + 1, year_anom.size):
            value = year_anom[idx]
            if np.isfinite(value) and value > 0.0:
                recover_idx = idx
                break
        if recover_idx < 0:
            counters["drop_no_positive_recovery"] += 1
            continue

        recovery_pentads.append((onset_year, float(recover_idx - peak_idx)))
        counters["events_valid"] += 1

    return recovery_pentads, counters


def summarize_values(values: List[float]) -> Dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return {
            "count": 0,
            "mean": math.nan,
            "median": math.nan,
            "p25": math.nan,
            "p75": math.nan,
        }
    return {
        "count": int(arr.size),
        "mean": float(np.nanmean(arr)),
        "median": float(np.nanmedian(arr)),
        "p25": float(np.nanpercentile(arr, 25)),
        "p75": float(np.nanpercentile(arr, 75)),
    }


def write_grid_nc(
    output_path: str,
    scenario: str,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
    pixel_event_total: np.ndarray,
    pixel_valid_event_count: np.ndarray,
    pixel_recovery_mean_days: np.ndarray,
    pixel_recovery_median_days: np.ndarray,
    pixel_recovery_p25_days: np.ndarray,
    pixel_recovery_p75_days: np.ndarray,
    annual_pixel_count: np.ndarray,
    annual_pixel_mean_days: np.ndarray,
) -> None:
    ensure_dir(os.path.dirname(output_path))
    if os.path.exists(output_path):
        os.remove(output_path)
    with nc.Dataset(output_path, "w", format="NETCDF4") as ds:
        ds.createDimension("year", annual_pixel_mean_days.shape[0])
        ds.createDimension("lat", latitudes.size)
        ds.createDimension("lon", longitudes.size)

        year_var = ds.createVariable("year", "i2", ("year",))
        lat_var = ds.createVariable("lat", "f4", ("lat",))
        lon_var = ds.createVariable("lon", "f4", ("lon",))
        total_var = ds.createVariable("event_total_count", "i4", ("lat", "lon"), zlib=True, complevel=1, fill_value=-9999)
        valid_var = ds.createVariable("valid_recovery_event_count", "i4", ("lat", "lon"), zlib=True, complevel=1, fill_value=-9999)
        mean_var = ds.createVariable("recovery_mean_days", "f4", ("lat", "lon"), zlib=True, complevel=1, fill_value=np.float32(np.nan))
        median_var = ds.createVariable("recovery_median_days", "f4", ("lat", "lon"), zlib=True, complevel=1, fill_value=np.float32(np.nan))
        p25_var = ds.createVariable("recovery_p25_days", "f4", ("lat", "lon"), zlib=True, complevel=1, fill_value=np.float32(np.nan))
        p75_var = ds.createVariable("recovery_p75_days", "f4", ("lat", "lon"), zlib=True, complevel=1, fill_value=np.float32(np.nan))
        annual_count_var = ds.createVariable("annual_valid_recovery_event_count", "i4", ("year", "lat", "lon"), zlib=True, complevel=1, fill_value=-9999)
        annual_mean_var = ds.createVariable("annual_recovery_mean_days", "f4", ("year", "lat", "lon"), zlib=True, complevel=1, fill_value=np.float32(np.nan))

        year_var[:] = np.arange(START_YEAR, END_YEAR + 1, dtype=np.int16)
        lat_var[:] = latitudes.astype(np.float32)
        lon_var[:] = longitudes.astype(np.float32)
        lat_var.units = "degrees_north"
        lon_var.units = "degrees_east"

        total_var[:] = pixel_event_total
        valid_var[:] = pixel_valid_event_count
        mean_var[:] = pixel_recovery_mean_days
        median_var[:] = pixel_recovery_median_days
        p25_var[:] = pixel_recovery_p25_days
        p75_var[:] = pixel_recovery_p75_days
        annual_count_var[:] = annual_pixel_count
        annual_mean_var[:] = annual_pixel_mean_days

        ds.title = f"FluxSat Lu2025-like recovery gridded output ({scenario})"
        ds.description = (
            "Approximate Lu et al. 2025 recovery-time gridded output. FluxSat daily GPP is aggregated to pentads, "
            "smoothed with a 3-pentad forward window, anomaly is defined as (GPP-mu)/sigma by pentad, and recovery "
            "runs from minimum negative anomaly to first positive anomaly. Existing 0.25 degree GLEAM event files are reused."
        )
        ds.study_years = f"{START_YEAR}-{END_YEAR}"
        ds.growing_months = ",".join(str(m) for m in sorted(GROWING_MONTHS))
        ds.scenario = scenario


def process_chunk(args):
    (
        scenario,
        fluxsat_path,
        event_path,
        selected_idx,
        slots,
        lat0,
        lat1,
    ) = args
    with nc.Dataset(fluxsat_path, "r") as flux_ds, nc.Dataset(event_path, "r") as evt_ds:
        gpp_var = flux_ds.variables["GPP"]
        lon_size = gpp_var.shape[2]
        event_count = evt_ds.variables["event_count"]
        onset_year = evt_ds.variables["onset_start_year"]
        onset_doy = evt_ds.variables["onset_start_doy"]
        end_doy = evt_ds.variables["drought_end_doy"]

        slot_years = [slot.year for slot in slots]
        year_to_indices: Dict[int, List[int]] = {}
        year_to_pentads: Dict[int, np.ndarray] = {}
        for i, year in enumerate(slot_years):
            year_to_indices.setdefault(year, []).append(i)
        for year, idxs in year_to_indices.items():
            year_to_pentads[year] = np.asarray([slots[idx].pentad for idx in idxs], dtype=np.int16)

        summary_counts = {
            "events_total": 0,
            "events_valid": 0,
            "drop_onset_outside_growing_season": 0,
            "drop_missing_year_segment": 0,
            "drop_no_negative_segment_overlap": 0,
            "drop_negative_before_onset": 0,
            "drop_negative_only_one_pentad": 0,
            "drop_no_positive_recovery": 0,
        }
        recovery_pentads_all: List[float] = []
        pixel_mean_days: List[float] = []
        annual_event_days: Dict[int, List[float]] = {year: [] for year in range(START_YEAR, END_YEAR + 1)}
        annual_pixel_days: Dict[int, List[float]] = {year: [] for year in range(START_YEAR, END_YEAR + 1)}

        n_lat = lat1 - lat0
        pixel_event_total = np.zeros((n_lat, lon_size), dtype=np.int32)
        pixel_valid_event_count = np.zeros((n_lat, lon_size), dtype=np.int32)
        pixel_recovery_mean_days = np.full((n_lat, lon_size), np.nan, dtype=np.float32)
        pixel_recovery_median_days = np.full((n_lat, lon_size), np.nan, dtype=np.float32)
        pixel_recovery_p25_days = np.full((n_lat, lon_size), np.nan, dtype=np.float32)
        pixel_recovery_p75_days = np.full((n_lat, lon_size), np.nan, dtype=np.float32)
        annual_pixel_count = np.zeros((END_YEAR - START_YEAR + 1, n_lat, lon_size), dtype=np.int32)
        annual_pixel_mean_days = np.full((END_YEAR - START_YEAR + 1, n_lat, lon_size), np.nan, dtype=np.float32)

        print(f"[{scenario}] lat {lat0}:{lat1}", flush=True)
        counts_chunk = np.asarray(event_count[lat0:lat1, :], dtype=np.int16)
        if not np.any(counts_chunk > 0):
            return {
                "lat0": lat0,
                "lat1": lat1,
                "summary_counts": summary_counts,
                "recovery_pentads_all": recovery_pentads_all,
                "pixel_mean_days": pixel_mean_days,
                "annual_event_days": annual_event_days,
                "annual_pixel_days": annual_pixel_days,
                "pixel_event_total": pixel_event_total,
                "pixel_valid_event_count": pixel_valid_event_count,
                "pixel_recovery_mean_days": pixel_recovery_mean_days,
                "pixel_recovery_median_days": pixel_recovery_median_days,
                "pixel_recovery_p25_days": pixel_recovery_p25_days,
                "pixel_recovery_p75_days": pixel_recovery_p75_days,
                "annual_pixel_count": annual_pixel_count,
                "annual_pixel_mean_days": annual_pixel_mean_days,
            }

        gpp_full = np.asarray(gpp_var[selected_idx, lat0:lat1, :], dtype=np.float32)
        n_days, _, n_lon = gpp_full.shape
        gpp_daily = gpp_full.reshape(n_days, n_lat * n_lon)
        pentad = aggregate_to_pentads(gpp_daily, slots)
        smoothed = np.full_like(pentad, np.nan, dtype=np.float32)
        for year, idxs in year_to_indices.items():
            year_values = pentad[np.asarray(idxs, dtype=np.int64), :]
            smoothed[np.asarray(idxs, dtype=np.int64), :] = forward_three_pentad(year_values)
        anomaly = build_anomaly(smoothed, slots)

        onset_year_chunk = np.asarray(onset_year[:, lat0:lat1, :], dtype=np.int16)
        onset_doy_chunk = np.asarray(onset_doy[:, lat0:lat1, :], dtype=np.int16)
        end_doy_chunk = np.asarray(end_doy[:, lat0:lat1, :], dtype=np.int16)

        for local_lat in range(n_lat):
            for lon in range(n_lon):
                n_evt = int(counts_chunk[local_lat, lon])
                if n_evt <= 0:
                    continue
                pixel_idx = local_lat * n_lon + lon
                pixel_anom = anomaly[:, pixel_idx]
                year_to_segment = {
                    year: pixel_anom[np.asarray(idxs, dtype=np.int64)]
                    for year, idxs in year_to_indices.items()
                }
                events: List[Tuple[int, int, int]] = []
                for e in range(n_evt):
                    y = int(onset_year_chunk[e, local_lat, lon])
                    od = int(onset_doy_chunk[e, local_lat, lon])
                    ed = int(end_doy_chunk[e, local_lat, lon])
                    if y < START_YEAR or y > END_YEAR:
                        continue
                    events.append((y, od, ed))
                if not events:
                    continue
                pixel_event_total[local_lat, lon] = len(events)

                recovery_pentads, counters = analyze_pixel_events(year_to_segment, year_to_pentads, events)
                for key, value in counters.items():
                    summary_counts[key] += int(value)
                if recovery_pentads:
                    days_values = np.asarray([v * 5.0 for _, v in recovery_pentads], dtype=np.float64)
                    pixel_valid_event_count[local_lat, lon] = int(days_values.size)
                    pixel_recovery_mean_days[local_lat, lon] = np.float32(np.nanmean(days_values))
                    pixel_recovery_median_days[local_lat, lon] = np.float32(np.nanmedian(days_values))
                    pixel_recovery_p25_days[local_lat, lon] = np.float32(np.nanpercentile(days_values, 25))
                    pixel_recovery_p75_days[local_lat, lon] = np.float32(np.nanpercentile(days_values, 75))
                    recovery_pentads_all.extend([v for _, v in recovery_pentads])
                    pixel_mean_days.append(float(np.nanmean(days_values)))
                    year_buckets: Dict[int, List[float]] = {}
                    for year, pentads_value in recovery_pentads:
                        annual_event_days[year].append(float(pentads_value * 5.0))
                        year_buckets.setdefault(year, []).append(float(pentads_value * 5.0))
                    for year, vals in year_buckets.items():
                        annual_pixel_days[year].append(float(np.nanmean(np.asarray(vals, dtype=np.float64))))
                        year_idx = year - START_YEAR
                        annual_pixel_count[year_idx, local_lat, lon] = len(vals)
                        annual_pixel_mean_days[year_idx, local_lat, lon] = np.float32(np.nanmean(np.asarray(vals, dtype=np.float64)))

        return {
            "lat0": lat0,
            "lat1": lat1,
            "summary_counts": summary_counts,
            "recovery_pentads_all": recovery_pentads_all,
            "pixel_mean_days": pixel_mean_days,
            "annual_event_days": annual_event_days,
            "annual_pixel_days": annual_pixel_days,
            "pixel_event_total": pixel_event_total,
            "pixel_valid_event_count": pixel_valid_event_count,
            "pixel_recovery_mean_days": pixel_recovery_mean_days,
            "pixel_recovery_median_days": pixel_recovery_median_days,
            "pixel_recovery_p25_days": pixel_recovery_p25_days,
            "pixel_recovery_p75_days": pixel_recovery_p75_days,
            "annual_pixel_count": annual_pixel_count,
            "annual_pixel_mean_days": annual_pixel_mean_days,
        }


def process_scenario(
    scenario: str,
    fluxsat_path: str,
    event_path: str,
    selected_idx: np.ndarray,
    slots: List[Slot],
    lat_start: int = 0,
    lat_end: int | None = None,
    jobs: int = 1,
) -> ScenarioResult:
    with nc.Dataset(fluxsat_path, "r") as flux_ds, nc.Dataset(event_path, "r") as evt_ds:
        gpp_var = flux_ds.variables["GPP"]
        lat_size = gpp_var.shape[1]
        lon_size = gpp_var.shape[2]
        latitudes = np.asarray(flux_ds.variables["lat"][:], dtype=np.float32)
        longitudes = np.asarray(flux_ds.variables["lon"][:], dtype=np.float32)
        if lat_end is None or lat_end > lat_size:
            lat_end = lat_size
    summary_counts = {
        "events_total": 0,
        "events_valid": 0,
        "drop_onset_outside_growing_season": 0,
        "drop_missing_year_segment": 0,
        "drop_no_negative_segment_overlap": 0,
        "drop_negative_before_onset": 0,
        "drop_negative_only_one_pentad": 0,
        "drop_no_positive_recovery": 0,
    }
    recovery_pentads_all: List[float] = []
    pixel_mean_days: List[float] = []
    annual_event_days: Dict[int, List[float]] = {year: [] for year in range(START_YEAR, END_YEAR + 1)}
    annual_pixel_days: Dict[int, List[float]] = {year: [] for year in range(START_YEAR, END_YEAR + 1)}
    pixel_event_total = np.zeros((lat_size, lon_size), dtype=np.int32)
    pixel_valid_event_count = np.zeros((lat_size, lon_size), dtype=np.int32)
    pixel_recovery_mean_days = np.full((lat_size, lon_size), np.nan, dtype=np.float32)
    pixel_recovery_median_days = np.full((lat_size, lon_size), np.nan, dtype=np.float32)
    pixel_recovery_p25_days = np.full((lat_size, lon_size), np.nan, dtype=np.float32)
    pixel_recovery_p75_days = np.full((lat_size, lon_size), np.nan, dtype=np.float32)
    annual_pixel_count = np.zeros((END_YEAR - START_YEAR + 1, lat_size, lon_size), dtype=np.int32)
    annual_pixel_mean_days = np.full((END_YEAR - START_YEAR + 1, lat_size, lon_size), np.nan, dtype=np.float32)

    chunk_jobs = [
        (scenario, fluxsat_path, event_path, selected_idx, slots, lat0, min(lat0 + LAT_CHUNK, lat_end))
        for lat0 in range(lat_start, lat_end, LAT_CHUNK)
    ]
    jobs = max(1, int(jobs))
    if jobs == 1:
        chunk_results = [process_chunk(job) for job in chunk_jobs]
    else:
        chunk_results = []
        with ProcessPoolExecutor(max_workers=jobs) as executor:
            futures = [executor.submit(process_chunk, job) for job in chunk_jobs]
            for future in as_completed(futures):
                chunk_results.append(future.result())

    chunk_results.sort(key=lambda item: item["lat0"])
    for chunk in chunk_results:
        lat0 = int(chunk["lat0"])
        lat1 = int(chunk["lat1"])
        for key, value in chunk["summary_counts"].items():
            summary_counts[key] += int(value)
        recovery_pentads_all.extend(chunk["recovery_pentads_all"])
        pixel_mean_days.extend(chunk["pixel_mean_days"])
        for year in range(START_YEAR, END_YEAR + 1):
            annual_event_days[year].extend(chunk["annual_event_days"][year])
            annual_pixel_days[year].extend(chunk["annual_pixel_days"][year])
        pixel_event_total[lat0:lat1, :] = chunk["pixel_event_total"]
        pixel_valid_event_count[lat0:lat1, :] = chunk["pixel_valid_event_count"]
        pixel_recovery_mean_days[lat0:lat1, :] = chunk["pixel_recovery_mean_days"]
        pixel_recovery_median_days[lat0:lat1, :] = chunk["pixel_recovery_median_days"]
        pixel_recovery_p25_days[lat0:lat1, :] = chunk["pixel_recovery_p25_days"]
        pixel_recovery_p75_days[lat0:lat1, :] = chunk["pixel_recovery_p75_days"]
        annual_pixel_count[:, lat0:lat1, :] = chunk["annual_pixel_count"]
        annual_pixel_mean_days[:, lat0:lat1, :] = chunk["annual_pixel_mean_days"]

    pentad_stats = summarize_values(recovery_pentads_all)
    day_stats = summarize_values([v * 5.0 for v in recovery_pentads_all])
    pixel_day_stats = summarize_values(pixel_mean_days)
    summary: Dict[str, object] = {
        "scenario": scenario,
        "method_note": (
            "Approximate Lu et al. 2025 reproduction: FluxSat daily GPP is aggregated to pentads, "
            "smoothed using a 3-pentad forward window, anomaly is defined as (GPP-mu)/sigma by pentad, "
            "and recovery runs from minimum negative anomaly to the first positive anomaly. "
            "Existing 0.25 degree GLEAM event files are reused instead of re-detecting 0.1 degree paper events."
        ),
        "study_years": [START_YEAR, END_YEAR],
        "growing_months": sorted(GROWING_MONTHS),
        "recovery_stats_pentad": pentad_stats,
        "recovery_stats_days_event_level": day_stats,
        "recovery_stats_days_pixel_level": pixel_day_stats,
        "counts": summary_counts,
    }
    annual_rows: List[Dict[str, object]] = []
    for year in range(START_YEAR, END_YEAR + 1):
        event_stats = summarize_values(annual_event_days[year])
        pixel_stats = summarize_values(annual_pixel_days[year])
        annual_rows.append(
            {
                "scenario": scenario,
                "year": year,
                "event_count": event_stats["count"],
                "event_mean_days": event_stats["mean"],
                "event_median_days": event_stats["median"],
                "pixel_count": pixel_stats["count"],
                "pixel_mean_days": pixel_stats["mean"],
                "pixel_median_days": pixel_stats["median"],
            }
        )
    grid_nc_path = os.path.join(OUT_DIR, f"fluxsat_lu2025_like_recovery_{scenario}.nc")
    write_grid_nc(
        grid_nc_path,
        scenario,
        latitudes,
        longitudes,
        pixel_event_total,
        pixel_valid_event_count,
        pixel_recovery_mean_days,
        pixel_recovery_median_days,
        pixel_recovery_p25_days,
        pixel_recovery_p75_days,
        annual_pixel_count,
        annual_pixel_mean_days,
    )
    return ScenarioResult(scenario=scenario, summary=summary, annual_rows=annual_rows, grid_nc_path=grid_nc_path)


def write_outputs(results: List[ScenarioResult], out_dir: str) -> None:
    ensure_dir(out_dir)
    json_path = os.path.join(out_dir, "fluxsat_lu2025_like_recovery_summary.json")
    csv_path = os.path.join(out_dir, "fluxsat_lu2025_like_recovery_summary.csv")
    md_path = os.path.join(out_dir, "fluxsat_lu2025_like_recovery_summary.md")
    annual_csv_path = os.path.join(out_dir, "fluxsat_lu2025_like_recovery_annual.csv")
    figure_path = os.path.join(out_dir, "fluxsat_lu2025_like_recovery_trend.png")

    payload = {item.scenario: item.summary for item in results}
    Path(json_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fieldnames = [
        "scenario",
        "event_valid_count",
        "event_mean_days",
        "event_median_days",
        "event_p25_days",
        "event_p75_days",
        "pixel_count",
        "pixel_mean_days",
        "pixel_median_days",
        "pixel_p25_days",
        "pixel_p75_days",
        "events_total",
        "drop_onset_outside_growing_season",
        "drop_missing_year_segment",
        "drop_no_negative_segment_overlap",
        "drop_negative_before_onset",
        "drop_negative_only_one_pentad",
        "drop_no_positive_recovery",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in results:
            s = item.summary
            counts = s["counts"]
            event_stats = s["recovery_stats_days_event_level"]
            pixel_stats = s["recovery_stats_days_pixel_level"]
            writer.writerow(
                {
                    "scenario": item.scenario,
                    "event_valid_count": event_stats["count"],
                    "event_mean_days": event_stats["mean"],
                    "event_median_days": event_stats["median"],
                    "event_p25_days": event_stats["p25"],
                    "event_p75_days": event_stats["p75"],
                    "pixel_count": pixel_stats["count"],
                    "pixel_mean_days": pixel_stats["mean"],
                    "pixel_median_days": pixel_stats["median"],
                    "pixel_p25_days": pixel_stats["p25"],
                    "pixel_p75_days": pixel_stats["p75"],
                    "events_total": counts["events_total"],
                    "drop_onset_outside_growing_season": counts["drop_onset_outside_growing_season"],
                    "drop_missing_year_segment": counts["drop_missing_year_segment"],
                    "drop_no_negative_segment_overlap": counts["drop_no_negative_segment_overlap"],
                    "drop_negative_before_onset": counts["drop_negative_before_onset"],
                    "drop_negative_only_one_pentad": counts["drop_negative_only_one_pentad"],
                    "drop_no_positive_recovery": counts["drop_no_positive_recovery"],
                }
            )

    lines = [
        "# FluxSat Lu et al. 2025 类口径恢复时间汇总",
        "",
        "> 说明：这是近似复现。FluxSat 恢复定义按论文口径重算，但事件仍沿用现有 0.25° GLEAM 事件文件，未重建论文 0.1° pentad 事件。",
        "",
        "| 情景 | 事件有效数 | 事件均值(d) | 事件中位数(d) | 像元均值(d) | 像元中位数(d) | 总事件数 | 负异常提前开始剔除 | 未恢复为正剔除 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in results:
        s = item.summary
        counts = s["counts"]
        event_stats = s["recovery_stats_days_event_level"]
        pixel_stats = s["recovery_stats_days_pixel_level"]
        lines.append(
            "| "
            + " | ".join(
                [
                    item.scenario,
                    f"{event_stats['count']}",
                    f"{event_stats['mean']:.2f}" if math.isfinite(event_stats["mean"]) else "-",
                    f"{event_stats['median']:.2f}" if math.isfinite(event_stats["median"]) else "-",
                    f"{pixel_stats['mean']:.2f}" if math.isfinite(pixel_stats["mean"]) else "-",
                    f"{pixel_stats['median']:.2f}" if math.isfinite(pixel_stats["median"]) else "-",
                    f"{counts['events_total']}",
                    f"{counts['drop_negative_before_onset']}",
                    f"{counts['drop_no_positive_recovery']}",
                ]
            )
            + " |"
        )
    Path(md_path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    annual_fieldnames = [
        "scenario",
        "year",
        "event_count",
        "event_mean_days",
        "event_median_days",
        "pixel_count",
        "pixel_mean_days",
        "pixel_median_days",
    ]
    annual_rows = []
    for item in results:
        annual_rows.extend(item.annual_rows)
    annual_rows.sort(key=lambda row: (row["scenario"], row["year"]))
    with open(annual_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=annual_fieldnames)
        writer.writeheader()
        writer.writerows(annual_rows)

    setup_chinese_font()
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, constrained_layout=True)
    styles = {
        "SMrz": {"color": "#1f78b4", "marker": "o"},
        "SMs": {"color": "#d95f02", "marker": "s"},
    }
    for item in results:
        rows = sorted(item.annual_rows, key=lambda row: row["year"])
        years = np.asarray([row["year"] for row in rows], dtype=np.float64)
        event_mean = np.asarray([row["event_mean_days"] for row in rows], dtype=np.float64)
        pixel_mean = np.asarray([row["pixel_mean_days"] for row in rows], dtype=np.float64)
        style = styles.get(item.scenario, {"color": "#333333", "marker": "o"})
        axes[0].plot(years, event_mean, color=style["color"], marker=style["marker"], linewidth=2.0, markersize=4.0, label=item.scenario)
        axes[1].plot(years, pixel_mean, color=style["color"], marker=style["marker"], linewidth=2.0, markersize=4.0, label=item.scenario)
    axes[0].set_title("FluxSat Lu et al. 2025 类口径恢复时间趋势（事件平均）")
    axes[0].set_ylabel("恢复时间均值 (天)")
    axes[1].set_title("FluxSat Lu et al. 2025 类口径恢复时间趋势（像元平均）")
    axes[1].set_ylabel("恢复时间均值 (天)")
    axes[1].set_xlabel("Year")
    for ax in axes:
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
        ax.legend(frameon=False, loc="best")
    fig.savefig(figure_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Approximate Lu et al. 2025 recovery-time analysis using FluxSat.")
    parser.add_argument("--fluxsat-file", default=FLUXSAT_FILE)
    parser.add_argument("--scenarios", nargs="+", choices=sorted(EVENT_FILES), default=["SMrz"])
    parser.add_argument("--out-dir", default=OUT_DIR)
    parser.add_argument("--lat-start", type=int, default=0)
    parser.add_argument("--lat-end", type=int, default=None)
    parser.add_argument("--jobs", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _, selected_idx, slots, _ = load_time_and_slots(args.fluxsat_file)
    results: List[ScenarioResult] = []
    for scenario in args.scenarios:
        results.append(
            process_scenario(
                scenario,
                args.fluxsat_file,
                EVENT_FILES[scenario],
                selected_idx,
                slots,
                lat_start=args.lat_start,
                lat_end=args.lat_end,
                jobs=args.jobs,
            )
        )
    write_outputs(results, args.out_dir)


if __name__ == "__main__":
    main()
