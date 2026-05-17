#!/usr/bin/env python
"""Plot prepeak vs recoverywin comparison figures from existing SHAP artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys

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


DEFAULT_BIOMES = ["Forest", "Grassland", "Savanna", "Cropland", "Shrubland"]
SCHEMES = ("prepeak", "recoverywin")
SHARED_FEATURES = [
    "total_precipitation_mean",
    "total_evaporation_mean",
    "temperature_2m_mean",
    "VPD_mean",
    "SMrz_mean",
    "ssrd_mean",
    "strd_mean",
    "wind_speed_mean",
]
FEATURE_LABELS = {
    "total_precipitation_mean": "PRE (mm)",
    "total_evaporation_mean": "EVA (mm)",
    "temperature_2m_mean": "TMP (K)",
    "VPD_mean": "VPD",
    "SMrz_mean": "SMrz",
    "lai_total_mean": "LAI",
    "ssrd_mean": "SSRD",
    "strd_mean": "STRD",
    "wind_speed_mean": "WIND (m s-1)",
    "event_onset_days": "Onset day",
    "event_duration": "Duration",
    "event_intensity": "Intensity",
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


@dataclass(frozen=True)
class BiomeSchemeInputs:
    sample_df: pd.DataFrame
    shap_df: pd.DataFrame


SCRIPT_21_PATH = Path(__file__).with_name("21_batch_dependence_plots_fast.py")
SCRIPT_21_SPEC = importlib.util.spec_from_file_location("batch_dependence_fast_module", SCRIPT_21_PATH)
if SCRIPT_21_SPEC is None or SCRIPT_21_SPEC.loader is None:
    raise RuntimeError(f"Unable to load helper module from {SCRIPT_21_PATH}")
batch_dependence_fast_module = importlib.util.module_from_spec(SCRIPT_21_SPEC)
sys.modules[SCRIPT_21_SPEC.name] = batch_dependence_fast_module
SCRIPT_21_SPEC.loader.exec_module(batch_dependence_fast_module)


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
    parser.add_argument("--beeswarm-max-points", type=int, default=2500)
    return parser.parse_args()


def normalize_biome_root(root: Path) -> Path:
    shap_by_biome = root / "shap_by_biome"
    if shap_by_biome.is_dir():
        return shap_by_biome
    return root


def list_biomes(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def resolve_biomes(
    explicit_biomes: list[str] | None,
    prepeak_root: Path | None = None,
    recoverywin_root: Path | None = None,
) -> list[str]:
    if explicit_biomes:
        return [str(biome) for biome in explicit_biomes]
    if prepeak_root is not None and recoverywin_root is not None:
        prepeak_biomes = set(list_biomes(prepeak_root))
        recoverywin_biomes = set(list_biomes(recoverywin_root))
        shared_biomes = sorted(prepeak_biomes & recoverywin_biomes)
        if shared_biomes:
            return shared_biomes
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
        if short_name in SHARED_FEATURES and short_name not in ordered:
            ordered.append(short_name)
    return ordered


def load_beeswarm_inputs(root: Path, biome: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_df = pd.read_parquet(root / biome / "dependence_sample_features.parquet")
    shap_df = pd.read_parquet(root / biome / "dependence_sample_shap_values.parquet")
    return feature_df, shap_df


def load_biome_scheme_inputs(root: Path, biome: str) -> BiomeSchemeInputs:
    sample_df, shap_df = load_beeswarm_inputs(root, biome)
    return BiomeSchemeInputs(sample_df=sample_df, shap_df=shap_df)


def infer_unit_scale_factor(feature_name: str, values: np.ndarray) -> float:
    if feature_name not in {"total_precipitation_mean", "total_evaporation_mean"}:
        return 1.0
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return 1.0
    q95 = float(np.nanquantile(np.abs(finite), 0.95))
    if q95 <= 0.05:
        return 1000.0
    return 1.0


def get_filtered_feature_arrays(
    sample_df: pd.DataFrame,
    shap_df: pd.DataFrame,
    feature_name: str,
    scheme: str,
) -> tuple[np.ndarray, np.ndarray]:
    cols = build_sample_columns(scheme, feature_name)
    if cols.feature_col not in sample_df.columns or cols.shap_col not in shap_df.columns:
        return np.array([], dtype=float), np.array([], dtype=float)
    x_raw = pd.to_numeric(sample_df[cols.feature_col], errors="coerce").to_numpy(dtype=float)
    y_raw = pd.to_numeric(shap_df[cols.shap_col], errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(x_raw) & np.isfinite(y_raw)
    x_raw = x_raw[finite]
    y_raw = y_raw[finite]
    if len(x_raw) == 0:
        return np.array([], dtype=float), np.array([], dtype=float)

    protect_mask = np.zeros(len(x_raw), dtype=bool)
    if feature_name == "total_precipitation_mean":
        scale_factor = infer_unit_scale_factor(feature_name, x_raw)
        if scale_factor == 1000.0:
            protect_mask = (x_raw >= 0.0) & (x_raw <= 0.002)

    if protect_mask.any():
        filtered_x, filtered_y, _ = batch_dependence_fast_module.filter_local_vertical_shap_outliers(
            x_raw[~protect_mask],
            y_raw[~protect_mask],
        )
        x_kept = np.concatenate([x_raw[protect_mask], filtered_x])
        y_kept = np.concatenate([y_raw[protect_mask], filtered_y])
    else:
        x_kept, y_kept, _ = batch_dependence_fast_module.filter_local_vertical_shap_outliers(x_raw, y_raw)

    scale_factor = infer_unit_scale_factor(feature_name, x_kept)
    return x_kept * scale_factor, y_kept


def compute_shared_limits(
    left_inputs: BiomeSchemeInputs,
    right_inputs: BiomeSchemeInputs,
    feature_name: str,
    q_low: float,
    q_high: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    left_x, left_y = get_filtered_feature_arrays(left_inputs.sample_df, left_inputs.shap_df, feature_name, "prepeak")
    right_x, right_y = get_filtered_feature_arrays(right_inputs.sample_df, right_inputs.shap_df, feature_name, "recoverywin")
    x = pd.concat([pd.Series(left_x), pd.Series(right_x)], ignore_index=True).replace([np.inf, -np.inf], np.nan).dropna()
    y = pd.concat([pd.Series(left_y), pd.Series(right_y)], ignore_index=True).replace([np.inf, -np.inf], np.nan).dropna()
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
    biome_inputs: BiomeSchemeInputs,
    scheme: str,
    feature_name: str,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    args: argparse.Namespace,
) -> int:
    x, y = get_filtered_feature_arrays(
        sample_df=biome_inputs.sample_df,
        shap_df=biome_inputs.shap_df,
        feature_name=feature_name,
        scheme=scheme,
    )
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
    return int(len(x))


def plot_biome_dependence(
    biome: str,
    prepeak_inputs: BiomeSchemeInputs,
    recoverywin_inputs: BiomeSchemeInputs,
    output_path: Path,
    args: argparse.Namespace,
) -> list[dict[str, object]]:
    fig, axes = plt.subplots(len(SHARED_FEATURES), 2, figsize=(12.8, 26.0))
    rows: list[dict[str, object]] = []
    for row_idx, feature_name in enumerate(SHARED_FEATURES):
        label = FEATURE_LABELS[feature_name]
        xlim, ylim = compute_shared_limits(
            prepeak_inputs,
            recoverywin_inputs,
            feature_name,
            q_low=args.clip_lower_quantile,
            q_high=args.clip_upper_quantile,
        )
        for col_idx, scheme in enumerate(SCHEMES):
            ax = axes[row_idx, col_idx]
            source = prepeak_inputs if scheme == "prepeak" else recoverywin_inputs
            n_points = plot_dependence_panel(
                ax=ax,
                biome_inputs=source,
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

    prepeak_root = normalize_biome_root(Path(args.prepeak_root))
    recoverywin_root = normalize_biome_root(Path(args.recoverywin_root))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    biomes = resolve_biomes(args.biomes, prepeak_root=prepeak_root, recoverywin_root=recoverywin_root)

    all_rows: list[dict[str, object]] = []
    for biome in biomes:
        prepeak_inputs = load_biome_scheme_inputs(prepeak_root, biome)
        recoverywin_inputs = load_biome_scheme_inputs(recoverywin_root, biome)
        all_rows.extend(
            plot_biome_dependence(
                biome=biome,
                prepeak_inputs=prepeak_inputs,
                recoverywin_inputs=recoverywin_inputs,
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
    summary_df = pd.DataFrame(all_rows)
    if not summary_df.empty:
        summary_df["clip_lower_quantile"] = args.clip_lower_quantile
        summary_df["clip_upper_quantile"] = args.clip_upper_quantile
        summary_df["prepeak_root"] = str(prepeak_root)
        summary_df["recoverywin_root"] = str(recoverywin_root)
        summary_df["biomes_used"] = ",".join(biomes)
    summary_df.to_csv(output_dir / "summary.csv", index=False)


if __name__ == "__main__":
    main()
