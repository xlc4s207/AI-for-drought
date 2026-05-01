#!/usr/bin/env python
"""Plot dependence curves for a selected feature colored by another feature."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np
import pandas as pd


SCRIPT_21_PATH = Path(__file__).with_name("21_batch_dependence_plots_fast.py")
SCRIPT_21_SPEC = importlib.util.spec_from_file_location("batch_dependence_fast_module", SCRIPT_21_PATH)
if SCRIPT_21_SPEC is None or SCRIPT_21_SPEC.loader is None:
    raise RuntimeError(f"Unable to load helper module from {SCRIPT_21_PATH}")
batch_dependence_fast_module = importlib.util.module_from_spec(SCRIPT_21_SPEC)
sys.modules[SCRIPT_21_SPEC.name] = batch_dependence_fast_module
SCRIPT_21_SPEC.loader.exec_module(batch_dependence_fast_module)

SCRIPT_33_PATH = Path(__file__).with_name("33_plot_prepeak_vs_recoverywin_comparison.py")
SCRIPT_33_SPEC = importlib.util.spec_from_file_location("plot_prepeak_vs_recoverywin_comparison", SCRIPT_33_PATH)
if SCRIPT_33_SPEC is None or SCRIPT_33_SPEC.loader is None:
    raise RuntimeError(f"Unable to load helper module from {SCRIPT_33_PATH}")
plot_prepeak_vs_recoverywin_comparison = importlib.util.module_from_spec(SCRIPT_33_SPEC)
sys.modules[SCRIPT_33_SPEC.name] = plot_prepeak_vs_recoverywin_comparison
SCRIPT_33_SPEC.loader.exec_module(plot_prepeak_vs_recoverywin_comparison)


BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]


def normalize_biome_root(root: Path) -> Path:
    shap_by_biome = root / "shap_by_biome"
    if shap_by_biome.is_dir():
        return shap_by_biome
    return root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--summary-name", default="summary.csv")
    parser.add_argument("--scheme", choices=["prepeak", "recoverywin"], required=True)
    parser.add_argument("--title-prefix", required=True)
    parser.add_argument("--x-feature-short", default="total_precipitation_mean")
    parser.add_argument("--x-label", default="PRE (mm)")
    parser.add_argument("--x-output-suffix", default="PRE")
    parser.add_argument("--color-feature-short", default="temperature_2m_mean")
    parser.add_argument("--color-label", default="TMP (K)")
    parser.add_argument("--color-output-suffix", default="TMP")
    parser.add_argument("--biomes", nargs="+", default=None)
    parser.add_argument("--axis-lower-quantile", type=float, default=0.01)
    parser.add_argument("--axis-upper-quantile", type=float, default=0.99)
    parser.add_argument("--color-lower-quantile", type=float, default=0.05)
    parser.add_argument("--color-upper-quantile", type=float, default=0.95)
    parser.add_argument("--point-alpha", type=float, default=0.55)
    parser.add_argument("--point-size", type=float, default=14.0)
    parser.add_argument("--dpi", type=int, default=220)
    return parser.parse_args()


def build_scheme_feature_name(scheme: str, short_name: str) -> str:
    return f"{scheme}_{short_name}"


def add_trend(ax: plt.Axes, x: np.ndarray, y: np.ndarray) -> None:
    if len(x) < 20:
        return
    order = np.argsort(x)
    x_sorted = x[order]
    y_sorted = y[order]
    window = max(21, len(x_sorted) // 35)
    trend = pd.Series(y_sorted).rolling(window=window, center=True, min_periods=1).mean()
    ax.plot(x_sorted, trend.to_numpy(), color="#c83349", linewidth=2.0, alpha=0.95, zorder=3)


def _mask_from_filtered_pairs(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    filtered_x, filtered_y, _ = batch_dependence_fast_module.filter_local_vertical_shap_outliers(x, y)
    keep = np.zeros(len(x), dtype=bool)
    used = np.zeros(len(x), dtype=bool)
    for fx, fy in zip(filtered_x, filtered_y):
        match = np.where(
            (~used)
            & np.isclose(x, fx, rtol=0.0, atol=1e-12)
            & np.isclose(y, fy, rtol=0.0, atol=1e-12)
        )[0]
        if len(match) == 0:
            continue
        idx = int(match[0])
        keep[idx] = True
        used[idx] = True
    return keep


def infer_feature_scale_factor(feature_short: str, values: np.ndarray) -> float:
    if feature_short not in {"total_precipitation_mean", "total_evaporation_mean"}:
        return 1.0
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return 1.0
    q95 = float(np.nanquantile(np.abs(finite), 0.95))
    if q95 <= 0.05:
        return 1000.0
    return 1.0


def build_filtered_frame(
    sample_df: pd.DataFrame,
    shap_df: pd.DataFrame,
    scheme: str,
    x_feature_short: str,
    color_feature_short: str,
) -> pd.DataFrame:
    x_col = build_scheme_feature_name(scheme, x_feature_short)
    color_col = build_scheme_feature_name(scheme, color_feature_short)
    if x_col not in sample_df.columns or color_col not in sample_df.columns or x_col not in shap_df.columns:
        return pd.DataFrame(columns=["x", "y", "color"])

    x_raw = pd.to_numeric(sample_df[x_col], errors="coerce").to_numpy(dtype=float)
    y_raw = pd.to_numeric(shap_df[x_col], errors="coerce").to_numpy(dtype=float)
    color_raw = pd.to_numeric(sample_df[color_col], errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(x_raw) & np.isfinite(y_raw) & np.isfinite(color_raw)
    x_raw = x_raw[finite]
    y_raw = y_raw[finite]
    color_raw = color_raw[finite]
    if len(x_raw) == 0:
        return pd.DataFrame(columns=["x", "y", "color"])

    x_scale_factor = infer_feature_scale_factor(x_feature_short, x_raw)
    color_scale_factor = infer_feature_scale_factor(color_feature_short, color_raw)
    # Only precipitation receives the hard lower-bound physical filter and low-value cluster protection.
    if x_feature_short == "total_precipitation_mean":
        if x_scale_factor == 1.0:
            valid_x = x_raw >= 0.0
        else:
            valid_x = x_raw >= -1e-12
        x_raw = x_raw[valid_x]
        y_raw = y_raw[valid_x]
        color_raw = color_raw[valid_x]
    if len(x_raw) == 0:
        return pd.DataFrame(columns=["x", "y", "color"])
    protect_mask = np.zeros(len(x_raw), dtype=bool)
    if x_feature_short == "total_precipitation_mean" and x_scale_factor == 1000.0:
        protect_mask = (x_raw >= 0.0) & (x_raw <= 0.002)

    keep_mask = np.zeros(len(x_raw), dtype=bool)
    if protect_mask.any():
        keep_mask[protect_mask] = True
        keep_mask[~protect_mask] = _mask_from_filtered_pairs(x_raw[~protect_mask], y_raw[~protect_mask])
    else:
        keep_mask = _mask_from_filtered_pairs(x_raw, y_raw)

    x_kept = x_raw[keep_mask] * x_scale_factor
    y_kept = y_raw[keep_mask]
    color_kept = color_raw[keep_mask] * color_scale_factor
    return pd.DataFrame({"x": x_kept, "y": y_kept, "color": color_kept})


def compute_axis_limits(values: pd.Series, q_low: float, q_high: float, pad_frac: float) -> tuple[float, float]:
    clean = values.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return (0.0, 1.0)
    low = float(clean.quantile(q_low))
    high = float(clean.quantile(q_high))
    if not np.isfinite(low) or not np.isfinite(high) or low == high:
        low = float(clean.min())
        high = float(clean.max())
    pad = max((high - low) * pad_frac, 1e-9)
    return (low - pad, high + pad)


def compute_color_norm(values: pd.Series, q_low: float, q_high: float) -> Normalize | None:
    clean = values.replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 20:
        return None
    low = float(clean.quantile(q_low))
    high = float(clean.quantile(q_high))
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        return None
    return Normalize(vmin=low, vmax=high, clip=True)


def plot_one_biome(
    biome: str,
    frame: pd.DataFrame,
    output_path: Path,
    title_prefix: str,
    args: argparse.Namespace,
) -> dict[str, object]:
    fig, ax = plt.subplots(figsize=(7.6, 5.8))
    if frame.empty:
        ax.text(0.5, 0.5, "No SHAP data", ha="center", va="center", fontsize=10)
        ax.set_axis_off()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=args.dpi, bbox_inches="tight")
        plt.close(fig)
        return {
            "biome": biome,
            "points": 0,
            "output_path": str(output_path),
        }

    xlim = compute_axis_limits(frame["x"], args.axis_lower_quantile, args.axis_upper_quantile, 0.06)
    ylim = compute_axis_limits(frame["y"], args.axis_lower_quantile, args.axis_upper_quantile, 0.08)
    color_norm = compute_color_norm(frame["color"], args.color_lower_quantile, args.color_upper_quantile)

    sc = ax.scatter(
        frame["x"].to_numpy(dtype=float),
        frame["y"].to_numpy(dtype=float),
        c=frame["color"].to_numpy(dtype=float),
        cmap="viridis",
        norm=color_norm,
        s=args.point_size,
        alpha=args.point_alpha,
        edgecolors="none",
        zorder=2,
    )
    add_trend(ax, frame["x"].to_numpy(dtype=float), frame["y"].to_numpy(dtype=float))
    ax.axhline(0.0, color="#6e6e6e", linewidth=1.0, linestyle="--", alpha=0.8, zorder=1)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xlabel(args.x_label, fontsize=11)
    ax.set_ylabel(f"SHAP value for {args.x_output_suffix}", fontsize=11)
    ax.set_title(
        f"{biome} | {title_prefix} {args.x_output_suffix} dependence colored by {args.color_output_suffix}",
        fontsize=12,
    )
    ax.grid(alpha=0.18, linewidth=0.6)
    cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.02)
    cbar.set_label(args.color_label, fontsize=10)
    cbar.ax.tick_params(labelsize=9)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)

    color_clean = frame["color"].replace([np.inf, -np.inf], np.nan).dropna()
    summary = {
        "biome": biome,
        "points": int(len(frame)),
        "output_path": str(output_path),
        "x_min": xlim[0],
        "x_max": xlim[1],
        "y_min": ylim[0],
        "y_max": ylim[1],
        "color_feature_short": args.color_feature_short,
        "color_label": args.color_label,
        "color_raw_min": float(color_clean.min()) if not color_clean.empty else np.nan,
        "color_raw_max": float(color_clean.max()) if not color_clean.empty else np.nan,
        "x_feature_short": args.x_feature_short,
        "x_label": args.x_label,
        "color_clip_lower_quantile": args.color_lower_quantile,
        "color_clip_upper_quantile": args.color_upper_quantile,
    }
    if color_norm is not None:
        summary["color_clip_min"] = float(color_norm.vmin)
        summary["color_clip_max"] = float(color_norm.vmax)
    return summary


def main() -> None:
    args = parse_args()
    input_root = normalize_biome_root(Path(args.input_root))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    biomes = args.biomes if args.biomes else list(BIOMES)

    rows: list[dict[str, object]] = []
    for biome in biomes:
        sample_df = pd.read_parquet(input_root / biome / "dependence_sample_features.parquet")
        shap_df = pd.read_parquet(input_root / biome / "dependence_sample_shap_values.parquet")
        frame = build_filtered_frame(
            sample_df,
            shap_df,
            args.scheme,
            args.x_feature_short,
            args.color_feature_short,
        )
        rows.append(
            plot_one_biome(
                biome=biome,
                frame=frame,
                output_path=output_dir / f"{biome}_{args.scheme}_{args.x_output_suffix}_colored_by_{args.color_output_suffix}.png",
                title_prefix=args.title_prefix,
                args=args,
            )
        )

    pd.DataFrame(rows).to_csv(output_dir / args.summary_name, index=False)


if __name__ == "__main__":
    main()
