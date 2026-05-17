#!/usr/bin/env python
"""Plot biome-wise PRE-SHAP samples with amp_max-based expected subsets highlighted."""

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
GROUP_COLORS = {
    "expected_mild": "#2a9d8f",
    "expected_severe": "#d1495b",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--drought-table", required=True)
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
    parser.add_argument("--low-pre-threshold", type=float, default=0.004)
    parser.add_argument("--severe-pre-threshold", type=float, default=0.001)
    return parser.parse_args()


def compute_gpp_drop_magnitude(values: pd.Series) -> pd.Series:
    arr = -pd.to_numeric(values, errors="coerce")
    arr = arr.clip(lower=0)
    return arr


def classify_expected_groups(
    frame: pd.DataFrame,
    pre_col: str,
    shap_col: str,
    amp_col: str,
    low_pre_threshold: float = 0.004,
    severe_pre_threshold: float = 0.001,
) -> pd.Series:
    pre = pd.to_numeric(frame[pre_col], errors="coerce")
    shap = pd.to_numeric(frame[shap_col], errors="coerce")
    gpp_drop = compute_gpp_drop_magnitude(frame[amp_col])

    low_cut = float(gpp_drop.quantile(1 / 3))
    high_cut = float(gpp_drop.quantile(2 / 3))

    groups = pd.Series("background", index=frame.index, dtype="object")
    mild_mask = (pre < low_pre_threshold) & (shap < 0) & (gpp_drop <= low_cut)
    severe_mask = (pre >= severe_pre_threshold) & (shap > 0) & (gpp_drop >= high_cut)
    groups.loc[mild_mask] = "expected_mild"
    groups.loc[severe_mask] = "expected_severe"
    return groups


def add_trend(ax: plt.Axes, x: np.ndarray, y: np.ndarray, color: str, label: str) -> None:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 20:
        return
    x2 = x[mask]
    y2 = y[mask]
    order = np.argsort(x2)
    x2 = x2[order]
    y2 = y2[order]
    trend = pd.Series(y2).rolling(window=max(21, len(y2) // 10), center=True, min_periods=1).mean()
    ax.plot(x2, trend.to_numpy(), color=color, linewidth=2.1, alpha=0.95, label=label, zorder=4)


def build_biome_frame(
    base_df: pd.DataFrame,
    drought_df: pd.DataFrame,
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
    merged = merged.merge(drought_df[["event_uid", "event_intensity", "event_onset_drop"]], on="event_uid", how="left")
    merged["biome"] = biome
    return merged


def plot_biome(df: pd.DataFrame, biome: str, args: argparse.Namespace, output_path: Path) -> pd.DataFrame:
    pre_col = f"{args.pre_col}__feature"
    shap_col = f"{args.shap_col}__shap"
    work = df.copy()
    work["expected_group"] = classify_expected_groups(
        work,
        pre_col=pre_col,
        shap_col=shap_col,
        amp_col="amp_max",
        low_pre_threshold=args.low_pre_threshold,
        severe_pre_threshold=args.severe_pre_threshold,
    )
    work["gpp_drop_magnitude"] = compute_gpp_drop_magnitude(work["amp_max"])

    x = pd.to_numeric(work[pre_col], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(work[shap_col], errors="coerce").to_numpy(dtype=float)
    base_mask = np.isfinite(x) & np.isfinite(y)

    fig, ax = plt.subplots(figsize=(8.4, 6.2))
    ax.scatter(
        x[base_mask],
        y[base_mask],
        s=13,
        alpha=0.18,
        color="#9aa0a6",
        edgecolors="none",
        zorder=1,
        label="background (all 5000)",
    )
    for group in ["expected_mild", "expected_severe"]:
        part = work[work["expected_group"] == group].copy()
        gx = pd.to_numeric(part[pre_col], errors="coerce").to_numpy(dtype=float)
        gy = pd.to_numeric(part[shap_col], errors="coerce").to_numpy(dtype=float)
        gmask = np.isfinite(gx) & np.isfinite(gy)
        ax.scatter(
            gx[gmask],
            gy[gmask],
            s=20,
            alpha=0.78,
            color=GROUP_COLORS[group],
            edgecolors="none",
            zorder=3,
            label=group,
        )
        add_trend(ax, gx[gmask], gy[gmask], color=GROUP_COLORS[group], label=f"{group} trend")
    ax.axhline(0.0, color="#6e6e6e", linewidth=1.0, linestyle="--", alpha=0.8, zorder=2)
    ax.axvline(args.low_pre_threshold, color="#7f5539", linewidth=1.0, linestyle=":", alpha=0.8, zorder=2)
    ax.set_title(f"{biome} | PRE-SHAP with amp_max expected subsets", fontsize=12.5)
    ax.set_xlabel("Recovery-window precipitation mean (m/day)", fontsize=11)
    ax.set_ylabel("SHAP value for recovery PRE", fontsize=11)
    ax.grid(alpha=0.18, linewidth=0.6)
    ax.legend(frameon=False, fontsize=9, loc="best")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)

    rows: list[dict[str, object]] = []
    for group, grp in work.groupby("expected_group", observed=True):
        rows.append(
            {
                "biome": biome,
                "group": str(group),
                "rows": int(len(grp)),
                "pre_median": float(pd.to_numeric(grp[pre_col], errors="coerce").median()),
                "shap_median": float(pd.to_numeric(grp[shap_col], errors="coerce").median()),
                "amp_max_median": float(pd.to_numeric(grp["amp_max"], errors="coerce").median()),
                "gpp_drop_magnitude_median": float(pd.to_numeric(grp["gpp_drop_magnitude"], errors="coerce").median()),
                "output_png": str(output_path),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    base_df = finalize_feature_table(pd.read_parquet(args.table))
    drought_df = pd.read_parquet(args.drought_table)
    shap_root = Path(args.shap_root)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_parts: list[pd.DataFrame] = []
    for biome in BIOMES:
        biome_frame = build_biome_frame(base_df, drought_df, shap_root, biome, args)
        out_png = out_dir / f"{biome}_recovery_pre_shap_ampmax_expected.png"
        summary_parts.append(plot_biome(biome_frame, biome=biome, args=args, output_path=out_png))
    pd.concat(summary_parts, ignore_index=True).to_csv(out_dir / "summary.csv", index=False)


if __name__ == "__main__":
    main()
