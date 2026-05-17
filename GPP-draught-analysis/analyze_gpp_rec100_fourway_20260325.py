#!/usr/bin/env python3
"""Summarize the four GPP rec100 outputs into a Chinese markdown report."""

import math
import os
from typing import Dict, List

import netCDF4 as nc
import numpy as np


FILES = [
    (
        "SMrz_flash",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    (
        "SMs_flash",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    (
        "SMrz_slow",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
    (
        "SMs_slow",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    ),
]

OUTPUT_MD = "/home/xulc/flash_drought/process/GPP-draught-analysis/gpp_rec100_fourway_summary_20260325.md"


def to_numpy(var):
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


def clean_time(values):
    arr = np.asarray(values, dtype=np.float64)
    arr[arr < 0] = np.nan
    return arr


def finite_stats(values):
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return math.nan, math.nan
    return float(np.nanmean(arr)), float(np.nanmedian(arr))


def fmt(value, decimals=2):
    if value is None or not math.isfinite(value):
        return "-"
    return f"{value:,.{decimals}f}"


def summarize(path: str) -> Dict[str, float]:
    with nc.Dataset(path, "r") as ds:
        response = to_numpy(ds.variables["response_detected"]) == 1
        t_onset = clean_time(to_numpy(ds.variables["t_response_onset_start"]))
        t_drought = clean_time(to_numpy(ds.variables["t_response_drought_start"]))
        t_recover_peak = clean_time(to_numpy(ds.variables["t_recover_to_baseline"]))
        t_recover_drought = clean_time(to_numpy(ds.variables["t_recover_drought_start"]))

    total = int(response.size)
    response_count = int(np.sum(response))
    recover_count = int(np.sum(np.isfinite(t_recover_peak)))
    response_onset_mean, response_onset_median = finite_stats(t_onset)
    response_drought_mean, response_drought_median = finite_stats(t_drought)
    recover_peak_mean, recover_peak_median = finite_stats(t_recover_peak)
    recover_drought_mean, recover_drought_median = finite_stats(t_recover_drought)

    return {
        "event_total": total,
        "response_count": response_count,
        "response_pct": 100.0 * response_count / total if total else math.nan,
        "recover_count": recover_count,
        "recover_pct_total": 100.0 * recover_count / total if total else math.nan,
        "recover_pct_response": 100.0 * recover_count / response_count if response_count else math.nan,
        "response_onset_mean": response_onset_mean,
        "response_onset_median": response_onset_median,
        "response_drought_mean": response_drought_mean,
        "response_drought_median": response_drought_median,
        "recover_peak_mean": recover_peak_mean,
        "recover_peak_median": recover_peak_median,
        "recover_drought_mean": recover_drought_mean,
        "recover_drought_median": recover_drought_median,
    }


def build_markdown(rows: List[Dict[str, object]]) -> str:
    lines = [
        "# GPP 四类 rec100 结果汇总分析",
        "",
        "## 对比总表",
        "",
        "| 类型 | 输出事件数 | 响应事件数 | 响应比例(%) | 恢复事件数 | 恢复/输出(%) | 恢复/响应(%) | 平均响应时间_onset(天) | 中位响应时间_onset(天) | 平均响应时间_drought(天) | 中位响应时间_drought(天) | 平均恢复时间_peak_to_recover(天) | 中位恢复时间_peak_to_recover(天) | 平均恢复时间_drought_to_recover(天) | 中位恢复时间_drought_to_recover(天) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | {row['event_total']:,} | {row['response_count']:,} | "
            f"{fmt(row['response_pct'])} | {row['recover_count']:,} | {fmt(row['recover_pct_total'])} | "
            f"{fmt(row['recover_pct_response'])} | {fmt(row['response_onset_mean'])} | "
            f"{fmt(row['response_onset_median'])} | {fmt(row['response_drought_mean'])} | "
            f"{fmt(row['response_drought_median'])} | {fmt(row['recover_peak_mean'])} | "
            f"{fmt(row['recover_peak_median'])} | {fmt(row['recover_drought_mean'])} | "
            f"{fmt(row['recover_drought_median'])} |"
        )

    flash = [r for r in rows if "flash" in r["label"]]
    slow = [r for r in rows if "slow" in r["label"]]
    lines.extend(["", "## 简要解读", ""])
    if len(flash) == 2:
        lines.append(
            f"- 两类骤旱中，`{flash[0]['label']}` 的峰值后平均恢复时间为 {fmt(flash[0]['recover_peak_mean'])} 天，"
            f"`{flash[1]['label']}` 为 {fmt(flash[1]['recover_peak_mean'])} 天，可直接比较根层与表层土壤湿度控制下的恢复差异。"
        )
    if len(slow) == 2:
        lines.append(
            f"- 两类慢旱中，`{slow[0]['label']}` 的峰值后平均恢复时间为 {fmt(slow[0]['recover_peak_mean'])} 天，"
            f"`{slow[1]['label']}` 为 {fmt(slow[1]['recover_peak_mean'])} 天。"
        )
    lines.append(
        "- 该口径统一使用：相对阈值响应、5 天平滑绝对值峰值、`0.95 × 干旱前 30 天均值` 恢复基线、"
        "`420` 天窗口、`30` 天内连续 `5` 天趋势门、`100` 天恢复上限。"
    )
    lines.append("")
    return "\n".join(lines)


def main():
    rows = []
    for label, path in FILES:
        stats = summarize(path)
        stats["label"] = label
        rows.append(stats)
    os.makedirs(os.path.dirname(OUTPUT_MD), exist_ok=True)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(build_markdown(rows))
    print(f"Wrote {OUTPUT_MD}")


if __name__ == "__main__":
    main()
