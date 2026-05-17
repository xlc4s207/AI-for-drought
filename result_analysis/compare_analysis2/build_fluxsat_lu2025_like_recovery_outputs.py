#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib import font_manager as fm
from matplotlib import rcParams
import netCDF4 as nc
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
OUT_DIR = (
    f"{BASE_DIR}/process/result_analysis/result_weighted/fluxsat_lu2025_like_recovery"
)
SUMMARY_CSV = os.path.join(OUT_DIR, "fluxsat_lu2025_like_recovery_summary.csv")
SUMMARY_MD = os.path.join(OUT_DIR, "fluxsat_lu2025_like_recovery_summary.md")
ANNUAL_CSV = os.path.join(OUT_DIR, "fluxsat_lu2025_like_recovery_annual_series.csv")
TREND_PNG = os.path.join(OUT_DIR, "fluxsat_lu2025_like_recovery_annual_trend.png")
MAP_OVERVIEW_PNG = os.path.join(
    OUT_DIR, "fluxsat_lu2025_like_recovery_spatial_overview.png"
)
MAP_SLOPE_PNG = os.path.join(
    OUT_DIR, "fluxsat_lu2025_like_recovery_spatial_trend.png"
)


@dataclass(frozen=True)
class ScenarioItem:
    scenario: str
    file_path: str
    color: str
    marker: str


