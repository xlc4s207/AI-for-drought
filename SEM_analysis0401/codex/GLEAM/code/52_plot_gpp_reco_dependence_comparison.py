#!/usr/bin/env python3
"""Plot side-by-side GPP vs RECO prepeak dependence comparisons by biome."""

from __future__ import annotations

from pathlib import Path
import importlib.util

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
PLOTS2_SCRIPT = SCRIPT_DIR / "48_redraw_prepeak_shap_plots2.py"
SPEC = importlib.util.spec_from_file_location("plots2_prepeak_redraw", PLOTS2_SCRIPT)
assert SPEC is not None
PLOTS2 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PLOTS2)

COMPARISON_ROOT = PLOTS2.OUTPUT_ROOT / "dependence_compare_gpp_vs_reco"
COMBINED_ROOT = COMPARISON_ROOT / "combined_by_biome"
COMBINED_VARIANT_ROOT = COMPARISON_ROOT / "combined_by_biome_no_lai_with_intensity"
COMPARISON_FEATURES = [
    "prepeak_total_precipitation_mean",
    "prepeak_total_evaporation_mean",
    "prepeak_temperature_2m_mean",
    "prepeak_VPD_mean",
    "prepeak_SMrz_mean",
    "prepeak_lai_total_mean",
    "prepeak_ssrd_mean",
    "prepeak_strd_mean",
    "prepeak_wind_speed_mean",
    "event_onset_days",
    "event_duration",
    "event_intensity",
]
COMBINED_EXCLUDED_FEATURES = {"event_onset_days", "event_intensity"}
COMBINED_FEATURES = [feature for feature in COMPARISON_FEATURES if feature not in COMBINED_EXCLUDED_FEATURES]
COMBINED_VARIANT_EXCLUDED_FEATURES = {"event_onset_days", "prepeak_lai_total_mean"}
COMBINED_VARIANT_FEATURES = [
    feature for feature in COMPARISON_FEATURES if feature not in COMBINED_VARIANT_EXCLUDED_FEATURES
]
COMBINED_CLIPPED_BIOMES = {"Cropland", "Forest"}
COMBINED_USE_COLOR_MAPPING = False


def comparison_output_path(biome: str, feature: str) -> Path:
    return COMPARISON_ROOT / biome / f"{PLOTS2.short_label(feature)}_gpp_vs_reco.png"


def combined_output_path(biome: str) -> Path:
    return COMBINED_ROOT / f"{biome}_all_features_gpp_vs_reco.png"


def combined_variant_output_path(biome: str) -> Path:
    return COMBINED_VARIANT_ROOT / f"{biome}_no_lai_with_intensity_gpp_vs_reco.png"


def combined_layout_shape(features: list[str] | None = None) -> tuple[int, int]:
    return len(features if features is not None else COMBINED_FEATURES), 2


def display_feature_values(frame: pd.DataFrame, feature: str) -> tuple[np.ndarray, str]:
    values = pd.to_numeric(frame[feature], errors="coerce").to_numpy(dtype=float)
    values, unit = PLOTS2.convert_feature_units(feature, values)
    values = PLOTS2.transform_dependence_display_values(feature, values)
    return values, unit


def display_label(feature: str) -> str:
    label = PLOTS2.short_label(feature)
    if PLOTS2.is_eva_feature(feature):
        return f"|{label}|"
    return label


def finite_limits(values: list[np.ndarray], q_low: float, q_high: float, pad_frac: float) -> tuple[float, float]:
    merged = np.concatenate([v[np.isfinite(v)] for v in values if len(v) > 0])
    if len(merged) == 0:
        return 0.0, 1.0
    low, high = np.nanquantile(merged, [q_low, q_high])
    if not np.isfinite(low) or not np.isfinite(high) or low == high:
        low = float(np.nanmin(merged))
        high = float(np.nanmax(merged))
    pad = max((high - low) * pad_frac, 1e-9)
    return float(low - pad), float(high + pad)


