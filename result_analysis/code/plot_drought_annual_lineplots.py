#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Mapping

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np
import pandas as pd


BASE_DIR = "/home/xulc/flash_drought"
PERF_DIR = os.path.join(BASE_DIR, "process/result_analysis/performance")

OUTPUT_CSV = os.path.join(PERF_DIR, "annual_drought_metric_timeseries_1980_2024.csv")
OUTPUT_RAW_PNG = os.path.join(PERF_DIR, "annual_drought_metric_lineplots_raw_filtered_1980_2024.png")
OUTPUT_SMOOTH_PNG = os.path.join(PERF_DIR, "annual_drought_metric_lineplots_smooth5_filtered_1980_2024.png")
OUTPUT_MD = os.path.join(PERF_DIR, "annual_drought_metric_lineplots_1980_2024.md")

YEAR_MIN = 1980
YEAR_MAX = 2024
LAT_CHUNK = 100
EXCLUDED_YEARS = {1980, 2024}
SMOOTH_WINDOW = 5

SCENARIO_ORDER = [("SMs", "flash"), ("SMs", "nonflash"), ("SMrz", "flash"), ("SMrz", "nonflash")]
SCENARIO_CN = {
    ("SMs", "flash"): "SMs-骤旱",
    ("SMs", "nonflash"): "SMs-非骤旱",
    ("SMrz", "flash"): "SMrz-骤旱",
    ("SMrz", "nonflash"): "SMrz-非骤旱",
}
SCENARIO_COLORS = {
    ("SMs", "flash"): "#8f1d21",
    ("SMs", "nonflash"): "#d17c4a",
    ("SMrz", "flash"): "#1c4e80",
    ("SMrz", "nonflash"): "#4d8f8b",
}


@dataclass(frozen=True)
class MetricSpec:
    source_var: str
    metric_cn: str
    ylabel_cn: str


METRIC_SPECS: Dict[str, MetricSpec] = {
    "frequency": MetricSpec("mean_annual_frequency", "频率", "全球年事件频次"),
    "duration": MetricSpec("duration", "持续时间", "全球事件平均持续时间"),
    "intensity": MetricSpec("intensity", "烈度", "全球事件平均烈度"),
    "onset_days": MetricSpec("onset_days", "爆发时间", "全球事件平均爆发时间"),
}


@dataclass(frozen=True)
class Scenario:
    soil_layer: str
    drought_type: str
    event_path: str


