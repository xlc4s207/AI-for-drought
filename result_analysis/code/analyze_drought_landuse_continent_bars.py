#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np
import pandas as pd
from osgeo import gdal


BASE_DIR = "/home/xulc/flash_drought"
PERF_DIR = os.path.join(BASE_DIR, "process/result_analysis/performance")
LANDUSE_TIF = os.path.join(BASE_DIR, "land_use/MCD12C1_LC_Type1_2010_11km.tif")

LANDUSE_CSV = os.path.join(PERF_DIR, "landuse_grouped_drought_metrics_1980_2024.csv")
CONTINENT_CSV = os.path.join(PERF_DIR, "continent_grouped_drought_metrics_1980_2024.csv")
SUMMARY_MD = os.path.join(PERF_DIR, "landuse_continent_grouped_summary_1980_2024.md")

SCENARIO_ORDER = [("SMs", "flash"), ("SMs", "nonflash"), ("SMrz", "flash"), ("SMrz", "nonflash")]
SCENARIO_CN = {
    ("SMs", "flash"): "SMs-骤旱",
    ("SMs", "nonflash"): "SMs-非骤旱",
    ("SMrz", "flash"): "SMrz-骤旱",
    ("SMrz", "nonflash"): "SMrz-非骤旱",
}
SCENARIO_COLORS = {
    ("SMs", "flash"): "#b2182b",
    ("SMs", "nonflash"): "#ef8a62",
    ("SMrz", "flash"): "#2166ac",
    ("SMrz", "nonflash"): "#67a9cf",
}

LANDUSE_GROUP_LABELS = ["森林", "灌丛", "稀树草原", "草地", "湿地", "农田"]
LANDUSE_GROUP_MAP = {
    1: 1,
    2: 1,
    3: 1,
    4: 1,
    5: 1,
    6: 2,
    7: 2,
    8: 3,
    9: 3,
    10: 4,
    11: 5,
    12: 6,
}

CONTINENT_CODES = {
    1: "北美洲",
    2: "南美洲",
    3: "欧洲",
    4: "非洲",
    5: "亚洲",
    6: "大洋洲",
    7: "南极洲",
}
PLOT_CONTINENT_CODES = [1, 2, 3, 4, 5, 6]


@dataclass(frozen=True)
class MetricSpec:
    source_var: str
    title_cn: str
    ylabel_cn: str
    out_name_landuse: str
    out_name_continent: str


METRIC_SPECS: Dict[str, MetricSpec] = {
    "duration": MetricSpec("duration_mean", "持续时间", "平均持续时间", "landuse_duration_bar.png", "continent_duration_bar.png"),
    "intensity": MetricSpec("intensity_mean", "烈度", "平均烈度", "landuse_intensity_bar.png", "continent_intensity_bar.png"),
    "frequency": MetricSpec("mean_annual_frequency", "频次", "平均年发生频次", "landuse_frequency_bar.png", "continent_frequency_bar.png"),
}


@dataclass(frozen=True)
class Scenario:
    soil_layer: str
    drought_type: str
    event_trend_path: str
    frequency_trend_path: str


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
        Scenario(
            soil_layer="SMs",
            drought_type="flash",
            event_trend_path=os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/trend_analysis/flash/pixel_trend_metrics_v1.nc"),
            frequency_trend_path=os.path.join(PERF_DIR, "frequency_trend_maps/drought_frequency_trend_SMs_flash_1980_2024.nc"),
        ),
        Scenario(
            soil_layer="SMs",
            drought_type="nonflash",
            event_trend_path=os.path.join(BASE_DIR, "gleam/clip_result/SMs_5.3/trend_analysis/nonflash/pixel_trend_metrics_v1.nc"),
            frequency_trend_path=os.path.join(PERF_DIR, "frequency_trend_maps/drought_frequency_trend_SMs_nonflash_1980_2024.nc"),
        ),
        Scenario(
            soil_layer="SMrz",
            drought_type="flash",
            event_trend_path=os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/trend_analysis/flash/pixel_trend_metrics_v1.nc"),
            frequency_trend_path=os.path.join(PERF_DIR, "frequency_trend_maps/drought_frequency_trend_SMrz_flash_1980_2024.nc"),
        ),
        Scenario(
            soil_layer="SMrz",
            drought_type="nonflash",
            event_trend_path=os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/trend_analysis/nonflash/pixel_trend_metrics_v1.nc"),
            frequency_trend_path=os.path.join(PERF_DIR, "frequency_trend_maps/drought_frequency_trend_SMrz_nonflash_1980_2024.nc"),
        ),
    ]


