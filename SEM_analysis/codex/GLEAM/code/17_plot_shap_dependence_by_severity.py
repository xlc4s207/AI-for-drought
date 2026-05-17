#!/usr/bin/env python
"""Plot SHAP dependence for PRE and SSRD colored by drought severity."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from matplotlib.lines import Line2D

from sem_gleam_common import finalize_feature_table

try:
    import shap  # type: ignore
except Exception as exc:  # pragma: no cover
    raise ImportError("shap is required for dependence plotting.") from exc


TARGET = "t_recover_to_baseline_abs_peak"
FEATURES = [
    "recoverywin_total_precipitation_mean",
    "recoverywin_total_evaporation_mean",
    "recoverywin_temperature_2m_mean",
    "recoverywin_VPD_mean",
    "recoverywin_SMrz_mean",
    "recoverywin_lai_total_mean",
    "recoverywin_ssrd_mean",
    "recoverywin_strd_mean",
    "recoverywin_wind_speed_mean",
]
FOCUS_FEATURES = [
    "recoverywin_total_precipitation_mean",
    "recoverywin_ssrd_mean",
]
SEVERITY_SOURCE_MAP = {
    "intensity": "event_intensity",
    "onset_drop": "event_onset_drop",
    "days_below_p20": "event_days_below_p20",
    "amp_max": "amp_max",
    "t_impact": "t_impact",
}

FEATURE_LABELS = {
    "recoverywin_total_precipitation_mean": "PRE",
    "recoverywin_ssrd_mean": "SSRD",
}
FEATURE_XLIMITS = {
    "recoverywin_total_precipitation_mean": (-1.0, 40.0),
}
FEATURE_XTICKS = {
    "recoverywin_total_precipitation_mean": [0, 10, 20, 30, 40],
}

SEVERITY_LABELS = {
    "event_intensity": "intensity",
    "event_onset_drop": "onset_drop",
    "event_days_below_p20": "days_below_p20",
    "amp_max": "amp_max",
    "t_impact": "t_impact",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--drought-table", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--metric", default="GPP")
    parser.add_argument("--code-id", default="code1")
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", default="SMrz")
    parser.add_argument("--sample-size", type=int, default=12000)
    parser.add_argument("--n-estimators", type=int, default=120)
    parser.add_argument("--n-jobs", type=int, default=12)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument(
        "--severity-vars",
        nargs="+",
        default=["intensity", "onset_drop", "days_below_p20", "amp_max", "t_impact"],
    )
    return parser.parse_args()


def load_data(args: argparse.Namespace) -> pd.DataFrame:
    base = pd.read_parquet(args.table)
    base = finalize_feature_table(base)
    mask = (
        (base["metric"].astype(str) == str(args.metric))
        & (base["code_id"].astype(str) == str(args.code_id))
        & (base["drought_type"].astype(str) == str(args.drought_type))
        & (base["soil_layer"].astype(str) == str(args.soil_layer))
    )
    base = base.loc[mask].copy()

    drought_cols = ["event_uid"]
    for severity_var in args.severity_vars:
        source_col = SEVERITY_SOURCE_MAP.get(str(severity_var))
        if source_col and source_col.startswith("event_"):
            drought_cols.append(source_col)
    drought_cols = list(dict.fromkeys(drought_cols))
    drought = pd.read_parquet(args.drought_table, columns=drought_cols)
    return base.merge(drought, on="event_uid", how="left")


def prepare_inputs(
    df: pd.DataFrame,
    severity_cols: list[str],
    sample_size: int,
    random_state: int,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    cols = ["event_uid", "biome", TARGET, *severity_cols, *FEATURES]
    work = df[cols].copy()
    for col in [TARGET, *severity_cols, *FEATURES]:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work[work[TARGET].notna()].copy()
    work[FEATURES] = work[FEATURES].fillna(work[FEATURES].median(numeric_only=True))
    work = work[np.isfinite(work[FEATURES]).all(axis=1)].copy()
    if len(work) > sample_size:
        work = work.sample(n=sample_size, random_state=random_state).copy()
    work = work.sort_index().reset_index(drop=True)
    X = work[FEATURES].astype(np.float32)
    y = work[TARGET].astype(np.float32)
    return X, y, work


def fit_model(X: pd.DataFrame, y: pd.Series, n_estimators: int, n_jobs: int, random_state: int):
    model = LGBMRegressor(
        objective="regression",
        n_estimators=n_estimators,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=random_state,
        n_jobs=n_jobs,
        verbosity=-1,
    )
    model.fit(X, y)
    return model


def draw_panel(
    ax: plt.Axes,
    values: np.ndarray,
    shap_values: np.ndarray,
    severity_values: np.ndarray,
    title: str,
    x_label: str,
    c_label: str,
    xlim: tuple[float, float] | None = None,
    xticks: list[float] | None = None,
) -> None:
    finite = np.isfinite(values) & np.isfinite(shap_values) & np.isfinite(severity_values)
    values = values[finite]
    shap_values = shap_values[finite]
    severity_values = severity_values[finite]
    sc = ax.scatter(
        values,
        shap_values,
        c=severity_values,
        cmap="viridis",
        s=14,
        alpha=0.42,
        linewidths=0,
    )
    ax.axhline(0.0, color="#444444", linewidth=1.0, linestyle="--", alpha=0.7)
    ax.set_title(title, fontsize=12)
    ax.set_xlabel(x_label, fontsize=10)
    ax.set_ylabel("SHAP value", fontsize=10)
    if xlim is not None:
        ax.set_xlim(*xlim)
    if xticks is not None:
        ax.set_xticks(xticks)
    cbar = plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.03)
    cbar.set_label(c_label, fontsize=9)
    cbar.ax.tick_params(labelsize=8)


def classify_severity_groups(severity_values: np.ndarray) -> np.ndarray:
    ranks = pd.Series(severity_values).rank(method="first")
    groups = pd.qcut(ranks, q=3, labels=["Low", "Mid", "High"])
    return groups.astype(str).to_numpy()


def draw_panel_terciles(
    ax: plt.Axes,
    values: np.ndarray,
    shap_values: np.ndarray,
    severity_values: np.ndarray,
    title: str,
    x_label: str,
    severity_label: str,
    xlim: tuple[float, float] | None = None,
    xticks: list[float] | None = None,
) -> None:
    finite = np.isfinite(values) & np.isfinite(shap_values) & np.isfinite(severity_values)
    values = values[finite]
    shap_values = shap_values[finite]
    severity_values = severity_values[finite]
    groups = classify_severity_groups(severity_values)

    color_map = {
        "Low": "#355c7d",
        "Mid": "#2a9d8f",
        "High": "#d77a61",
    }
    for group in ["Low", "Mid", "High"]:
        mask = groups == group
        if not np.any(mask):
            continue
        ax.scatter(
            values[mask],
            shap_values[mask],
            color=color_map[group],
            s=14,
            alpha=0.42,
            linewidths=0,
            label=group,
        )

    ax.axhline(0.0, color="#444444", linewidth=1.0, linestyle="--", alpha=0.7)
    ax.set_title(title, fontsize=12)
    ax.set_xlabel(x_label, fontsize=10)
    ax.set_ylabel("SHAP value", fontsize=10)
    if xlim is not None:
        ax.set_xlim(*xlim)
    if xticks is not None:
        ax.set_xticks(xticks)
    handles = [
        Line2D([0], [0], marker="o", linestyle="", color=color_map[group], markersize=6, label=group)
        for group in ["Low", "Mid", "High"]
    ]
    ax.legend(handles=handles, title=severity_label, fontsize=8, title_fontsize=9, loc="best", frameon=False)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_data(args)
    severity_cols = [
        SEVERITY_SOURCE_MAP[str(name)]
        for name in args.severity_vars
        if str(name) in SEVERITY_SOURCE_MAP
    ]
    X, y, meta = prepare_inputs(
        df,
        severity_cols=severity_cols,
        sample_size=args.sample_size,
        random_state=args.random_state,
    )
    model = fit_model(
        X,
        y,
        n_estimators=args.n_estimators,
        n_jobs=args.n_jobs,
        random_state=args.random_state,
    )
    explainer = shap.TreeExplainer(model)
    shap_array = np.asarray(explainer.shap_values(X))

    for severity_col in severity_cols:
        severity_label = SEVERITY_LABELS[severity_col]
        fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.9))
        for ax, feature_name in zip(axes.flat, FOCUS_FEATURES):
            feature_idx = FEATURES.index(feature_name)
            draw_panel(
                ax=ax,
                values=X[feature_name].to_numpy(dtype=float),
                shap_values=shap_array[:, feature_idx].astype(float),
                severity_values=meta[severity_col].to_numpy(dtype=float),
                title=f"{FEATURE_LABELS[feature_name]} colored by {severity_label}",
                x_label=FEATURE_LABELS[feature_name],
                c_label=severity_label,
                xlim=FEATURE_XLIMITS.get(feature_name),
                xticks=FEATURE_XTICKS.get(feature_name),
            )

        fig.suptitle(
            f"SHAP dependence of PRE and SSRD under {severity_label} background",
            fontsize=15,
            y=0.98,
        )
        fig.tight_layout(rect=(0.02, 0.03, 0.98, 0.96))
        fig.savefig(
            output_dir / f"pre_ssrd_dependence_by_{severity_label}.png",
            dpi=220,
            bbox_inches="tight",
        )
        plt.close(fig)

        fig2, axes2 = plt.subplots(1, 2, figsize=(12.5, 4.9))
        for ax, feature_name in zip(axes2.flat, FOCUS_FEATURES):
            feature_idx = FEATURES.index(feature_name)
            draw_panel_terciles(
                ax=ax,
                values=X[feature_name].to_numpy(dtype=float),
                shap_values=shap_array[:, feature_idx].astype(float),
                severity_values=meta[severity_col].to_numpy(dtype=float),
                title=f"{FEATURE_LABELS[feature_name]} colored by {severity_label} terciles",
                x_label=FEATURE_LABELS[feature_name],
                severity_label=severity_label,
                xlim=FEATURE_XLIMITS.get(feature_name),
                xticks=FEATURE_XTICKS.get(feature_name),
            )

        fig2.suptitle(f"SHAP dependence with {severity_label} terciles", fontsize=15, y=0.98)
        fig2.tight_layout(rect=(0.02, 0.03, 0.98, 0.96))
        fig2.savefig(
            output_dir / f"pre_ssrd_dependence_by_{severity_label}_terciles.png",
            dpi=220,
            bbox_inches="tight",
        )
        plt.close(fig2)

    pd.DataFrame(
        {
            "event_uid": meta["event_uid"],
            "biome": meta["biome"],
            "PRE_value": X["recoverywin_total_precipitation_mean"],
            "PRE_shap": shap_array[:, FEATURES.index("recoverywin_total_precipitation_mean")],
            "SSRD_value": X["recoverywin_ssrd_mean"],
            "SSRD_shap": shap_array[:, FEATURES.index("recoverywin_ssrd_mean")],
            **{SEVERITY_LABELS[col]: meta[col] for col in severity_cols},
        }
    ).to_csv(output_dir / "pre_ssrd_dependence_plot_data.csv", index=False)
    print(f"[DONE] dependence figures saved under {output_dir}")


if __name__ == "__main__":
    main()
