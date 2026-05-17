#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from typing import Dict, List

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import rcParams
import numpy as np
import pandas as pd
import rasterio

BASE_DIR = "/home/xulc/flash_drought/process/response_analysis"
OUT_DIR = os.path.join(BASE_DIR, "summary")
os.makedirs(OUT_DIR, exist_ok=True)

VARIABLES = ["GPP", "RECO", "NEE"]
SCENARIOS = ["SMs_flash", "SMrz_flash", "SMs_nonflash", "SMrz_nonflash"]

METRICS = [
    "min",
    "mean",
    "trend",
    "t_min",
    "t_response",
    "t_impact",
    "amp_max",
    "t_recover",
    "recovery_rate",
]


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
        # 尝试从常见路径动态注册
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

    if selected is not None:
        rcParams["font.sans-serif"] = [selected, "DejaVu Sans"]
    else:
        rcParams["font.sans-serif"] = ["DejaVu Sans"]

    rcParams["axes.unicode_minus"] = False
    return selected if selected is not None else "DejaVu Sans"


def metric_to_filename(variable: str, metric: str) -> str:
    v = variable.lower()
    if metric in ["min", "mean", "trend"]:
        return f"{v}_{metric}.tif"
    return f"{metric}.tif"


def tif_path(variable: str, scenario: str, metric: str) -> str:
    return os.path.join(
        BASE_DIR,
        variable,
        f"{variable}_total_analysis",
        f"{variable}_{scenario}",
        metric_to_filename(variable, metric),
    )


def read_vals(path: str, metric: str) -> np.ndarray:
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float64)

    valid = np.isfinite(data)
    valid &= (np.abs(data) < 1e6)

    if metric in ["t_min", "t_response", "t_impact", "t_recover"]:
        valid &= (data >= 0)

    data = data[valid]
    return data


def calc_stats(vals: np.ndarray) -> Dict[str, float]:
    if vals.size == 0:
        return {
            "n_valid": 0,
            "mean": np.nan,
            "std": np.nan,
            "median": np.nan,
            "p10": np.nan,
            "p25": np.nan,
            "p75": np.nan,
            "p90": np.nan,
            "min": np.nan,
            "max": np.nan,
            "positive_ratio": np.nan,
            "negative_ratio": np.nan,
        }
    return {
        "n_valid": int(vals.size),
        "mean": float(np.nanmean(vals)),
        "std": float(np.nanstd(vals)),
        "median": float(np.nanmedian(vals)),
        "p10": float(np.nanpercentile(vals, 10)),
        "p25": float(np.nanpercentile(vals, 25)),
        "p75": float(np.nanpercentile(vals, 75)),
        "p90": float(np.nanpercentile(vals, 90)),
        "min": float(np.nanmin(vals)),
        "max": float(np.nanmax(vals)),
        "positive_ratio": float(np.mean(vals > 0)),
        "negative_ratio": float(np.mean(vals < 0)),
    }


def build_stats_table() -> pd.DataFrame:
    rows: List[Dict] = []
    for var in VARIABLES:
        for scen in SCENARIOS:
            for metric in METRICS:
                path = tif_path(var, scen, metric)
                vals = read_vals(path, metric)
                row = {
                    "variable": var,
                    "scenario": scen,
                    "metric": metric,
                    "file": path,
                }
                row.update(calc_stats(vals))
                rows.append(row)
    return pd.DataFrame(rows)


def scenario_chinese(s: str) -> str:
    mapping = {
        "SMs_flash": "SMs-骤旱",
        "SMrz_flash": "SMrz-骤旱",
        "SMs_nonflash": "SMs-非骤旱",
        "SMrz_nonflash": "SMrz-非骤旱",
    }
    return mapping.get(s, s)