def _to_float(arr) -> np.ndarray:
    if hasattr(arr, "filled"):
        arr = arr.filled(np.nan)
    return np.asarray(arr, dtype=np.float64)


def _normalize_lon(lon_1d: np.ndarray) -> np.ndarray:
    lon = np.asarray(lon_1d, dtype=np.float64).copy()
    lon = ((lon + 180.0) % 360.0) - 180.0
    return lon


def build_continent_code(lat_1d: np.ndarray, lon_1d: np.ndarray) -> np.ndarray:
    lat2d, lon2d = np.meshgrid(lat_1d, _normalize_lon(lon_1d), indexing="ij")
    code = np.zeros(lat2d.shape, dtype=np.int8)
    unassigned = np.ones(lat2d.shape, dtype=bool)

    def assign(mask: np.ndarray, cid: int) -> None:
        nonlocal unassigned
        m = mask & unassigned
        code[m] = cid
        unassigned[m] = False

    antarctica = lat2d < -60.0
    north_america = (lon2d >= -170.0) & (lon2d <= -50.0) & (lat2d >= 7.0) & (lat2d <= 84.0)
    south_america = (lon2d >= -92.0) & (lon2d <= -30.0) & (lat2d >= -60.0) & (lat2d < 15.0)
    europe = (lon2d >= -25.0) & (lon2d <= 60.0) & (lat2d >= 35.0) & (lat2d <= 72.0)
    africa = (lon2d >= -20.0) & (lon2d <= 55.0) & (lat2d >= -35.0) & (lat2d < 38.0)
    asia = (
        ((lon2d >= 25.0) & (lon2d <= 180.0) & (lat2d >= 5.0) & (lat2d <= 82.0))
        | ((lon2d >= 60.0) & (lon2d <= 150.0) & (lat2d >= -10.0) & (lat2d < 5.0))
        | ((lon2d <= -170.0) & (lat2d >= 50.0) & (lat2d <= 72.0))
    )
    oceania = (lon2d >= 110.0) & (lon2d <= 180.0) & (lat2d >= -50.0) & (lat2d < 10.0)

    assign(north_america, 1)
    assign(south_america, 2)
    assign(europe, 3)
    assign(africa, 4)
    assign(asia, 5)
    assign(oceania, 6)
    assign(antarctica, 7)
    return code


def merge_landuse_classes(raw_classes: np.ndarray) -> np.ndarray:
    grouped = np.zeros(np.asarray(raw_classes).shape, dtype=np.int8)
    for raw_code, group_code in LANDUSE_GROUP_MAP.items():
        grouped[np.asarray(raw_classes) == raw_code] = group_code
    return grouped


def area_weighted_mean(data: np.ndarray, weights: np.ndarray) -> Tuple[float, int]:
    valid = np.isfinite(data) & np.isfinite(weights) & (weights > 0)
    pixel_count = int(np.count_nonzero(valid))
    if pixel_count == 0:
        return np.nan, 0
    data_valid = np.asarray(data[valid], dtype=np.float64)
    w_valid = np.asarray(weights[valid], dtype=np.float64)
    return float(np.sum(data_valid * w_valid) / np.sum(w_valid)), pixel_count