def setup_chinese_font() -> str:
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

    if selected is None:
        common_font_files = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKSC-Regular.otf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]
        for fp in common_font_files:
            if os.path.exists(fp):
                try:
                    fm.fontManager.addfont(fp)
                    selected = fm.FontProperties(fname=fp).get_name()
                    break
                except Exception:
                    continue

    rcParams["font.sans-serif"] = [selected, "DejaVu Sans"] if selected else ["DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    return selected if selected else "DejaVu Sans"


def build_scenarios() -> List[Scenario]:
    return [
        Scenario("SMs", "flash", os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/flash_drought_events_v5.nc")),
        Scenario("SMs", "nonflash", os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/nonflash_drought_events_v5.nc")),
        Scenario("SMrz", "flash", os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/flash_drought_events_v5.nc")),
        Scenario("SMrz", "nonflash", os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/nonflash_drought_events_v5.nc")),
    ]


def _to_float(arr) -> np.ndarray:
    if hasattr(arr, "filled"):
        arr = arr.astype(np.float64).filled(np.nan)
    return np.asarray(arr, dtype=np.float64)


def _read_chunk(var_obj, slc, dtype=np.float32) -> np.ndarray:
    data = var_obj[slc]
    if isinstance(data, np.ma.MaskedArray):
        data = data.astype(dtype).filled(np.nan)
    else:
        data = np.asarray(data, dtype=dtype)
    fill = getattr(var_obj, "_FillValue", None)
    if fill is not None:
        data[data == fill] = np.nan
    return data


def aggregate_event_metric_by_year(years: np.ndarray, values: np.ndarray, year_min: int, year_max: int) -> Dict[int, float]:
    year_arr = np.asarray(years, dtype=np.int32).reshape(-1)
    value_arr = np.asarray(values, dtype=np.float64).reshape(-1)
    valid = np.isfinite(value_arr) & (year_arr >= year_min) & (year_arr <= year_max)
    result: Dict[int, float] = {}
    if not np.any(valid):
        return result

    for year in range(year_min, year_max + 1):
        mask = valid & (year_arr == year)
        if np.any(mask):
            result[year] = float(np.nanmean(value_arr[mask]))
    return result


def build_metric_dataframe(
    scenario_cn: str,
    soil_layer: str,
    drought_type: str,
    metric_name: str,
    metric_cn: str,
    annual_values: Mapping[int, float],
) -> pd.DataFrame:
    rows = []
    for year in sorted(annual_values):
        rows.append(
            {
                "soil_layer": soil_layer,
                "drought_type": drought_type,
                "scenario_cn": scenario_cn,
                "metric": metric_name,
                "metric_cn": metric_cn,
                "year": int(year),
                "value": float(annual_values[year]),
            }
        )
    return pd.DataFrame(rows, columns=["soil_layer", "drought_type", "scenario_cn", "metric", "metric_cn", "year", "value"])


def filter_plot_years(df: pd.DataFrame) -> pd.DataFrame:
    out = df.loc[~df["year"].isin(EXCLUDED_YEARS)].copy()
    return out.sort_values(["metric", "soil_layer", "drought_type", "year"]).reset_index(drop=True)


def add_centered_rolling_mean(df: pd.DataFrame, window: int = SMOOTH_WINDOW) -> pd.DataFrame:
    out = df.copy()
    out["smoothed_5yr"] = np.nan
    group_cols = ["soil_layer", "drought_type", "scenario_cn", "metric", "metric_cn"]
    for _, idx in out.groupby(group_cols, sort=False).groups.items():
        sub = out.loc[idx].sort_values("year")
        smooth = sub["value"].rolling(window=window, center=True, min_periods=1).mean()
        out.loc[sub.index, "smoothed_5yr"] = smooth.to_numpy()
    return out.sort_values(["metric", "soil_layer", "drought_type", "year"]).reset_index(drop=True)


def build_event_mask(
    years: np.ndarray,
    onset_days: np.ndarray,
    scenario: Scenario,
    year_min: int = YEAR_MIN,
    year_max: int = YEAR_MAX,
) -> np.ndarray:
    year_arr = np.asarray(years, dtype=np.float64).reshape(-1)
    onset_arr = np.asarray(onset_days, dtype=np.float64).reshape(-1)

    valid = np.isfinite(year_arr) & (year_arr >= year_min) & (year_arr <= year_max)
    valid &= np.isfinite(onset_arr)

    if scenario.drought_type == "flash":
        valid &= onset_arr >= 5
        valid &= onset_arr <= 20
    elif scenario.drought_type == "nonflash":
        valid &= onset_arr > 20

    return valid


def aggregate_metrics_from_event_file(scenario: Scenario) -> Dict[str, Dict[int, float]]:
    with nc.Dataset(scenario.event_path, "r") as ds:
        nlat = len(ds.dimensions["lat"])
        n_years = YEAR_MAX - YEAR_MIN + 1
        metric_names = ("frequency", "duration", "intensity", "onset_days")
        sum_by_metric = {name: np.zeros(n_years, dtype=np.float64) for name in metric_names}
        count_by_metric = {name: np.zeros(n_years, dtype=np.int64) for name in metric_names}

        for lat0 in range(0, nlat, LAT_CHUNK):
            lat1 = min(lat0 + LAT_CHUNK, nlat)
            slc = (slice(None), slice(lat0, lat1), slice(None))
            years = _read_chunk(ds.variables["drought_start_year"], slc).reshape(-1)
            onset_days = _read_chunk(ds.variables["onset_days"], slc).reshape(-1)
            valid_event = build_event_mask(years, onset_days, scenario, YEAR_MIN, YEAR_MAX)
            if not np.any(valid_event):
                continue

            year_idx = years[valid_event].astype(np.int64, copy=False) - YEAR_MIN
            count_by_year = np.bincount(year_idx, minlength=n_years)
            count_by_metric["frequency"] += count_by_year
            sum_by_metric["frequency"] += count_by_year.astype(np.float64)

            metric_values = {
                "duration": _read_chunk(ds.variables["duration"], slc).reshape(-1),
                "intensity": _read_chunk(ds.variables["intensity"], slc).reshape(-1),
                "onset_days": onset_days,
            }
            for metric_name, values in metric_values.items():
                valid = valid_event & np.isfinite(values)
                if not np.any(valid):
                    continue
                year_idx = years[valid].astype(np.int64, copy=False) - YEAR_MIN
                sum_by_metric[metric_name] += np.bincount(
                    year_idx, weights=values[valid].astype(np.float64), minlength=n_years
                )
                count_by_metric[metric_name] += np.bincount(year_idx, minlength=n_years)

    result: Dict[str, Dict[int, float]] = {}
    for metric_name in ("frequency", "duration", "intensity", "onset_days"):
        annual_values: Dict[int, float] = {}
        for offset in range(n_years):
            if count_by_metric[metric_name][offset] > 0:
                if metric_name == "frequency":
                    annual_values[YEAR_MIN + offset] = float(sum_by_metric[metric_name][offset])
                else:
                    annual_values[YEAR_MIN + offset] = float(
                        sum_by_metric[metric_name][offset] / count_by_metric[metric_name][offset]
                    )
        result[metric_name] = annual_values
    return result


def build_timeseries_dataframe() -> pd.DataFrame:
    frames = []
    for scenario in build_scenarios():
        scenario_cn = SCENARIO_CN[(scenario.soil_layer, scenario.drought_type)]
        metric_map = aggregate_metrics_from_event_file(scenario)
        for metric_name in ("frequency", "duration", "intensity", "onset_days"):
            frames.append(
                build_metric_dataframe(
                    scenario_cn=scenario_cn,
                    soil_layer=scenario.soil_layer,
                    drought_type=scenario.drought_type,
                    metric_name=metric_name,
                    metric_cn=METRIC_SPECS[metric_name].metric_cn,
                    annual_values=metric_map[metric_name],
                )
            )
    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values(["metric", "soil_layer", "drought_type", "year"]).reset_index(drop=True)
    df = filter_plot_years(df)
    df = add_centered_rolling_mean(df, window=SMOOTH_WINDOW)
    return df


def plot_line_panels(df: pd.DataFrame, value_col: str, title: str, out_path: str) -> None:
    metric_order = ["frequency", "duration", "intensity", "onset_days"]
    fig, axes = plt.subplots(2, 2, figsize=(16.5, 9.5), dpi=320, sharex=True)
    axes = axes.ravel()
    fig.patch.set_facecolor("white")

    for ax, metric_name in zip(axes, metric_order):
        metric_df = df[df["metric"] == metric_name]
        spec = METRIC_SPECS[metric_name]
        ax.set_facecolor("#fbf8f3")
        for key in SCENARIO_ORDER:
            label = SCENARIO_CN[key]
            subset = metric_df[metric_df["scenario_cn"] == label].sort_values("year")
            series = subset[value_col]
            ax.plot(
                subset["year"],
                series,
                label=label,
                color=SCENARIO_COLORS[key],
                linewidth=2.4,
                solid_capstyle="round",
            )
        ax.set_title(spec.metric_cn, fontsize=13, pad=8, fontweight="bold")
        ax.set_ylabel(spec.ylabel_cn, fontsize=11)
        ax.grid(True, axis="y", linestyle="--", linewidth=0.55, alpha=0.35)
        ax.set_xlim(YEAR_MIN + 1, YEAR_MAX - 1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_linewidth(0.8)
        ax.spines["bottom"].set_linewidth(0.8)
        ax.tick_params(axis="both", labelsize=9, length=3.5, width=0.8)

    axes[2].set_xlabel("年份")
    axes[3].set_xlabel("年份")
    xticks = [1981, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2023]
    for ax in axes:
        ax.set_xticks(xticks)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.02), fontsize=10)
    fig.suptitle(title, fontsize=18, y=1.045, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _metric_summary_lines(df: pd.DataFrame, metric_name: str) -> List[str]:
    lines: List[str] = []
    metric_df = df[df["metric"] == metric_name]
    for key in SCENARIO_ORDER:
        label = SCENARIO_CN[key]
        subset = metric_df[metric_df["scenario_cn"] == label].sort_values("year")
        if subset.empty:
            lines.append(f"- {label}：无有效数据。")
            continue
        start_val = float(subset.iloc[0]["value"])
        end_val = float(subset.iloc[-1]["value"])
        start_smooth = float(subset.iloc[0]["smoothed_5yr"])
        end_smooth = float(subset.iloc[-1]["smoothed_5yr"])
        max_row = subset.loc[subset["value"].idxmax()]
        min_row = subset.loc[subset["value"].idxmin()]
        lines.append(
            f"- {label}：过滤后起始年 1981 为 {start_val:.3f}，末年 2023 为 {end_val:.3f}；"
            f"5 年滑动平均由 {start_smooth:.3f} 变化到 {end_smooth:.3f}。"
        )
        lines.append(
            f"- {label}：原始序列最高出现在 {int(max_row['year'])} 年（{float(max_row['value']):.3f}），"
            f"最低出现在 {int(min_row['year'])} 年（{float(min_row['value']):.3f}）。"
        )
    return lines


def write_summary(df: pd.DataFrame) -> None:
    lines = [
        "# 四种干旱年际折线图论文风格解读",
        "",
        "本轮图件在上一版基础上做了三项调整：剔除了 1980 和 2024 两个失真年份，分别输出了原始年际序列图和 5 年滑动平均图，并统一优化为更适合论文展示的绘图风格。",
        "",
        "统计口径：",
        "- 四个指标均直接从事件文件重新统计，不再混用旧版频率 CSV。",
        "- `SMs-非骤旱` 与 `SMrz-非骤旱` 在本轮图件中仅指 `slow_onset` 事件，即 `onset_days > 20`。",
        "- `dry_to_drier` 事件因不存在有效 `onset_start`，已从非骤旱统计中排除。",
        "- 频率按 `drought_start_year` 统计为当年事件总数；持续时间、烈度、爆发时间按当年所有事件求全球平均值。",
        "- 展示年份为 `1981-2023`，其中 `1980` 和 `2024` 已剔除。",
        "- 平滑图使用 `5` 年居中滑动平均，边缘年份允许使用不足 `5` 年的可用窗口。",
        "- 四条线分别代表 `SMs-骤旱`、`SMs-非骤旱`、`SMrz-骤旱`、`SMrz-非骤旱`。",
        "",
        "注意：",
        "- 爆发时间使用 `onset_days`，表示从 `onset_start` 到 `drought_start` 所经历的天数。",
        "- 在该指标下，数值越小表示爆发越快，数值越大表示爆发越慢。",
        "- 原始图更适合观察年际异常与波动峰谷，平滑图更适合判断长期背景变化方向。",
        "",
    ]

    for metric_name in ["frequency", "duration", "intensity", "onset_days"]:
        lines.append(f"## {METRIC_SPECS[metric_name].metric_cn}")
        lines.extend(_metric_summary_lines(df, metric_name))
        lines.append("")

    lines.extend(
        [
            "## 综合解读",
            "- 剔除 1980 和 2024 后，序列首尾异常尖点被明显压制，长期演变特征更稳定。",
            "- 原始图保留了 ENSO、区域极端气候年等可能带来的强波动信息，适合说明年际扰动。",
            "- 5 年滑动平均图更适合用于论文正文讨论长期趋势，因为它弱化了单一年份异常值的干扰。",
            "- 若后续需要进行趋势检验或分阶段比较，建议基于本次过滤后的时间序列继续开展。",
        ]
    )

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    os.makedirs(PERF_DIR, exist_ok=True)
    font_name = setup_chinese_font()
    print(f"中文字体: {font_name}")

    scenarios = build_scenarios()
    for scenario in scenarios:
        if not os.path.exists(scenario.event_path):
            raise FileNotFoundError(f"缺少文件: {scenario.event_path}")

    df = build_timeseries_dataframe()
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    plot_line_panels(df, value_col="value", title="四种干旱四指标年际变化（剔除 1980 和 2024）", out_path=OUTPUT_RAW_PNG)
    plot_line_panels(df, value_col="smoothed_5yr", title="四种干旱四指标 5 年滑动平均变化", out_path=OUTPUT_SMOOTH_PNG)
    write_summary(df)

    print(f"已写出: {OUTPUT_CSV}")
    print(f"已写出: {OUTPUT_RAW_PNG}")
    print(f"已写出: {OUTPUT_SMOOTH_PNG}")
    print(f"已写出: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
