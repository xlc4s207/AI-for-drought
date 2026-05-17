#!/usr/bin/env python3
"""Build combined beeswarm and dependence figures for orthogonal SHAP results."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from matplotlib.colors import TwoSlopeNorm
from matplotlib.cm import ScalarMappable


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_shap_nomulticollinearity")
ORTHO = ROOT / "orthogonal_decomposition"
OUT = ORTHO / "combined_figures"

BIOMES = ["Forest", "Grassland", "Savanna", "Cropland", "Shrubland"]
METRICS = ["GPP", "RECO"]

FEATURE_ORDER = [
    "SSRD_z",
    "EVA_resid_after_SSRD_Pre_VPD",
    "TMP_resid_after_SSRD_STRD",
    "VPD_resid_after_SSRD_TMP_Wind",
    "SMrz_resid_after_Pre_EVA",
    "Pre_z",
    "STRD_resid_after_SSRD",
    "Wind_z",
    "Duration_z",
    "Intensity_z",
]

DISPLAY_LABELS = {
    "SSRD_z": "SSRD",
    "Pre_z": "Pre",
    "Duration_z": "Duration",
    "Intensity_z": "Intensity",
    "Wind_z": "Wind",
    "STRD_resid_after_SSRD": "STRD_resid",
    "TMP_resid_after_SSRD_STRD": "TMP_resid",
    "VPD_resid_after_SSRD_TMP_Wind": "VPD_resid",
    "EVA_resid_after_SSRD_Pre_VPD": "EVA_resid",
    "SMrz_resid_after_Pre_EVA": "SMrz_resid",
}

COLOR_BY_MAP = {
    "SSRD_z": "EVA_resid_after_SSRD_Pre_VPD",
    "EVA_resid_after_SSRD_Pre_VPD": "VPD_resid_after_SSRD_TMP_Wind",
    "TMP_resid_after_SSRD_STRD": "VPD_resid_after_SSRD_TMP_Wind",
    "VPD_resid_after_SSRD_TMP_Wind": "SMrz_resid_after_Pre_EVA",
    "SMrz_resid_after_Pre_EVA": "Pre_z",
    "Pre_z": "Duration_z",
    "STRD_resid_after_SSRD": "TMP_resid_after_SSRD_STRD",
    "Wind_z": "VPD_resid_after_SSRD_TMP_Wind",
    "Duration_z": "Pre_z",
    "Intensity_z": "Duration_z",
}

ENERGY_FEATURES = [
    "SSRD_z",
    "STRD_resid_after_SSRD",
    "TMP_resid_after_SSRD_STRD",
]
WATER_FEATURES = [
    "EVA_resid_after_SSRD_Pre_VPD",
    "SMrz_resid_after_Pre_EVA",
    "VPD_resid_after_SSRD_TMP_Wind",
    "Pre_z",
]
EVENT_FEATURES = [
    "Duration_z",
    "Intensity_z",
]
ATMOS_FEATURES = [
    "Wind_z",
]


def load_bundle(metric: str, biome: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    folder = ORTHO / metric / biome
    features = pd.read_parquet(folder / "dependence_sample_features.parquet")
    shap_values = pd.read_parquet(folder / "dependence_sample_shap_values.parquet")
    importance = pd.read_csv(folder / "feature_importance.csv")
    return features, shap_values, importance


def robust_limits(values: np.ndarray, q_low: float = 0.01, q_high: float = 0.99) -> tuple[float, float]:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return -1.0, 1.0
    lo, hi = np.nanquantile(vals, [q_low, q_high])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        mid = float(np.nanmedian(vals)) if len(vals) else 0.0
        return mid - 1.0, mid + 1.0
    pad = (hi - lo) * 0.04
    return float(lo - pad), float(hi + pad)


def expanded_shap_limits(values: np.ndarray) -> tuple[float, float]:
    """Wider x limits for beeswarm panels so edge SHAP values are not clipped."""
    lo, hi = robust_limits(values, 0.001, 0.999)
    span = hi - lo
    if not np.isfinite(span) or span <= 0:
        return lo, hi
    pad = span * 0.12
    lo -= pad
    hi += pad
    if lo > 0:
        lo = 0.0
    if hi < 0:
        hi = 0.0
    return float(lo), float(hi)


def binned_trend(x: np.ndarray, y: np.ndarray, bins: int = 32) -> tuple[np.ndarray, np.ndarray]:
    finite = np.isfinite(x) & np.isfinite(y)
    x = x[finite]
    y = y[finite]
    if len(x) < 30:
        order = np.argsort(x)
        return x[order], y[order]
    edges = np.unique(np.nanquantile(x, np.linspace(0, 1, bins + 1)))
    xs: list[float] = []
    ys: list[float] = []
    for left, right in zip(edges[:-1], edges[1:]):
        if right <= left:
            continue
        mask = (x >= left) & (x <= right if right == edges[-1] else x < right)
        if mask.sum() < 8:
            continue
        xs.append(float(np.nanmedian(x[mask])))
        ys.append(float(np.nanmedian(y[mask])))
    return np.asarray(xs), np.asarray(ys)


def clip_xy(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    finite = np.isfinite(x) & np.isfinite(y)
    x = x[finite]
    y = y[finite]
    if len(x) < 10:
        return x, y
    xlo, xhi = np.nanquantile(x, [0.01, 0.99])
    ylo, yhi = np.nanquantile(y, [0.005, 0.995])
    mask = (x >= xlo) & (x <= xhi) & (y >= ylo) & (y <= yhi)
    return x[mask], y[mask]


def plot_combined_beeswarm() -> Path:
    fig, axes = plt.subplots(len(BIOMES), len(METRICS), figsize=(15.2, 18.5), sharex=False)
    cmap = plt.get_cmap("coolwarm")
    norm = TwoSlopeNorm(vmin=-2.5, vcenter=0.0, vmax=2.5)
    for i, biome in enumerate(BIOMES):
        for j, metric in enumerate(METRICS):
            ax = axes[i, j]
            X, S, imp = load_bundle(metric, biome)
            order = imp["feature"].tolist()
            labels = [DISPLAY_LABELS.get(f, f) for f in order]
            features = X[order].apply(pd.to_numeric, errors="coerce").clip(-2.5, 2.5)
            features.columns = labels
            shap_matrix = S[order].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
            finite_rows = np.isfinite(shap_matrix).all(axis=1) & np.isfinite(features.to_numpy(dtype=float)).all(axis=1)
            shap_matrix = shap_matrix[finite_rows]
            features = features.loc[finite_rows]
            # Use SHAP's own beeswarm packing instead of manual jitter, while keeping
            # the project-level coolwarm color scale and the existing 5x2 layout.
            plt.sca(ax)
            shap.summary_plot(
                shap_matrix,
                features,
                feature_names=labels,
                max_display=len(order),
                plot_type="dot",
                sort=False,
                color_bar=False,
                show=False,
                plot_size=None,
                cmap=cmap,
                alpha=0.72,
                rng=np.random.default_rng(42 + i * len(METRICS) + j),
            )
            ax.axvline(0, color="#6f6f6f", lw=0.8, ls="--", alpha=0.85)
            ax.tick_params(axis="y", labelsize=8)
            ax.tick_params(axis="x", labelsize=8)
            ax.grid(axis="x", alpha=0.16, ls="--", lw=0.6)
            ax.set_title(f"{biome} - {metric}", fontsize=11, fontweight="bold")
            if i == len(BIOMES) - 1:
                ax.set_xlabel("SHAP value for recovery time", fontsize=9)
            else:
                ax.set_xlabel("")
            xlim = expanded_shap_limits(
                np.concatenate([pd.to_numeric(S[f], errors="coerce").to_numpy(dtype=float) for f in order])
            )
            ax.set_xlim(xlim)
    fig.suptitle("Orthogonal decomposition SHAP beeswarm comparison: GPP vs RECO across biomes", fontsize=15, fontweight="bold", y=0.995)
    fig.subplots_adjust(left=0.09, right=0.895, top=0.965, bottom=0.055, hspace=0.37, wspace=0.24)
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cax = fig.add_axes([0.925, 0.12, 0.015, 0.75])
    cbar = fig.colorbar(sm, cax=cax)
    cbar.set_label("Transformed feature value\n(z-score / residual z-score)", fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    out = OUT / "orthogonal_beeswarm_comparison_5biomes_gpp_vs_reco.png"
    out_alt = OUT / "orthogonal_beeswarm_comparison_5biomes_gpp_vs_reco_shap_summary.png"
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=260)
    fig.savefig(out_alt, dpi=260)
    plt.close(fig)
    return out


def plot_dependence_panel(ax: plt.Axes, X: pd.DataFrame, S: pd.DataFrame, feature: str, metric: str) -> None:
    x = pd.to_numeric(X[feature], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(S[feature], errors="coerce").to_numpy(dtype=float)
    x, y = clip_xy(x, y)
    ax.scatter(x, y, s=5.0, alpha=0.22, color="#315f86", linewidths=0, rasterized=True)
    tx, ty = binned_trend(x, y)
    if len(tx) > 1:
        ax.plot(tx, ty, color="#bf3b3b", lw=1.65)
    ax.axhline(0, color="#747474", lw=0.75, ls="--", alpha=0.85)
    ax.set_xlim(*robust_limits(x))
    ax.set_ylim(*robust_limits(y, 0.005, 0.995))
    ax.grid(alpha=0.15, ls="--", lw=0.55)
    ax.tick_params(labelsize=7)
    ax.set_title(metric, fontsize=9, fontweight="bold", pad=2)
    ax.set_xlabel(DISPLAY_LABELS.get(feature, feature), fontsize=8)
    ax.set_ylabel("SHAP value", fontsize=8)


def robust_color_values(values: np.ndarray, q_low: float = 0.02, q_high: float = 0.98) -> tuple[np.ndarray, float, float]:
    vals = np.asarray(values, dtype=float)
    finite = vals[np.isfinite(vals)]
    if len(finite) == 0:
        return vals, -1.0, 1.0
    lo, hi = np.nanquantile(finite, [q_low, q_high])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = float(np.nanmedian(finite) - 1.0), float(np.nanmedian(finite) + 1.0)
    return np.clip(vals, lo, hi), float(lo), float(hi)


def plot_colored_dependence_panel(
    ax: plt.Axes,
    X: pd.DataFrame,
    S: pd.DataFrame,
    feature: str,
    color_feature: str,
    metric: str,
    add_colorbar: bool = False,
) -> None:
    x = pd.to_numeric(X[feature], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(S[feature], errors="coerce").to_numpy(dtype=float)
    c = pd.to_numeric(X[color_feature], errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(c)
    x = x[finite]
    y = y[finite]
    c = c[finite]
    if len(x) >= 10:
        xlo, xhi = np.nanquantile(x, [0.01, 0.99])
        ylo, yhi = np.nanquantile(y, [0.005, 0.995])
        mask = (x >= xlo) & (x <= xhi) & (y >= ylo) & (y <= yhi)
        x, y, c = x[mask], y[mask], c[mask]
    c_clip, clo, chi = robust_color_values(c)
    sc = ax.scatter(
        x,
        y,
        c=c_clip,
        s=5.5,
        alpha=0.42,
        cmap="RdYlGn_r",
        vmin=clo,
        vmax=chi,
        linewidths=0,
        rasterized=True,
    )
    tx, ty = binned_trend(x, y)
    if len(tx) > 1:
        ax.plot(tx, ty, color="#202020", lw=1.5)
    ax.axhline(0, color="#747474", lw=0.75, ls="--", alpha=0.85)
    ax.set_xlim(*robust_limits(x))
    ax.set_ylim(*robust_limits(y, 0.005, 0.995))
    ax.grid(alpha=0.15, ls="--", lw=0.55)
    ax.tick_params(labelsize=7)
    ax.set_title(f"{metric} | color: {DISPLAY_LABELS.get(color_feature, color_feature)}", fontsize=8.2, fontweight="bold", pad=2)
    ax.set_xlabel(DISPLAY_LABELS.get(feature, feature), fontsize=8)
    ax.set_ylabel("SHAP value", fontsize=8)
    if add_colorbar:
        cbar = plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.02)
        cbar.ax.tick_params(labelsize=7)
        cbar.set_label(DISPLAY_LABELS.get(color_feature, color_feature), fontsize=7)


def plot_colored_dependence_by_biome() -> list[Path]:
    outputs: list[Path] = []
    dep_dir = OUT / "combined_by_biome_colored"
    dep_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for biome in BIOMES:
        bundles = {metric: load_bundle(metric, biome) for metric in METRICS}
        fig, axes = plt.subplots(len(FEATURE_ORDER), len(METRICS), figsize=(13.2, 24.5), sharex=False, sharey=False)
        for i, feature in enumerate(FEATURE_ORDER):
            color_feature = COLOR_BY_MAP[feature]
            for j, metric in enumerate(METRICS):
                X, S, _ = bundles[metric]
                plot_colored_dependence_panel(axes[i, j], X, S, feature, color_feature, metric, add_colorbar=True)
            axes[i, 0].text(
                -0.32,
                0.5,
                DISPLAY_LABELS.get(feature, feature),
                transform=axes[i, 0].transAxes,
                ha="right",
                va="center",
                fontsize=10,
                fontweight="bold",
            )
        fig.suptitle(f"{biome}: colored orthogonal SHAP dependence comparison (GPP vs RECO)", fontsize=15, fontweight="bold", y=0.997)
        fig.subplots_adjust(left=0.105, right=0.975, top=0.975, bottom=0.035, hspace=0.62, wspace=0.34)
        out = dep_dir / f"{biome}_orthogonal_all_features_gpp_vs_reco_colored.png"
        fig.savefig(out, dpi=250)
        plt.close(fig)
        outputs.append(out)
        rows.append(
            {
                "biome": biome,
                "output_png": str(out),
                "color_mapping": ";".join(
                    f"{DISPLAY_LABELS.get(k, k)} colored by {DISPLAY_LABELS.get(v, v)}"
                    for k, v in COLOR_BY_MAP.items()
                ),
            }
        )
    pd.DataFrame(rows).to_csv(dep_dir / "orthogonal_colored_dependence_index.csv", index=False)
    return outputs


def plot_selected_colored_dependence_singletons() -> list[Path]:
    outputs: list[Path] = []
    for metric in METRICS:
        for biome in BIOMES:
            X, S, _ = load_bundle(metric, biome)
            out_dir = ORTHO / metric / biome / "dependence_colored_selected"
            out_dir.mkdir(parents=True, exist_ok=True)
            rows = []
            for feature in FEATURE_ORDER:
                color_feature = COLOR_BY_MAP[feature]
                fig, ax = plt.subplots(figsize=(5.2, 4.0))
                plot_colored_dependence_panel(ax, X, S, feature, color_feature, metric, add_colorbar=True)
                ax.set_title(
                    f"{biome} - {metric}: {DISPLAY_LABELS.get(feature, feature)} colored by {DISPLAY_LABELS.get(color_feature, color_feature)}",
                    fontsize=10,
                    fontweight="bold",
                )
                fig.tight_layout()
                out = out_dir / f"{DISPLAY_LABELS.get(feature, feature)}_colored_by_{DISPLAY_LABELS.get(color_feature, color_feature)}.png"
                fig.savefig(out, dpi=220)
                plt.close(fig)
                outputs.append(out)
                rows.append({"feature": feature, "color_feature": color_feature, "output_png": str(out)})
            pd.DataFrame(rows).to_csv(out_dir / "colored_dependence_selected_index.csv", index=False)
    return outputs


def cross_color_features_for_target(feature: str) -> list[str]:
    """Mechanism-cross color mapping similar to original dependence_all outputs."""
    if feature in ENERGY_FEATURES:
        return WATER_FEATURES
    if feature in WATER_FEATURES:
        return ENERGY_FEATURES
    if feature in EVENT_FEATURES:
        return ENERGY_FEATURES + WATER_FEATURES
    if feature in ATMOS_FEATURES:
        return ENERGY_FEATURES + WATER_FEATURES
    return [f for f in FEATURE_ORDER if f != feature]


def plot_cross_colored_dependence_all() -> list[Path]:
    """Create small dependence_all-style plots with cross mechanism color maps."""
    outputs: list[Path] = []
    for metric in METRICS:
        for biome in BIOMES:
            X, S, _ = load_bundle(metric, biome)
            out_dir = ORTHO / metric / biome / "dependence_all_colored_cross"
            out_dir.mkdir(parents=True, exist_ok=True)
            rows = []
            for feature in FEATURE_ORDER:
                for color_feature in cross_color_features_for_target(feature):
                    if color_feature == feature:
                        continue
                    fig, ax = plt.subplots(figsize=(5.2, 4.0))
                    plot_colored_dependence_panel(ax, X, S, feature, color_feature, metric, add_colorbar=True)
                    x_label = DISPLAY_LABELS.get(feature, feature)
                    color_label = DISPLAY_LABELS.get(color_feature, color_feature)
                    ax.set_title(f"{biome} - {metric}: {x_label} colored by {color_label}", fontsize=10, fontweight="bold")
                    fig.tight_layout()
                    out = out_dir / f"{x_label}_colored_by_{color_label}.png"
                    fig.savefig(out, dpi=220)
                    plt.close(fig)
                    outputs.append(out)
                    rows.append(
                        {
                            "metric": metric,
                            "biome": biome,
                            "feature": feature,
                            "feature_label": x_label,
                            "color_feature": color_feature,
                            "color_label": color_label,
                            "output_png": str(out),
                        }
                    )
            pd.DataFrame(rows).to_csv(out_dir / "dependence_all_colored_cross_index.csv", index=False)
    summary = pd.DataFrame(
        [
            {
                "metric": metric,
                "biome": biome,
                "directory": str(ORTHO / metric / biome / "dependence_all_colored_cross"),
            }
            for metric in METRICS
            for biome in BIOMES
        ]
    )
    summary.to_csv(ORTHO / "dependence_all_colored_cross_summary.csv", index=False)
    return outputs


def plot_dependence_by_biome() -> list[Path]:
    outputs: list[Path] = []
    dep_dir = OUT / "combined_by_biome"
    dep_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for biome in BIOMES:
        bundles = {metric: load_bundle(metric, biome) for metric in METRICS}
        fig, axes = plt.subplots(len(FEATURE_ORDER), len(METRICS), figsize=(12.8, 24.0), sharex=False, sharey=False)
        for i, feature in enumerate(FEATURE_ORDER):
            for j, metric in enumerate(METRICS):
                X, S, _ = bundles[metric]
                plot_dependence_panel(axes[i, j], X, S, feature, metric)
            axes[i, 0].text(
                -0.30,
                0.5,
                DISPLAY_LABELS.get(feature, feature),
                transform=axes[i, 0].transAxes,
                ha="right",
                va="center",
                fontsize=10,
                fontweight="bold",
            )
        fig.suptitle(f"{biome}: orthogonal SHAP dependence comparison (GPP vs RECO)", fontsize=15, fontweight="bold", y=0.997)
        fig.subplots_adjust(left=0.105, right=0.985, top=0.975, bottom=0.035, hspace=0.56, wspace=0.24)
        out = dep_dir / f"{biome}_orthogonal_all_features_gpp_vs_reco.png"
        fig.savefig(out, dpi=250)
        plt.close(fig)
        outputs.append(out)
        rows.append({"biome": biome, "output_png": str(out), "features": ",".join(FEATURE_ORDER)})
    pd.DataFrame(rows).to_csv(dep_dir / "orthogonal_combined_dependence_index.csv", index=False)
    return outputs


def write_readme(beeswarm: Path, dep_outputs: list[Path]) -> None:
    lines = [
        "# Orthogonal decomposition combined figures",
        "",
        "These figures are redrawn from `dependence_sample_features.parquet`, `dependence_sample_shap_values.parquet`, and `feature_importance.csv` in each metric-biome folder.",
        "",
        "- `orthogonal_beeswarm_comparison_5biomes_gpp_vs_reco.png`: five-biome GPP/RECO beeswarm comparison for orthogonal SHAP inputs.",
        "- `combined_by_biome/*_orthogonal_all_features_gpp_vs_reco.png`: one large dependence figure per biome, with GPP and RECO side by side for all ten transformed features.",
        "",
        "Note: x axes are transformed variables: standardized anchors such as `SSRD_z` or residual z-scores such as `TMP_resid_after_SSRD_STRD`. They are intended for collinearity robustness interpretation rather than raw-unit thresholds.",
        "",
        f"Beeswarm: {beeswarm}",
        "Dependence figures:",
    ]
    lines.extend([f"- {p}" for p in dep_outputs])
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    beeswarm = plot_combined_beeswarm()
    dep_outputs = plot_dependence_by_biome()
    colored_outputs = plot_colored_dependence_by_biome()
    single_outputs = plot_selected_colored_dependence_singletons()
    cross_outputs = plot_cross_colored_dependence_all()
    write_readme(beeswarm, dep_outputs)
    print(f"beeswarm={beeswarm}")
    for p in dep_outputs:
        print(f"dependence={p}")
    for p in colored_outputs:
        print(f"colored_dependence={p}")
    print(f"selected_colored_dependence_count={len(single_outputs)}")
    print(f"cross_colored_dependence_count={len(cross_outputs)}")


if __name__ == "__main__":
    main()