def load_metric_array(scenario: Scenario, metric_name: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    spec = METRIC_SPECS[metric_name]
    src_path = scenario.event_trend_path if metric_name in {"duration", "intensity"} else scenario.frequency_trend_path
    with nc.Dataset(src_path, "r") as ds:
        lon = _to_float(ds.variables["lon"][:]).astype(np.float32)
        lat = _to_float(ds.variables["lat"][:]).astype(np.float32)
        arr = _to_float(ds.variables[spec.source_var][:]).astype(np.float32)
    return lon, lat, arr


def load_landuse_group_grid(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    ds = gdal.Open(LANDUSE_TIF)
    if ds is None:
        raise FileNotFoundError(f"无法打开土地利用栅格: {LANDUSE_TIF}")
    raw = ds.GetRasterBand(1).ReadAsArray()
    gt = ds.GetGeoTransform()
    origin_x, pixel_width, _, origin_y, _, pixel_height = gt

    cols = np.floor((np.asarray(lon, dtype=np.float64) - origin_x) / pixel_width).astype(np.int64)
    rows = np.floor((np.asarray(lat, dtype=np.float64) - origin_y) / pixel_height).astype(np.int64)
    cols = np.clip(cols, 0, raw.shape[1] - 1)
    rows = np.clip(rows, 0, raw.shape[0] - 1)

    raw_matched = raw[np.ix_(rows, cols)]
    return merge_landuse_classes(raw_matched)


def build_lat_weights(lat: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    weights_1d = np.cos(np.deg2rad(np.asarray(lat, dtype=np.float64)))
    return np.broadcast_to(weights_1d[:, None], shape)


def compute_group_rows(
    metric_name: str,
    scenario: Scenario,
    data: np.ndarray,
    group_grid: np.ndarray,
    group_codes: Iterable[int],
    group_name_lookup: Dict[int, str],
    grouping_kind: str,
    weights: np.ndarray,
) -> List[dict]:
    rows: List[dict] = []
    scenario_label = SCENARIO_CN[(scenario.soil_layer, scenario.drought_type)]
    for code in group_codes:
        mask = group_grid == code
        group_data = np.where(mask, data, np.nan)
        group_weights = np.where(mask, weights, 0.0)
        value, pixel_count = area_weighted_mean(group_data, group_weights)
        rows.append(
            {
                "grouping_kind": grouping_kind,
                "group_code": code,
                "group_name": group_name_lookup[code],
                "metric": metric_name,
                "metric_cn": METRIC_SPECS[metric_name].title_cn,
                "soil_layer": scenario.soil_layer,
                "drought_type": scenario.drought_type,
                "scenario": scenario_label,
                "value": value,
                "pixel_count": pixel_count,
            }
        )
    return rows


def _bar_positions(n_groups: int, n_series: int, width: float = 0.18) -> Tuple[np.ndarray, np.ndarray]:
    x = np.arange(n_groups, dtype=np.float64)
    offsets = (np.arange(n_series, dtype=np.float64) - (n_series - 1) / 2.0) * width
    return x, offsets


def plot_grouped_bars(df: pd.DataFrame, metric_name: str, categories: List[str], out_path: str, title_prefix: str) -> None:
    spec = METRIC_SPECS[metric_name]
    fig, ax = plt.subplots(figsize=(14, 7), dpi=260)
    x, offsets = _bar_positions(len(categories), len(SCENARIO_ORDER))

    for idx, key in enumerate(SCENARIO_ORDER):
        label = SCENARIO_CN[key]
        subset = df[df["scenario"] == label].set_index("group_name")
        values = [subset.at[name, "value"] if name in subset.index else np.nan for name in categories]
        ax.bar(
            x + offsets[idx],
            values,
            width=0.18,
            label=label,
            color=SCENARIO_COLORS[key],
            edgecolor="black",
            linewidth=0.4,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=20)
    ax.set_ylabel(spec.ylabel_cn)
    ax.set_title(f"{title_prefix}{spec.title_cn}对比（1980-2024）")
    ax.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.35)
    ax.legend(ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def summarize_dimension(df: pd.DataFrame, dimension_title: str, categories: List[str]) -> List[str]:
    lines = [f"## {dimension_title}"]
    for metric_name in METRIC_SPECS:
        lines.append(f"### {METRIC_SPECS[metric_name].title_cn}")
        metric_df = df[df["metric"] == metric_name]
        for key in SCENARIO_ORDER:
            label = SCENARIO_CN[key]
            subset = metric_df[metric_df["scenario"] == label].set_index("group_name")
            values = subset["value"].dropna()
            if values.empty:
                lines.append(f"- {label}：无有效结果。")
                continue
            top_group = values.idxmax()
            low_group = values.idxmin()
            top_value = values.loc[top_group]
            low_value = values.loc[low_group]
            lines.append(
                f"- {label}：{METRIC_SPECS[metric_name].title_cn}最高为{top_group}（{top_value:.3f}），最低为{low_group}（{low_value:.3f}）。"
            )
    return lines


def write_summary(landuse_df: pd.DataFrame, continent_df: pd.DataFrame) -> None:
    lines = [
        "# 四类干旱土地利用与大洲分组统计总结",
        "",
        "本分析基于 1980-2024 年四类干旱像元多年平均结果，比较不同土地利用类型和不同大洲中的干旱持续时间、烈度与发生频次。",
        "",
        "统计说明：",
        "- 持续时间与烈度使用 `pixel_trend_metrics_v1.nc` 中的多年平均字段。",
        "- 频次使用 `drought_frequency_trend_*_1980_2024.nc` 中的 `mean_annual_frequency`。",
        "- 组内平均采用 `cos(lat)` 面积权重。",
        "- 土地利用采用 6 个合并大类，大洲采用六大洲分区。",
        "",
    ]
    lines.extend(summarize_dimension(landuse_df, "土地利用类型结果", LANDUSE_GROUP_LABELS))
    lines.append("")
    lines.extend(summarize_dimension(continent_df, "六大洲结果", [CONTINENT_CODES[c] for c in PLOT_CONTINENT_CODES]))
    lines.append("")
    lines.append("## 说明")
    lines.append("- 若某类分组像元较少，则其平均值更容易受到局地极端值影响。")
    lines.append("- 土地利用结果反映的是该类像元的空间平均水平，不代表该类内部所有区域都具有相同变化。")
    lines.append("- 本文件用于快速总结，详细解释可结合空间分布图与趋势报告共同讨论。")
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    os.makedirs(PERF_DIR, exist_ok=True)
    font_name = setup_chinese_font()
    print(f"中文字体: {font_name}")

    scenarios = build_scenarios()
    for scenario in scenarios:
        if not os.path.exists(scenario.event_trend_path):
            raise FileNotFoundError(f"缺少文件: {scenario.event_trend_path}")
        if not os.path.exists(scenario.frequency_trend_path):
            raise FileNotFoundError(f"缺少文件: {scenario.frequency_trend_path}")

    lon, lat, template_arr = load_metric_array(scenarios[0], "duration")
    landuse_group_grid = load_landuse_group_grid(lat, lon)
    continent_grid = build_continent_code(lat, lon)
    lat_weights = build_lat_weights(lat, template_arr.shape)

    landuse_rows: List[dict] = []
    continent_rows: List[dict] = []

    landuse_lookup = {idx + 1: label for idx, label in enumerate(LANDUSE_GROUP_LABELS)}
    continent_lookup = {code: CONTINENT_CODES[code] for code in PLOT_CONTINENT_CODES}

    for scenario in scenarios:
        for metric_name in METRIC_SPECS:
            _, _, data = load_metric_array(scenario, metric_name)
            landuse_rows.extend(
                compute_group_rows(
                    metric_name=metric_name,
                    scenario=scenario,
                    data=data,
                    group_grid=landuse_group_grid,
                    group_codes=range(1, len(LANDUSE_GROUP_LABELS) + 1),
                    group_name_lookup=landuse_lookup,
                    grouping_kind="landuse",
                    weights=lat_weights,
                )
            )
            continent_rows.extend(
                compute_group_rows(
                    metric_name=metric_name,
                    scenario=scenario,
                    data=data,
                    group_grid=continent_grid,
                    group_codes=PLOT_CONTINENT_CODES,
                    group_name_lookup=continent_lookup,
                    grouping_kind="continent",
                    weights=lat_weights,
                )
            )

    landuse_df = pd.DataFrame(landuse_rows)
    continent_df = pd.DataFrame(continent_rows)
    landuse_df.to_csv(LANDUSE_CSV, index=False, encoding="utf-8-sig")
    continent_df.to_csv(CONTINENT_CSV, index=False, encoding="utf-8-sig")

    for metric_name, spec in METRIC_SPECS.items():
        plot_grouped_bars(
            landuse_df[landuse_df["metric"] == metric_name],
            metric_name,
            LANDUSE_GROUP_LABELS,
            os.path.join(PERF_DIR, spec.out_name_landuse),
            "不同土地利用类型",
        )
        plot_grouped_bars(
            continent_df[continent_df["metric"] == metric_name],
            metric_name,
            [CONTINENT_CODES[c] for c in PLOT_CONTINENT_CODES],
            os.path.join(PERF_DIR, spec.out_name_continent),
            "不同大洲",
        )

    write_summary(landuse_df, continent_df)

    print(f"已写出: {LANDUSE_CSV}")
    print(f"已写出: {CONTINENT_CSV}")
    print(f"已写出: {SUMMARY_MD}")


if __name__ == "__main__":
    main()
