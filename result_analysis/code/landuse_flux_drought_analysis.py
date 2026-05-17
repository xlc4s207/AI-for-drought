#!/usr/bin/env python3

import math
import os
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import netCDF4 as nc
import numpy as np
import rasterio

from compare_with_abs_nc import (
    DATASET_PATHS,
    _read_chunk,
    classify_dataset,
    metric_field_lookup,
    select_year_field,
    write_csv,
    write_text,
)


BASE_DIR = "/home/xulc/flash_drought"
LANDUSE_DIR = os.path.join(BASE_DIR, "land_use")
OUTPUT_DIR = os.path.join(BASE_DIR, "process", "result_analysis", "landuse_analysis")
PLOT_DIR = os.path.join(OUTPUT_DIR, "plots")
CHUNK_SIZE = 1_000_000
LANDUSE_YEAR_MIN = 2001
LANDUSE_YEAR_MAX = 2021

MODIS_LC_TYPE1 = {
    0: "Water Bodies",
    1: "Evergreen Needleleaf Forest",
    2: "Evergreen Broadleaf Forest",
    3: "Deciduous Needleleaf Forest",
    4: "Deciduous Broadleaf Forest",
    5: "Mixed Forests",
    6: "Closed Shrublands",
    7: "Open Shrublands",
    8: "Woody Savannas",
    9: "Savannas",
    10: "Grasslands",
    11: "Permanent Wetlands",
    12: "Croplands",
    13: "Urban and Built-up",
    14: "Cropland and Natural Vegetation Mosaic",
    15: "Snow and Ice",
    16: "Barren or Sparsely Vegetated",
}

VARIABLE_ORDER = ["GPP", "NEE", "RECO"]
SCENARIO_ORDER = [
    ("flash", "SMrz"),
    ("flash", "SMs"),
    ("nonflash", "SMrz"),
    ("nonflash", "SMs"),
]
METRIC_MEAN_FIELDS = [
    "directional_change_abs_mean",
    "t_response_mean",
    "t_impact_mean",
    "t_recover_mean",
]
EXCLUDED_NONVEGETATED_CODES = {0, 15, 16}


def map_event_year_to_landuse_year(year: int) -> int:
    year = int(year)
    if year < LANDUSE_YEAR_MIN:
        return LANDUSE_YEAR_MIN
    if year > LANDUSE_YEAR_MAX:
        return LANDUSE_YEAR_MAX
    return year


def directional_change_metric(variable: str) -> str:
    return "rise_abs" if str(variable).upper() == "NEE" else "drop_abs"


def landuse_code_name(code: int) -> str:
    return MODIS_LC_TYPE1.get(int(code), "Unclassified")


def filter_rows_for_vegetated_plots(rows: Sequence[Dict]) -> List[Dict]:
    return [row for row in rows if int(row["landuse_code"]) not in EXCLUDED_NONVEGETATED_CODES]


def available_dataset_specs() -> Tuple[List, List[str]]:
    specs = []
    missing = []
    for path in DATASET_PATHS:
        if not os.path.exists(path):
            missing.append(path)
            continue
        specs.append(classify_dataset(path))
    return specs, missing


def available_landuse_dataset_specs() -> Tuple[List, List[str]]:
    return available_dataset_specs()


def discover_landuse_rasters() -> Dict[int, str]:
    out: Dict[int, str] = {}
    for year in range(LANDUSE_YEAR_MIN, LANDUSE_YEAR_MAX + 1):
        path = os.path.join(LANDUSE_DIR, f"MCD12C1_LC_Type1_{year}_11km.tif")
        if os.path.exists(path):
            out[year] = path
    if LANDUSE_YEAR_MIN not in out:
        raise FileNotFoundError("Missing required 2001 MODIS land-use raster.")
    return out


