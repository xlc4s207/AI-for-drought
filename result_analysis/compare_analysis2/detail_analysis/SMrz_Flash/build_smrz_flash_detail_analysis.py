#!/usr/bin/env python3
"""Build detailed three-flux sample analysis for SMrz flash drought events."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np


OUT_DIR = (
    "/home/xulc/flash_drought/process/result_analysis/compare_analysis2/"
    "detail_analysis/SMrz_Flash"
)
BASE_TIME = datetime(1982, 1, 1)
SMOOTH_WINDOW = 5
SAMPLE_COUNT = 10

RESULT_FILES = {
    "GPP": (
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/"
        "gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_"
        "c30x095_w420_decline30_d5_rec100.nc"
    ),
    "NEE": (
        "/home/xulc/flash_drought/process/NEE-draught-analysis/code1SMrz/result/"
        "nee_response_SMrz_drought_v20260325_latfix_relp03_abspeak_absrec_"
        "c30x095_w420_decline30_d5_rec100.nc"
    ),
    "RECO": (
        "/home/xulc/flash_drought/process/RECO-draught-analysis/code1/results/"
        "reco_response_SMrz_events_global_v20260325_latfix_relm03_abspeak_absrec_"
        "c30x095_w420_decline30_d5_rec100.nc"
    ),
}

RAW_FILES = {
    "GPP": ("/data/BESS_V2/BESS_GPP_1982_2022_0.25deg.nc", "GPP"),
    "NEE": ("/data/BESS_V2/NEE_1982-2022_0.25deg.nc", "NEE"),
    "RECO": ("/data/BESS_V2/BESS_RECO_1982-2022_0.25deg.nc", "RECO"),
}

PLOT_STYLE = {
    "GPP": {"color": "#2a9d8f", "baseline": "gpp_baseline_abs", "peak": "gpp_min_abs", "change": "gpp_change_to_peak_abs"},
    "NEE": {"color": "#d62828", "baseline": "nee_baseline_abs", "peak": "nee_max_abs", "change": "nee_change_to_peak_abs"},
    "RECO": {"color": "#577590", "baseline": "reco_baseline_abs", "peak": "reco_min_abs", "change": "reco_change_to_peak_abs"},
}

KEY_DTYPE = np.dtype(
    [
        ("lat_key", np.int32),
        ("lon_key", np.int32),
        ("onset_year", np.int32),
        ("onset_doy", np.int32),
        ("drought_start_year", np.int32),
        ("drought_start_doy", np.int32),
    ]
)


def to_numpy(var) -> np.ndarray:
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        arr = arr.filled(getattr(var, "_FillValue", np.nan))
    return np.asarray(arr)


def to_float_array(var) -> np.ndarray:
    arr = to_numpy(var).astype(np.float64, copy=False)
    fill_value = getattr(var, "_FillValue", None)
    if fill_value is not None:
        arr[np.isclose(arr, float(fill_value), equal_nan=False)] = np.nan
    return arr


def to_int_array(var) -> np.ndarray:
    arr = to_numpy(var)
    fill_value = getattr(var, "_FillValue", None)
    if fill_value is None:
        return arr.astype(np.int32, copy=False)
    out = arr.astype(np.int32, copy=False)
    out[out == int(fill_value)] = -999999
    return out


def clean_time_array(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    arr[~np.isfinite(arr)] = np.nan
    arr[arr < 0] = np.nan
    return arr


def clean_binary_array(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values)
    fill_mask = arr == -127
    out = arr.astype(np.int16, copy=False)
    out[fill_mask] = 0
    return out


def build_event_keys(data: Dict[str, np.ndarray]) -> np.ndarray:
    lat_key = np.rint(np.asarray(data["lat"], dtype=np.float64) * 1000.0).astype(np.int32)
    lon_key = np.rint(np.asarray(data["lon"], dtype=np.float64) * 1000.0).astype(np.int32)
    keys = np.empty(lat_key.shape[0], dtype=KEY_DTYPE)
    keys["lat_key"] = lat_key
    keys["lon_key"] = lon_key
    keys["onset_year"] = np.asarray(data["onset_year"], dtype=np.int32)
    keys["onset_doy"] = np.asarray(data["onset_doy"], dtype=np.int32)
    keys["drought_start_year"] = np.asarray(data["drought_start_year"], dtype=np.int32)
    keys["drought_start_doy"] = np.asarray(data["drought_start_doy"], dtype=np.int32)
    return keys


def pick_peak_field(data: Dict[str, np.ndarray]) -> str:
    if "t_peak_abs" in data:
        return "t_peak_abs"
    return "t_peak"


def build_valid_mask(data: Dict[str, np.ndarray], peak_field: str) -> np.ndarray:
    response = clean_binary_array(data["response_detected"]) == 1
    onset_resp = clean_time_array(data["t_response_onset_start"])
    peak = clean_time_array(data[peak_field])
    recover = clean_time_array(data["t_recover_to_baseline"])
    recover_onset = (
        clean_time_array(data["t_recover_onset_start"])
        if "t_recover_onset_start" in data
        else np.full(recover.shape, np.nan, dtype=np.float64)
    )
    lat = np.asarray(data["lat"], dtype=np.float64)
    lon = np.asarray(data["lon"], dtype=np.float64)
    years_ok = np.asarray(data["onset_year"], dtype=np.int32) > 0
    doy_ok = np.asarray(data["onset_doy"], dtype=np.int32) > 0
    drought_year_ok = np.asarray(data["drought_start_year"], dtype=np.int32) > 0
    drought_doy_ok = np.asarray(data["drought_start_doy"], dtype=np.int32) > 0
    return (
        response
        & np.isfinite(onset_resp)
        & np.isfinite(peak)
        & np.isfinite(recover)
        & np.isfinite(recover_onset)
        & np.isfinite(lat)
        & np.isfinite(lon)
        & years_ok
        & doy_ok
        & drought_year_ok
        & drought_doy_ok
    )


def prepare_valid_unique_index(data: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    peak_field = pick_peak_field(data)
    mask = build_valid_mask(data, peak_field)
    valid_idx = np.flatnonzero(mask)
    if valid_idx.size == 0:
        return np.empty(0, dtype=KEY_DTYPE), np.empty(0, dtype=np.int64)
    valid_data = {
        "lat": np.asarray(data["lat"])[valid_idx],
        "lon": np.asarray(data["lon"])[valid_idx],
        "onset_year": np.asarray(data["onset_year"])[valid_idx],
        "onset_doy": np.asarray(data["onset_doy"])[valid_idx],
        "drought_start_year": np.asarray(data["drought_start_year"])[valid_idx],
        "drought_start_doy": np.asarray(data["drought_start_doy"])[valid_idx],
    }
    valid_keys = build_event_keys(valid_data)
    unique_keys, first_idx = np.unique(valid_keys, return_index=True)
    return unique_keys, valid_idx[first_idx]


def _lookup_common_indices(unique_keys: np.ndarray, source_idx: np.ndarray, common_keys: np.ndarray) -> np.ndarray:
    if common_keys.size == 0:
        return np.empty(0, dtype=np.int64)
    pos = np.searchsorted(unique_keys, common_keys)
    return source_idx[pos]


def intersect_three_way_valid_events(
    gpp: Dict[str, np.ndarray],
    nee: Dict[str, np.ndarray],
    reco: Dict[str, np.ndarray],
) -> Dict[str, np.ndarray]:
    gpp_keys, gpp_idx = prepare_valid_unique_index(gpp)
    nee_keys, nee_idx = prepare_valid_unique_index(nee)
    reco_keys, reco_idx = prepare_valid_unique_index(reco)
    common = np.intersect1d(np.intersect1d(gpp_keys, nee_keys), reco_keys)
    return {
        "count": int(common.size),
        "keys": common,
        "gpp_idx": _lookup_common_indices(gpp_keys, gpp_idx, common),
        "nee_idx": _lookup_common_indices(nee_keys, nee_idx, common),
        "reco_idx": _lookup_common_indices(reco_keys, reco_idx, common),
    }


def pick_even_samples(indices: Iterable[int], sort_values: Iterable[float], n_samples: int) -> List[int]:
    indices = np.asarray(list(indices), dtype=np.int64)
    if indices.size == 0 or n_samples <= 0:
        return []
    sort_values = np.asarray(list(sort_values), dtype=np.float64)
    order = indices[np.argsort(sort_values)]
    chunks = np.array_split(order, min(n_samples, order.size))
    picks: List[int] = []
    for chunk in chunks:
        if chunk.size == 0:
            continue
        picks.append(int(chunk[chunk.size // 2]))
    return sorted(picks)


def read_result_dataset(path: str, variable: str) -> Dict[str, np.ndarray]:
    style = PLOT_STYLE[variable]
    fields = [
        "event_id",
        "lat",
        "lon",
        "onset_year",
        "onset_doy",
        "drought_start_year",
        "drought_start_doy",
        "actual_window_after",
        "response_detected",
        "t_response_onset_start",
        "t_response_drought_start",
        "t_peak",
        "t_peak_abs",
        "t_recover_to_baseline",
        "t_recover_onset_start",
        "t_recover_drought_start",
        style["baseline"],
        style["peak"],
        style["change"],
    ]
    out: Dict[str, np.ndarray] = {}
    with nc.Dataset(path, "r") as ds:
        for name in fields:
            if name not in ds.variables:
                continue
            var = ds.variables[name]
            if np.issubdtype(var.dtype, np.floating):
                out[name] = to_float_array(var)
            else:
                out[name] = to_int_array(var)
    return out


def smooth_causal(values: np.ndarray, window: int = SMOOTH_WINDOW) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    out = np.full(arr.shape, np.nan, dtype=np.float64)
    width = max(1, int(window))
    for i in range(arr.size):
        start = max(0, i - width + 1)
        vals = arr[start : i + 1]
        vals = vals[np.isfinite(vals)]
        if vals.size > 0:
            out[i] = float(np.nanmean(vals))
    return out


def year_doy_to_datetime(year_val: float, doy_val: float) -> datetime | None:
    if not np.isfinite(year_val) or not np.isfinite(doy_val):
        return None
    year_int = int(year_val)
    doy_int = int(doy_val)
    if year_int < 1900 or doy_int < 1 or doy_int > 366:
        return None
    try:
        return datetime(year_int, 1, 1) + timedelta(days=doy_int - 1)
    except ValueError:
        return None


def day_from_base(year_val: float, doy_val: float) -> int | None:
    dt = year_doy_to_datetime(year_val, doy_val)
    if dt is None:
        return None
    return int((dt - BASE_TIME).days)


def series_value_at(x_days: np.ndarray, y_vals: np.ndarray, day: float) -> float:
    if not np.isfinite(day):
        return np.nan
    where = np.where(x_days == int(round(float(day))))[0]
    if where.size == 0:
        return np.nan
    val = y_vals[int(where[0])]
    return float(val) if np.isfinite(val) else np.nan


def open_flux_dataset(variable: str):
    file_path, var_name = RAW_FILES[variable]
    ds = nc.Dataset(file_path, "r")
    lat = to_float_array(ds.variables["lat"])
    lon = to_float_array(ds.variables["lon"])
    time_var = ds.variables["time"]
    time = to_numpy(time_var).astype(np.float64, copy=False)
    return ds, var_name, lat, lon, time


def nearest_coord_index(coord: np.ndarray, value: float) -> int:
    return int(np.argmin(np.abs(coord - float(value))))


def extract_smoothed_relative_series(
    ds,
    var_name: str,
    lat_arr: np.ndarray,
    lon_arr: np.ndarray,
    onset_t: int,
    lat_value: float,
    lon_value: float,
    pre_days: int,
    post_days: int,
) -> Tuple[np.ndarray, np.ndarray]:
    lat_idx = nearest_coord_index(lat_arr, lat_value)
    lon_idx = nearest_coord_index(lon_arr, lon_value)
    n_time = ds.dimensions["time"].size
    start = max(0, onset_t - pre_days)
    end = min(n_time - 1, onset_t + post_days)
    raw = to_numpy(ds.variables[var_name][start : end + 1, lat_idx, lon_idx]).astype(np.float64, copy=False)
    fill_value = getattr(ds.variables[var_name], "_FillValue", None)
    if fill_value is not None:
        raw[np.isclose(raw, float(fill_value), equal_nan=False)] = np.nan
    x_days = np.arange(start - onset_t, end - onset_t + 1, dtype=np.int32)
    return x_days, smooth_causal(raw, SMOOTH_WINDOW)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(path: str, payload: object) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_csv(path: str, rows: List[Dict[str, object]]) -> None:
    if not rows:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_sample_title(sample_no: int, lat: float, lon: float, onset_date: datetime, drought_date: datetime | None) -> str:
    drought_text = drought_date.strftime("%Y-%m-%d") if drought_date is not None else "NA"
    return (
        f"Sample {sample_no:02d} | lat={lat:.2f}, lon={lon:.2f} | "
        f"onset={onset_date.strftime('%Y-%m-%d')} | drought={drought_text}"
    )


def build_summary_lines(record: Dict[str, object]) -> List[str]:
    lines = []
    for variable in ["GPP", "NEE", "RECO"]:
        item = record[variable]
        lines.append(
            (
                f"{variable}: resp={item['t_response_onset_start']:.0f} d, "
                f"peak={item['t_peak_abs']:.0f} d, "
                f"rec_onset={item['t_recover_onset_start']:.0f} d, "
                f"rec_from_peak={item['t_recover_to_baseline']:.0f} d, "
                f"baseline={item['baseline_abs']:.2f}, "
                f"peak_abs={item['peak_abs']:.2f}, change={item['change_to_peak_abs']:.2f}"
            )
        )
    return lines


def plot_sample_event(
    sample_no: int,
    record: Dict[str, object],
    flux_handles: Dict[str, Tuple],
    out_path: str,
) -> None:
    lat = float(record["lat"])
    lon = float(record["lon"])
    onset_date = year_doy_to_datetime(record["onset_year"], record["onset_doy"])
    drought_date = year_doy_to_datetime(record["drought_start_year"], record["drought_start_doy"])
    if onset_date is None:
        return
    onset_t = day_from_base(record["onset_year"], record["onset_doy"])
    if onset_t is None:
        return

    max_recover = max(float(record[var]["t_recover_onset_start"]) for var in ["GPP", "NEE", "RECO"])
    max_peak = max(float(record[var]["t_peak_abs"]) for var in ["GPP", "NEE", "RECO"])
    post_days = min(220, max(140, int(np.ceil(max(max_recover, max_peak))) + 35))
    pre_days = 40

    fig, ax = plt.subplots(figsize=(12, 6), dpi=220)
    for variable in ["GPP", "NEE", "RECO"]:
        ds, var_name, lat_arr, lon_arr, _ = flux_handles[variable]
        x_days, smooth_series = extract_smoothed_relative_series(
            ds, var_name, lat_arr, lon_arr, onset_t, lat, lon, pre_days, post_days
        )
        style = PLOT_STYLE[variable]
        ax.plot(x_days, smooth_series, color=style["color"], lw=1.7, label=variable)

        resp_day = float(record[variable]["t_response_onset_start"])
        peak_day = float(record[variable]["t_peak_abs"])
        recover_day = float(record[variable]["t_recover_onset_start"])

        ax.scatter(resp_day, series_value_at(x_days, smooth_series, resp_day), s=34, marker="o", color=style["color"], edgecolor="black", linewidth=0.4, zorder=5)
        ax.scatter(peak_day, series_value_at(x_days, smooth_series, peak_day), s=40, marker="v", color=style["color"], edgecolor="black", linewidth=0.4, zorder=5)
        ax.scatter(recover_day, series_value_at(x_days, smooth_series, recover_day), s=34, marker="s", color=style["color"], edgecolor="black", linewidth=0.4, zorder=5)

    ax.axvline(0, color="#444444", ls="--", lw=1.0, alpha=0.7)
    if drought_date is not None:
        drought_from_onset = (drought_date - onset_date).days
        ax.axvline(drought_from_onset, color="#999999", ls=":", lw=1.0, alpha=0.9)
        ax.text(drought_from_onset + 1, ax.get_ylim()[1] * 0.95, "drought start", color="#666666", fontsize=9)

    ax.set_title(build_sample_title(sample_no, lat, lon, onset_date, drought_date))
    ax.set_xlabel("Days since onset")
    ax.set_ylabel("Absolute flux value")
    ax.grid(alpha=0.25, linewidth=0.5)
    ax.legend(loc="upper right", frameon=False)

    text = "Markers: o=response, v=peak(abs), s=recovery\n" + "\n".join(build_summary_lines(record))
    ax.text(
        0.015,
        0.015,
        text,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.5,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.88, "edgecolor": "#cccccc"},
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def build_sample_manifest(
    match: Dict[str, np.ndarray],
    gpp: Dict[str, np.ndarray],
    nee: Dict[str, np.ndarray],
    reco: Dict[str, np.ndarray],
) -> List[Dict[str, object]]:
    if match["count"] == 0:
        return []
    sort_values = clean_time_array(gpp["t_recover_to_baseline"][match["gpp_idx"]])
    sample_positions = pick_even_samples(np.arange(match["count"], dtype=np.int64), sort_values, SAMPLE_COUNT)

    sample_records: List[Dict[str, object]] = []
    for sample_no, pos in enumerate(sample_positions, start=1):
        gpp_idx = int(match["gpp_idx"][pos])
        nee_idx = int(match["nee_idx"][pos])
        reco_idx = int(match["reco_idx"][pos])
        base = {
            "sample_no": sample_no,
            "match_rank": int(pos),
            "lat": float(gpp["lat"][gpp_idx]),
            "lon": float(gpp["lon"][gpp_idx]),
            "onset_year": int(gpp["onset_year"][gpp_idx]),
            "onset_doy": int(gpp["onset_doy"][gpp_idx]),
            "drought_start_year": int(gpp["drought_start_year"][gpp_idx]),
            "drought_start_doy": int(gpp["drought_start_doy"][gpp_idx]),
        }
        variable_payload = {}
        for variable, dataset, idx in [
            ("GPP", gpp, gpp_idx),
            ("NEE", nee, nee_idx),
            ("RECO", reco, reco_idx),
        ]:
            style = PLOT_STYLE[variable]
            peak_field = pick_peak_field(dataset)
            variable_payload[variable] = {
                "result_index": idx,
                "event_id": int(dataset["event_id"][idx]) if "event_id" in dataset else -1,
                "t_response_onset_start": float(clean_time_array(dataset["t_response_onset_start"][idx: idx + 1])[0]),
                "t_response_drought_start": float(clean_time_array(dataset["t_response_drought_start"][idx: idx + 1])[0]) if "t_response_drought_start" in dataset else np.nan,
                "t_peak_abs": float(clean_time_array(dataset[peak_field][idx: idx + 1])[0]),
                "t_recover_to_baseline": float(clean_time_array(dataset["t_recover_to_baseline"][idx: idx + 1])[0]),
                "t_recover_onset_start": float(clean_time_array(dataset["t_recover_onset_start"][idx: idx + 1])[0]) if "t_recover_onset_start" in dataset else np.nan,
                "baseline_abs": float(dataset[style["baseline"]][idx]),
                "peak_abs": float(dataset[style["peak"]][idx]),
                "change_to_peak_abs": float(dataset[style["change"]][idx]),
            }
        base.update(variable_payload)
        sample_records.append(base)
    return sample_records


def flatten_records(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for record in records:
        row = {
            "sample_no": record["sample_no"],
            "match_rank": record["match_rank"],
            "lat": record["lat"],
            "lon": record["lon"],
            "onset_year": record["onset_year"],
            "onset_doy": record["onset_doy"],
            "drought_start_year": record["drought_start_year"],
            "drought_start_doy": record["drought_start_doy"],
        }
        for variable in ["GPP", "NEE", "RECO"]:
            payload = record[variable]
            row[f"{variable.lower()}_result_index"] = payload["result_index"]
            row[f"{variable.lower()}_event_id"] = payload["event_id"]
            row[f"{variable.lower()}_t_response_onset_start"] = payload["t_response_onset_start"]
            row[f"{variable.lower()}_t_peak_abs"] = payload["t_peak_abs"]
            row[f"{variable.lower()}_t_recover_to_baseline"] = payload["t_recover_to_baseline"]
            row[f"{variable.lower()}_t_recover_onset_start"] = payload["t_recover_onset_start"]
            row[f"{variable.lower()}_baseline_abs"] = payload["baseline_abs"]
            row[f"{variable.lower()}_peak_abs"] = payload["peak_abs"]
            row[f"{variable.lower()}_change_to_peak_abs"] = payload["change_to_peak_abs"]
        rows.append(row)
    return rows


def write_summary_md(path: str, match: Dict[str, np.ndarray], sample_records: List[Dict[str, object]]) -> None:
    lines = [
        "# SMrz Flash 三通量详细抽样分析",
        "",
        f"- 三者共同满足 `response_detected=1` 且 `t_response_onset_start / t_peak(abs) / t_recover_to_baseline / t_recover_onset_start` 均有效的共同事件数：{match['count']:,}",
        f"- 实际抽样图件数：{len(sample_records):,}",
        f"- 平滑方式：5 天因果滑动平均",
        f"- 图中时间原点：onset start = day 0",
        "",
        "## 样本清单",
        "",
    ]
    for record in sample_records:
        lines.append(
            (
                f"- sample_{record['sample_no']:02d}: lat={record['lat']:.2f}, lon={record['lon']:.2f}, "
                f"onset={record['onset_year']}-{record['onset_doy']}, "
                f"GPP/NEE/RECO recovery_onset="
                f"{record['GPP']['t_recover_onset_start']:.0f}/"
                f"{record['NEE']['t_recover_onset_start']:.0f}/"
                f"{record['RECO']['t_recover_onset_start']:.0f} d; "
                f"recovery_from_peak="
                f"{record['GPP']['t_recover_to_baseline']:.0f}/"
                f"{record['NEE']['t_recover_to_baseline']:.0f}/"
                f"{record['RECO']['t_recover_to_baseline']:.0f} d"
            )
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ensure_dir(OUT_DIR)
    gpp = read_result_dataset(RESULT_FILES["GPP"], "GPP")
    nee = read_result_dataset(RESULT_FILES["NEE"], "NEE")
    reco = read_result_dataset(RESULT_FILES["RECO"], "RECO")

    match = intersect_three_way_valid_events(gpp, nee, reco)
    sample_records = build_sample_manifest(match, gpp, nee, reco)
    flat_rows = flatten_records(sample_records)

    json_path = os.path.join(OUT_DIR, "sample_events_smrz_flash_threeflux.json")
    csv_path = os.path.join(OUT_DIR, "sample_events_smrz_flash_threeflux.csv")
    summary_path = os.path.join(OUT_DIR, "summary.md")
    write_json(json_path, sample_records)
    write_csv(csv_path, flat_rows)
    write_summary_md(summary_path, match, sample_records)

    flux_handles = {variable: open_flux_dataset(variable) for variable in ["GPP", "NEE", "RECO"]}
    try:
        for record in sample_records:
            out_png = os.path.join(
                OUT_DIR,
                f"sample_{record['sample_no']:02d}_lat_{record['lat']:.2f}_lon_{record['lon']:.2f}_"
                f"onset_{record['onset_year']}_{record['onset_doy']}.png",
            )
            plot_sample_event(record["sample_no"], record, flux_handles, out_png)
            print(f"Wrote {out_png}")
    finally:
        for handle in flux_handles.values():
            handle[0].close()

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
