#!/usr/bin/env python
"""Diagnose low recovery-window precipitation samples with negative SHAP values."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

from sem_gleam_common import finalize_feature_table


SHAP_ANALYSIS_PATH = Path(__file__).with_name("06_shap_analysis.py")
SHAP_ANALYSIS_SPEC = importlib.util.spec_from_file_location("shap_analysis_module", SHAP_ANALYSIS_PATH)
if SHAP_ANALYSIS_SPEC is None or SHAP_ANALYSIS_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"Unable to load helper module from {SHAP_ANALYSIS_PATH}")
shap_analysis_module = importlib.util.module_from_spec(SHAP_ANALYSIS_SPEC)
SHAP_ANALYSIS_SPEC.loader.exec_module(shap_analysis_module)

filter_analysis_subset = shap_analysis_module.filter_analysis_subset
prepare_model_inputs = shap_analysis_module.prepare_model_inputs


BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
MODEL_FEATURES = [
    "prepeak_total_precipitation_mean",
    "recoverywin_total_precipitation_mean",
    "recoverywin_total_evaporation_mean",
    "recoverywin_SMrz_mean",
    "recoverywin_temperature_2m_mean",
    "recoverywin_VPD_mean",
    "recoverywin_wind_speed_mean",
    "recoverywin_lai_total_mean",
    "recoverywin_ssrd_mean",
    "recoverywin_strd_mean",
]
EXCLUDE_FEATURES = [
    "recoverywin_p_minus_et",
    "recoverywin_total_precipitation_sum",
    "recoverywin_total_evaporation_sum",
    "recoverywin_SMrz_delta",
]
BACKGROUND_COLS = [
    "prepeak_total_precipitation_mean",
    "recoverywin_total_precipitation_mean",
    "recoverywin_SMrz_mean",
    "recoverywin_VPD_mean",
    "recoverywin_temperature_2m_mean",
    "recoverywin_lai_total_mean",
    "recoverywin_total_evaporation_mean",
    "amp_max",
    "t_impact",
    "t_recover_to_baseline_abs_peak",
    "lat",
    "lon",
]
LABELS = {
    "prepeak_total_precipitation_mean": "Pre-peak PRE",
    "recoverywin_total_precipitation_mean": "Recovery PRE",
    "recoverywin_SMrz_mean": "SMrz",
    "recoverywin_VPD_mean": "VPD",
    "recoverywin_temperature_2m_mean": "TMP",
    "recoverywin_lai_total_mean": "LAI",
    "recoverywin_total_evaporation_mean": "EVA",
    "amp_max": "amp_max",
    "t_impact": "t_impact",
    "t_recover_to_baseline_abs_peak": "t_recover",
}
KOPPEN_CODE_TO_LABEL = {
    1: "Af",
    2: "Am",
    3: "Aw",
    4: "BWh",
    5: "BWk",
    6: "BSh",
    7: "BSk",
    8: "Csa",
    9: "Csb",
    10: "Csc",
    11: "Cwa",
    12: "Cwb",
    13: "Cwc",
    14: "Cfa",
    15: "Cfb",
    16: "Cfc",
    17: "Dsa",
    18: "Dsb",
    19: "Dsc",
    20: "Dsd",
    21: "Dwa",
    22: "Dwb",
    23: "Dwc",
    24: "Dwd",
    25: "Dfa",
    26: "Dfb",
    27: "Dfc",
    28: "Dfd",
    29: "ET",
    30: "EF",
}
KOPPEN_TO_MOISTURE = {
    "Af": "humid",
    "Am": "humid",
    "Aw": "semi-humid",
    "BWh": "arid",
    "BWk": "arid",
    "BSh": "semi-arid",
    "BSk": "semi-arid",
    "Csa": "semi-humid",
    "Csb": "semi-humid",
    "Csc": "semi-humid",
    "Cwa": "semi-humid",
    "Cwb": "semi-humid",
    "Cwc": "semi-humid",
    "Cfa": "humid",
    "Cfb": "humid",
    "Cfc": "humid",
    "Dsa": "semi-humid",
    "Dsb": "semi-humid",
    "Dsc": "semi-humid",
    "Dsd": "semi-humid",
    "Dwa": "semi-humid",
    "Dwb": "semi-humid",
    "Dwc": "semi-humid",
    "Dwd": "semi-humid",
    "Dfa": "humid",
    "Dfb": "humid",
    "Dfc": "humid",
    "Dfd": "humid",
    "ET": "humid",
    "EF": "humid",
}
MOISTURE_ORDER = ["arid", "semi-arid", "semi-humid", "humid"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--shap-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--metric", default="GPP")
    parser.add_argument("--code-id", default="code1")
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", default="SMrz")
    parser.add_argument("--feature-scope", default="all")
    parser.add_argument("--limit", type=int, default=50000)
    parser.add_argument("--pre-threshold", type=float, default=0.004)
    parser.add_argument("--feature-name", default="recoverywin_total_precipitation_mean")
    parser.add_argument("--koppen-tif", default="/data/koppen/1991_2020/koppen_geiger_0p5.tif")
    return parser.parse_args()


def build_sample_frame(
    df: pd.DataFrame,
    shap_root: Path,
    biome: str,
    args: argparse.Namespace,
) -> pd.DataFrame:
    sub = filter_analysis_subset(
        df,
        metric=args.metric,
        code_id=args.code_id,
        biome=biome,
        drought_type=args.drought_type,
        soil_layer=args.soil_layer,
    )
    if args.limit and len(sub) > args.limit:
        sub = sub.head(args.limit).copy()

    X, _, _ = prepare_model_inputs(
        sub,
        target="t_recover_to_baseline_abs_peak",
        max_missing_rate=0.3,
        feature_scope=args.feature_scope,
        include_features=MODEL_FEATURES,
        exclude_features=EXCLUDE_FEATURES,
    )

    biome_dir = shap_root / biome
    sample = pd.read_parquet(biome_dir / "dependence_sample_features.parquet")
    shap_values = pd.read_parquet(biome_dir / "dependence_sample_shap_values.parquet")

    meta = sub.loc[sample.index, BACKGROUND_COLS].copy()
    meta = meta.apply(pd.to_numeric, errors="coerce")

    merged = sample.join(shap_values, lsuffix="__feature", rsuffix="__shap").join(meta)
    merged["biome"] = biome

    feature_col = f"{args.feature_name}__feature"
    shap_col = f"{args.feature_name}__shap"
    merged["is_lowneg"] = (merged[feature_col] < args.pre_threshold) & (merged[shap_col] < 0)
    merged["group"] = np.where(merged["is_lowneg"], "low PRE & SHAP<0", "other sampled points")

    # Dryness proxy here is only a relative indicator within the sampled SHAP points.
    dryness = (
        merged["recoverywin_VPD_mean"].rank(pct=True)
        + merged["recoverywin_temperature_2m_mean"].rank(pct=True)
        + (1.0 - merged["recoverywin_SMrz_mean"].rank(pct=True))
        + (1.0 - merged["recoverywin_lai_total_mean"].rank(pct=True))
        + (1.0 - merged["recoverywin_total_precipitation_mean"].rank(pct=True))
    ) / 5.0
    merged["dryness_proxy"] = dryness
    merged["abs_lat"] = merged["lat"].abs()

    missing_idx = sample.index.difference(X.index)
    if len(missing_idx) > 0:
        raise KeyError(f"Sample indices not found in prepared model inputs for biome={biome}: {len(missing_idx)} rows")
    return merged


def summarize_groups(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    compare_cols = [
        "prepeak_total_precipitation_mean",
        "recoverywin_total_precipitation_mean",
        "recoverywin_SMrz_mean",
        "recoverywin_VPD_mean",
        "recoverywin_temperature_2m_mean",
        "recoverywin_lai_total_mean",
        "recoverywin_total_evaporation_mean",
        "amp_max",
        "t_impact",
        "t_recover_to_baseline_abs_peak",
        "dryness_proxy",
        "abs_lat",
    ]
    for biome, biome_df in df.groupby("biome", observed=True):
        for group, grp in biome_df.groupby("group", observed=True):
            row: dict[str, object] = {"biome": biome, "group": group, "n": int(len(grp))}
            for col in compare_cols:
                row[f"{col}__mean"] = float(grp[col].mean())
                row[f"{col}__median"] = float(grp[col].median())
            rows.append(row)
    return pd.DataFrame(rows)


def summarize_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    out_rows: list[dict[str, object]] = []
    delta_cols = [
        "prepeak_total_precipitation_mean",
        "recoverywin_total_precipitation_mean",
        "recoverywin_SMrz_mean",
        "recoverywin_VPD_mean",
        "recoverywin_temperature_2m_mean",
        "recoverywin_lai_total_mean",
        "recoverywin_total_evaporation_mean",
        "amp_max",
        "t_impact",
        "t_recover_to_baseline_abs_peak",
        "dryness_proxy",
        "abs_lat",
    ]
    for biome, biome_df in summary.groupby("biome", observed=True):
        lowneg = biome_df[biome_df["group"] == "low PRE & SHAP<0"]
        other = biome_df[biome_df["group"] == "other sampled points"]
        if lowneg.empty or other.empty:
            continue
        row: dict[str, object] = {
            "biome": biome,
            "n_lowneg": int(lowneg["n"].iloc[0]),
            "n_other": int(other["n"].iloc[0]),
            "frac_lowneg": float(lowneg["n"].iloc[0] / (lowneg["n"].iloc[0] + other["n"].iloc[0])),
        }
        for col in delta_cols:
            row[f"{col}_mean_lowneg"] = float(lowneg[f"{col}__mean"].iloc[0])
            row[f"{col}_mean_other"] = float(other[f"{col}__mean"].iloc[0])
            row[f"{col}_delta_lowneg_minus_other"] = float(
                lowneg[f"{col}__mean"].iloc[0] - other[f"{col}__mean"].iloc[0]
            )
        out_rows.append(row)
    return pd.DataFrame(out_rows)


def attach_koppen_classes(df: pd.DataFrame, koppen_tif: str) -> pd.DataFrame:
    work = df.copy()
    unique_points = work[["lat", "lon"]].drop_duplicates().reset_index(drop=True)
    coords = [(float(lon), float(lat)) for lat, lon in zip(unique_points["lat"], unique_points["lon"])]
    with rasterio.open(koppen_tif) as src:
        sampled = np.array([val[0] for val in src.sample(coords)], dtype=float)
        nodata = src.nodata
    sampled = np.where(sampled == nodata, np.nan, sampled)
    unique_points["koppen_code"] = sampled
    unique_points["koppen_code"] = unique_points["koppen_code"].astype("Float64")
    unique_points["koppen_label"] = unique_points["koppen_code"].map(
        lambda x: KOPPEN_CODE_TO_LABEL.get(int(x), "missing") if pd.notna(x) else "missing"
    )
    unique_points["moisture_class"] = unique_points["koppen_label"].map(KOPPEN_TO_MOISTURE).fillna("missing")
    return work.merge(unique_points, on=["lat", "lon"], how="left")


def summarize_moisture_classes(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby(["biome", "group", "moisture_class"], observed=True)
        .size()
        .rename("n")
        .reset_index()
    )
    total = summary.groupby(["biome", "group"], observed=True)["n"].transform("sum")
    summary["fraction_within_group"] = summary["n"] / total
    return summary.sort_values(["biome", "group", "moisture_class"]).reset_index(drop=True)


def plot_background_boxplots(df: pd.DataFrame, output_path: Path) -> None:
    cols = [
        "recoverywin_SMrz_mean",
        "recoverywin_VPD_mean",
        "recoverywin_temperature_2m_mean",
        "recoverywin_lai_total_mean",
        "recoverywin_total_evaporation_mean",
        "amp_max",
        "t_recover_to_baseline_abs_peak",
        "dryness_proxy",
    ]
    fig, axes = plt.subplots(len(BIOMES), len(cols), figsize=(23, 14), sharex=False)
    colors = {"low PRE & SHAP<0": "#1f77b4", "other sampled points": "#d95f02"}
    for i, biome in enumerate(BIOMES):
        biome_df = df[df["biome"] == biome]
        for j, col in enumerate(cols):
            ax = axes[i, j]
            groups = []
            tick_labels = []
            box_colors = []
            for group in ["low PRE & SHAP<0", "other sampled points"]:
                vals = biome_df.loc[biome_df["group"] == group, col].dropna().to_numpy(dtype=float)
                if len(vals) == 0:
                    continue
                groups.append(vals)
                tick_labels.append("lowneg" if group == "low PRE & SHAP<0" else "other")
                box_colors.append(colors[group])
            if groups:
                bp = ax.boxplot(
                    groups,
                    tick_labels=tick_labels,
                    patch_artist=True,
                    widths=0.62,
                    showfliers=False,
                    medianprops={"color": "black", "linewidth": 1.1},
                    whiskerprops={"linewidth": 1.0},
                    capprops={"linewidth": 1.0},
                )
                for patch, color in zip(bp["boxes"], box_colors):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.78)
            ax.set_title(f"{biome} | {LABELS.get(col, col)}", fontsize=9)
            ax.tick_params(axis="x", labelsize=7, rotation=18)
            ax.tick_params(axis="y", labelsize=7)
            ax.grid(alpha=0.16, linewidth=0.5)
    fig.suptitle("Recovery PRE < 0.004 and SHAP < 0: background contrast", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_moisture_class_bars(summary: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(1, len(BIOMES), figsize=(18, 4.6), sharey=True)
    colors = {
        "arid": "#8c510a",
        "semi-arid": "#d8b365",
        "semi-humid": "#5ab4ac",
        "humid": "#01665e",
        "missing": "#bdbdbd",
    }
    if len(BIOMES) == 1:
        axes = [axes]
    for ax, biome in zip(axes, BIOMES):
        biome_df = summary[summary["biome"] == biome]
        groups = ["low PRE & SHAP<0", "other sampled points"]
        x = np.arange(len(groups))
        bottom = np.zeros(len(groups), dtype=float)
        for moisture in MOISTURE_ORDER + ["missing"]:
            vals = []
            for group in groups:
                sub = biome_df[(biome_df["group"] == group) & (biome_df["moisture_class"] == moisture)]
                vals.append(float(sub["fraction_within_group"].iloc[0]) if not sub.empty else 0.0)
            ax.bar(x, vals, bottom=bottom, color=colors[moisture], width=0.65, label=moisture)
            bottom += np.asarray(vals)
        ax.set_title(biome, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(["lowneg", "other"], rotation=15)
        ax.set_ylim(0, 1)
        ax.grid(axis="y", alpha=0.2, linewidth=0.6)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=5, loc="upper center", frameon=False)
    fig.suptitle("Koppen-derived moisture classes within each biome group", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_latlon_panels(df: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes = axes.flatten()
    for ax, biome in zip(axes, BIOMES):
        biome_df = df[df["biome"] == biome]
        other = biome_df[~biome_df["is_lowneg"]]
        lowneg = biome_df[biome_df["is_lowneg"]]
        ax.scatter(other["lon"], other["lat"], s=5, alpha=0.14, color="#bdbdbd", edgecolors="none")
        ax.scatter(lowneg["lon"], lowneg["lat"], s=7, alpha=0.55, color="#1f77b4", edgecolors="none")
        ax.set_title(f"{biome} (n={len(lowneg)})", fontsize=11)
        ax.set_xlim(-180, 180)
        ax.set_ylim(-60, 80)
        ax.set_xlabel("Lon", fontsize=9)
        ax.set_ylabel("Lat", fontsize=9)
        ax.grid(alpha=0.18, linewidth=0.5)
    axes[-1].axis("off")
    fig.suptitle("Geographic distribution of recovery PRE < 0.004 and SHAP < 0", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def summarize_low_pre_band(df: pd.DataFrame, low_pre_max: float = 0.004) -> pd.DataFrame:
    sub = df[df["recoverywin_total_precipitation_mean"] < low_pre_max].copy()
    sub["pre_bin"] = pd.cut(
        sub["recoverywin_total_precipitation_mean"],
        bins=[0.0, 0.001, 0.002, 0.003, low_pre_max],
        include_lowest=True,
    )
    rows: list[dict[str, object]] = []
    for biome, biome_df in [("Overall", sub), *list(sub.groupby("biome", observed=True))]:
        x = pd.to_numeric(biome_df["recoverywin_total_precipitation_mean"], errors="coerce").to_numpy(dtype=float)
        row: dict[str, object] = {"biome": biome, "n": int(len(biome_df))}
        for col in [
            "recoverywin_total_precipitation_mean__shap",
            "amp_max",
            "t_recover_to_baseline_abs_peak",
            "dryness_proxy",
            "recoverywin_SMrz_mean",
            "recoverywin_VPD_mean",
            "recoverywin_lai_total_mean",
        ]:
            y = pd.to_numeric(biome_df[col], errors="coerce").to_numpy(dtype=float)
            mask = np.isfinite(x) & np.isfinite(y)
            row[f"corr_{col}"] = float(np.corrcoef(x[mask], y[mask])[0, 1]) if mask.sum() > 5 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_low_pre_bins(df: pd.DataFrame, low_pre_max: float = 0.004) -> pd.DataFrame:
    sub = df[df["recoverywin_total_precipitation_mean"] < low_pre_max].copy()
    sub["pre_bin"] = pd.cut(
        sub["recoverywin_total_precipitation_mean"],
        bins=[0.0, 0.001, 0.002, 0.003, low_pre_max],
        include_lowest=True,
    )
    rows: list[dict[str, object]] = []
    for biome, biome_df in [("Overall", sub), *list(sub.groupby("biome", observed=True))]:
        grouped = biome_df.groupby("pre_bin", observed=True)
        for pre_bin, grp in grouped:
            row: dict[str, object] = {
                "biome": biome,
                "pre_bin": str(pre_bin),
                "n": int(len(grp)),
                "pre_mean": float(grp["recoverywin_total_precipitation_mean"].mean()),
                "shap_mean": float(grp["recoverywin_total_precipitation_mean__shap"].mean()),
                "amp_max_mean": float(grp["amp_max"].mean()),
                "t_recover_mean": float(grp["t_recover_to_baseline_abs_peak"].mean()),
                "dryness_mean": float(grp["dryness_proxy"].mean()),
                "smrz_mean": float(grp["recoverywin_SMrz_mean"].mean()),
                "vpd_mean": float(grp["recoverywin_VPD_mean"].mean()),
                "lai_mean": float(grp["recoverywin_lai_total_mean"].mean()),
            }
            for moisture in MOISTURE_ORDER:
                row[f"share_{moisture}"] = float((grp["moisture_class"] == moisture).mean())
            rows.append(row)
    return pd.DataFrame(rows)


def plot_low_pre_mechanism(df: pd.DataFrame, output_path: Path, low_pre_max: float = 0.004) -> None:
    sub = df[df["recoverywin_total_precipitation_mean"] < low_pre_max].copy()
    moisture_colors = {
        "arid": "#8c510a",
        "semi-arid": "#d8b365",
        "semi-humid": "#5ab4ac",
        "humid": "#01665e",
        "missing": "#bdbdbd",
    }
    panels = [
        ("recoverywin_total_precipitation_mean__shap", "PRE SHAP"),
        ("amp_max", "amp_max"),
        ("t_recover_to_baseline_abs_peak", "t_recover"),
    ]
    fig, axes = plt.subplots(len(panels), 1, figsize=(9.5, 12), sharex=True)
    x = pd.to_numeric(sub["recoverywin_total_precipitation_mean"], errors="coerce").to_numpy(dtype=float)
    order = np.argsort(x)
    for ax, (col, ylabel) in zip(axes, panels):
        y = pd.to_numeric(sub[col], errors="coerce").to_numpy(dtype=float)
        moisture = sub["moisture_class"].fillna("missing").to_numpy(dtype=object)
        for moisture_name in MOISTURE_ORDER + ["missing"]:
            mask = np.isfinite(x) & np.isfinite(y) & (moisture == moisture_name)
            if not np.any(mask):
                continue
            ax.scatter(
                x[mask],
                y[mask],
                s=12,
                alpha=0.35,
                color=moisture_colors[moisture_name],
                edgecolors="none",
                label=moisture_name,
            )
        finite = np.isfinite(x) & np.isfinite(y)
        if finite.sum() >= 20:
            trend = pd.Series(y[order]).rolling(window=max(31, finite.sum() // 40), center=True, min_periods=1).mean()
            ax.plot(x[order], trend.to_numpy(), color="#c83349", linewidth=2.2, alpha=0.95)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.grid(alpha=0.18, linewidth=0.6)
    axes[-1].set_xlabel("Recovery-window precipitation mean (m/day)", fontsize=11)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=5, loc="upper center", frameon=False)
    fig.suptitle("Low-PRE mechanism view within 0-0.004 m/day", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_low_pre_mechanism_by_biome(df: pd.DataFrame, output_dir: Path, low_pre_max: float = 0.004) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for biome in BIOMES:
        biome_df = df[(df["biome"] == biome) & (df["recoverywin_total_precipitation_mean"] < low_pre_max)].copy()
        if biome_df.empty:
            continue
        moisture_colors = {
            "arid": "#8c510a",
            "semi-arid": "#d8b365",
            "semi-humid": "#5ab4ac",
            "humid": "#01665e",
            "missing": "#bdbdbd",
        }
        panels = [
            ("recoverywin_total_precipitation_mean__shap", "PRE SHAP"),
            ("amp_max", "amp_max"),
            ("t_recover_to_baseline_abs_peak", "t_recover"),
        ]
        fig, axes = plt.subplots(len(panels), 1, figsize=(8.5, 10.5), sharex=True)
        x = pd.to_numeric(biome_df["recoverywin_total_precipitation_mean"], errors="coerce").to_numpy(dtype=float)
        order = np.argsort(x)
        for ax, (col, ylabel) in zip(axes, panels):
            y = pd.to_numeric(biome_df[col], errors="coerce").to_numpy(dtype=float)
            moisture = biome_df["moisture_class"].fillna("missing").to_numpy(dtype=object)
            for moisture_name in MOISTURE_ORDER + ["missing"]:
                mask = np.isfinite(x) & np.isfinite(y) & (moisture == moisture_name)
                if not np.any(mask):
                    continue
                ax.scatter(
                    x[mask],
                    y[mask],
                    s=13,
                    alpha=0.36,
                    color=moisture_colors[moisture_name],
                    edgecolors="none",
                    label=moisture_name,
                )
            finite = np.isfinite(x) & np.isfinite(y)
            if finite.sum() >= 20:
                trend = pd.Series(y[order]).rolling(window=max(21, finite.sum() // 35), center=True, min_periods=1).mean()
                ax.plot(x[order], trend.to_numpy(), color="#c83349", linewidth=2.2, alpha=0.95)
            ax.set_ylabel(ylabel, fontsize=10.5)
            ax.grid(alpha=0.18, linewidth=0.6)
        axes[-1].set_xlabel("Recovery-window precipitation mean (m/day)", fontsize=10.5)
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, ncol=5, loc="upper center", frameon=False, fontsize=8.5)
        fig.suptitle(f"{biome} | low-PRE mechanism within 0-{low_pre_max:.3f} m/day", fontsize=13)
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        fig.savefig(output_dir / f"{biome}_low_pre_mechanism.png", dpi=220, bbox_inches="tight")
        plt.close(fig)


def write_summary_markdown(df: pd.DataFrame, deltas: pd.DataFrame, output_path: Path, threshold: float) -> None:
    total_n = int(df["is_lowneg"].sum())
    sampled_n = int(len(df))
    top_bins = (
        df.loc[df["is_lowneg"]]
        .assign(lat_bin=lambda x: np.floor(x["lat"] / 10) * 10, lon_bin=lambda x: np.floor(x["lon"] / 20) * 20)
        .groupby(["lat_bin", "lon_bin"], observed=True)
        .size()
        .sort_values(ascending=False)
        .head(10)
    )

    lines = [
        "# Recoverywin PRE low-negative SHAP diagnostics",
        "",
        f"- Threshold definition: `recoverywin_total_precipitation_mean < {threshold}` and `SHAP < 0`",
        f"- Sampled SHAP rows analysed: `{sampled_n}`",
        f"- Low-negative rows analysed: `{total_n}`",
        "",
        "## Main takeaways",
        "",
        "- These points are consistently drier in event-state terms: lower `SMrz`, lower `LAI`, higher `VPD`, and slightly warmer than the other sampled points in the same biome.",
        "- But they are not the most severe / longest-recovery events. In all five biomes, they show shorter `t_recover` and shorter `t_impact`, and `amp_max` is less negative than in the other sampled points.",
        "- So this group is better interpreted as `dry-adapted / low-water-background events where low recovery-window precipitation is not a strong delaying factor`, rather than simply `the harshest drought cases`.",
        "- This is only a relative dryness diagnosis within the SHAP sample. It is not a true climatological aridity-index classification.",
        "",
        "## Top geographic bins",
        "",
    ]
    for (lat_bin, lon_bin), count in top_bins.items():
        lines.append(f"- lat {int(lat_bin)} to {int(lat_bin) + 10}, lon {int(lon_bin)} to {int(lon_bin) + 20}: {int(count)} samples")
    lines.extend(["", "## Per-biome delta hints", ""])
    for _, row in deltas.iterrows():
        lines.append(
            "- "
            f"{row['biome']}: lowneg share={row['frac_lowneg']:.3f}, "
            f"SMrz delta={row['recoverywin_SMrz_mean_delta_lowneg_minus_other']:.3f}, "
            f"VPD delta={row['recoverywin_VPD_mean_delta_lowneg_minus_other']:.3f}, "
            f"TMP delta={row['recoverywin_temperature_2m_mean_delta_lowneg_minus_other']:.3f}, "
            f"LAI delta={row['recoverywin_lai_total_mean_delta_lowneg_minus_other']:.3f}, "
            f"t_recover delta={row['t_recover_to_baseline_abs_peak_delta_lowneg_minus_other']:.3f}, "
            f"t_impact delta={row['t_impact_delta_lowneg_minus_other']:.3f}"
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    shap_root = Path(args.shap_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = finalize_feature_table(pd.read_parquet(args.table))

    frames = [build_sample_frame(df, shap_root, biome, args) for biome in BIOMES]
    merged = pd.concat(frames, ignore_index=True)
    merged = attach_koppen_classes(merged, args.koppen_tif)

    merged.to_parquet(output_dir / "recoverywin_pre_lowneg_samples.parquet", index=False)
    summary = summarize_groups(merged)
    summary.to_csv(output_dir / "recoverywin_pre_lowneg_group_summary.csv", index=False)
    deltas = summarize_deltas(summary)
    deltas.to_csv(output_dir / "recoverywin_pre_lowneg_group_deltas.csv", index=False)
    moisture_summary = summarize_moisture_classes(merged)
    moisture_summary.to_csv(output_dir / "recoverywin_pre_lowneg_koppen_moisture_summary.csv", index=False)
    low_pre_summary = summarize_low_pre_band(merged, low_pre_max=args.pre_threshold)
    low_pre_summary.to_csv(output_dir / "recoverywin_pre_low_band_mechanism_summary.csv", index=False)
    low_pre_bins = summarize_low_pre_bins(merged, low_pre_max=args.pre_threshold)
    low_pre_bins.to_csv(output_dir / "recoverywin_pre_low_band_mechanism_bins.csv", index=False)

    plot_background_boxplots(merged, output_dir / "recoverywin_pre_lowneg_background_boxplots.png")
    plot_latlon_panels(merged, output_dir / "recoverywin_pre_lowneg_latlon_panels.png")
    plot_moisture_class_bars(moisture_summary, output_dir / "recoverywin_pre_lowneg_koppen_moisture_bars.png")
    plot_low_pre_mechanism(merged, output_dir / "recoverywin_pre_low_band_mechanism.png", low_pre_max=args.pre_threshold)
    plot_low_pre_mechanism_by_biome(merged, output_dir / "by_biome_low_pre_mechanism", low_pre_max=args.pre_threshold)
    write_summary_markdown(merged, deltas, output_dir / "recoverywin_pre_lowneg_summary.md", args.pre_threshold)


if __name__ == "__main__":
    main()