def load_landuse_grids() -> Dict[int, Dict[str, np.ndarray]]:
    rasters = discover_landuse_rasters()
    out: Dict[int, Dict[str, np.ndarray]] = {}
    for year, path in sorted(rasters.items()):
        with rasterio.open(path) as src:
            out[year] = {
                "array": src.read(1),
                "transform": src.transform,
                "height": src.height,
                "width": src.width,
            }
    return out


def _normalize_lon(lon: np.ndarray) -> np.ndarray:
    return ((np.asarray(lon, dtype=np.float64) + 180.0) % 360.0) - 180.0


def sample_landuse_codes(
    lat: np.ndarray,
    lon: np.ndarray,
    years: np.ndarray,
    landuse_grids: Dict[int, Dict[str, np.ndarray]],
) -> np.ndarray:
    lat = np.asarray(lat, dtype=np.float64)
    lon = _normalize_lon(lon)
    years = np.asarray(years, dtype=np.int32)
    out = np.full(lat.shape, -1, dtype=np.int16)

    for lu_year in np.unique(years):
        mask = years == lu_year
        if not np.any(mask):
            continue
        grid = landuse_grids.get(int(lu_year))
        if grid is None:
            continue
        transform = grid["transform"]
        arr = grid["array"]
        height = int(grid["height"])
        width = int(grid["width"])

        cols = np.floor((lon[mask] - transform.c) / transform.a).astype(np.int64)
        rows = np.floor((lat[mask] - transform.f) / transform.e).astype(np.int64)
        valid = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
        idx = np.flatnonzero(mask)
        valid_idx = idx[valid]
        out[valid_idx] = arr[rows[valid], cols[valid]].astype(np.int16, copy=False)
    return out


def _new_bucket() -> Dict[str, float]:
    return {
        "event_count": 0.0,
        "response_sum": 0.0,
        "directional_change_abs_sum": 0.0,
        "directional_change_abs_count": 0.0,
        "t_response_sum": 0.0,
        "t_response_count": 0.0,
        "t_impact_sum": 0.0,
        "t_impact_count": 0.0,
        "t_recover_sum": 0.0,
        "t_recover_count": 0.0,
    }


def accumulate_group_chunk(
    accumulator: Dict[Tuple, Dict[str, float]],
    group_prefix: Tuple,
    labels: np.ndarray,
    response: np.ndarray,
    directional_change_abs: np.ndarray,
    t_response: np.ndarray,
    t_impact: np.ndarray,
    t_recover: np.ndarray,
) -> None:
    labels = np.asarray(labels, dtype=object)
    for label in np.unique(labels):
        mask = labels == label
        if not np.any(mask):
            continue
        key = tuple(group_prefix) + (str(label),)
        bucket = accumulator.setdefault(key, _new_bucket())
        bucket["event_count"] += float(np.count_nonzero(mask))

        valid_response = mask & np.isfinite(response)
        if np.any(valid_response):
            bucket["response_sum"] += float(np.sum(response[valid_response] > 0))

        for metric_name, values in (
            ("directional_change_abs", directional_change_abs),
            ("t_response", t_response),
            ("t_impact", t_impact),
            ("t_recover", t_recover),
        ):
            valid = mask & np.isfinite(values)
            if not np.any(valid):
                continue
            bucket[f"{metric_name}_sum"] += float(np.sum(values[valid]))
            bucket[f"{metric_name}_count"] += float(np.count_nonzero(valid))


