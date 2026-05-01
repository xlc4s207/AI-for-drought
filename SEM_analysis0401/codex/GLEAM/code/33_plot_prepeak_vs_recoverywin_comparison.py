#!/usr/bin/env python
"""Plot prepeak vs recoverywin comparison figures from existing SHAP artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.colors import Normalize
import numpy as np
import pandas as pd
try:
    import shap  # type: ignore
except ImportError:  # pragma: no cover
    shap = None


DEFAULT_BIOMES = ["Forest", "Grassland", "Savanna", "Cropland", "Shrubland", "Wetland"]
SCHEMES = ("prepeak", "recoverywin")
SHARED_FEATURES = [
    "total_precipitation_mean",
    "total_evaporation_mean",
    "temperature_2m_mean",
    "VPD_mean",
    "SMrz_mean",
    "lai_total_mean",
    "ssrd_mean",
    "strd_mean",
    "wind_speed_mean",
]
FEATURE_LABELS = {
    "total_precipitation_mean": "PRE",
    "total_evaporation_mean": "EVA",
    "temperature_2m_mean": "TMP",
    "VPD_mean": "VPD",
    "SMrz_mean": "SMrz",
    "lai_total_mean": "LAI",
    "ssrd_mean": "SSRD",
    "strd_mean": "STRD",
    "wind_speed_mean": "WIND",
    "event_onset_days": "ONS",
    "event_duration": "DUR",
    "event_intensity": "INT",
}
SCHEME_TITLES = {
    "prepeak": "Prepeak",
    "recoverywin": "Recoverywin",
}


@dataclass(frozen=True)
class SchemeColumns:
    feature_col: str
    shap_col: str


@dataclass(frozen=True)
class SampleColumns:
    feature_col: str
    shap_col: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepeak-root", required=True)
    parser.add_argument("--recoverywin-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--biomes", nargs="+", default=None)
    parser.add_argument("--clip-lower-quantile", type=float, default=0.01)
    parser.add_argument("--clip-upper-quantile", type=float, default=0.99)
    parser.add_argument("--point-alpha", type=float, default=0.22)
    parser.add_argument("--point-size", type=float, default=7.0)
    parser.add_argument("--beeswarm-alpha", type=float, default=0.45)
    parser.add_argument("--beeswarm-size", type=float, default=7.0)
    parser.add_argument("--beeswarm-max-points", type=int, default=5000)
    return parser.parse_args()


def resolve_biomes(explicit_biomes: list[str] | None) -> list[str]:
    if explicit_biomes:
        return [str(biome) for biome in explicit_biomes]
    return list(DEFAULT_BIOMES)


def build_scheme_columns(scheme: str, feature_name: str) -> SchemeColumns:
    if scheme not in SCHEMES:
        raise ValueError(f"Unsupported scheme: {scheme}")
    full_name = f"{scheme}_{feature_name}"
    return SchemeColumns(
        feature_col=f"feature__{full_name}",
        shap_col=f"shap__{full_name}",
    )


def build_sample_columns(scheme: str, feature_name: str) -> SampleColumns:
    if scheme not in SCHEMES:
        raise ValueError(f"Unsupported scheme: {scheme}")
    full_name = f"{scheme}_{feature_name}"
    return SampleColumns(
        feature_col=full_name,
        shap_col=full_name,
    )


def format_beeswarm_feature_name(name: str) -> str:
    label = str(name)
    for prefix in ("prepeak_", "recoverywin_", "shock_"):
        if label.startswith(prefix):
            label = label[len(prefix) :]
            break
    return FEATURE_LABELS.get(label, label)


def read_importance_order(csv_path: Path, scheme: str) -> list[str]:
    df = pd.read_csv(csv_path)
    prefix = f"{scheme}_"
    ordered: list[str] = []
    for feature in df.sort_values("rank")["feature"].tolist():
        if not isinstance(feature, str) or not feature.startswith(prefix):
            continue
        short_name = feature[len(prefix) :]
        if short_name in SHARED_FEATURES and short_name not in ordered:
            ordered.append(short_name)
    return ordered


def read_beeswarm_feature_order(csv_path: Path, scheme: str) -> list[str]:
    df = pd.read_csv(csv_path)
    prefix = f"{scheme}_"
    ordered: list[str] = []
    for feature in df.sort_values("rank")["feature"].tolist():
        if not isinstance(feature, str) or not feature.startswith(prefix):
            continue
        short_name = feature[len(prefix) :]
        if short_name not in ordered:
            ordered.append(short_name)
    return ordered


def load_dependence_frame(root: Path, biome: str) -> pd.DataFrame:
    return pd.read_parquet(root / biome / "dependence_plot_data.parquet")


def load_beeswarm_inputs(root: Path, biome: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_df = pd.read_parquet(root / biome / "dependence_sample_features.parquet")
    shap_df = pd.read_parquet(root / biome / "dependence_sample_shap_values.parquet")
    return feature_df, shap_df


def compute_shared_limits(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    feature_name: str,
    q_low: float,
    q_high: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    left_cols = build_scheme_columns("prepeak", feature_name)
    right_cols = build_scheme_columns("recoverywin", feature_name)
    x = pd.concat(
        [
            pd.to_numeric(left_df[left_cols.feature_col], errors="coerce"),
            pd.to_numeric(right_df[right_cols.feature_col], errors="coerce"),
        ],
        ignore_index=True,
    ).replace([np.inf, -np.inf], np.nan).dropna()
    y = pd.concat(
        [
            pd.to_numeric(left_df[left_cols.shap_col], errors="coerce"),
            pd.to_numeric(right_df[right_cols.shap_col], errors="coerce"),
        ],
        ignore_index=True,
    ).replace([np.inf, -np.inf], np.nan).dropna()
    if x.empty or y.empty:
        return (0.0, 1.0), (-1.0, 1.0)
    x_low = float(x.quantile(q_low))
    x_high = float(x.quantile(q_high))
    y_low = float(y.quantile(q_low))
    y_high = float(y.quantile(q_high))
    if not np.isfinite(x_low) or not np.isfinite(x_high) or x_low == x_high:
        x_low = float(x.min())
        x_high = float(x.max())
    if not np.isfinite(y_low) or not np.isfinite(y_high) or y_low == y_high:
        y_low = float(y.min())
        y_high = float(y.max())
    x_pad = max((x_high - x_low) * 0.06, 1e-9)
    y_pad = max((y_high - y_low) * 0.08, 1e-9)
    return (x_low - x_pad, x_high + x_pad), (y_low - y_pad, y_high + y_pad)


def add_trend(ax: plt.Axes, x: np.ndarray, y: np.ndarray) -> None:
    if len(x) < 20:
        return
    order = np.argsort(x)
    x_sorted = x[order]
    y_sorted = y[order]
    window = max(15, len(x_sorted) // 30)
    trend = pd.Series(y_sorted).rolling(window=window, center=True, min_periods=1).mean()
    ax.plot(x_sorted, trend.to_numpy(), color="#c83349", linewidth=1.8, alpha=0.95, zorder=3)


def plot_dependence_panel(
    ax: plt.Axes,
    frame: pd.DataFrame,
    scheme: str,
    feature_name: str,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    args: argparse.Namespace,
) -> int:
    cols = build_scheme_columns(scheme, feature_name)
    x = pd.to_numeric(frame[cols.feature_col], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(frame[cols.shap_col], errors="coerce").to_numpy(dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    ax.scatter(
        x,
        y,
        s=args.point_size,
        alpha=args.point_alpha,
        color="#2f6b8a",
        edgecolors="none",
        zorder=2,
    )
    add_trend(ax, x, y)
    ax.axhline(0.0, color="#666666", linewidth=1.0, linestyle="--", alpha=0.85, zorder=1)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.grid(alpha=0.18, linewidth=0.6)
    ax.set_title(SCHEME_TITLES[scheme], fontsize=11.5)
    return int(mask.sum())


def plot_biome_dependence(
    biome: str,
    prepeak_df: pd.DataFrame,
    recoverywin_df: pd.DataFrame,
    output_path: Path,
    args: argparse.Namespace,
) -> list[dict[str, object]]:
    fig, axes = plt.subplots(len(SHARED_FEATURES), 2, figsize=(12.8, 26.0))
    rows: list[dict[str, object]] = []
    for row_idx, feature_name in enumerate(SHARED_FEATURES):
        label = FEATURE_LABELS[feature_name]
        xlim, ylim = compute_shared_limits(
            prepeak_df,
            recoverywin_df,
            feature_name,
            q_low=args.clip_lower_quantile,
            q_high=args.clip_upper_quantile,
        )
        for col_idx, scheme in enumerate(SCHEMES):
            ax = axes[row_idx, col_idx]
            source = prepeak_df if scheme == "prepeak" else recoverywin_df
            n_points = plot_dependence_panel(
                ax=ax,
                frame=source,
                scheme=scheme,
                feature_name=feature_name,
                xlim=xlim,
                ylim=ylim,
                args=args,
            )
            if row_idx == len(SHARED_FEATURES) - 1:
                ax.set_xlabel(label, fontsize=10.5)
            if col_idx == 0:
                ax.set_ylabel(f"SHAP for {label}", fontsize=10.5)
            rows.append(
                {
                    "plot_type": "dependence",
                    "biome": biome,
                    "scheme": scheme,
                    "feature_name": feature_name,
                    "points": n_points,
                    "x_min": xlim[0],
                    "x_max": xlim[1],
                    "y_min": ylim[0],
                    "y_max": ylim[1],
                    "output_path": str(output_path),
                }
            )
    fig.suptitle(f"{biome} | Prepeak vs Recoverywin dependence comparison", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return rows


def sample_frame(frame: pd.DataFrame, max_points: int) -> pd.DataFrame:
    if len(frame) <= max_points:
        return frame
    return frame.sample(n=max_points, random_state=42)


def compute_beeswarm_offsets(x: np.ndarray, max_swarm: float = 0.28) -> np.ndarray:
    if len(x) == 0:
        return np.array([], dtype=float)
    if len(x) == 1:
        return np.array([0.0], dtype=float)

    x = np.asarray(x, dtype=float)
    finite = x[np.isfinite(x)]
    if len(finite) == 0:
        return np.zeros(len(x), dtype=float)

    span = float(finite.max() - finite.min())
    neighborhood = max(span / 60.0, 1e-9)

    order = np.argsort(x, kind="mergesort")
    offsets_sorted = np.zeros(len(x), dtype=float)
    cluster: list[int] = []

    def assign_cluster(indices: list[int]) -> None:
        if not indices:
            return
        if len(indices) == 1:
            offsets_sorted[indices[0]] = 0.0
            return

        step = min(max_swarm / max((len(indices) - 1) / 2.0, 1.0), max_swarm / 2.0)
        pattern = [0.0]
        level = 1
        while len(pattern) < len(indices):
            pattern.append(level * step)
            if len(pattern) < len(indices):
                pattern.append(-level * step)
            level += 1
        for idx, offset in zip(indices, pattern):
            offsets_sorted[idx] = offset

    prev_x = x[order[0]]
    cluster.append(0)
    for sorted_idx in range(1, len(order)):
        current_x = x[order[sorted_idx]]
        if abs(current_x - prev_x) <= neighborhood:
            cluster.append(sorted_idx)
        else:
            assign_cluster(cluster)
            cluster = [sorted_idx]
        prev_x = current_x
    assign_cluster(cluster)

    offsets = np.zeros(len(x), dtype=float)
    offsets[order] = offsets_sorted
    return offsets


def prepare_standard_beeswarm_inputs(
    sample_df: pd.DataFrame,
    shap_df: pd.DataFrame,
    scheme: str,
    feature_order: list[str],
    max_points: int,
) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    selected_cols: list[str] = []
    for feature_name in feature_order:
        cols = build_sample_columns(scheme, feature_name)
        if cols.feature_col in sample_df.columns and cols.shap_col in shap_df.columns:
            selected_cols.append(cols.feature_col)
    if not selected_cols:
        return pd.DataFrame(), np.empty((0, 0), dtype=float), []

    feature_frame = sample_df[selected_cols].apply(pd.to_numeric, errors="coerce")
    shap_frame = shap_df[selected_cols].apply(pd.to_numeric, errors="coerce")
    valid_mask = feature_frame.notna().all(axis=1) & shap_frame.notna().all(axis=1)
    feature_frame = feature_frame.loc[valid_mask].reset_index(drop=True)
    shap_frame = shap_frame.loc[valid_mask].reset_index(drop=True)
    if feature_frame.empty:
        return pd.DataFrame(columns=selected_cols), np.empty((0, len(selected_cols)), dtype=float), selected_cols
    if len(feature_frame) > max_points:
        sampled_idx = feature_frame.sample(n=max_points, random_state=42).index
        feature_frame = feature_frame.loc[sampled_idx].reset_index(drop=True)
        shap_frame = shap_frame.loc[sampled_idx].reset_index(drop=True)
    return feature_frame, shap_frame.to_numpy(dtype=float), selected_cols


def plot_standard_beeswarm_panel(
    ax: plt.Axes,
    sample_df: pd.DataFrame,
    shap_df: pd.DataFrame,
    scheme: str,
    feature_order: list[str],
    max_points: int,
) -> None:
    feature_frame, shap_matrix, feature_names = prepare_standard_beeswarm_inputs(
        sample_df=sample_df,
        shap_df=shap_df,
        scheme=scheme,
        feature_order=feature_order,
        max_points=max_points,
    )
    ax.set_title(SCHEME_TITLES[scheme], fontsize=11.5)
    if shap is None or feature_frame.empty or shap_matrix.size == 0:
        ax.text(0.5, 0.5, "No SHAP data", ha="center", va="center", fontsize=10)
        ax.set_axis_off()
        return
    display_feature_names = [format_beeswarm_feature_name(name) for name in feature_names]
    plt.sca(ax)
    shap.summary_plot(
        shap_matrix,
        feature_frame,
        feature_names=display_feature_names,
        show=False,
        max_display=len(feature_names),
        color_bar=False,
        plot_size=None,
    )
    ax.set_title(SCHEME_TITLES[scheme], fontsize=11.5)
    ax.tick_params(axis="y", labelsize=9.0)
    ax.tick_params(axis="x", labelsize=9.0)


def plot_all_biome_beeswarm(
    prepeak_root: Path,
    recoverywin_root: Path,
    output_path: Path,
    args: argparse.Namespace,
    biomes: list[str],
) -> list[dict[str, object]]:
    fig, axes = plt.subplots(len(biomes), 2, figsize=(15.5, max(4.0 * len(biomes), 8.0)), sharex=False)
    summary_rows: list[dict[str, object]] = []
    if len(biomes) == 1:
        axes = np.array([axes])
    for row_idx, biome in enumerate(biomes):
        for col_idx, scheme in enumerate(SCHEMES):
            ax = axes[row_idx, col_idx]
            root = prepeak_root if scheme == "prepeak" else recoverywin_root
            sample_df, shap_df = load_beeswarm_inputs(root, biome)
            feature_order = read_beeswarm_feature_order(root / biome / "feature_importance.csv", scheme)
            plot_standard_beeswarm_panel(
                ax=ax,
                sample_df=sample_df,
                shap_df=shap_df,
                scheme=scheme,
                feature_order=feature_order,
                max_points=args.beeswarm_max_points,
            )
            if col_idx == 0:
                ax.text(
                    -0.08,
                    0.98,
                    biome,
                    transform=ax.transAxes,
                    ha="left",
                    va="top",
                    fontsize=11.0,
                    fontweight="bold",
                )
            summary_rows.append(
                {
                    "plot_type": "beeswarm",
                    "biome": biome,
                    "scheme": scheme,
                    "feature_name": ",".join(feature_order),
                    "points": min(len(sample_df), args.beeswarm_max_points),
                    "output_path": str(output_path),
                }
            )
    cmap = LinearSegmentedColormap.from_list("beeswarm_ref", ["#1e88e5", "#ff0052"])
    cax = fig.add_axes([0.94, 0.12, 0.012, 0.76])
    mappable = plt.cm.ScalarMappable(norm=Normalize(vmin=0.0, vmax=1.0), cmap=cmap)
    cbar = fig.colorbar(mappable, cax=cax)
    cbar.set_ticks([0.0, 1.0])
    cbar.set_ticklabels(["Low", "High"])
    cbar.set_label("Feature value", fontsize=11)
    fig.suptitle("All biomes | Prepeak vs Recoverywin beeswarm comparison", fontsize=16)
    fig.tight_layout(rect=[0, 0, 0.93, 0.985])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return summary_rows


def main() -> None:
    args = parse_args()
    if not 0.0 <= args.clip_lower_quantile < args.clip_upper_quantile <= 1.0:
        raise ValueError("Need 0 <= clip-lower-quantile < clip-upper-quantile <= 1.")

    prepeak_root = Path(args.prepeak_root)
    recoverywin_root = Path(args.recoverywin_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    biomes = resolve_biomes(args.biomes)

    all_rows: list[dict[str, object]] = []
    for biome in biomes:
        prepeak_df = load_dependence_frame(prepeak_root, biome)
        recoverywin_df = load_dependence_frame(recoverywin_root, biome)
        all_rows.extend(
            plot_biome_dependence(
                biome=biome,
                prepeak_df=prepeak_df,
                recoverywin_df=recoverywin_df,
                output_path=output_dir / f"{biome}_prepeak_vs_recoverywin_dependence.png",
                args=args,
            )
        )

    all_rows.extend(
        plot_all_biome_beeswarm(
            prepeak_root=prepeak_root,
            recoverywin_root=recoverywin_root,
            output_path=output_dir / "all_biomes_prepeak_vs_recoverywin_beeswarm.png",
            args=args,
            biomes=biomes,
        )
    )
    pd.DataFrame(all_rows).to_csv(output_dir / "summary.csv", index=False)


if __name__ == "__main__":
    main()