ITEMS: List[ScenarioItem] = [
    ScenarioItem(
        scenario="SMrz",
        file_path=(
            f"{BASE_DIR}/process/fluxsat-draught-analysis/analysis/lu2025_like_recovery/"
            "fluxsat_lu2025_like_recovery_SMrz.nc"
        ),
        color="#1f78b4",
        marker="o",
    ),
    ScenarioItem(
        scenario="SMs",
        file_path=(
            f"{BASE_DIR}/process/fluxsat-draught-analysis/analysis/lu2025_like_recovery/"
            "fluxsat_lu2025_like_recovery_SMs.nc"
        ),
        color="#d95f02",
        marker="s",
    ),
]


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
    if selected is None:
        for fp in [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKSC-Regular.otf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]:
            if os.path.exists(fp):
                try:
                    fm.fontManager.addfont(fp)
                    selected = fm.FontProperties(fname=fp).get_name()
                    break
                except Exception:
                    continue
    rcParams["font.sans-serif"] = [selected, "DejaVu Sans"] if selected else ["DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False


def to_numpy(var) -> np.ndarray:
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        arr = arr.filled(np.nan)
    arr = np.asarray(arr)
    fill_value = getattr(var, "_FillValue", None)
    if fill_value is not None:
        arr = arr.astype(np.float64, copy=False)
        arr[np.isclose(arr, float(fill_value), equal_nan=False)] = np.nan
    return np.asarray(arr)


def latitude_weights(lat: Iterable[float]) -> np.ndarray:
    lat = np.asarray(lat, dtype=np.float64)
    weights = np.cos(np.deg2rad(lat))
    weights[~np.isfinite(weights)] = np.nan
    weights[weights <= 0] = np.nan
    return weights


def area_weighted_mean_grid(grid: np.ndarray, lat: np.ndarray) -> float:
    arr = np.asarray(grid, dtype=np.float64)
    lat2d = np.repeat(np.asarray(lat, dtype=np.float64)[:, None], arr.shape[1], axis=1)
    weights = latitude_weights(lat2d)
    valid = np.isfinite(arr) & np.isfinite(weights)
    if not np.any(valid):
        return math.nan
    return float(np.average(arr[valid], weights=weights[valid]))


def area_weighted_mean_series(cube: np.ndarray, lat: np.ndarray) -> np.ndarray:
    out = np.full(cube.shape[0], np.nan, dtype=np.float64)
    for i in range(cube.shape[0]):
        out[i] = area_weighted_mean_grid(cube[i], lat)
    return out


def compute_slope_days_per_decade(years: np.ndarray, cube: np.ndarray) -> np.ndarray:
    years = np.asarray(years, dtype=np.float64)
    cube = np.asarray(cube, dtype=np.float64)
    valid = np.isfinite(cube)
    count = valid.sum(axis=0)
    n_year = years.size
    years3 = years[:, None, None]
    sum_x = np.sum(np.where(valid, years3, 0.0), axis=0)
    sum_y = np.nansum(np.where(valid, cube, np.nan), axis=0)
    sum_xy = np.nansum(np.where(valid, cube * years3, np.nan), axis=0)
    sum_x2 = np.sum(np.where(valid, years3 * years3, 0.0), axis=0)
    numerator = count * sum_xy - sum_x * sum_y
    denominator = count * sum_x2 - sum_x * sum_x
    slope = np.full(cube.shape[1:], np.nan, dtype=np.float64)
    ok = (count >= 2) & np.isfinite(numerator) & np.isfinite(denominator) & (denominator != 0)
    slope[ok] = numerator[ok] / denominator[ok] * 10.0
    return slope


def nice_percentile_limits(arrays: List[np.ndarray], low: float, high: float) -> Tuple[float, float]:
    merged = np.concatenate([a[np.isfinite(a)] for a in arrays if np.any(np.isfinite(a))])
    if merged.size == 0:
        return (0.0, 1.0)
    vmin, vmax = np.percentile(merged, [low, high])
    if not np.isfinite(vmin) or not np.isfinite(vmax) or math.isclose(vmin, vmax):
        return (float(np.nanmin(merged)), float(np.nanmax(merged) + 1.0))
    return (float(vmin), float(vmax))


def fmt(value: object, decimals: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            return "-"
        return f"{float(value):,.{decimals}f}"
    return str(value)


def load_item(item: ScenarioItem) -> Dict[str, np.ndarray]:
    with nc.Dataset(item.file_path, "r") as ds:
        return {
            "scenario": np.array(item.scenario),
            "year": to_numpy(ds.variables["year"]).astype(np.int32),
            "lat": to_numpy(ds.variables["lat"]).astype(np.float64),
            "lon": to_numpy(ds.variables["lon"]).astype(np.float64),
            "event_total_count": to_numpy(ds.variables["event_total_count"]).astype(np.float64),
            "valid_recovery_event_count": to_numpy(ds.variables["valid_recovery_event_count"]).astype(np.float64),
            "recovery_mean_days": to_numpy(ds.variables["recovery_mean_days"]).astype(np.float64),
            "recovery_median_days": to_numpy(ds.variables["recovery_median_days"]).astype(np.float64),
            "recovery_p25_days": to_numpy(ds.variables["recovery_p25_days"]).astype(np.float64),
            "recovery_p75_days": to_numpy(ds.variables["recovery_p75_days"]).astype(np.float64),
            "annual_valid_recovery_event_count": to_numpy(
                ds.variables["annual_valid_recovery_event_count"]
            ).astype(np.float64),
            "annual_recovery_mean_days": to_numpy(
                ds.variables["annual_recovery_mean_days"]
            ).astype(np.float64),
        }


def build_summary_and_annual_rows(
    item: ScenarioItem, data: Dict[str, np.ndarray]
) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    years = data["year"]
    lat = data["lat"]
    recovery_mean = data["recovery_mean_days"]
    recovery_median = data["recovery_median_days"]
    recovery_p25 = data["recovery_p25_days"]
    recovery_p75 = data["recovery_p75_days"]
    valid_event_count = data["valid_recovery_event_count"]
    event_total_count = data["event_total_count"]
    annual_recovery = data["annual_recovery_mean_days"]
    annual_valid_count = data["annual_valid_recovery_event_count"]

    annual_area_mean = area_weighted_mean_series(annual_recovery, lat)
    annual_total_valid = np.nansum(annual_valid_count, axis=(1, 2))
    annual_rows: List[Dict[str, object]] = []
    for year, mean_days, total_valid in zip(years, annual_area_mean, annual_total_valid):
        annual_rows.append(
            {
                "scenario": item.scenario,
                "year": int(year),
                "global_valid_event_count": int(total_valid) if math.isfinite(total_valid) else 0,
                "global_areaweighted_recovery_mean_days": mean_days,
            }
        )

    valid_pixels = np.isfinite(recovery_mean)
    recovery_slope = compute_slope_days_per_decade(years, annual_recovery)
    summary_row = {
        "scenario": item.scenario,
        "grid_event_total_sum": int(np.nansum(event_total_count)),
        "grid_valid_recovery_sum": int(np.nansum(valid_event_count)),
        "grid_valid_recovery_ratio_pct": (
            float(np.nansum(valid_event_count) * 100.0 / np.nansum(event_total_count))
            if np.nansum(event_total_count) > 0
            else math.nan
        ),
        "valid_pixel_count": int(np.sum(valid_pixels)),
        "recovery_mean_days_areaweighted": area_weighted_mean_grid(recovery_mean, lat),
        "recovery_median_days_areaweighted": area_weighted_mean_grid(recovery_median, lat),
        "recovery_p25_days_areaweighted": area_weighted_mean_grid(recovery_p25, lat),
        "recovery_p75_days_areaweighted": area_weighted_mean_grid(recovery_p75, lat),
        "annual_recovery_trend_days_per_decade": (
            float(np.polyfit(years[np.isfinite(annual_area_mean)], annual_area_mean[np.isfinite(annual_area_mean)], 1)[0] * 10.0)
            if np.sum(np.isfinite(annual_area_mean)) >= 2
            else math.nan
        ),
        "pixel_recovery_slope_median_days_per_decade": float(np.nanmedian(recovery_slope)),
        "file_path": item.file_path,
    }
    return summary_row, annual_rows


def write_csv(path: str, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_md(rows: List[Dict[str, object]]) -> None:
    headers = [
        "情景",
        "总事件数",
        "有效恢复数",
        "有效恢复%",
        "有效像元数",
        "恢复均值(d)",
        "恢复中位(d)",
        "恢复P25(d)",
        "恢复P75(d)",
        "年际趋势(d/10a)",
        "像元趋势中位(d/10a)",
    ]
    lines = [
        "# FluxSat Lu 等 2025 类口径恢复趋势与空间汇总",
        "",
        "> 说明：该目录只读取已经生成好的 `lu2025_like_recovery` nc，不重跑恢复分析。",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario"]),
                    fmt(row["grid_event_total_sum"], 0),
                    fmt(row["grid_valid_recovery_sum"], 0),
                    fmt(row["grid_valid_recovery_ratio_pct"]),
                    fmt(row["valid_pixel_count"], 0),
                    fmt(row["recovery_mean_days_areaweighted"]),
                    fmt(row["recovery_median_days_areaweighted"]),
                    fmt(row["recovery_p25_days_areaweighted"]),
                    fmt(row["recovery_p75_days_areaweighted"]),
                    fmt(row["annual_recovery_trend_days_per_decade"]),
                    fmt(row["pixel_recovery_slope_median_days_per_decade"]),
                ]
            )
            + " |"
        )
    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def add_trend_line(ax: plt.Axes, years: np.ndarray, values: np.ndarray, color: str) -> None:
    valid = np.isfinite(years) & np.isfinite(values)
    if np.sum(valid) < 2:
        return
    slope, intercept = np.polyfit(years[valid], values[valid], 1)
    ax.plot(years[valid], intercept + slope * years[valid], linestyle="--", linewidth=1.4, color=color, alpha=0.9)


def plot_annual_trend(items: List[ScenarioItem], annual_rows: List[Dict[str, object]]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, constrained_layout=True)
    for item in items:
        rows = [r for r in annual_rows if r["scenario"] == item.scenario]
        rows.sort(key=lambda r: r["year"])
        years = np.array([r["year"] for r in rows], dtype=np.float64)
        mean_days = np.array(
            [r["global_areaweighted_recovery_mean_days"] for r in rows], dtype=np.float64
        )
        valid_count = np.array([r["global_valid_event_count"] for r in rows], dtype=np.float64)

        axes[0].plot(
            years,
            mean_days,
            color=item.color,
            marker=item.marker,
            linewidth=2.0,
            markersize=4.2,
            label=item.scenario,
        )
        axes[1].plot(
            years,
            valid_count,
            color=item.color,
            marker=item.marker,
            linewidth=2.0,
            markersize=4.2,
            label=item.scenario,
        )
        add_trend_line(axes[0], years, mean_days, item.color)
        add_trend_line(axes[1], years, valid_count, item.color)

    axes[0].set_title("FluxSat 恢复时间年际变化")
    axes[0].set_ylabel("面积加权恢复均值 (天)")
    axes[1].set_title("FluxSat 有效恢复事件数年际变化")
    axes[1].set_ylabel("有效恢复事件数")
    axes[1].set_xlabel("Year")
    for ax in axes:
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
        ax.legend(frameon=False, loc="best")
    fig.savefig(TREND_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)


def draw_grid(
    ax: plt.Axes,
    lon: np.ndarray,
    lat: np.ndarray,
    grid: np.ndarray,
    title: str,
    cmap: str,
    vmin: float,
    vmax: float,
    norm: colors.Normalize | None = None,
) -> None:
    extent = [float(np.nanmin(lon)), float(np.nanmax(lon)), float(np.nanmin(lat)), float(np.nanmax(lat))]
    image = ax.imshow(
        grid,
        origin="lower",
        extent=extent,
        cmap=cmap,
        vmin=None if norm is not None else vmin,
        vmax=None if norm is not None else vmax,
        norm=norm,
        aspect="auto",
    )
    ax.set_title(title)
    ax.set_xlabel("Lon")
    ax.set_ylabel("Lat")
    return image


def plot_spatial_overview(items: List[ScenarioItem], loaded: Dict[str, Dict[str, np.ndarray]]) -> None:
    mean_arrays = [loaded[item.scenario]["recovery_mean_days"] for item in items]
    count_arrays = [loaded[item.scenario]["valid_recovery_event_count"] for item in items]
    mean_vmin, mean_vmax = nice_percentile_limits(mean_arrays, 2, 98)
    count_vmin, count_vmax = nice_percentile_limits(count_arrays, 5, 98)

    fig, axes = plt.subplots(2, 2, figsize=(14, 7.8), constrained_layout=True)
    for col, item in enumerate(items):
        data = loaded[item.scenario]
        im0 = draw_grid(
            axes[0, col],
            data["lon"],
            data["lat"],
            data["recovery_mean_days"],
            f"{item.scenario} 恢复时间均值",
            "YlGnBu",
            mean_vmin,
            mean_vmax,
        )
        im1 = draw_grid(
            axes[1, col],
            data["lon"],
            data["lat"],
            data["valid_recovery_event_count"],
            f"{item.scenario} 有效恢复事件数",
            "YlOrRd",
            count_vmin,
            count_vmax,
        )
    cbar0 = fig.colorbar(im0, ax=axes[0, :], shrink=0.95, pad=0.02)
    cbar0.set_label("天")
    cbar1 = fig.colorbar(im1, ax=axes[1, :], shrink=0.95, pad=0.02)
    cbar1.set_label("事件数")
    fig.savefig(MAP_OVERVIEW_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_spatial_trend(items: List[ScenarioItem], loaded: Dict[str, Dict[str, np.ndarray]]) -> None:
    slopes = []
    slope_by_scenario: Dict[str, np.ndarray] = {}
    for item in items:
        data = loaded[item.scenario]
        slope = compute_slope_days_per_decade(data["year"], data["annual_recovery_mean_days"])
        slope_by_scenario[item.scenario] = slope
        slopes.append(slope)
    slope_vmin, slope_vmax = nice_percentile_limits(slopes, 2, 98)
    vmax = max(abs(slope_vmin), abs(slope_vmax))
    norm = colors.TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)

    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8), constrained_layout=True)
    for idx, item in enumerate(items):
        data = loaded[item.scenario]
        image = draw_grid(
            axes[idx],
            data["lon"],
            data["lat"],
            slope_by_scenario[item.scenario],
            f"{item.scenario} 恢复时间趋势",
            "RdBu_r",
            -vmax,
            vmax,
            norm=norm,
        )
    cbar = fig.colorbar(image, ax=axes[:], shrink=0.92, pad=0.02)
    cbar.set_label("d/10a")
    fig.savefig(MAP_SLOPE_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    setup_chinese_font()

    loaded: Dict[str, Dict[str, np.ndarray]] = {}
    summary_rows: List[Dict[str, object]] = []
    annual_rows: List[Dict[str, object]] = []
    for item in ITEMS:
        data = load_item(item)
        loaded[item.scenario] = data
        summary_row, item_annual_rows = build_summary_and_annual_rows(item, data)
        summary_rows.append(summary_row)
        annual_rows.extend(item_annual_rows)

    summary_rows.sort(key=lambda row: row["scenario"])
    annual_rows.sort(key=lambda row: (row["scenario"], row["year"]))

    write_csv(
        SUMMARY_CSV,
        summary_rows,
        [
            "scenario",
            "grid_event_total_sum",
            "grid_valid_recovery_sum",
            "grid_valid_recovery_ratio_pct",
            "valid_pixel_count",
            "recovery_mean_days_areaweighted",
            "recovery_median_days_areaweighted",
            "recovery_p25_days_areaweighted",
            "recovery_p75_days_areaweighted",
            "annual_recovery_trend_days_per_decade",
            "pixel_recovery_slope_median_days_per_decade",
            "file_path",
        ],
    )
    write_csv(
        ANNUAL_CSV,
        annual_rows,
        [
            "scenario",
            "year",
            "global_valid_event_count",
            "global_areaweighted_recovery_mean_days",
        ],
    )
    write_summary_md(summary_rows)
    plot_annual_trend(ITEMS, annual_rows)
    plot_spatial_overview(ITEMS, loaded)
    plot_spatial_trend(ITEMS, loaded)

    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {SUMMARY_MD}")
    print(f"Wrote {ANNUAL_CSV}")
    print(f"Wrote {TREND_PNG}")
    print(f"Wrote {MAP_OVERVIEW_PNG}")
    print(f"Wrote {MAP_SLOPE_PNG}")


if __name__ == "__main__":
    main()