def _round(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if not math.isfinite(float(value)):
        return None
    return round(float(value), 6)


def _bucket_to_row(
    key: Tuple,
    bucket: Dict[str, float],
    yearly: bool = False,
) -> Dict:
    if yearly:
        variable, drought_type, soil_layer, year, landuse_code, landuse_name = key
    else:
        variable, drought_type, soil_layer, landuse_code, landuse_name = key

    row = {
        "variable": variable,
        "drought_type": drought_type,
        "soil_layer": soil_layer,
        "scenario": f"{drought_type}+{soil_layer}",
        "landuse_code": int(landuse_code),
        "landuse_name": landuse_name,
        "event_count": int(bucket["event_count"]),
        "response_rate": _round(bucket["response_sum"] / bucket["event_count"]) if bucket["event_count"] > 0 else None,
        "directional_change_abs_mean": _round(bucket["directional_change_abs_sum"] / bucket["directional_change_abs_count"])
        if bucket["directional_change_abs_count"] > 0
        else None,
        "t_response_mean": _round(bucket["t_response_sum"] / bucket["t_response_count"]) if bucket["t_response_count"] > 0 else None,
        "t_impact_mean": _round(bucket["t_impact_sum"] / bucket["t_impact_count"]) if bucket["t_impact_count"] > 0 else None,
        "t_recover_mean": _round(bucket["t_recover_sum"] / bucket["t_recover_count"]) if bucket["t_recover_count"] > 0 else None,
    }
    if yearly:
        row["year"] = int(year)
    return row


def build_summary_rows(accumulator: Dict[Tuple, Dict[str, float]], yearly: bool = False) -> List[Dict]:
    rows = [_bucket_to_row(key, bucket, yearly=yearly) for key, bucket in sorted(accumulator.items())]
    rows.sort(
        key=lambda row: (
            VARIABLE_ORDER.index(row["variable"]),
            SCENARIO_ORDER.index((row["drought_type"], row["soil_layer"])),
            row.get("year", -9999),
            row["landuse_code"],
        )
    )
    return rows


def build_pairwise_rows(summary_rows: Sequence[Dict]) -> List[Dict]:
    lookup = {
        (row["variable"], row["drought_type"], row["soil_layer"], row["landuse_code"]): row
        for row in summary_rows
    }
    rows: List[Dict] = []
    for variable in VARIABLE_ORDER:
        landuse_codes = sorted({row["landuse_code"] for row in summary_rows if row["variable"] == variable})
        for code in landuse_codes:
            name = next(row["landuse_name"] for row in summary_rows if row["variable"] == variable and row["landuse_code"] == code)
            for soil_layer in ("SMrz", "SMs"):
                left = lookup.get((variable, "flash", soil_layer, code))
                right = lookup.get((variable, "nonflash", soil_layer, code))
                if left and right:
                    for metric in ["response_rate"] + METRIC_MEAN_FIELDS:
                        if left.get(metric) is None or right.get(metric) is None:
                            continue
                        rows.append(
                            {
                                "comparison_type": "flash_vs_nonflash",
                                "variable": variable,
                                "soil_layer": soil_layer,
                                "landuse_code": code,
                                "landuse_name": name,
                                "metric": metric,
                                "left_scenario": left["scenario"],
                                "right_scenario": right["scenario"],
                                "left_value": left[metric],
                                "right_value": right[metric],
                                "delta_right_minus_left": _round(right[metric] - left[metric]),
                            }
                        )
            for drought_type in ("flash", "nonflash"):
                left = lookup.get((variable, drought_type, "SMrz", code))
                right = lookup.get((variable, drought_type, "SMs", code))
                if left and right:
                    for metric in ["response_rate"] + METRIC_MEAN_FIELDS:
                        if left.get(metric) is None or right.get(metric) is None:
                            continue
                        rows.append(
                            {
                                "comparison_type": "SMrz_vs_SMs",
                                "variable": variable,
                                "soil_layer": drought_type,
                                "landuse_code": code,
                                "landuse_name": name,
                                "metric": metric,
                                "left_scenario": left["scenario"],
                                "right_scenario": right["scenario"],
                                "left_value": left[metric],
                                "right_value": right[metric],
                                "delta_right_minus_left": _round(right[metric] - left[metric]),
                            }
                        )
    return rows


def aggregate_landuse_rows(dataset_specs: Sequence, landuse_grids: Dict[int, Dict[str, np.ndarray]]) -> Tuple[List[Dict], List[Dict]]:
    summary_acc: Dict[Tuple, Dict[str, float]] = {}
    yearly_acc: Dict[Tuple, Dict[str, float]] = {}

    for spec in dataset_specs:
        with nc.Dataset(spec.path, "r") as ds:
            n_events = len(ds.dimensions["event"])
            year_field = select_year_field(tuple(ds.variables.keys()))
            field_lookup = metric_field_lookup(ds, spec.variable)
            change_field = field_lookup[directional_change_metric(spec.variable)]

            for start in range(0, n_events, CHUNK_SIZE):
                end = min(start + CHUNK_SIZE, n_events)
                lat = _read_chunk(ds, "lat", start, end)
                lon = _read_chunk(ds, "lon", start, end)
                years_raw = _read_chunk(ds, year_field, start, end).astype(np.int32, copy=False)
                response = _read_chunk(ds, "response_detected", start, end)
                directional_change_abs = _read_chunk(ds, change_field, start, end)
                t_response = _read_chunk(ds, "t_response", start, end)
                t_impact = _read_chunk(ds, "t_impact", start, end)
                t_recover = _read_chunk(ds, "t_recover", start, end)

                valid_geo = np.isfinite(lat) & np.isfinite(lon) & np.isfinite(years_raw)
                if not np.any(valid_geo):
                    continue

                lat = lat[valid_geo]
                lon = lon[valid_geo]
                years_raw = years_raw[valid_geo]
                response = response[valid_geo]
                directional_change_abs = directional_change_abs[valid_geo]
                t_response = t_response[valid_geo]
                t_impact = t_impact[valid_geo]
                t_recover = t_recover[valid_geo]

                lu_years = np.array([map_event_year_to_landuse_year(y) for y in years_raw], dtype=np.int32)
                landuse_codes = sample_landuse_codes(lat, lon, lu_years, landuse_grids)
                valid_landuse = landuse_codes >= 0
                if not np.any(valid_landuse):
                    continue

                years_raw = years_raw[valid_landuse]
                response = response[valid_landuse]
                directional_change_abs = directional_change_abs[valid_landuse]
                t_response = t_response[valid_landuse]
                t_impact = t_impact[valid_landuse]
                t_recover = t_recover[valid_landuse]
                landuse_codes = landuse_codes[valid_landuse]
                landuse_names = np.array([landuse_code_name(code) for code in landuse_codes], dtype=object)

                for code in np.unique(landuse_codes):
                    code_mask = landuse_codes == code
                    name = landuse_code_name(int(code))
                    accumulate_group_chunk(
                        accumulator=summary_acc,
                        group_prefix=(spec.variable, spec.drought_type, spec.soil_layer, int(code)),
                        labels=np.full(np.count_nonzero(code_mask), name, dtype=object),
                        response=response[code_mask],
                        directional_change_abs=directional_change_abs[code_mask],
                        t_response=t_response[code_mask],
                        t_impact=t_impact[code_mask],
                        t_recover=t_recover[code_mask],
                    )

                    years_for_code = years_raw[code_mask]
                    for year in np.unique(years_for_code):
                        year_mask = code_mask & (years_raw == year)
                        accumulate_group_chunk(
                            accumulator=yearly_acc,
                            group_prefix=(spec.variable, spec.drought_type, spec.soil_layer, int(year), int(code)),
                            labels=np.full(np.count_nonzero(year_mask), name, dtype=object),
                            response=response[year_mask],
                            directional_change_abs=directional_change_abs[year_mask],
                            t_response=t_response[year_mask],
                            t_impact=t_impact[year_mask],
                            t_recover=t_recover[year_mask],
                        )

    return build_summary_rows(summary_acc, yearly=False), build_summary_rows(yearly_acc, yearly=True)


def _import_plotting():
    import matplotlib.pyplot as plt

    return plt


def plot_metric_by_landuse(summary_rows: Sequence[Dict], variable: str, metric: str, out_png: str) -> None:
    plt = _import_plotting()
    subset = [row for row in summary_rows if row["variable"] == variable and row[metric] is not None]
    subset = filter_rows_for_vegetated_plots(subset)
    landuse_codes = sorted({row["landuse_code"] for row in subset})
    scenarios = [sc for sc in SCENARIO_ORDER if any(row["drought_type"] == sc[0] and row["soil_layer"] == sc[1] for row in subset)]
    if not subset or not landuse_codes or not scenarios:
        return

    x = np.arange(len(landuse_codes))
    width = 0.8 / max(len(scenarios), 1)
    fig, ax = plt.subplots(figsize=(max(12, len(landuse_codes) * 0.8), 5))
    colors = ["#b22222", "#ff8c00", "#1f78b4", "#33a02c"]
    for idx, scenario in enumerate(scenarios):
        vals = []
        for code in landuse_codes:
            row = next(
                (
                    r for r in subset
                    if r["landuse_code"] == code and r["drought_type"] == scenario[0] and r["soil_layer"] == scenario[1]
                ),
                None,
            )
            vals.append(np.nan if row is None or row[metric] is None else row[metric])
        ax.bar(x + (idx - (len(scenarios) - 1) / 2) * width, vals, width=width, label=f"{scenario[0]}+{scenario[1]}", color=colors[idx])

    ax.set_xticks(x)
    ax.set_xticklabels([landuse_code_name(code) for code in landuse_codes], rotation=45, ha="right")
    ax.set_title(f"{variable} by land-use type: {metric}")
    ax.set_ylabel(metric)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_png, dpi=220)
    plt.close(fig)


