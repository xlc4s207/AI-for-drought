#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

import netCDF4 as nc
import numpy as np

BASE_DIR = "/home/xulc/flash_drought"
OUTPUT_DIR = os.path.join(BASE_DIR, "process/result_analysis/performance")
os.makedirs(OUTPUT_DIR, exist_ok=True)


@dataclass(frozen=True)
class DatasetSpec:
    variable: str
    drought_type: str
    soil_layer: str
    path: str


DATASETS: List[DatasetSpec] = [
    DatasetSpec("GPP", "flash", "SMrz", os.path.join(BASE_DIR, "process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v11_complete.nc")),
    DatasetSpec("GPP", "flash", "SMs", os.path.join(BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v11.nc")),
    DatasetSpec("GPP", "nonflash", "SMrz", os.path.join(BASE_DIR, "process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v11_global.nc")),
    DatasetSpec("GPP", "nonflash", "SMs", os.path.join(BASE_DIR, "process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v11_global.nc")),
    DatasetSpec("NEE", "flash", "SMrz", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code1SMrz/result/nee_response_events_global_v11.nc")),
    DatasetSpec("NEE", "flash", "SMs", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code2SMs/result/nee_response_SMs_drought_v11_global.nc")),
    DatasetSpec("NEE", "nonflash", "SMrz", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v11_global.nc")),
    DatasetSpec("NEE", "nonflash", "SMs", os.path.join(BASE_DIR, "process/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v11_global.nc")),
    DatasetSpec("RECO", "flash", "SMrz", os.path.join(BASE_DIR, "process/RECO-draught-analysis/results/reco_response_events_global_v11.nc")),
    DatasetSpec("RECO", "flash", "SMs", os.path.join(BASE_DIR, "process/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_drought_v11_global.nc")),
    DatasetSpec("RECO", "nonflash", "SMrz", os.path.join(BASE_DIR, "process/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v11_global.nc")),
    DatasetSpec("RECO", "nonflash", "SMs", os.path.join(BASE_DIR, "process/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v11_global.nc")),
]

DURATION_BINS: List[Tuple[str, int, int]] = [
    ("<=30", -10**9, 30),
    ("31-90", 31, 90),
    ("91-180", 91, 180),
    ("181-365", 181, 365),
    (">365", 366, 10**9),
]


def _to_filled_array(var_obj):
    data = var_obj[:]
    if hasattr(data, "filled"):
        data = data.filled(np.nan)
    return np.asarray(data)


def _safe_mean(ds, var_name: str) -> float:
    if var_name not in ds.variables:
        return float("nan")
    arr = _to_filled_array(ds.variables[var_name]).astype(np.float64, copy=False)
    if arr.size == 0:
        return float("nan")
    valid = np.isfinite(arr)
    if not np.any(valid):
        return float("nan")
    return float(np.nanmean(arr[valid]))


def summarize_dataset(spec: DatasetSpec) -> Dict:
    with nc.Dataset(spec.path, "r") as ds:
        n_events = len(ds.dimensions["event"])
        title = getattr(ds, "title", "")

        response = _to_filled_array(ds.variables["response_detected"]).astype(np.int8, copy=False)
        response_count = int(np.sum(response > 0))
        response_rate = response_count / n_events if n_events > 0 else float("nan")

        row = {
            "variable": spec.variable,
            "drought_type": spec.drought_type,
            "soil_layer": spec.soil_layer,
            "events": n_events,
            "response_count": response_count,
            "response_rate": response_rate,
            "t_response_mean": _safe_mean(ds, "t_response"),
            "t_min_mean": _safe_mean(ds, "t_min"),
            "amp_max_mean": _safe_mean(ds, "amp_max"),
            "recovery_rate_mean": _safe_mean(ds, "recovery_rate"),
            "file_path": spec.path,
            "title": title,
        }

        if "drought_duration" in ds.variables:
            duration = _to_filled_array(ds.variables["drought_duration"]).astype(np.float64, copy=False)
            row["duration_mean"] = float(np.nanmean(duration)) if np.any(np.isfinite(duration)) else float("nan")
        else:
            row["duration_mean"] = float("nan")

    return row


def build_duration_table(spec: DatasetSpec) -> List[Dict]:
    rows: List[Dict] = []
    with nc.Dataset(spec.path, "r") as ds:
        if "drought_duration" not in ds.variables:
            return rows

        duration = _to_filled_array(ds.variables["drought_duration"]).astype(np.float64, copy=False)
        response = _to_filled_array(ds.variables["response_detected"]).astype(np.int8, copy=False)

        valid = np.isfinite(duration)
        duration = duration[valid]
        response = response[valid]

        for label, low, high in DURATION_BINS:
            mask = (duration >= low) & (duration <= high)
            count = int(np.sum(mask))
            if count == 0:
                rate = float("nan")
                resp_count = 0
            else:
                resp_count = int(np.sum(response[mask] > 0))
                rate = resp_count / count

            rows.append(
                {
                    "variable": spec.variable,
                    "drought_type": spec.drought_type,
                    "soil_layer": spec.soil_layer,
                    "duration_bin": label,
                    "events": count,
                    "response_count": resp_count,
                    "response_rate": rate,
                }
            )
    return rows


def write_csv(path: str, rows: List[Dict], headers: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            out = {}
            for h in headers:
                val = row.get(h, "")
                if isinstance(val, float):
                    if np.isnan(val):
                        out[h] = ""
                    else:
                        out[h] = f"{val:.6f}"
                else:
                    out[h] = val
            writer.writerow(out)


def weighted_rate(rows: List[Dict]) -> float:
    total_e = sum(int(r["events"]) for r in rows)
    total_r = sum(int(r["response_count"]) for r in rows)
    return (total_r / total_e) if total_e > 0 else float("nan")


def main() -> None:
    summary_rows = [summarize_dataset(s) for s in DATASETS]

    summary_headers = [
        "variable",
        "drought_type",
        "soil_layer",
        "events",
        "response_count",
        "response_rate",
        "duration_mean",
        "t_response_mean",
        "t_min_mean",
        "amp_max_mean",
        "recovery_rate_mean",
        "file_path",
        "title",
    ]
    write_csv(os.path.join(OUTPUT_DIR, "response_summary_overall.csv"), summary_rows, summary_headers)

    duration_rows: List[Dict] = []
    for spec in DATASETS:
        duration_rows.extend(build_duration_table(spec))
    duration_headers = [
        "variable",
        "drought_type",
        "soil_layer",
        "duration_bin",
        "events",
        "response_count",
        "response_rate",
    ]
    write_csv(os.path.join(OUTPUT_DIR, "response_summary_duration_bins.csv"), duration_rows, duration_headers)

    # 对比1：同变量同土层下，骤旱 vs 非骤旱
    pair_rows: List[Dict] = []
    idx = {(r["variable"], r["soil_layer"], r["drought_type"]): r for r in summary_rows}
    for variable in ["GPP", "NEE", "RECO"]:
        for soil in ["SMrz", "SMs"]:
            flash = idx[(variable, soil, "flash")]
            nonflash = idx[(variable, soil, "nonflash")]
            pair_rows.append(
                {
                    "variable": variable,
                    "soil_layer": soil,
                    "flash_events": flash["events"],
                    "flash_response_rate": flash["response_rate"],
                    "nonflash_events": nonflash["events"],
                    "nonflash_response_rate": nonflash["response_rate"],
                    "rate_delta_nonflash_minus_flash": nonflash["response_rate"] - flash["response_rate"],
                }
            )

    pair_headers = [
        "variable",
        "soil_layer",
        "flash_events",
        "flash_response_rate",
        "nonflash_events",
        "nonflash_response_rate",
        "rate_delta_nonflash_minus_flash",
    ]
    write_csv(os.path.join(OUTPUT_DIR, "comparison_flash_vs_nonflash.csv"), pair_rows, pair_headers)

    # 对比2：按变量汇总（SMrz+SMs加权）
    var_rows: List[Dict] = []
    for variable in ["GPP", "NEE", "RECO"]:
        flash_group = [r for r in summary_rows if r["variable"] == variable and r["drought_type"] == "flash"]
        nonflash_group = [r for r in summary_rows if r["variable"] == variable and r["drought_type"] == "nonflash"]
        flash_rate = weighted_rate(flash_group)
        nonflash_rate = weighted_rate(nonflash_group)
        var_rows.append(
            {
                "variable": variable,
                "flash_total_events": sum(int(r["events"]) for r in flash_group),
                "flash_weighted_response_rate": flash_rate,
                "nonflash_total_events": sum(int(r["events"]) for r in nonflash_group),
                "nonflash_weighted_response_rate": nonflash_rate,
                "rate_delta_nonflash_minus_flash": nonflash_rate - flash_rate,
            }
        )

    var_headers = [
        "variable",
        "flash_total_events",
        "flash_weighted_response_rate",
        "nonflash_total_events",
        "nonflash_weighted_response_rate",
        "rate_delta_nonflash_minus_flash",
    ]
    write_csv(os.path.join(OUTPUT_DIR, "comparison_by_variable_weighted.csv"), var_rows, var_headers)

    # 中文说明
    lines: List[str] = []
    lines.append("# 骤旱 vs 非骤旱响应结果汇总（GPP/NEE/RECO）")
    lines.append("")
    lines.append("## 分析范围")
    lines.append("- 数据来源：`process/GPP-draught-analysis`、`process/NEE-draught-analysis`、`process/RECO-draught-analysis` 下的12个全球结果文件。")
    lines.append("- 维度：3个变量（GPP/NEE/RECO）× 2类干旱（flash/nonflash）× 2土层（SMrz/SMs）。")
    lines.append("")
    lines.append("## 关键发现")

    for r in pair_rows:
        lines.append(
            f"- {r['variable']} ({r['soil_layer']}): flash响应率={r['flash_response_rate']:.2%}, "
            f"nonflash响应率={r['nonflash_response_rate']:.2%}, 差值={r['rate_delta_nonflash_minus_flash']:+.2%}."
        )

    lines.append("")
    lines.append("### 按变量加权汇总（SMrz+SMs）")
    for r in var_rows:
        lines.append(
            f"- {r['variable']}: flash={r['flash_weighted_response_rate']:.2%}, "
            f"nonflash={r['nonflash_weighted_response_rate']:.2%}, "
            f"差值={r['rate_delta_nonflash_minus_flash']:+.2%}."
        )

    lines.append("")
    lines.append("## 输出文件")
    lines.append("- `response_summary_overall.csv`: 12个结果文件的核心指标汇总。")
    lines.append("- `response_summary_duration_bins.csv`: 非骤旱按持续时间分组统计。")
    lines.append("- `comparison_flash_vs_nonflash.csv`: 同变量同土层的骤旱/非骤旱对比。")
    lines.append("- `comparison_by_variable_weighted.csv`: 按变量加权汇总对比。")

    report_path = os.path.join(OUTPUT_DIR, "summary_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("分析完成，输出目录:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
