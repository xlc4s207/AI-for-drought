#!/usr/bin/env python3
"""Build a unified comparison report for 12 rec100 carbon-flux outputs."""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import netCDF4 as nc
import numpy as np


OUT_DIR = "/home/xulc/flash_drought/process/result_analysis/result_weighted/compare_analysis2"
CSV_PATH = os.path.join(OUT_DIR, "compare_analysis2_rec100_summary_20260325.csv")
MD_PATH = os.path.join(OUT_DIR, "compare_analysis2_rec100_report_20260325.md")


@dataclass(frozen=True)
class Item:
    variable: str
    code: str
    soil_layer: str
    drought_type: str
    file_path: str


ITEMS: List[Item] = [
    Item("GPP", "code1", "SMrz", "flash", "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    Item("GPP", "code2", "SMs", "flash", "/home/xulc/flash_drought/process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    Item("GPP", "code3", "SMrz", "slow", "/home/xulc/flash_drought/process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    Item("GPP", "code4", "SMs", "slow", "/home/xulc/flash_drought/process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    Item("NEE", "code1", "SMrz", "flash", "/home/xulc/flash_drought/process/NEE-draught-analysis/code1SMrz/result/nee_response_SMrz_drought_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    Item("NEE", "code2", "SMs", "flash", "/home/xulc/flash_drought/process/NEE-draught-analysis/code2SMs/result/nee_response_SMs_drought_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    Item("NEE", "code3", "SMrz", "slow", "/home/xulc/flash_drought/process/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    Item("NEE", "code4", "SMs", "slow", "/home/xulc/flash_drought/process/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260325_latfix_relp03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    Item("RECO", "code1", "SMrz", "flash", "/home/xulc/flash_drought/process/RECO-draught-analysis/code1/results/reco_response_SMrz_events_global_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    Item("RECO", "code2", "SMs", "flash", "/home/xulc/flash_drought/process/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_drought_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    Item("RECO", "code3", "SMrz", "slow", "/home/xulc/flash_drought/process/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
    Item("RECO", "code4", "SMs", "slow", "/home/xulc/flash_drought/process/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260325_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc"),
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
    arr[arr < 0] = np.nan
    return arr


def latitude_area_weights(latitudes: Iterable[float]) -> np.ndarray:
    lat = np.asarray(latitudes, dtype=np.float64)
    weights = np.cos(np.deg2rad(lat))
    weights[~np.isfinite(weights)] = np.nan
    weights[weights < 0] = np.nan
    return weights


def finite_weighted_mean(values: Iterable[float], latitudes: Iterable[float]) -> float:
    arr = np.asarray(values, dtype=np.float64)
    weights = latitude_area_weights(latitudes)
    valid = np.isfinite(arr) & np.isfinite(weights) & (weights > 0)
    if not np.any(valid):
        return math.nan
    return float(np.average(arr[valid], weights=weights[valid]))


def finite_mean(values: Iterable[float]) -> float:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    return float(np.nanmean(arr)) if arr.size else math.nan


def finite_median(values: Iterable[float]) -> float:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    return float(np.nanmedian(arr)) if arr.size else math.nan


def fmt(value: object, decimals: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        return "-" if not math.isfinite(float(value)) else f"{float(value):,.{decimals}f}"
    return str(value)


def pick_metric_fields(variable: str) -> Dict[str, str]:
    name = variable.lower()
    direction = "positive" if name == "nee" else "negative"
    return {
        "baseline_abs": f"{name}_baseline_abs",
        "baseline_std_abs": f"{name}_baseline_std_abs",
        "peak_abs": f"{name}_max_abs" if direction == "positive" else f"{name}_min_abs",
        "change_to_peak_abs": f"{name}_change_to_peak_abs",
        "direction": direction,
    }


def unique_pixel_count(lat: np.ndarray, lon: np.ndarray, mask: np.ndarray) -> int:
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    valid = mask & np.isfinite(lat) & np.isfinite(lon)
    if not np.any(valid):
        return 0
    pairs = np.column_stack((np.round(lat[valid], 6), np.round(lon[valid], 6)))
    return int(np.unique(pairs, axis=0).shape[0])


def annual_series_stats(
    years: np.ndarray,
    values: np.ndarray,
    latitudes: np.ndarray,
    min_samples_per_year: int = 30,
    min_years_for_trend: int = 5,
) -> Dict[str, float]:
    years = np.asarray(years, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    latitudes = np.asarray(latitudes, dtype=np.float64)
    valid = np.isfinite(years) & np.isfinite(values) & np.isfinite(latitudes)
    years = years[valid].astype(np.int32, copy=False)
    values = values[valid]
    latitudes = latitudes[valid]
    if years.size == 0:
        return {
            "mean_slope_days_per_decade": math.nan,
            "median_slope_days_per_decade": math.nan,
            "years_used": 0,
            "first_year": math.nan,
            "last_year": math.nan,
            "first_period_mean": math.nan,
            "last_period_mean": math.nan,
            "first_period_median": math.nan,
            "last_period_median": math.nan,
        }

    unique_years = np.unique(years)
    annual_means: List[float] = []
    annual_medians: List[float] = []
    annual_years: List[int] = []
    for year in unique_years:
        year_mask = years == year
        vals = values[year_mask]
        year_lats = latitudes[year_mask]
        vals = vals[np.isfinite(vals)]
        if vals.size < min_samples_per_year:
            continue
        annual_years.append(int(year))
        annual_means.append(finite_weighted_mean(values[year_mask], year_lats))
        annual_medians.append(float(np.nanmedian(values[year_mask][np.isfinite(values[year_mask])])))

    if len(annual_years) < min_years_for_trend:
        return {
            "mean_slope_days_per_decade": math.nan,
            "median_slope_days_per_decade": math.nan,
            "years_used": len(annual_years),
            "first_year": annual_years[0] if annual_years else math.nan,
            "last_year": annual_years[-1] if annual_years else math.nan,
            "first_period_mean": math.nan,
            "last_period_mean": math.nan,
            "first_period_median": math.nan,
            "last_period_median": math.nan,
        }

    yrs = np.asarray(annual_years, dtype=np.float64)
    means = np.asarray(annual_means, dtype=np.float64)
    medians = np.asarray(annual_medians, dtype=np.float64)
    mean_slope = float(np.polyfit(yrs, means, 1)[0] * 10.0)
    median_slope = float(np.polyfit(yrs, medians, 1)[0] * 10.0)
    half_window = min(10, len(annual_years))
    return {
        "mean_slope_days_per_decade": mean_slope,
        "median_slope_days_per_decade": median_slope,
        "years_used": len(annual_years),
        "first_year": int(annual_years[0]),
        "last_year": int(annual_years[-1]),
        "first_period_mean": float(np.nanmean(means[:half_window])),
        "last_period_mean": float(np.nanmean(means[-half_window:])),
        "first_period_median": float(np.nanmean(medians[:half_window])),
        "last_period_median": float(np.nanmean(medians[-half_window:])),
    }


def summarize_item(item: Item) -> Dict[str, object]:
    fields = pick_metric_fields(item.variable)
    with nc.Dataset(item.file_path, "r") as ds:
        attrs = {name: getattr(ds, name) for name in ds.ncattrs()}
        lat = to_numpy(ds.variables["lat"])
        lon = to_numpy(ds.variables["lon"])
        onset_year = to_numpy(ds.variables["onset_year"])
        response_detected = to_numpy(ds.variables["response_detected"]) == 1
        t_response_onset = clean_nonnegative(to_numpy(ds.variables["t_response_onset_start"]))
        t_response_drought = clean_nonnegative(to_numpy(ds.variables["t_response_drought_start"]))
        t_peak = clean_nonnegative(to_numpy(ds.variables["t_peak"]))
        t_impact = clean_nonnegative(to_numpy(ds.variables["t_impact"]))
        t_recover_peak = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))
        t_recover_drought = clean_nonnegative(to_numpy(ds.variables["t_recover_drought_start"]))
        legacy_duration = clean_nonnegative(to_numpy(ds.variables["legacy_duration"]))
        amp_max = to_numpy(ds.variables["amp_max"])
        baseline_abs = to_numpy(ds.variables[fields["baseline_abs"]])
        baseline_std_abs = to_numpy(ds.variables[fields["baseline_std_abs"]])
        peak_abs = to_numpy(ds.variables[fields["peak_abs"]])
        change_to_peak_abs = to_numpy(ds.variables[fields["change_to_peak_abs"]])
        recovery_rate = to_numpy(ds.variables["recovery_rate_to_baseline"])

    total_events = int(response_detected.size)
    total_pixels = unique_pixel_count(lat, lon, np.isfinite(lat) & np.isfinite(lon))
    response_pixels = unique_pixel_count(lat, lon, response_detected)
    recovery_mask = np.isfinite(t_recover_peak)
    recovery_pixels = unique_pixel_count(lat, lon, recovery_mask)

    response_count = int(np.sum(response_detected))
    recovery_count = int(np.sum(recovery_mask))

    summary: Dict[str, object] = {
        "variable": item.variable,
        "code": item.code,
        "soil_layer": item.soil_layer,
        "drought_type": item.drought_type,
        "label": f"{item.variable}_{item.soil_layer}_{item.drought_type}",
        "file_path": item.file_path,
        "title": attrs.get("title", ""),
        "description": attrs.get("description", ""),
        "source_event_file": attrs.get("source_event_file", ""),
        "source_data_file": attrs.get("source_data_file", ""),
        "event_total": total_events,
        "total_pixel_count": total_pixels,
        "response_count": response_count,
        "response_ratio_pct": 100.0 * response_count / total_events if total_events else math.nan,
        "response_pixel_count": response_pixels,
        "response_pixel_ratio_pct": 100.0 * response_pixels / total_pixels if total_pixels else math.nan,
        "recovery_count": recovery_count,
        "recovery_ratio_total_pct": 100.0 * recovery_count / total_events if total_events else math.nan,
        "recovery_ratio_response_pct": 100.0 * recovery_count / response_count if response_count else math.nan,
        "recovery_pixel_count": recovery_pixels,
        "recovery_pixel_ratio_pct": 100.0 * recovery_pixels / total_pixels if total_pixels else math.nan,
        "response_time_onset_mean": finite_weighted_mean(t_response_onset, lat),
        "response_time_onset_median": finite_median(t_response_onset),
        "response_time_drought_mean": finite_weighted_mean(t_response_drought, lat),
        "response_time_drought_median": finite_median(t_response_drought),
        "peak_time_mean": finite_weighted_mean(t_peak, lat),
        "peak_time_median": finite_median(t_peak),
        "impact_time_mean": finite_weighted_mean(t_impact, lat),
        "impact_time_median": finite_median(t_impact),
        "recovery_time_peak_mean": finite_weighted_mean(t_recover_peak, lat),
        "recovery_time_peak_median": finite_median(t_recover_peak),
        "recovery_time_drought_mean": finite_weighted_mean(t_recover_drought, lat),
        "recovery_time_drought_median": finite_median(t_recover_drought),
        "legacy_duration_mean": finite_weighted_mean(legacy_duration, lat),
        "legacy_duration_median": finite_median(legacy_duration),
        "change_value_mean": finite_weighted_mean(change_to_peak_abs, lat),
        "change_value_median": finite_median(change_to_peak_abs),
        "change_magnitude_mean": finite_weighted_mean(np.abs(change_to_peak_abs), lat),
        "change_magnitude_median": finite_median(np.abs(change_to_peak_abs)),
        "amp_max_mean": finite_weighted_mean(amp_max, lat),
        "amp_max_median": finite_median(amp_max),
        "baseline_abs_mean": finite_weighted_mean(baseline_abs, lat),
        "baseline_abs_median": finite_median(baseline_abs),
        "baseline_std_abs_mean": finite_weighted_mean(baseline_std_abs, lat),
        "baseline_std_abs_median": finite_median(baseline_std_abs),
        "peak_abs_mean": finite_weighted_mean(peak_abs, lat),
        "peak_abs_median": finite_median(peak_abs),
        "recovery_rate_mean": finite_weighted_mean(recovery_rate, lat),
        "recovery_rate_median": finite_median(recovery_rate),
        "metric_peak_field": fields["peak_abs"],
        "metric_change_field": fields["change_to_peak_abs"],
        "metric_baseline_field": fields["baseline_abs"],
        "direction": fields["direction"],
    }

    trend_mappings = {
        "response_onset": annual_series_stats(onset_year, t_response_onset, lat),
        "response_drought": annual_series_stats(onset_year, t_response_drought, lat),
        "recovery_peak": annual_series_stats(onset_year, t_recover_peak, lat),
        "recovery_drought": annual_series_stats(onset_year, t_recover_drought, lat),
    }
    for prefix, stats in trend_mappings.items():
        for key, value in stats.items():
            summary[f"{prefix}_{key}"] = value
    return summary


CSV_COLUMNS: List[str] = [
    "variable",
    "code",
    "soil_layer",
    "drought_type",
    "label",
    "file_path",
    "title",
    "description",
    "source_event_file",
    "source_data_file",
    "direction",
    "metric_baseline_field",
    "metric_peak_field",
    "metric_change_field",
    "event_total",
    "total_pixel_count",
    "response_count",
    "response_ratio_pct",
    "response_pixel_count",
    "response_pixel_ratio_pct",
    "recovery_count",
    "recovery_ratio_total_pct",
    "recovery_ratio_response_pct",
    "recovery_pixel_count",
    "recovery_pixel_ratio_pct",
    "change_value_mean",
    "change_value_median",
    "change_magnitude_mean",
    "change_magnitude_median",
    "amp_max_mean",
    "amp_max_median",
    "baseline_abs_mean",
    "baseline_abs_median",
    "baseline_std_abs_mean",
    "baseline_std_abs_median",
    "peak_abs_mean",
    "peak_abs_median",
    "response_time_onset_mean",
    "response_time_onset_median",
    "response_time_drought_mean",
    "response_time_drought_median",
    "peak_time_mean",
    "peak_time_median",
    "impact_time_mean",
    "impact_time_median",
    "recovery_time_peak_mean",
    "recovery_time_peak_median",
    "recovery_time_drought_mean",
    "recovery_time_drought_median",
    "legacy_duration_mean",
    "legacy_duration_median",
    "recovery_rate_mean",
    "recovery_rate_median",
    "response_onset_mean_slope_days_per_decade",
    "response_onset_median_slope_days_per_decade",
    "response_onset_years_used",
    "response_onset_first_year",
    "response_onset_last_year",
    "response_onset_first_period_mean",
    "response_onset_last_period_mean",
    "response_onset_first_period_median",
    "response_onset_last_period_median",
    "response_drought_mean_slope_days_per_decade",
    "response_drought_median_slope_days_per_decade",
    "response_drought_years_used",
    "response_drought_first_year",
    "response_drought_last_year",
    "response_drought_first_period_mean",
    "response_drought_last_period_mean",
    "response_drought_first_period_median",
    "response_drought_last_period_median",
    "recovery_peak_mean_slope_days_per_decade",
    "recovery_peak_median_slope_days_per_decade",
    "recovery_peak_years_used",
    "recovery_peak_first_year",
    "recovery_peak_last_year",
    "recovery_peak_first_period_mean",
    "recovery_peak_last_period_mean",
    "recovery_peak_first_period_median",
    "recovery_peak_last_period_median",
    "recovery_drought_mean_slope_days_per_decade",
    "recovery_drought_median_slope_days_per_decade",
    "recovery_drought_years_used",
    "recovery_drought_first_year",
    "recovery_drought_last_year",
    "recovery_drought_first_period_mean",
    "recovery_drought_last_period_mean",
    "recovery_drought_first_period_median",
    "recovery_drought_last_period_median",
]


def normalize_row_keys(row: Dict[str, object]) -> Dict[str, object]:
    mapped = dict(row)
    remap = {
        "response_onset_mean_slope_days_per_decade": row["response_onset_mean_slope_days_per_decade"] if "response_onset_mean_slope_days_per_decade" in row else row["response_onset_mean_slope_days_per_decade"],
    }
    mapped.update(remap)
    return mapped


def trend_direction_text(value: float) -> str:
    if not math.isfinite(value):
        return "样本不足"
    if value > 0.2:
        return "延长"
    if value < -0.2:
        return "缩短"
    return "基本稳定"


def compare_group(rows: List[Dict[str, object]], variable: str) -> List[str]:
    subset = [r for r in rows if r["variable"] == variable]
    if not subset:
        return []
    highest_resp = max(subset, key=lambda r: r["response_ratio_pct"])
    highest_reco = max(subset, key=lambda r: r["recovery_ratio_total_pct"])
    largest_change = max(subset, key=lambda r: r["change_magnitude_mean"])
    lines = [
        f"- `{variable}` 中响应事件占比最高的是 `{highest_resp['label']}`，为 {fmt(highest_resp['response_ratio_pct'])}%。",
        f"- `{variable}` 中恢复事件占比最高的是 `{highest_reco['label']}`，为 {fmt(highest_reco['recovery_ratio_total_pct'])}%。",
        f"- `{variable}` 中平均绝对变化幅度最大的是 `{largest_change['label']}`，均值为 {fmt(largest_change['change_magnitude_mean'])}。",  # noqa: E501
    ]
    for row in subset:
        lines.append(
            f"- `{row['label']}`：响应时间(onset)均值/中位数 {fmt(row['response_time_onset_mean'])}/{fmt(row['response_time_onset_median'])} 天，"
            f"恢复时间(peak)均值/中位数 {fmt(row['recovery_time_peak_mean'])}/{fmt(row['recovery_time_peak_median'])} 天；"
            f"响应时间趋势 {trend_direction_text(float(row['response_onset_mean_slope_days_per_decade']))} "
            f"({fmt(row['response_onset_mean_slope_days_per_decade'])} 天/10年)，"
            f"恢复时间趋势 {trend_direction_text(float(row['recovery_peak_mean_slope_days_per_decade']))} "
            f"({fmt(row['recovery_peak_mean_slope_days_per_decade'])} 天/10年)。"
        )
    return lines


def write_csv(rows: List[Dict[str, object]]) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            out = {}
            for col in CSV_COLUMNS:
                if col in row:
                    out[col] = row[col]
                    continue
                alias = col.replace("_slope_days_per_decade", "_mean_slope_days_per_decade")
                out[col] = row.get(alias)
            writer.writerow(out)


def build_markdown(rows: List[Dict[str, object]]) -> str:
    lines: List[str] = [
        "# 碳通量 12 个 rec100 结果综合对比分析",
        "",
        "## 数据范围与口径",
        "",
        "- 本次共对比 12 个结果文件：GPP、NEE、RECO 各 4 个脚本，对应 `code1-code4`。",
        "- 时间趋势统一按 `onset_year` 聚合为逐年均值/中位数后，再拟合线性趋势，单位为 `天/10年`。",
        "- `变化的值` 对应结果文件中的 `*_change_to_peak_abs`，保留原符号。",
        "- `变化幅度` 对应 `abs(*_change_to_peak_abs)`，表示绝对变化量大小。",
        "- `相对峰值幅度` 对应 `amp_max`，是基于相对异常序列识别出的峰值幅度。",
        "- 响应像元/恢复像元占比是相对于该结果文件全部输出事件涉及的唯一像元数计算。",
        "",
        "## 综合总表",
        "",
        "| 标签 | 输出事件数 | 响应事件数 | 响应事件占比(%) | 响应像元数 | 响应像元占比(%) | 恢复事件数 | 恢复/输出(%) | 恢复/响应(%) | 恢复像元数 | 恢复像元占比(%) | 变化值均值 | 变化幅度均值 | 相对峰值幅度均值 | 响应时间_onset均值 | 响应时间_onset中位数 | 恢复时间_peak均值 | 恢复时间_peak中位数 | 响应时间趋势(天/10年) | 恢复时间趋势(天/10年) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | {fmt(row['event_total'],0)} | {fmt(row['response_count'],0)} | {fmt(row['response_ratio_pct'])} | "
            f"{fmt(row['response_pixel_count'],0)} | {fmt(row['response_pixel_ratio_pct'])} | {fmt(row['recovery_count'],0)} | "
            f"{fmt(row['recovery_ratio_total_pct'])} | {fmt(row['recovery_ratio_response_pct'])} | {fmt(row['recovery_pixel_count'],0)} | "
            f"{fmt(row['recovery_pixel_ratio_pct'])} | {fmt(row['change_value_mean'])} | {fmt(row['change_magnitude_mean'])} | "
            f"{fmt(row['amp_max_mean'])} | {fmt(row['response_time_onset_mean'])} | {fmt(row['response_time_onset_median'])} | "
            f"{fmt(row['recovery_time_peak_mean'])} | {fmt(row['recovery_time_peak_median'])} | "
            f"{fmt(row['response_onset_mean_slope_days_per_decade'])} | {fmt(row['recovery_peak_mean_slope_days_per_decade'])} |"
        )

    lines.extend(["", "## 分变量详细解读", ""])
    for variable in ["GPP", "NEE", "RECO"]:
        lines.append(f"### {variable}")
        lines.extend(compare_group(rows, variable))
        lines.append("")

    lines.extend(["## 结果文件与字段说明", ""])
    for row in rows:
        lines.append(f"- `{row['label']}`")
        lines.append(f"  数据文件: `{row['source_data_file']}`")
        lines.append(f"  事件文件: `{row['source_event_file']}`")
        lines.append(
            f"  绝对基线字段: `{row['metric_baseline_field']}`；峰值字段: `{row['metric_peak_field']}`；变化值字段: `{row['metric_change_field']}`。"
        )
    lines.append("")
    lines.append(f"完整宽表见: `{CSV_PATH}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    rows = [summarize_item(item) for item in ITEMS]
    rows.sort(key=lambda r: (r["variable"], r["code"]))

    # Normalize trend column names used by CSV/markdown
    for row in rows:
        for prefix in ["response_onset", "response_drought", "recovery_peak", "recovery_drought"]:
            row[f"{prefix}_mean_slope_days_per_decade"] = row[f"{prefix}_mean_slope_days_per_decade"]
            row[f"{prefix}_median_slope_days_per_decade"] = row[f"{prefix}_median_slope_days_per_decade"]

    os.makedirs(OUT_DIR, exist_ok=True)
    write_csv(rows)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(build_markdown(rows))
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {MD_PATH}")


if __name__ == "__main__":
    main()