def build_report(summary_rows: Sequence[Dict], pairwise_rows: Sequence[Dict], missing_files: Sequence[str]) -> str:
    available_dataset_count = len({(row["variable"], row["drought_type"], row["soil_layer"]) for row in summary_rows})
    report_summary_rows = filter_rows_for_vegetated_plots(summary_rows)
    if not report_summary_rows:
        report_summary_rows = list(summary_rows)

    report_pairwise_rows = [
        row for row in pairwise_rows if int(row["landuse_code"]) not in EXCLUDED_NONVEGETATED_CODES
    ]
    if not report_pairwise_rows:
        report_pairwise_rows = list(pairwise_rows)

    lines = [
        "# 基于 MODIS 土地利用类型的干旱碳通量分组分析",
        "",
        "## 1. 分析范围",
        f"- 本轮基于 {len(summary_rows)} 条土地利用分组摘要记录。",
        f"- 输入数据为 {available_dataset_count} 个可用 `nc` 文件，对应 GPP / NEE / RECO × flash / nonflash × SMrz / SMs 组合。",
        "- `1982-2000` 事件统一映射到 `2001` 年 MODIS 土地利用类型；`2001-2021` 使用对应年份土地利用图。",
        "- `GPP/RECO` 的不利变化值使用 `drop_abs`，`NEE` 使用 `rise_abs`。",
        "- 图件与下述文本对比结论统一排除 `Water Bodies`、`Snow and Ice`、`Barren or Sparsely Vegetated` 三类非典型植被下垫面。",
        "",
        "## 2. 主体结论",
    ]
    if missing_files:
        lines.append(f"- 当前仍缺失 {len(missing_files)} 个源文件：{'; '.join(missing_files)}")
        lines.append("")

    for variable in VARIABLE_ORDER:
        subset = [row for row in report_summary_rows if row["variable"] == variable]
        if not subset:
            continue
        strongest_change = max(
            [row for row in subset if row["directional_change_abs_mean"] is not None],
            key=lambda row: row["directional_change_abs_mean"],
            default=None,
        )
        slowest_recover = max(
            [row for row in subset if row["t_recover_mean"] is not None],
            key=lambda row: row["t_recover_mean"],
            default=None,
        )
        fastest_response = min(
            [row for row in subset if row["t_response_mean"] is not None],
            key=lambda row: row["t_response_mean"],
            default=None,
        )
        lines.append(f"### 2.{VARIABLE_ORDER.index(variable) + 1} {variable}")
        if strongest_change:
            lines.append(
                f"- 最大不利变化值出现在 `{strongest_change['landuse_name']}` | `{strongest_change['scenario']}`，均值为 {strongest_change['directional_change_abs_mean']}。"
            )
        if fastest_response:
            lines.append(
                f"- 最快响应出现在 `{fastest_response['landuse_name']}` | `{fastest_response['scenario']}`，平均 `t_response={fastest_response['t_response_mean']}`。"
            )
        if slowest_recover:
            lines.append(
                f"- 最慢恢复出现在 `{slowest_recover['landuse_name']}` | `{slowest_recover['scenario']}`，平均 `t_recover={slowest_recover['t_recover_mean']}`。"
            )
        lines.append("")

    lines.extend(["## 3. 差值对比（按土地利用类型）"])
    focus = sorted(
        [row for row in report_pairwise_rows if row["metric"] in {"directional_change_abs_mean", "t_response_mean", "t_impact_mean", "t_recover_mean"}],
        key=lambda row: (-abs(row["delta_right_minus_left"]), row["variable"], row["landuse_code"], row["metric"]),
    )
    for row in focus[:30]:
        lines.append(
            "- "
            f"{row['comparison_type']} | {row['variable']} | {row['landuse_name']} | {row['metric']} | "
            f"{row['left_scenario']}={row['left_value']}, {row['right_scenario']}={row['right_value']}, "
            f"delta={row['delta_right_minus_left']}"
        )

    lines.extend(
        [
            "",
            "## 4. 解释边界",
            "- `1982-2000` 使用 `2001` 年土地利用图代替，适用于“土地利用总体变化不大”的近似分析，不等同于真实逐年地表覆盖历史。",
            "- MODIS `LC_Type1` 当前实际值域为 `0-16`，其中 `0` 视为 `Water Bodies`。",
            "- 为避免非植被下垫面干扰，图件与文本重点比较均排除了 `0`、`15`、`16` 三类地表类型；完整原始统计仍保留在 CSV 中。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PLOT_DIR, exist_ok=True)

    dataset_specs, missing_files = available_landuse_dataset_specs()
    landuse_grids = load_landuse_grids()

    summary_rows, yearly_rows = aggregate_landuse_rows(dataset_specs, landuse_grids)
    pairwise_rows = build_pairwise_rows(summary_rows)

    summary_headers = [
        "variable",
        "drought_type",
        "soil_layer",
        "scenario",
        "landuse_code",
        "landuse_name",
        "event_count",
        "response_rate",
        "directional_change_abs_mean",
        "t_response_mean",
        "t_impact_mean",
        "t_recover_mean",
    ]
    yearly_headers = ["year"] + summary_headers
    pairwise_headers = [
        "comparison_type",
        "variable",
        "soil_layer",
        "landuse_code",
        "landuse_name",
        "metric",
        "left_scenario",
        "right_scenario",
        "left_value",
        "right_value",
        "delta_right_minus_left",
    ]

    write_csv(os.path.join(OUTPUT_DIR, "landuse_summary.csv"), summary_rows, summary_headers)
    write_csv(os.path.join(OUTPUT_DIR, "landuse_yearly_summary.csv"), yearly_rows, yearly_headers)
    write_csv(os.path.join(OUTPUT_DIR, "landuse_pairwise_deltas.csv"), pairwise_rows, pairwise_headers)

    for variable in VARIABLE_ORDER:
        for metric in ("directional_change_abs_mean", "t_response_mean", "t_impact_mean", "t_recover_mean"):
            plot_metric_by_landuse(
                summary_rows,
                variable,
                metric,
                os.path.join(PLOT_DIR, f"{variable.lower()}_{metric}_by_landuse.png"),
            )

    report = build_report(summary_rows, pairwise_rows, missing_files)
    write_text(os.path.join(OUTPUT_DIR, "landuse_analysis_report_CN.md"), report)
    print(f"Wrote land-use analysis outputs to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