def plotted_x_limits(x_color_pairs: list[tuple[np.ndarray, np.ndarray]], pad_frac: float = 0.03) -> tuple[float, float]:
    plotted = []
    for x, color in x_color_pairs:
        mask = np.isfinite(x) & np.isfinite(color)
        if np.any(mask):
            plotted.append(x[mask])
    if not plotted:
        return 0.0, 1.0
    merged = np.concatenate(plotted)
    low = float(np.nanmin(merged))
    high = float(np.nanmax(merged))
    if not np.isfinite(low) or not np.isfinite(high):
        return 0.0, 1.0
    if low == high:
        pad = max(abs(low) * pad_frac, 1e-9)
    else:
        pad = max((high - low) * pad_frac, 1e-9)
    return low - pad, high + pad


def feature_color_values(x: np.ndarray, clip_tails: bool) -> np.ndarray:
    if clip_tails:
        return PLOTS2.clip_two_sided_color_tail(x, low_q=0.05, high_q=0.95)
    return x.copy()


def add_trend(ax: plt.Axes, x: np.ndarray, y: np.ndarray) -> None:
    if len(x) < 30:
        return
    order = np.argsort(x)
    xs = x[order]
    ys = y[order]
    window = max(21, len(xs) // 20)
    trend = pd.Series(ys).rolling(window=window, center=True, min_periods=max(5, window // 5)).median()
    ax.plot(xs, trend.to_numpy(), color="#c83349", linewidth=2.0, alpha=0.92)


def plot_metric_panel(
    ax: plt.Axes,
    metric: str,
    biome: str,
    feature: str,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    color_limits: tuple[float, float],
) -> int:
    data = PLOTS2.load_biome(metric, biome)
    x, unit = display_feature_values(data.sample, feature)
    y = pd.to_numeric(data.shap[feature], errors="coerce").to_numpy(dtype=float)
    color = PLOTS2.clip_two_sided_color_tail(x, low_q=0.05, high_q=0.95)
    valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(color)
    x = x[valid]
    y = y[valid]
    color = color[valid]
    if len(x) > 4000:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(x), size=4000, replace=False)
        x = x[idx]
        y = y[idx]
        color = color[idx]
    sc = ax.scatter(
        x,
        y,
        c=color,
        cmap="viridis",
        vmin=color_limits[0],
        vmax=color_limits[1],
        s=10,
        alpha=0.55,
        linewidths=0,
        rasterized=True,
    )
    add_trend(ax, x, y)
    ax.axhline(0.0, color="#666666", linestyle="--", linewidth=0.9, alpha=0.8)
    label = display_label(feature)
    ax.set_xlabel(label + (f" ({unit})" if unit else ""), fontsize=10)
    ax.set_ylabel(f"SHAP value for {label}", fontsize=10)
    ax.set_title(f"{metric} | {biome}", fontsize=10)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.grid(alpha=0.16, linestyle="--")
    cbar = plt.colorbar(sc, ax=ax, pad=0.02)
    cbar_label = label + (f" ({unit})" if unit else "")
    cbar.set_label(cbar_label, fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    return int(valid.sum())


def plot_metric_panel_compact(
    ax: plt.Axes,
    metric: str,
    biome: str,
    feature: str,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    color_limits: tuple[float, float],
    clip_tails: bool = True,
    use_color_mapping: bool = True,
) -> int:
    data = PLOTS2.load_biome(metric, biome)
    x, unit = display_feature_values(data.sample, feature)
    y = pd.to_numeric(data.shap[feature], errors="coerce").to_numpy(dtype=float)
    color = feature_color_values(x, clip_tails=clip_tails)
    valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(color)
    x = x[valid]
    y = y[valid]
    color = color[valid]
    if len(x) > 2500:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(x), size=2500, replace=False)
        x = x[idx]
        y = y[idx]
        color = color[idx]
    scatter_kwargs = {
        "s": 6,
        "alpha": 0.48,
        "linewidths": 0,
        "rasterized": True,
    }
    if use_color_mapping:
        scatter_kwargs.update(
            {
                "c": color,
                "cmap": "viridis",
                "vmin": color_limits[0],
                "vmax": color_limits[1],
            }
        )
    else:
        scatter_kwargs["color"] = "#4b79a8"
    ax.scatter(x, y, **scatter_kwargs)
    add_trend(ax, x, y)
    ax.axhline(0.0, color="#666666", linestyle="--", linewidth=0.75, alpha=0.8)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.grid(alpha=0.14, linestyle="--", linewidth=0.5)
    ax.tick_params(labelsize=6.5)
    if unit:
        ax.set_xlabel(f"{display_label(feature)} ({unit})", fontsize=7.5)
    else:
        ax.set_xlabel(display_label(feature), fontsize=7.5)
    return int(valid.sum())


def plot_biome_feature(biome: str, feature: str) -> dict[str, object]:
    metric_values = {}
    for metric in ["GPP", "RECO"]:
        data = PLOTS2.load_biome(metric, biome)
        x, _ = display_feature_values(data.sample, feature)
        y = pd.to_numeric(data.shap[feature], errors="coerce").to_numpy(dtype=float)
        color = PLOTS2.clip_two_sided_color_tail(x, low_q=0.05, high_q=0.95)
        metric_values[metric] = (x, y, color)

    xlim = plotted_x_limits(
        [
            (metric_values["GPP"][0], metric_values["GPP"][2]),
            (metric_values["RECO"][0], metric_values["RECO"][2]),
        ]
    )
    ylim = finite_limits([metric_values["GPP"][1], metric_values["RECO"][1]], 0.01, 0.99, 0.08)
    color_limits = finite_limits([metric_values["GPP"][2], metric_values["RECO"][2]], 0.00, 1.00, 0.0)

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.4), sharex=True, sharey=True)
    points = {}
    for ax, metric in zip(axes, ["GPP", "RECO"], strict=True):
        points[metric] = plot_metric_panel(ax, metric, biome, feature, xlim, ylim, color_limits)
    fig.suptitle(f"{biome} | {display_label(feature)} dependence: GPP vs RECO", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.955])
    output_path = comparison_output_path(biome, feature)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return {
        "biome": biome,
        "feature": feature,
        "label": display_label(feature),
        "gpp_points": points["GPP"],
        "reco_points": points["RECO"],
        "output_png": str(output_path),
    }