def plot_group_bars(df: pd.DataFrame, metric: str, ylabel: str, out_name: str) -> None:
    plot_df = df[df["metric"] == metric].copy()
    pivot = plot_df.pivot(index="scenario", columns="variable", values="mean").reindex(SCENARIOS)

    x = np.arange(len(SCENARIOS))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 6), dpi=600)
    for i, var in enumerate(VARIABLES):
        vals = pivot[var].values
        ax.bar(x + (i - 1) * width, vals, width=width, label=var)

    ax.set_xticks(x)
    ax.set_xticklabels([scenario_chinese(s) for s in SCENARIOS], rotation=20)
    ax.set_ylabel(ylabel)
    ax.set_title(f"{metric} 均值对比")
    ax.legend()
    ax.grid(alpha=0.25, axis="y")

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, out_name), dpi=600)
    plt.close(fig)


def plot_heatmap(df: pd.DataFrame, out_name: str) -> None:
    temp = df.copy()
    temp["row"] = temp["variable"] + "|" + temp["scenario"]
    mat = temp.pivot(index="row", columns="metric", values="mean")

    arr = mat.values.astype(np.float64)
    arr_show = arr.copy()
    for j in range(arr.shape[1]):
        col = arr[:, j]
        m = np.nanmean(col)
        s = np.nanstd(col)
        if not np.isfinite(s) or s == 0:
            s = 1.0
        arr_show[:, j] = (col - m) / s

    fig, ax = plt.subplots(figsize=(14, 8), dpi=600)
    im = ax.imshow(arr_show, aspect="auto", cmap="RdBu_r", vmin=-2.5, vmax=2.5)
    ax.set_xticks(np.arange(mat.shape[1]))
    ax.set_xticklabels(mat.columns.tolist(), rotation=35, ha="right")
    ax.set_yticks(np.arange(mat.shape[0]))
    ax.set_yticklabels(mat.index.tolist())
    ax.set_title("指标均值标准化热力图（Z-score）")

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("标准化值")

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, out_name), dpi=600)
    plt.close(fig)


def plot_flash_nonflash_delta(df: pd.DataFrame, out_name: str) -> pd.DataFrame:
    rows = []
    for var in VARIABLES:
        for layer in ["SMs", "SMrz"]:
            for metric in METRICS:
                flash_s = f"{layer}_flash"
                nonflash_s = f"{layer}_nonflash"
                flash_val = df[(df.variable == var) & (df.scenario == flash_s) & (df.metric == metric)]["mean"].iloc[0]
                nonflash_val = df[(df.variable == var) & (df.scenario == nonflash_s) & (df.metric == metric)]["mean"].iloc[0]
                rows.append({
                    "variable": var,
                    "layer": layer,
                    "metric": metric,
                    "flash_mean": flash_val,
                    "nonflash_mean": nonflash_val,
                    "delta_nonflash_minus_flash": nonflash_val - flash_val,
                })

    ddf = pd.DataFrame(rows)
    ddf.to_csv(os.path.join(OUT_DIR, "flash_nonflash_delta.csv"), index=False, encoding="utf-8-sig")

    for layer in ["SMs", "SMrz"]:
        sub = ddf[ddf.layer == layer].copy()
        mat = sub.pivot(index="variable", columns="metric", values="delta_nonflash_minus_flash").reindex(VARIABLES)

        fig, ax = plt.subplots(figsize=(14, 3.8), dpi=600)
        vmax = np.nanpercentile(np.abs(mat.values), 95)
        vmax = max(vmax, 1e-6)
        im = ax.imshow(mat.values, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
        ax.set_xticks(np.arange(len(mat.columns)))
        ax.set_xticklabels(mat.columns, rotation=35, ha="right")
        ax.set_yticks(np.arange(len(mat.index)))
        ax.set_yticklabels(mat.index)
        ax.set_title(f"{layer}: 非骤旱 - 骤旱（均值差）")
        cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
        cbar.set_label("差值")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT_DIR, f"delta_heatmap_{layer}.png"), dpi=600)
        plt.close(fig)

    return ddf


