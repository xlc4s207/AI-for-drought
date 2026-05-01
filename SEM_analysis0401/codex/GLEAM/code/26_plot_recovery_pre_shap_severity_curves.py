#!/usr/bin/env python
"""Plot biome-wise recovery PRE-SHAP curves stratified by drought severity groups."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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
SEVERITY_SPECS = [
    ("event_intensity", "Intensity"),
    ("event_onset_drop_abs", "|Onset drop|"),
    ("severity_composite", "Composite severity"),
]
GROUP_ORDER = ["Low", "Mid", "High"]
GROUP_COLORS = {
    "Low": "#355c7d",
    "Mid": "#2a9d8f",
    "High": "#d1495b",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--drought-features", required=True)
    parser.add_argument("--event-master", required=True)
    parser.add_argument("--shap-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--metric", default="GPP")
    parser.add_argument("--code-id", default="code1")
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", default="SMrz")
    parser.add_argument("--feature-scope", default="all")
    parser.add_argument("--limit", type=int, default=50000)
    parser.add_argument("--pre-col", default="recoverywin_total_precipitation_mean")
    parser.add_argument("--shap-col", default="recoverywin_total_precipitation_mean")
    parser.add_argument("--n-severity-groups", type=int, default=3)
    parser.add_argument("--n-bins", type=int, default=18)
    parser.add_argument("--min-bin-count", type=int, default=20)
    parser.add_argument("--low-pre-threshold", type=float, default=0.004)
    return parser.parse_args()


def compute_percentile_composite(frame: pd.DataFrame) -> pd.Series:
    work = pd.DataFrame(index=frame.index)
    work["event_intensity"] = pd.to_numeric(frame["event_intensity"], errors="coerce")
    work["event_onset_drop_abs"] = pd.to_numeric(frame["event_onset_drop"], errors="coerce").abs()
    work["amp_max_severity"] = -pd.to_numeric(frame["amp_max"], errors="coerce")
    ranked = work.rank(pct=True)
    return ranked.mean(axis=1)


def assign_severity_groups(values: pd.Series, n_groups: int = 3) -> pd.Series:
    ranked = pd.to_numeric(values, errors="coerce").rank(method="first")
    labels = GROUP_ORDER[:n_groups]
    return pd.qcut(ranked, q=n_groups, labels=labels)


def build_group_curve_summary(
    frame: pd.DataFrame,
    x_col: str,
    y_col: str,
    group_col: str,
    n_bins: int = 18,
    min_bin_count: int = 20,
) -> pd.DataFrame:
    work = frame[[x_col, y_col, group_col]].copy()
    work[x_col] = pd.to_numeric(work[x_col], errors="coerce")
    work[y_col] = pd.to_numeric(work[y_col], errors="coerce")
    work[group_col] = work[group_col].astype(str)
    work = work[np.isfinite(work[x_col]) & np.isfinite(work[y_col])].copy()
    if work.empty:
        return pd.DataFrame(columns=[group_col, "bin_id", "point_count", "x_center", "y_center", "y_mean"])

    quantiles = np.linspace(0.0, 1.0, n_bins + 1)
    edges = np.unique(np.nanquantile(work[x_col].to_numpy(dtype=float), quantiles))
    if len(edges) < 3:
        return pd.DataFrame(columns=[group_col, "bin_id", "point_count", "x_center", "y_center", "y_mean"])

    work["bin_id"] = pd.cut(work[x_col], bins=edges, labels=False, include_lowest=True, duplicates="drop")
    work = work[work["bin_id"].notna()].copy()
    grouped = (
        work.groupby([group_col, "bin_id"], observed=True)
        .agg(
            point_count=(x_col, "size"),
            x_center=(x_col, "median"),
            y_center=(y_col, "median"),
            y_mean=(y_col, "mean"),
        )
        .reset_index()
    )
    grouped["bin_id"] = grouped["bin_id"].astype(int)
    grouped = grouped[grouped["point_count"] >= int(min_bin_count)].copy()
    return grouped.sort_values([group_col, "bin_id"]).reset_index(drop=True)


def build_biome_frame(
    base_df: pd.DataFrame,
    drought_df: pd.DataFrame,
    master_df: pd.DataFrame,
    shap_root: Path,
    biome: str,
    args: argparse.Namespace,
) -> pd.DataFrame:
    sub = filter_analysis_subset(
        base_df,
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
    missing_idx = sample.index.difference(X.index)
    if len(missing_idx) > 0:
        raise KeyError(f"Sample indices not found in model inputs for biome={biome}: {len(missing_idx)}")

    meta_cols = ["event_uid", "t_recover_to_baseline_abs_peak", "amp_max"]
    meta = sub.loc[sample.index, meta_cols].copy()
    merged = sample.add_suffix("__feature").join(shap_values.add_suffix("__shap")).join(meta)
    merged = merged.merge(drought_df, on="event_uid", how="left")
    merged = merged.merge(master_df, on="event_uid", how="left", suffixes=("", "__master"))
    if "amp_max__master" in merged.columns:
        merged["amp_max"] = merged["amp_max__master"].combine_first(merged["amp_max"])
        merged = merged.drop(columns=["amp_max__master"])
    merged["event_onset_drop_abs"] = pd.to_numeric(merged["event_onset_drop"], errors="coerce").abs()
    merged["severity_composite"] = compute_percentile_composite(merged)
    merged["biome"] = biome
    return merged


def summarize_groups(df: pd.DataFrame, value_col: str, group_col: str, low_pre_threshold: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    x = pd.to_numeric(df["recoverywin_total_precipitation_mean__feature"], errors="coerce")
    y = pd.to_numeric(df["recoverywin_total_precipitation_mean__shap"], errors="coerce")
    values = pd.to_numeric(df[value_col], errors="coerce")
    groups = assign_severity_groups(values, n_groups=3)
    work = pd.DataFrame({"x": x, "y": y, "value": values, "group": groups})
    work = work[np.isfinite(work["x"]) & np.isfinite(work["y"]) & np.isfinite(work["value"]) & work["group"].notna()].copy()
    for label, grp in work.groupby("group", observed=True):
        rows.append(
            {
                "severity_metric": value_col,
                "severity_group": str(label),
                "rows": int(len(grp)),
                "value_median": float(grp["value"].median()),
                "pre_median": float(grp["x"].median()),
                "shap_median": float(grp["y"].median()),
                "low_pre_rows": int((grp["x"] < low_pre_threshold).sum()),
                "low_pre_shap_mean": float(grp.loc[grp["x"] < low_pre_threshold, "y"].mean()),
            }
        )
    return pd.DataFrame(rows)


def plot_biome(
    df: pd.DataFrame,
    biome: str,
    output_path: Path,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.6), sharex=True, sharey=True)
    x = pd.to_numeric(df[f"{args.pre_col}__feature"], errors="coerce")
    y = pd.to_numeric(df[f"{args.shap_col}__shap"], errors="coerce")
    finite_base = np.isfinite(x) & np.isfinite(y)

    curve_rows: list[pd.DataFrame] = []
    group_rows: list[pd.DataFrame] = []
    for ax, (value_col, panel_label) in zip(axes, SEVERITY_SPECS):
        values = pd.to_numeric(df[value_col], errors="coerce")
        groups = assign_severity_groups(values, n_groups=args.n_severity_groups)
        work = pd.DataFrame({"x": x, "y": y, "severity_value": values, "severity_group": groups})
        work = work[finite_base & np.isfinite(work["severity_value"]) & work["severity_group"].notna()].copy()
        curve = build_group_curve_summary(
            work,
            x_col="x",
            y_col="y",
            group_col="severity_group",
            n_bins=args.n_bins,
            min_bin_count=args.min_bin_count,
        )
        curve["biome"] = biome
        curve["severity_metric"] = value_col
        curve_rows.append(curve)

        group_summary = summarize_groups(df, value_col=value_col, group_col="severity_group", low_pre_threshold=args.low_pre_threshold)
        group_summary["biome"] = biome
        group_rows.append(group_summary)

        ax.scatter(
            x[finite_base],
            y[finite_base],
            s=10,
            alpha=0.12,
            color="#9aa0a6",
            edgecolors="none",
            zorder=1,
        )
        for group in GROUP_ORDER[: args.n_severity_groups]:
            part = curve[curve["severity_group"].astype(str) == group]
            if part.empty:
                continue
            ax.plot(
                part["x_center"],
                part["y_center"],
                color=GROUP_COLORS[group],
                linewidth=2.2,
                marker="o",
                markersize=3.8,
                alpha=0.95,
                label=group,
                zorder=3,
            )
        ax.axhline(0.0, color="#6e6e6e", linewidth=1.0, linestyle="--", alpha=0.8, zorder=2)
        ax.set_title(f"{biome} | {panel_label}", fontsize=12)
        ax.set_xlabel("Recovery-window precipitation mean (m/day)", fontsize=10.5)
        ax.grid(alpha=0.18, linewidth=0.6)
        ax.legend(frameon=False, fontsize=9, title="Severity", title_fontsize=9, loc="best")

    axes[0].set_ylabel("SHAP value for recovery PRE", fontsize=10.5)
    fig.suptitle(f"{biome} | PRE-SHAP curves by severity groups", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return pd.concat(curve_rows, ignore_index=True), pd.concat(group_rows, ignore_index=True)


def main() -> None:
    args = parse_args()
    base_df = finalize_feature_table(pd.read_parquet(args.table))
    drought_df = pd.read_parquet(
        args.drought_features,
        columns=["event_uid", "event_intensity", "event_onset_drop"],
    )
    master_df = pd.read_parquet(
        args.event_master,
        columns=["event_uid", "amp_max", "t_impact"],
    )
    shap_root = Path(args.shap_root)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_curve_rows: list[pd.DataFrame] = []
    all_group_rows: list[pd.DataFrame] = []
    figure_rows: list[dict[str, object]] = []
    for biome in BIOMES:
        biome_frame = build_biome_frame(base_df, drought_df, master_df, shap_root, biome, args)
        out_png = out_dir / f"{biome}_recovery_pre_shap_severity_curves.png"
        curve_df, group_df = plot_biome(biome_frame, biome=biome, output_path=out_png, args=args)
        all_curve_rows.append(curve_df)
        all_group_rows.append(group_df)
        figure_rows.append({"biome": biome, "rows": int(len(biome_frame)), "output_png": str(out_png)})

    pd.DataFrame(figure_rows).to_csv(out_dir / "figure_summary.csv", index=False)
    pd.concat(all_curve_rows, ignore_index=True).to_csv(out_dir / "curve_summary.csv", index=False)
    pd.concat(all_group_rows, ignore_index=True).to_csv(out_dir / "group_summary.csv", index=False)


if __name__ == "__main__":
    main()