def metric_values_for_feature(
    metric: str,
    biome: str,
    feature: str,
    clip_tails: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    data = PLOTS2.load_biome(metric, biome)
    x, _ = display_feature_values(data.sample, feature)
    y = pd.to_numeric(data.shap[feature], errors="coerce").to_numpy(dtype=float)
    color = feature_color_values(x, clip_tails=clip_tails)
    return x, y, color


def combined_clip_tails_for_biome(biome: str) -> bool:
    return biome in COMBINED_CLIPPED_BIOMES


def plot_biome_combined(
    biome: str,
    features: list[str] | None = None,
    output_path: Path | None = None,
    variant_name: str = "combined_by_biome",
) -> list[dict[str, object]]:
    features = features if features is not None else COMBINED_FEATURES
    output_path = output_path if output_path is not None else combined_output_path(biome)
    clip_tails = combined_clip_tails_for_biome(biome)
    nrows, ncols = combined_layout_shape(features)
    fig, axes = plt.subplots(nrows, ncols, figsize=(13.4, 2.35 * nrows), sharex=False, sharey=False)
    rows: list[dict[str, object]] = []
    for row_idx, feature in enumerate(features):
        metric_values = {
            "GPP": metric_values_for_feature("GPP", biome, feature, clip_tails=clip_tails),
            "RECO": metric_values_for_feature("RECO", biome, feature, clip_tails=clip_tails),
        }
        xlim = plotted_x_limits(
            [
                (metric_values["GPP"][0], metric_values["GPP"][2]),
                (metric_values["RECO"][0], metric_values["RECO"][2]),
            ]
        )
        ylim = finite_limits([metric_values["GPP"][1], metric_values["RECO"][1]], 0.01, 0.99, 0.08)
        color_limits = finite_limits([metric_values["GPP"][2], metric_values["RECO"][2]], 0.00, 1.00, 0.0)
        label = display_label(feature)
        for col_idx, metric in enumerate(["GPP", "RECO"]):
            ax = axes[row_idx, col_idx]
            points = plot_metric_panel_compact(
                ax,
                metric,
                biome,
                feature,
                xlim,
                ylim,
                color_limits,
                clip_tails=clip_tails,
                use_color_mapping=COMBINED_USE_COLOR_MAPPING,
            )
            ax.set_title(f"{metric} | {label}", fontsize=8.5)
            if col_idx == 0:
                ax.set_ylabel(f"SHAP for {label}", fontsize=7.5)
            rows.append(
                {
                    "biome": biome,
                    "metric": metric,
                    "feature": feature,
                    "label": label,
                    "points": points,
                    "clip_tails": clip_tails,
                    "color_mapping": COMBINED_USE_COLOR_MAPPING,
                    "variant": variant_name,
                    "output_png": str(output_path),
                }
            )
    fig.suptitle(f"{biome} | All-feature dependence comparison: GPP vs RECO", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.988])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return rows