def write_md(df: pd.DataFrame, ddf: pd.DataFrame) -> None:
    lines = []
    lines.append("# GPP / NEE / RECO 响应统计分析报告")
    lines.append("")
    lines.append("## 数据来源")
    lines.append("- 输入路径：`process/response_analysis/GPP`、`process/response_analysis/NEE`、`process/response_analysis/RECO`")
    lines.append("- 统计对象：12组场景（3变量 × 4情景），每组9个指标栅格")
    lines.append("")

    lines.append("## 数理统计方法")
    lines.append("- 对每个tif的有效像元进行描述统计：均值、标准差、中位数、P10/P25/P75/P90、最小值、最大值、正负值占比。")
    lines.append("- 比较维度：")
    lines.append("  - 同变量不同情景（SMs/SMrz × 骤旱/非骤旱）")
    lines.append("  - 同土层下非骤旱与骤旱差值（nonflash - flash）")
    lines.append("")

    lines.append("## 关键发现（基于均值）")
    key_metrics = ["amp_max", "t_response", "t_recover", "recovery_rate", "min", "mean", "trend"]
    for layer in ["SMs", "SMrz"]:
        lines.append(f"### {layer} 土层")
        for var in VARIABLES:
            lines.append(f"- {var}:")
            for m in key_metrics:
                sub = ddf[(ddf.variable == var) & (ddf.layer == layer) & (ddf.metric == m)]
                if len(sub) == 0:
                    continue
                row = sub.iloc[0]
                lines.append(
                    f"  - {m}: flash={row['flash_mean']:.4f}, nonflash={row['nonflash_mean']:.4f}, Δ={row['delta_nonflash_minus_flash']:+.4f}"
                )
        lines.append("")

    lines.append("## 响应解释（GPP / NEE / RECO）")
    lines.append("- GPP：反映植被同化能力变化；`gpp_min/gpp_mean/gpp_trend` 与 `amp_max`、`t_response`、`t_recover` 联合刻画冲击深度与恢复节律。")
    lines.append("- NEE：反映净生态系统交换变化；NEE 的响应方向需结合符号约定解读，建议重点比较同一指标在骤旱与非骤旱之间的差值。")
    lines.append("- RECO：反映生态系统呼吸过程变化；通过 `reco_*` 与时间指标可识别呼吸系统受扰动及恢复过程。")
    lines.append("- 土层差异：SMs 通常体现更快的表层响应，SMrz 更能反映持续性水分亏缺影响。")
    lines.append("- 干旱类型差异：`delta_nonflash_minus_flash` 热图展示非骤旱相对骤旱的均值偏移方向与幅度。")
    lines.append("")

    lines.append("## 输出文件")
    lines.append("- `response_statistics_summary.csv`：完整统计总表")
    lines.append("- `flash_nonflash_delta.csv`：同土层下非骤旱-骤旱差值表")
    lines.append("- `bar_amp_max_mean.png`、`bar_t_response_mean.png`、`bar_recovery_rate_mean.png`")
    lines.append("- `heatmap_mean_zscore.png`、`delta_heatmap_SMs.png`、`delta_heatmap_SMrz.png`")

    with open(os.path.join(OUT_DIR, "response_statistics_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    font_used = setup_chinese_font()
    print("中文绘图字体:", font_used)

    df = build_stats_table()
    out_csv = os.path.join(OUT_DIR, "response_statistics_summary.csv")
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    plot_group_bars(df, "amp_max", "amp_max mean", "bar_amp_max_mean.png")
    plot_group_bars(df, "t_response", "t_response mean", "bar_t_response_mean.png")
    plot_group_bars(df, "recovery_rate", "recovery_rate mean", "bar_recovery_rate_mean.png")
    plot_heatmap(df, "heatmap_mean_zscore.png")

    ddf = plot_flash_nonflash_delta(df, "delta_heatmap.png")
    write_md(df, ddf)

    print("输出目录:", OUT_DIR)
    print("主CSV:", out_csv)


if __name__ == "__main__":
    main()
