#!/usr/bin/env python3

import math
import os
from typing import Dict, List, Optional, Sequence, Tuple

import netCDF4 as nc
import numpy as np

from compare_with_abs_nc import (
    _read_chunk,
    load_dataset_specs,
    metric_field_lookup,
    select_year_field,
    write_csv,
    write_text,
)


BASE_DIR = "/home/xulc/flash_drought"
OUTPUT_DIR = os.path.join(BASE_DIR, "process", "result_analysis", "compare_analysis")
FIGURE_DIR = os.path.join(OUTPUT_DIR, "annual_trend_figures")
YEAR_START = 1982
YEAR_END = 2021
YEARS = np.arange(YEAR_START, YEAR_END + 1, dtype=np.int32)
N_YEARS = int(YEARS.size)
CHUNK_SIZE = 1_000_000
SCENARIO_ORDER = [
    ("flash", "SMrz"),
    ("flash", "SMs"),
    ("nonflash", "SMrz"),
    ("nonflash", "SMs"),
]
VARIABLE_ORDER = ["GPP", "NEE", "RECO"]
METRIC_ORDER = [
    "directional_change_abs_mean",
    "relative_change_mean",
    "t_response_mean",
    "t_impact_mean",
    "t_recover_mean",
]


def directional_change_metric(variable: str) -> str:
    return "rise_abs" if str(variable).upper() == "NEE" else "drop_abs"


def directional_change_note(variable: str) -> str:
    if str(variable).upper() == "NEE":
        return "NEE uses rise_abs because drought-driven increases indicate sink weakening or source strengthening."
    return "GPP/RECO use drop_abs because drought-driven decreases indicate stronger stress."


def compute_relative_change(change_abs: np.ndarray, baseline_abs: np.ndarray) -> np.ndarray:
    change_abs = np.asarray(change_abs, dtype=np.float64)
    baseline_abs = np.asarray(baseline_abs, dtype=np.float64)
    out = np.full(change_abs.shape, np.nan, dtype=np.float64)
    valid = np.isfinite(change_abs) & np.isfinite(baseline_abs) & (np.abs(baseline_abs) > 1e-12)
    out[valid] = change_abs[valid] / np.abs(baseline_abs[valid])
    return out


