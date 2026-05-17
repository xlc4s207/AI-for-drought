#!/usr/bin/env python3
"""Create pooled all-biome prepeak SHAP beeswarm and dependence figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
OVERALL_ROOT = ROOT / "results/overall_shap_results_20260502"
OUT = ROOT / "plots2/prepeak_shap_summary_20260502/overall_all_biomes"
METRICS = {
    "GPP": OVERALL_ROOT / "gpp_prepeak",
    "RECO": OVERALL_ROOT / "reco_prepeak",
}
FIXED_FEATURES = [
    "prepeak_ssrd_mean",
    "prepeak_total_evaporation_mean",
    "prepeak_temperature_2m_mean",
    "prepeak_strd_mean",
    "prepeak_SMrz_mean",
    "prepeak_wind_speed_mean",
    "prepeak_VPD_mean",
    "event_duration",
    "prepeak_total_precipitation_mean",
    "event_intensity",
]
LABELS = {
    "prepeak_total_precipitation_mean": "PRE",
    "prepeak_total_evaporation_mean": "|EVA|",
    "prepeak_temperature_2m_mean": "TMP",
    "prepeak_VPD_mean": "VPD",
    "prepeak_SMrz_mean": "SMrz",
    "prepeak_lai_total_mean": "LAI",
    "prepeak_ssrd_mean": "SSRD",
    "prepeak_strd_mean": "STRD",
    "prepeak_wind_speed_mean": "WIND",
    "event_onset_days": "Onset",
    "event_duration": "Duration",
    "event_intensity": "Intensity",
}


def label(feature: str) -> str:
    return LABELS.get(feature, feature)


def is_eva(feature: str) -> bool:
    return "evaporation" in feature


def convert_units(feature: str, values: np.ndarray) -> tuple[np.ndarray, str]:
    values = np.asarray(values, dtype=float)
    if "precipitation" in feature:
        finite = values[np.isfinite(values)]
        if len(finite) and np.nanquantile(np.abs(finite), 0.99) < 1.0:
            return values * 1000.0, "mm"
        return values, "mm"
    if "evaporation" in feature:
        vals = np.abs(values)
        finite = vals[np.isfinite(vals)]
        if len(finite) and np.nanquantile(np.abs(finite), 0.99) < 1.0:
            return vals * 1000.0, "mm"
        return vals, "mm"
    if feature == "prepeak_temperature_2m_mean":
        return values, "K"
    if feature == "prepeak_VPD_mean":
        return values / 10.0, "kPa"
    if feature == "prepeak_SMrz_mean":
        return values, "m3/m3"
    if feature == "event_duration":
        return values, "days"
    return values, ""


def clip_color(values: np.ndarray, low_q: float = 0.05, high_q: float = 0.95) -> np.ndarray:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return values
    low, high = np.nanquantile(finite, [low_q, high_q])
    out = values.copy()
    out[(out <= low) | (out >= high)] = np.nan
    return out


def load_overall(metric: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root = METRICS[metric]
    sample = pd.read_parquet(root / "overall_dependence_sample_features.parquet")
    shap_values = pd.read_parquet(root / "overall_dependence_sample_shap_values.parquet")
    importance = pd.read_csv(root / "overall_feature_importance.csv")
    return sample, shap_values, importance


def prepare_beeswarm(sample: pd.DataFrame, shap_values: pd.DataFrame, top_n: int = 10) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    features = [f for f in FIXED_FEATURES[:top_n] if f in sample.columns and f in shap_values.columns]
    frame = sample[features].copy()
    for feature in features:
        vals = pd.to_numeric(frame[feature], errors="coerce").to_numpy(dtype=float)
        vals, _ = convert_units(feature, vals)
        frame[feature] = vals
    frame.columns = [label(f) for f in features]
    shap_matrix = shap_values[features].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    return frame, shap_matrix, [label(f) for f in features]


def plot_beeswarm() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 5.8))
    for ax, metric in zip(axes, ["GPP", "RECO"], strict=True):
        sample, shap_values, importance = load_overall(metric)
        del importance
        frame, shap_matrix, names = prepare_beeswarm(sample, shap_values, top_n=10)
        plt.sca(ax)
        shap.summary_plot(
            shap_values=shap_matrix,
            features=frame,
            feature_names=names,
            plot_type="dot",
            max_display=len(names),
            sort=True,
            show=False,
            plot_size=None,
        )
        ax.set_title(f"{metric} | all five biomes", fontsize=12)
    fig.suptitle("Overall pre-event SHAP beeswarm across all five biomes", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "overall_all_biomes_beeswarm_gpp_vs_reco.png", dpi=240, bbox_inches="tight")
    plt.close(fig)


def color_feature_for(feature: str) -> str:
    if feature == "prepeak_total_evaporation_mean":
        return "prepeak_VPD_mean"
    if feature == "prepeak_total_precipitation_mean":
        return "event_duration"
    if feature == "prepeak_temperature_2m_mean":
        return "prepeak_VPD_mean"
    return "prepeak_total_evaporation_mean"


def robust_xlim(values: np.ndarray) -> tuple[float, float]:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return 0.0, 1.0
    lo, hi = np.nanquantile(finite, [0.01, 0.99])
    pad = max((hi - lo) * 0.04, 1e-9)
    return float(lo - pad), float(hi + pad)


def plot_dependence_panel(
    ax: plt.Axes,
    sample: pd.DataFrame,
    shap_values: pd.DataFrame,
    feature: str,
    metric: str,
) -> None:
    color_feature = color_feature_for(feature)
    x = pd.to_numeric(sample[feature], errors="coerce").to_numpy(dtype=float)
    x, unit = convert_units(feature, x)
    y = pd.to_numeric(shap_values[feature], errors="coerce").to_numpy(dtype=float)
    c = pd.to_numeric(sample[color_feature], errors="coerce").to_numpy(dtype=float)
    c, c_unit = convert_units(color_feature, c)
    c = clip_color(c)
    valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(c)
    x = x[valid]
    y = y[valid]
    c = c[valid]
    if len(x) > 5000:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(x), size=5000, replace=False)
        x = x[idx]
        y = y[idx]
        c = c[idx]
    sc = ax.scatter(x, y, c=c, cmap="viridis", s=8, alpha=0.48, linewidths=0, rasterized=True)
    if len(x) >= 30:
        order = np.argsort(x)
        xs = x[order]
        ys = y[order]
        window = max(31, len(xs) // 22)
        trend = pd.Series(ys).rolling(window=window, center=True, min_periods=max(7, window // 5)).median()
        ax.plot(xs, trend.to_numpy(), color="#c83349", linewidth=1.9)
    ax.axhline(0.0, color="#666666", linestyle="--", linewidth=0.8, alpha=0.75)
    ax.set_xlim(*robust_xlim(x))
    ax.set_title(f"{metric} | {label(feature)}", fontsize=10)
    ax.set_xlabel(f"{label(feature)} ({unit})" if unit else label(feature), fontsize=9)
    ax.set_ylabel("SHAP value", fontsize=9)
    ax.grid(alpha=0.14, linestyle="--")
    cbar = plt.colorbar(sc, ax=ax, pad=0.012)
    cbar.set_label(f"{label(color_feature)} ({c_unit})" if c_unit else label(color_feature), fontsize=8)
    cbar.ax.tick_params(labelsize=7)


def plot_dependence() -> pd.DataFrame:
    rows = []
    for metric in ["GPP", "RECO"]:
        sample, shap_values, importance = load_overall(metric)
        features = [f for f in importance.sort_values("rank")["feature"].tolist() if f in FIXED_FEATURES][:10]
        ncols = 5
        nrows = int(np.ceil(len(features) / ncols))
        fig, axes = plt.subplots(nrows, ncols, figsize=(20, 3.6 * nrows))
        axes = np.asarray(axes).reshape(-1)
        for ax, feature in zip(axes, features, strict=False):
            plot_dependence_panel(ax, sample, shap_values, feature, metric)
            rows.append(
                {
                    "metric": metric,
                    "feature": feature,
                    "label": label(feature),
                    "color_feature": color_feature_for(feature),
                    "color_label": label(color_feature_for(feature)),
                    "output": str(OUT / f"{metric.lower()}_overall_all_biomes_dependence_top10.png"),
                }
            )
        for ax in axes[len(features) :]:
            ax.axis("off")
        fig.suptitle(f"{metric} overall SHAP dependence across all five biomes", fontsize=15)
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        fig.savefig(OUT / f"{metric.lower()}_overall_all_biomes_dependence_top10.png", dpi=240, bbox_inches="tight")
        plt.close(fig)
    index = pd.DataFrame(rows)
    index.to_csv(OUT / "overall_all_biomes_dependence_index.csv", index=False)
    return index


def save_importance_summary() -> None:
    rows = []
    for metric in ["GPP", "RECO"]:
        _, _, importance = load_overall(metric)
        work = importance.copy()
        work["metric"] = metric
        work["display_label"] = work["feature"].map(label)
        total = float(work["importance"].sum())
        work["percent"] = np.where(total > 0, work["importance"] / total * 100.0, np.nan)
        rows.append(work)
    pd.concat(rows, ignore_index=True).to_csv(OUT / "overall_all_biomes_feature_importance.csv", index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plot_beeswarm()
    save_importance_summary()
    plot_dependence()
    (OUT / "README.md").write_text(
        "\n".join(
            [
                "# Overall all-biome prepeak SHAP summary",
                "",
                "This folder pools the five main biomes and provides overall GPP/RECO SHAP visualizations.",
                "",
                "Outputs:",
                "- overall_all_biomes_beeswarm_gpp_vs_reco.png",
                "- gpp_overall_all_biomes_dependence_top10.png",
                "- reco_overall_all_biomes_dependence_top10.png",
                "- overall_all_biomes_feature_importance.csv",
            ]
        ),
        encoding="utf-8",
    )
    print(OUT)


if __name__ == "__main__":
    main()
