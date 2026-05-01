#!/usr/bin/env python
"""Build a Chinese overview catalog and PRE/SSRD interpretation summary for SHAP dependence plots."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


BASE = Path("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean")

DATASETS = {
    "recoverywin_mean": BASE / "shap_process_recoverywin_precipEmean_sample50k_by_biome",
    "prepeak_mean": BASE / "prepeak_precip_shap_sem_20260417/shap_by_biome",
}

FEATURE_CN = {
    "recoverywin_total_precipitation_mean": "恢复窗平均降水 PRE",
    "prepeak_total_precipitation_mean": "峰值前平均降水 PRE",
    "recoverywin_total_evaporation_mean": "恢复窗平均蒸发 EVA",
    "recoverywin_temperature_2m_mean": "恢复窗平均气温 TMP",
    "recoverywin_VPD_mean": "恢复窗平均 VPD",
    "recoverywin_SMrz_mean": "恢复窗平均 SMrz",
    "recoverywin_lai_total_mean": "恢复窗平均 LAI",
    "recoverywin_ssrd_mean": "恢复窗平均 SSRD",
    "recoverywin_strd_mean": "恢复窗平均 STRD",
    "recoverywin_wind_speed_mean": "恢复窗平均风速 WIND",
}


def safe_read_summary(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def tercile_summary(feature_values: pd.Series, shap_values: pd.Series) -> dict[str, float]:
    df = pd.DataFrame({"feature": feature_values, "shap": shap_values}).dropna()
    if len(df) < 30:
        return {
            "n": float(len(df)),
            "rho": np.nan,
            "low_mean": np.nan,
            "mid_mean": np.nan,
            "high_mean": np.nan,
        }
    df["bin"] = pd.qcut(df["feature"], q=3, labels=["low", "mid", "high"], duplicates="drop")
    grouped = df.groupby("bin", observed=False)["shap"].mean()
    rho = df["feature"].corr(df["shap"], method="spearman")
    return {
        "n": float(len(df)),
        "rho": float(rho) if pd.notna(rho) else np.nan,
        "low_mean": float(grouped.get("low", np.nan)),
        "mid_mean": float(grouped.get("mid", np.nan)),
        "high_mean": float(grouped.get("high", np.nan)),
    }


def describe_pattern(stats: dict[str, float], feature_key: str) -> str:
    low = stats["low_mean"]
    mid = stats["mid_mean"]
    high = stats["high_mean"]
    rho = stats["rho"]
    if np.isnan(low) or np.isnan(high):
        return "样本不足，暂不解释。"
    delta = high - low
    turning = ""
    if pd.notna(mid):
        if mid < low and mid < high:
            turning = "，呈现中间偏低的 U 型/回升特征"
        elif mid > low and mid > high:
            turning = "，呈现中间偏高的倒 U 型特征"
    if abs(delta) < 0.02:
        base = "整体 SHAP 变化较弱，方向不稳定"
    elif delta > 0:
        base = "从低值到高值，SHAP 整体偏上升，说明更高取值更倾向于延长恢复时间"
    else:
        base = "从低值到高值，SHAP 整体偏下降，说明更高取值更倾向于缩短恢复时间"
    corr_text = f"；Spearman rho={rho:.3f}" if pd.notna(rho) else ""
    if feature_key.endswith("ssrd_mean"):
        return base + "。对 SSRD 更适合解释为受水分背景调制的条件效应" + turning + corr_text + "。"
    if "precipitation" in feature_key:
        return base + "。对 PRE 更适合解释为与事件时长/严重度共现的条件信号，而不是直接单向因果" + turning + corr_text + "。"
    return base + turning + corr_text + "。"


def collect_catalog_lines(dataset_name: str, root: Path) -> tuple[list[str], list[str]]:
    catalog_lines = [f"## {dataset_name}", ""]
    interp_lines = [f"## {dataset_name}", ""]
    for biome_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        summary = safe_read_summary(biome_dir / "dependence_plots_summary.txt")
        count = len(list((biome_dir / "dependence_plots").glob("*.png")))
        catalog_lines.append(f"### {biome_dir.name}")
        catalog_lines.append(f"- 图数量：{count}")
        if summary:
            catalog_lines.append(f"- filtered_rows：{summary.get('filtered_rows', 'NA')}")
            catalog_lines.append(f"- shap_sample_size：{summary.get('shap_sample_size', 'NA')}")
            catalog_lines.append(f"- holdout R2：{summary.get('r2_holdout_split', 'NA')}")
        catalog_lines.append(f"- 图目录：`{biome_dir / 'dependence_plots'}`")
        catalog_lines.append(f"- 数据：`{biome_dir / 'dependence_plot_data.parquet'}`")
        catalog_lines.append("")

        data_path = biome_dir / "dependence_plot_data.parquet"
        if not data_path.exists():
            continue
        df = pd.read_parquet(data_path)
        interp_lines.append(f"### {biome_dir.name}")
        for feature_key in ("recoverywin_total_precipitation_mean", "prepeak_total_precipitation_mean", "recoverywin_ssrd_mean"):
            feature_col = f"feature__{feature_key}"
            shap_col = f"shap__{feature_key}"
            if feature_col not in df.columns or shap_col not in df.columns:
                continue
            stats = tercile_summary(df[feature_col], df[shap_col])
            interp_lines.append(f"- {FEATURE_CN.get(feature_key, feature_key)}：{describe_pattern(stats, feature_key)}")
            interp_lines.append(
                f"  低/中/高三分位平均 SHAP = "
                f"{stats['low_mean']:.4f} / {stats['mid_mean']:.4f} / {stats['high_mean']:.4f}"
                if not np.isnan(stats["low_mean"])
                else "- 三分位结果不足"
            )
        interp_lines.append("")
    return catalog_lines, interp_lines


def main() -> None:
    catalog = [
        "# SHAP Dependence Plot 总览",
        "",
        "下面汇总两版结果中每个 biome 的 dependence plot 路径、样本量和 holdout R2。",
        "",
    ]
    interpretation = [
        "# PRE 与 SSRD Dependence Plot 中文解读",
        "",
        "说明：这里不是重新定义因果机制，而是基于 dependence plot 的三分位 SHAP 变化，对 PRE 和 SSRD 给出更稳妥的解释框架。",
        "",
    ]
    for dataset_name, root in DATASETS.items():
        catalog_lines, interp_lines = collect_catalog_lines(dataset_name, root)
        catalog.extend(catalog_lines)
        interpretation.extend(interp_lines)

    (BASE / "shap_dependence_catalog_20260417.md").write_text("\n".join(catalog), encoding="utf-8")
    (BASE / "shap_pre_ssrd_interpretation_20260417.md").write_text("\n".join(interpretation), encoding="utf-8")


if __name__ == "__main__":
    main()