def main() -> None:
    rows = []
    combined_rows = []
    combined_variant_rows = []
    for biome in PLOTS2.BIOMES:
        combined_rows.extend(plot_biome_combined(biome))
        combined_variant_rows.extend(
            plot_biome_combined(
                biome,
                features=COMBINED_VARIANT_FEATURES,
                output_path=combined_variant_output_path(biome),
                variant_name="combined_by_biome_no_lai_with_intensity",
            )
        )
        for feature in COMPARISON_FEATURES:
            rows.append(plot_biome_feature(biome, feature))
    COMPARISON_ROOT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(COMPARISON_ROOT / "dependence_compare_index.csv", index=False)
    pd.DataFrame(combined_rows).to_csv(COMBINED_ROOT / "combined_dependence_compare_index.csv", index=False)
    pd.DataFrame(combined_variant_rows).to_csv(
        COMBINED_VARIANT_ROOT / "combined_dependence_compare_index.csv", index=False
    )
    (COMBINED_VARIANT_ROOT / "README.txt").write_text(
        "\n".join(
            [
                "Variant combined GPP vs RECO dependence figures.",
                "This version removes LAI and includes event intensity.",
                "It still excludes event onset.",
                "Combined figures use a uniform point color without feature-value color mapping.",
                "Forest and Cropland use two-sided 5%-95% feature tail clipping to suppress extreme PRE outliers.",
                "Other biomes keep the full displayed feature range.",
            ]
        ),
        encoding="utf-8",
    )
    (COMPARISON_ROOT / "README.txt").write_text(
        "\n".join(
            [
                "GPP vs RECO prepeak dependence comparison figures.",
                "combined_by_biome/: one large PNG per biome with selected dependence features.",
                "combined_by_biome excludes event onset and event intensity rows.",
                "combined_by_biome_no_lai_with_intensity/: one large PNG per biome, excluding LAI and onset but including event intensity.",
                "biome subfolders: one PNG per biome and feature.",
                "Each figure uses shared x/y limits across GPP and RECO panels.",
                "Forest and Cropland combined figures use two-sided 5%-95% feature tail clipping to suppress extreme PRE outliers.",
                "Other combined figures keep the full displayed feature range.",
                "Combined figures use a uniform point color without feature-value color mapping.",
                "Biome subfolder figures use two-sided 5%-95% feature tail clipping.",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