def aggregate_year_metric(years: np.ndarray, values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    years = np.asarray(years, dtype=np.int32)
    values = np.asarray(values, dtype=np.float64)
    valid = (years >= YEAR_START) & (years <= YEAR_END) & np.isfinite(values)
    sums = np.zeros(N_YEARS, dtype=np.float64)
    counts = np.zeros(N_YEARS, dtype=np.float64)
    if not np.any(valid):
        return sums, counts
    year_idx = years[valid] - YEAR_START
    sums += np.bincount(year_idx, weights=values[valid], minlength=N_YEARS)
    counts += np.bincount(year_idx, minlength=N_YEARS)
    return sums, counts


def fit_linear_trend(years: np.ndarray, values: np.ndarray) -> Dict[str, Optional[float]]:
    years = np.asarray(years, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(years) & np.isfinite(values)
    out = {
        "valid_year_count": int(np.count_nonzero(valid)),
        "slope_per_year": None,
        "intercept": None,
        "start_value": None,
        "end_value": None,
        "delta_end_start": None,
    }
    if np.count_nonzero(valid) < 2:
        return out
    slope, intercept = np.polyfit(years[valid], values[valid], 1)
    out["slope_per_year"] = float(slope)
    out["intercept"] = float(intercept)

    valid_years = years[valid]
    valid_values = values[valid]
    out["start_value"] = float(valid_values[0])
    out["end_value"] = float(valid_values[-1])
    if out["start_value"] is not None and out["end_value"] is not None:
        out["delta_end_start"] = float(out["end_value"] - out["start_value"])
    return out


def _scenario_label(drought_type: str, soil_layer: str) -> str:
    return f"{drought_type}+{soil_layer}"


def _metric_mean(sum_arr: np.ndarray, count_arr: np.ndarray) -> np.ndarray:
    out = np.full(sum_arr.shape, np.nan, dtype=np.float64)
    valid = count_arr > 0
    out[valid] = sum_arr[valid] / count_arr[valid]
    return out


def _round(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if not math.isfinite(float(value)):
        return None
    return round(float(value), 6)


def summarize_dataset_by_year(spec) -> List[Dict]:
    with nc.Dataset(spec.path, "r") as ds:
        n_events = len(ds.dimensions["event"])
        year_field = select_year_field(tuple(ds.variables.keys()))
        lookup = metric_field_lookup(ds, spec.variable)
        change_metric = directional_change_metric(spec.variable)
        required = {
            "baseline_abs": lookup["baseline_abs"],
            change_metric: lookup[change_metric],
            "t_response": lookup["t_response"],
            "t_impact": lookup["t_impact"],
            "t_recover": lookup["t_recover"],
        }

        event_count = np.zeros(N_YEARS, dtype=np.float64)
        metric_sums = {name: np.zeros(N_YEARS, dtype=np.float64) for name in METRIC_ORDER}
        metric_counts = {name: np.zeros(N_YEARS, dtype=np.float64) for name in METRIC_ORDER}

        for start in range(0, n_events, CHUNK_SIZE):
            end = min(start + CHUNK_SIZE, n_events)
            years = _read_chunk(ds, year_field, start, end).astype(np.int32, copy=False)
            in_range = (years >= YEAR_START) & (years <= YEAR_END)
            if not np.any(in_range):
                continue

            year_idx = years[in_range] - YEAR_START
            event_count += np.bincount(year_idx, minlength=N_YEARS)

            change_abs = _read_chunk(ds, required[change_metric], start, end)
            baseline_abs = _read_chunk(ds, required["baseline_abs"], start, end)
            relative_change = compute_relative_change(change_abs, baseline_abs)
            t_response = _read_chunk(ds, required["t_response"], start, end)
            t_impact = _read_chunk(ds, required["t_impact"], start, end)
            t_recover = _read_chunk(ds, required["t_recover"], start, end)

            for metric_name, values in (
                ("directional_change_abs_mean", change_abs),
                ("relative_change_mean", relative_change),
                ("t_response_mean", t_response),
                ("t_impact_mean", t_impact),
                ("t_recover_mean", t_recover),
            ):
                sums, counts = aggregate_year_metric(years, values)
                metric_sums[metric_name] += sums
                metric_counts[metric_name] += counts

    rows: List[Dict] = []
    for idx, year in enumerate(YEARS):
        row = {
            "dataset_id": spec.dataset_id,
            "variable": spec.variable,
            "drought_type": spec.drought_type,
            "soil_layer": spec.soil_layer,
            "scenario": _scenario_label(spec.drought_type, spec.soil_layer),
            "year": int(year),
            "event_count": int(event_count[idx]),
            "directional_change_metric": directional_change_metric(spec.variable),
            "directional_change_note": directional_change_note(spec.variable),
        }
        for metric_name in METRIC_ORDER:
            mean_values = _metric_mean(metric_sums[metric_name], metric_counts[metric_name])
            row[metric_name] = _round(mean_values[idx])
        rows.append(row)
    return rows


def build_annual_rows(dataset_specs: Sequence) -> List[Dict]:
    rows: List[Dict] = []
    for spec in dataset_specs:
        rows.extend(summarize_dataset_by_year(spec))
    rows.sort(key=lambda row: (VARIABLE_ORDER.index(row["variable"]), SCENARIO_ORDER.index((row["drought_type"], row["soil_layer"])), row["year"]))
    return rows


def build_trend_rows(annual_rows: Sequence[Dict]) -> List[Dict]:
    rows: List[Dict] = []
    dataset_ids = sorted({row["dataset_id"] for row in annual_rows})
    for dataset_id in dataset_ids:
        subset = [row for row in annual_rows if row["dataset_id"] == dataset_id]
        meta = subset[0]
        years = np.array([row["year"] for row in subset], dtype=np.int32)
        for metric_name in METRIC_ORDER:
            values = np.array(
                [np.nan if row[metric_name] is None else float(row[metric_name]) for row in subset],
                dtype=np.float64,
            )
            trend = fit_linear_trend(years, values)
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "variable": meta["variable"],
                    "drought_type": meta["drought_type"],
                    "soil_layer": meta["soil_layer"],
                    "scenario": meta["scenario"],
                    "metric": metric_name,
                    "valid_year_count": trend["valid_year_count"],
                    "slope_per_year": _round(trend["slope_per_year"]),
                    "intercept": _round(trend["intercept"]),
                    "start_value_1982": _round(trend["start_value"]),
                    "end_value_2021": _round(trend["end_value"]),
                    "delta_2021_minus_1982": _round(trend["delta_end_start"]),
                }
            )
    return rows


def build_overview_rows(annual_rows: Sequence[Dict]) -> List[Dict]:
    rows: List[Dict] = []
    dataset_ids = sorted({row["dataset_id"] for row in annual_rows})
    for dataset_id in dataset_ids:
        subset = [row for row in annual_rows if row["dataset_id"] == dataset_id]
        meta = subset[0]
        row = {
            "dataset_id": dataset_id,
            "variable": meta["variable"],
            "drought_type": meta["drought_type"],
            "soil_layer": meta["soil_layer"],
            "scenario": meta["scenario"],
            "directional_change_metric": meta["directional_change_metric"],
        }
        row["mean_event_count_per_year"] = _round(np.mean([r["event_count"] for r in subset]))
        for metric_name in METRIC_ORDER:
            values = np.array(
                [np.nan if r[metric_name] is None else float(r[metric_name]) for r in subset],
                dtype=np.float64,
            )
            row[f"{metric_name}_avg_1982_2021"] = _round(np.nanmean(values)) if np.any(np.isfinite(values)) else None
        rows.append(row)
    return rows


def _import_plotting():
    import matplotlib.pyplot as plt

    return plt


def plot_metric_trends(annual_rows: Sequence[Dict], metric_name: str, y_label: str, title: str, out_png: str) -> None:
    plt = _import_plotting()
    colors = {
        ("flash", "SMrz"): "#b22222",
        ("flash", "SMs"): "#ff8c00",
        ("nonflash", "SMrz"): "#1f78b4",
        ("nonflash", "SMs"): "#33a02c",
    }
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharex=True)
    for ax, variable in zip(axes, VARIABLE_ORDER):
        subset_var = [row for row in annual_rows if row["variable"] == variable]
        for drought_type, soil_layer in SCENARIO_ORDER:
            subset = [
                row for row in subset_var
                if row["drought_type"] == drought_type and row["soil_layer"] == soil_layer and row[metric_name] is not None
            ]
            subset.sort(key=lambda row: row["year"])
            if not subset:
                continue
            ax.plot(
                [row["year"] for row in subset],
                [row[metric_name] for row in subset],
                label=_scenario_label(drought_type, soil_layer),
                color=colors[(drought_type, soil_layer)],
                linewidth=1.6,
            )
        ax.set_title(variable)
        ax.set_xlabel("Year")
        ax.grid(alpha=0.25, linewidth=0.5)
    axes[0].set_ylabel(y_label)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.04), frameon=False)
    fig.suptitle(title, y=1.08, fontsize=14)
    fig.tight_layout()
    fig.savefig(out_png, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _lookup_rows_by_series(rows: Sequence[Dict], metric_name: str) -> Dict[Tuple[str, str, str], Dict]:
    return {
        (row["variable"], row["drought_type"], row["soil_layer"]): row
        for row in rows
        if row.get("metric", metric_name) == metric_name or metric_name.startswith("directional_change")
    }


def build_report(overview_rows: Sequence[Dict], trend_rows: Sequence[Dict]) -> str:
    overview_lookup = {(row["variable"], row["drought_type"], row["soil_layer"]): row for row in overview_rows}
    trend_lookup = {(row["dataset_id"], row["metric"]): row for row in trend_rows}

    lines = [
        "# 1982-2021 年四种干旱情景下 GPP、NEE、RECO 年际对比分析",
        "",
        "## 1. 口径说明",
        "- 时间范围固定为 1982-2021。",
        "- `GPP` 与 `RECO` 的干旱不利变化值使用 `drop_abs`。",
        "- `NEE` 的干旱不利变化值使用 `rise_abs`，因为 `NEE<0` 表示碳汇，干旱后数值上升通常代表碳汇减弱或向碳源方向移动。",
        "- 相对变化幅度统一定义为 `directional_change_abs / abs(baseline_abs)`，用于保证三类通量在符号含义上的可比性。",
        "",
        "## 2. 分变量对比",
    ]

    for variable in VARIABLE_ORDER:
        lines.append(f"### 2.{VARIABLE_ORDER.index(variable) + 1} {variable}")
        for drought_type, soil_layer in SCENARIO_ORDER:
            key = (variable, drought_type, soil_layer)
            overview = overview_lookup[key]
            dataset_id = overview["dataset_id"]
            change_trend = trend_lookup[(dataset_id, "directional_change_abs_mean")]
            relative_trend = trend_lookup[(dataset_id, "relative_change_mean")]
            response_trend = trend_lookup[(dataset_id, "t_response_mean")]
            impact_trend = trend_lookup[(dataset_id, "t_impact_mean")]
            recover_trend = trend_lookup[(dataset_id, "t_recover_mean")]
            lines.append(
                "- "
                f"{overview['scenario']}: "
                f"绝对变化均值={overview['directional_change_abs_mean_avg_1982_2021']}, "
                f"相对变化均值={overview['relative_change_mean_avg_1982_2021']}, "
                f"t_response={overview['t_response_mean_avg_1982_2021']}, "
                f"t_impact={overview['t_impact_mean_avg_1982_2021']}, "
                f"t_recover={overview['t_recover_mean_avg_1982_2021']}; "
                f"绝对变化斜率={change_trend['slope_per_year']}, "
                f"相对变化斜率={relative_trend['slope_per_year']}, "
                f"响应时间斜率={response_trend['slope_per_year']}, "
                f"影响时间斜率={impact_trend['slope_per_year']}, "
                f"恢复时间斜率={recover_trend['slope_per_year']}."
            )
        lines.append("")

    lines.extend(
        [
            "## 3. 总体判断",
            "- 若 `flash` 系列在同一变量下的绝对变化均值高于 `nonflash`，说明骤旱的瞬时冲击更强。",
            "- 若 `nonflash` 系列的 `t_response` 或 `t_impact` 更长，说明慢旱具有更显著的累积拖尾效应。",
            "- 若 `t_recover` 上升，说明后干旱恢复过程在变长；若下降，则说明平均恢复过程在缩短。",
            "- `NEE` 结果必须结合“负值为碳汇”来解释，因此图表中的上升不代表系统改善，而通常代表净碳汇能力减弱。",
            "",
            "## 4. 输出文件",
            "- `annual_drought_metric_summary_1982_2021.csv`：逐年统计表",
            "- `annual_drought_metric_trend_stats_1982_2021.csv`：趋势统计表",
            "- `annual_drought_metric_overview_1982_2021.csv`：1982-2021 年平均概览",
            "- `annual_trend_figures/*.png`：年际趋势图",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FIGURE_DIR, exist_ok=True)

    dataset_specs = load_dataset_specs()
    annual_rows = build_annual_rows(dataset_specs)
    trend_rows = build_trend_rows(annual_rows)
    overview_rows = build_overview_rows(annual_rows)

    annual_headers = [
        "dataset_id",
        "variable",
        "drought_type",
        "soil_layer",
        "scenario",
        "year",
        "event_count",
        "directional_change_metric",
        "directional_change_note",
        "directional_change_abs_mean",
        "relative_change_mean",
        "t_response_mean",
        "t_impact_mean",
        "t_recover_mean",
    ]
    write_csv(
        os.path.join(OUTPUT_DIR, "annual_drought_metric_summary_1982_2021.csv"),
        annual_rows,
        annual_headers,
    )

    trend_headers = [
        "dataset_id",
        "variable",
        "drought_type",
        "soil_layer",
        "scenario",
        "metric",
        "valid_year_count",
        "slope_per_year",
        "intercept",
        "start_value_1982",
        "end_value_2021",
        "delta_2021_minus_1982",
    ]
    write_csv(
        os.path.join(OUTPUT_DIR, "annual_drought_metric_trend_stats_1982_2021.csv"),
        trend_rows,
        trend_headers,
    )

    overview_headers = [
        "dataset_id",
        "variable",
        "drought_type",
        "soil_layer",
        "scenario",
        "directional_change_metric",
        "mean_event_count_per_year",
        "directional_change_abs_mean_avg_1982_2021",
        "relative_change_mean_avg_1982_2021",
        "t_response_mean_avg_1982_2021",
        "t_impact_mean_avg_1982_2021",
        "t_recover_mean_avg_1982_2021",
    ]
    write_csv(
        os.path.join(OUTPUT_DIR, "annual_drought_metric_overview_1982_2021.csv"),
        overview_rows,
        overview_headers,
    )

    plot_metric_trends(
        annual_rows,
        "directional_change_abs_mean",
        "Directional change (absolute)",
        "1982-2021 annual drought-driven absolute change",
        os.path.join(FIGURE_DIR, "annual_directional_change_trend_1982_2021.png"),
    )
    plot_metric_trends(
        annual_rows,
        "relative_change_mean",
        "Directional change / |baseline|",
        "1982-2021 annual relative drought impact",
        os.path.join(FIGURE_DIR, "annual_relative_change_trend_1982_2021.png"),
    )
    plot_metric_trends(
        annual_rows,
        "t_response_mean",
        "Days",
        "1982-2021 annual t_response",
        os.path.join(FIGURE_DIR, "annual_t_response_trend_1982_2021.png"),
    )
    plot_metric_trends(
        annual_rows,
        "t_impact_mean",
        "Days",
        "1982-2021 annual t_impact",
        os.path.join(FIGURE_DIR, "annual_t_impact_trend_1982_2021.png"),
    )
    plot_metric_trends(
        annual_rows,
        "t_recover_mean",
        "Days",
        "1982-2021 annual t_recover",
        os.path.join(FIGURE_DIR, "annual_t_recover_trend_1982_2021.png"),
    )

    report = build_report(overview_rows, trend_rows)
    write_text(
        os.path.join(OUTPUT_DIR, "annual_drought_metric_report_CN_1982_2021.md"),
        report,
    )
    print(f"Wrote annual drought metric outputs to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
