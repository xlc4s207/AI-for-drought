#!/usr/bin/env python
"""Batch-generate per-feature SHAP dependence plots for existing biome result sets."""

from __future__ import annotations

import argparse
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sem_gleam_common import finalize_feature_table

try:
    import shap  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("This script requires the shap package to be installed.") from exc


SHAP_ANALYSIS_PATH = Path(__file__).with_name("06_shap_analysis.py")
SHAP_ANALYSIS_SPEC = importlib.util.spec_from_file_location("shap_analysis_module", SHAP_ANALYSIS_PATH)
if SHAP_ANALYSIS_SPEC is None or SHAP_ANALYSIS_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"Unable to load helper module from {SHAP_ANALYSIS_PATH}")
shap_analysis_module = importlib.util.module_from_spec(SHAP_ANALYSIS_SPEC)
SHAP_ANALYSIS_SPEC.loader.exec_module(shap_analysis_module)

compute_split_r2 = shap_analysis_module.compute_split_r2
filter_analysis_subset = shap_analysis_module.filter_analysis_subset
fit_tree_model = shap_analysis_module.fit_tree_model
prepare_model_inputs = shap_analysis_module.prepare_model_inputs
resolve_model_backend = shap_analysis_module.resolve_model_backend
sample_for_shap = shap_analysis_module.sample_for_shap


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    table: Path
    output_root: Path
    feature_scope: str
    model_backend: str
    n_estimators: int
    n_jobs: int
    shap_sample_size: int
    include_features: tuple[str, ...]
    exclude_features: tuple[str, ...]
    row_limit: int | None = 50000
    metric: str = "GPP"
    code_id: str = "code1"
    drought_type: str = "flash"
    soil_layer: str = "SMrz"
    biomes: tuple[str, ...] = ()


PROJECT_ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM")

DATASET_CONFIGS: dict[str, DatasetConfig] = {
    "recoverywin_mean": DatasetConfig(
        name="recoverywin_mean",
        table=PROJECT_ROOT / "data/feature_table_recovery_phase_GPP_code1_flash_SMrz_precipEmean.parquet",
        output_root=PROJECT_ROOT / "results/gpp_code1_flash_smrz_rechunk_py_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome",
        feature_scope="process_recoverywin",
        model_backend="random_forest",
        n_estimators=60,
        n_jobs=4,
        shap_sample_size=5000,
        include_features=(
            "recoverywin_total_precipitation_mean",
            "recoverywin_total_evaporation_mean",
            "recoverywin_temperature_2m_mean",
            "recoverywin_VPD_mean",
            "recoverywin_SMrz_mean",
            "recoverywin_lai_total_mean",
            "recoverywin_ssrd_mean",
            "recoverywin_strd_mean",
            "recoverywin_wind_speed_mean",
        ),
        exclude_features=(
            "recoverywin_p_minus_et",
            "recoverywin_total_precipitation_sum",
            "recoverywin_total_evaporation_sum",
        ),
        biomes=("Forest", "Grassland", "Savanna", "Cropland", "Shrubland", "Wetland"),
    ),
    "prepeak_mean": DatasetConfig(
        name="prepeak_mean",
        table=PROJECT_ROOT / "data/feature_table_recovery_phase_GPP_code1_flash_SMrz_precipEmean_prepeak.parquet",
        output_root=PROJECT_ROOT / "results/gpp_code1_flash_smrz_rechunk_py_clean/prepeak_precip_shap_sem_20260417/shap_by_biome",
        feature_scope="all",
        model_backend="lightgbm",
        n_estimators=120,
        n_jobs=12,
        shap_sample_size=5000,
        include_features=(
            "prepeak_total_precipitation_mean",
            "recoverywin_total_evaporation_mean",
            "recoverywin_SMrz_mean",
            "recoverywin_temperature_2m_mean",
            "recoverywin_VPD_mean",
            "recoverywin_wind_speed_mean",
            "recoverywin_lai_total_mean",
            "recoverywin_ssrd_mean",
            "recoverywin_strd_mean",
        ),
        exclude_features=(
            "recoverywin_p_minus_et",
            "recoverywin_total_precipitation_sum",
            "recoverywin_total_evaporation_sum",
            "recoverywin_total_precipitation_mean",
            "recoverywin_SMrz_delta",
        ),
        biomes=("Forest", "Grassland", "Savanna", "Cropland", "Shrubland"),
    ),
}


FEATURE_LABELS = {
    "recoverywin_total_precipitation_mean": "PRE(mean, recoverywin)",
    "prepeak_total_precipitation_mean": "PRE(mean, prepeak)",
    "recoverywin_total_evaporation_mean": "EVA(mean, recoverywin)",
    "recoverywin_temperature_2m_mean": "TMP(mean, recoverywin)",
    "recoverywin_VPD_mean": "VPD(mean, recoverywin)",
    "recoverywin_SMrz_mean": "SMrz(mean, recoverywin)",
    "recoverywin_lai_total_mean": "LAI(mean, recoverywin)",
    "recoverywin_ssrd_mean": "SSRD(mean, recoverywin)",
    "recoverywin_strd_mean": "STRD(mean, recoverywin)",
    "recoverywin_wind_speed_mean": "WIND(mean, recoverywin)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=tuple(DATASET_CONFIGS.keys()),
        default=list(DATASET_CONFIGS.keys()),
    )
    parser.add_argument("--biomes", nargs="+", default=None)
    parser.add_argument("--max-missing-rate", type=float, default=0.3)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def sanitize_feature_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in name)


def _round_feature_values_for_grouping(values: np.ndarray) -> np.ndarray:
    max_abs = float(np.nanmax(np.abs(values))) if len(values) else 0.0
    if max_abs >= 1e6:
        return np.round(values, decimals=-3)
    if max_abs >= 1e3:
        return np.round(values, decimals=3)
    return np.round(values, decimals=3)


def _interpolate_local_median_trend(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    if len(x) == 0:
        return np.array([], dtype=float)
    if len(x) < 20:
        return np.full(len(x), float(np.nanmedian(y)), dtype=float)
    order = np.argsort(x)
    xs = x[order]
    ys = y[order]
    bins = min(40, max(12, len(xs) // 120))
    edges = np.linspace(0, len(xs), bins + 1, dtype=int)
    bx: list[float] = []
    by: list[float] = []
    for start, end in zip(edges[:-1], edges[1:]):
        if end <= start:
            continue
        bx.append(float(np.nanmedian(xs[start:end])))
        by.append(float(np.nanmedian(ys[start:end])))
    if len(bx) < 2:
        return np.full(len(x), float(np.nanmedian(y)), dtype=float)
    trend_frame = (
        pd.DataFrame({"x": bx, "y": by})
        .groupby("x", as_index=False, sort=True)["y"]
        .median()
        .sort_values("x")
    )
    trend_x = trend_frame["x"].to_numpy(dtype=float)
    trend_y = trend_frame["y"].to_numpy(dtype=float)
    return np.interp(x, trend_x, trend_y, left=trend_y[0], right=trend_y[-1])


def filter_local_vertical_shap_outliers(
    feature_values: np.ndarray,
    shap_values: np.ndarray,
    *,
    min_group_size: int = 40,
    min_group_fraction: float = 0.01,
    global_sigma: float = 4.5,
    local_sigma: float = 3.5,
    max_removed_fraction_per_group: float = 0.15,
    lower_tail_trim_fraction: float = 0.03,
    min_neighbor_points: int = 6,
    max_neighbor_groups: int = 3,
) -> tuple[np.ndarray, np.ndarray, int]:
    finite = np.isfinite(feature_values) & np.isfinite(shap_values)
    x = feature_values[finite].astype(float)
    y = shap_values[finite].astype(float)
    if len(x) == 0:
        return x, y, 0

    expected = _interpolate_local_median_trend(x, y)
    residual = y - expected
    global_center = float(np.nanmedian(residual))
    global_mad = float(np.nanmedian(np.abs(residual - global_center)))
    global_scale = max(1.4826 * global_mad, 1e-6)

    group_keys = _round_feature_values_for_grouping(x)
    group_sizes = pd.Series(group_keys).value_counts()
    group_min_count = max(min_group_size, int(np.ceil(len(x) * min_group_fraction)))
    sorted_group_keys = np.sort(pd.unique(group_keys))

    keep = np.ones(len(x), dtype=bool)
    for key, count in group_sizes.items():
        if int(count) < group_min_count:
            continue
        group_mask = group_keys == key
        group_residual = residual[group_mask]
        group_center = float(np.nanmedian(group_residual))
        group_mad = float(np.nanmedian(np.abs(group_residual - group_center)))
        group_scale = max(1.4826 * group_mad, global_scale * 0.5, 1e-6)
        cutoff = min(
            global_center - global_sigma * global_scale,
            group_center - local_sigma * group_scale,
        )
        flagged = group_mask & (residual < cutoff)
        flagged_idx = np.flatnonzero(flagged)
        if len(flagged_idx) > 0:
            max_remove = max(1, int(np.floor(count * max_removed_fraction_per_group)))
            if len(flagged_idx) > max_remove:
                ranked = flagged_idx[np.argsort(residual[flagged_idx])]
                flagged_idx = ranked[:max_remove]
            keep[flagged_idx] = False

            remaining_group_idx = np.flatnonzero(group_mask & keep)
            if len(remaining_group_idx) > 0:
                trimmed_count = max(1, int(np.floor(count * lower_tail_trim_fraction)))
                if trimmed_count < len(remaining_group_idx):
                    remaining_residual = residual[remaining_group_idx]
                    spread = float(np.nanquantile(remaining_residual, 0.95) - np.nanquantile(remaining_residual, 0.05))
                    if spread >= global_scale * 4.0:
                        ranked_remaining = remaining_group_idx[np.argsort(remaining_residual)]
                        tail_idx = ranked_remaining[:trimmed_count]
                        if np.nanmax(residual[tail_idx]) < global_center:
                            keep[tail_idx] = False

        neighbor_mask = np.zeros(len(x), dtype=bool)
        key_pos = int(np.searchsorted(sorted_group_keys, key))
        for offset in range(1, max_neighbor_groups + 1):
            added_neighbor = False
            left_pos = key_pos - offset
            right_pos = key_pos + offset
            if left_pos >= 0:
                neighbor_mask |= group_keys == sorted_group_keys[left_pos]
                added_neighbor = True
            if right_pos < len(sorted_group_keys):
                neighbor_mask |= group_keys == sorted_group_keys[right_pos]
                added_neighbor = True
            if neighbor_mask.sum() >= min_neighbor_points or not added_neighbor:
                break
        neighbor_mask &= ~group_mask
        if neighbor_mask.sum() == 0:
            continue

        neighbor_values = y[neighbor_mask]
        if len(neighbor_values) < min_neighbor_points:
            continue
        neighbor_q05 = float(np.nanquantile(neighbor_values, 0.05))
        neighbor_q25 = float(np.nanquantile(neighbor_values, 0.25))
        neighbor_q75 = float(np.nanquantile(neighbor_values, 0.75))
        neighbor_q95 = float(np.nanquantile(neighbor_values, 0.95))
        neighbor_center = float(np.nanmedian(neighbor_values))
        neighbor_mad = float(np.nanmedian(np.abs(neighbor_values - neighbor_center)))
        neighbor_scale = max(1.4826 * neighbor_mad, 1e-6)

        group_values = y[group_mask]
        group_q05 = float(np.nanquantile(group_values, 0.05))
        group_q25 = float(np.nanquantile(group_values, 0.25))
        group_q75 = float(np.nanquantile(group_values, 0.75))
        group_q95 = float(np.nanquantile(group_values, 0.95))
        is_lower_shifted = group_q25 < neighbor_q25
        is_vertically_stretched = (group_q75 > neighbor_q75 + neighbor_scale) and (group_q05 < neighbor_q05)
        if not (is_lower_shifted or is_vertically_stretched):
            pass
        else:
            neighbor_flagged = group_mask & (y < neighbor_q05)
            if neighbor_flagged.any():
                keep[neighbor_flagged] = False

        is_upper_shifted = group_q75 > neighbor_q75
        is_upper_spike = (group_q25 > neighbor_q75) or (
            (group_q95 > neighbor_q95 + 0.5 * neighbor_scale) and (group_q75 > neighbor_q75)
        )
        if is_upper_shifted and is_upper_spike:
            neighbor_flagged_high = group_mask & (y > neighbor_q95)
            if neighbor_flagged_high.any():
                keep[neighbor_flagged_high] = False

    return x[keep], y[keep], int((~keep).sum())


def save_dependence_plot(
    sample: pd.DataFrame,
    shap_df: pd.DataFrame,
    feature: str,
    output_path: Path,
    title: str,
) -> tuple[int, int]:
    values = pd.to_numeric(sample[feature], errors="coerce").to_numpy(dtype=float)
    shap_values = pd.to_numeric(shap_df[feature], errors="coerce").to_numpy(dtype=float)
    values, shap_values, removed_count = filter_local_vertical_shap_outliers(values, shap_values)
    if len(values) == 0:
        return 0, removed_count

    order = np.argsort(values)
    values = values[order]
    shap_values = shap_values[order]

    density = None
    if len(values) >= 20:
        try:
            bins = min(30, max(10, len(values) // 40))
            counts, xedges, yedges = np.histogram2d(values, shap_values, bins=bins)
            x_idx = np.clip(np.digitize(values, xedges) - 1, 0, counts.shape[0] - 1)
            y_idx = np.clip(np.digitize(shap_values, yedges) - 1, 0, counts.shape[1] - 1)
            density = counts[x_idx, y_idx]
        except Exception:
            density = None

    plt.figure(figsize=(7.8, 5.8))
    plt.axhline(0.0, color="#7f7f7f", linewidth=1.0, linestyle="--", alpha=0.8, zorder=1)
    scatter = plt.scatter(
        values,
        shap_values,
        c=density if density is not None else "#2f6b8a",
        cmap="viridis" if density is not None else None,
        s=22,
        alpha=0.72,
        edgecolors="none",
        zorder=2,
    )
    if density is not None:
        cbar = plt.colorbar(scatter)
        cbar.set_label("Local point density", fontsize=11)
        cbar.ax.tick_params(labelsize=10)

    if len(values) >= 10:
        try:
            window = max(5, len(values) // 25)
            trend = pd.Series(shap_values).rolling(window=window, center=True, min_periods=1).mean()
            plt.plot(values, trend.to_numpy(), color="#c83349", linewidth=2.0, alpha=0.9, zorder=3)
        except Exception:
            pass

    plt.xlabel(FEATURE_LABELS.get(feature, feature), fontsize=12)
    plt.ylabel(f"SHAP value for {FEATURE_LABELS.get(feature, feature)}", fontsize=12)
    plt.title(title, fontsize=13)
    plt.xticks(fontsize=10)
    plt.yticks(fontsize=10)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=220)
    plt.close()
    return int(len(values)), int(removed_count)


def iter_target_biomes(config: DatasetConfig, requested_biomes: Iterable[str] | None) -> list[str]:
    if requested_biomes:
        requested = {str(item) for item in requested_biomes}
        return [biome for biome in config.biomes if biome in requested]
    return list(config.biomes)


def fit_and_explain(
    config: DatasetConfig,
    biome: str,
    max_missing_rate: float,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float | int], list[str], int]:
    df = pd.read_parquet(config.table)
    df = finalize_feature_table(df)
    df = filter_analysis_subset(
        df,
        metric=config.metric,
        code_id=config.code_id,
        biome=biome,
        drought_type=config.drought_type,
        soil_layer=config.soil_layer,
    )
    if config.row_limit is not None and len(df) > config.row_limit:
        df = df.head(config.row_limit).copy()
    X, y, feature_names = prepare_model_inputs(
        df,
        target="t_recover_to_baseline_abs_peak",
        max_missing_rate=max_missing_rate,
        feature_scope=config.feature_scope,
        include_features=config.include_features,
        exclude_features=config.exclude_features,
    )
    backend = resolve_model_backend(config.model_backend)
    split_metrics = compute_split_r2(
        X,
        y,
        backend=backend,
        random_state=random_state,
        n_estimators=config.n_estimators,
        n_jobs=config.n_jobs,
    )
    model = fit_tree_model(
        X,
        y,
        backend=backend,
        random_state=random_state,
        n_estimators=config.n_estimators,
        n_jobs=config.n_jobs,
    )
    sample = sample_for_shap(X, sample_size=config.shap_sample_size, random_state=random_state)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(sample)
    if isinstance(shap_values, list):
        shap_values = shap_values[0]
    shap_df = pd.DataFrame(np.asarray(shap_values), columns=sample.columns, index=sample.index)
    return sample, shap_df, split_metrics, feature_names, len(df)


def run_dataset(
    config: DatasetConfig,
    biomes: Iterable[str] | None,
    max_missing_rate: float,
    random_state: int,
) -> None:
    for biome in iter_target_biomes(config, biomes):
        biome_dir = config.output_root / biome
        dependence_dir = biome_dir / "dependence_plots"
        dependence_dir.mkdir(parents=True, exist_ok=True)

        sample, shap_df, split_metrics, feature_names, filtered_rows = fit_and_explain(
            config=config,
            biome=biome,
            max_missing_rate=max_missing_rate,
            random_state=random_state,
        )

        sample.to_parquet(biome_dir / "dependence_sample_features.parquet", index=True)
        shap_df.to_parquet(biome_dir / "dependence_sample_shap_values.parquet", index=True)
        merged = sample.add_prefix("feature__").join(shap_df.add_prefix("shap__"), how="left")
        merged.to_parquet(biome_dir / "dependence_plot_data.parquet", index=True)

        filter_records: list[dict[str, object]] = []
        removed_total = 0
        for feature in feature_names:
            output_path = dependence_dir / f"{sanitize_feature_name(feature)}.png"
            title = f"{config.name} | {biome} | {FEATURE_LABELS.get(feature, feature)}"
            points_used, removed_count = save_dependence_plot(
                sample=sample,
                shap_df=shap_df,
                feature=feature,
                output_path=output_path,
                title=title,
            )
            removed_total += removed_count
            filter_records.append(
                {
                    "feature": feature,
                    "points_used": points_used,
                    "local_tail_removed": removed_count,
                    "plot_path": str(output_path),
                }
            )

        pd.DataFrame(filter_records).to_csv(biome_dir / "dependence_plot_filter_index.csv", index=False)

        summary_lines = [
            f"dataset={config.name}",
            f"biome={biome}",
            f"filtered_rows={filtered_rows}",
            f"rows={len(sample)}",
            f"feature_count={len(feature_names)}",
            "local_vertical_shap_outlier_filter=enabled",
            f"local_tail_removed_total={removed_total}",
            f"feature_names={','.join(feature_names)}",
            f"shap_sample_size={config.shap_sample_size}",
            f"r2_train_split={split_metrics['r2_train_split']}",
            f"r2_holdout_split={split_metrics['r2_holdout_split']}",
            f"split_train_rows={split_metrics['split_train_rows']}",
            f"split_test_rows={split_metrics['split_test_rows']}",
            f"dependence_dir={dependence_dir}",
            f"sample_features_path={biome_dir / 'dependence_sample_features.parquet'}",
            f"sample_shap_path={biome_dir / 'dependence_sample_shap_values.parquet'}",
            f"plot_data_path={biome_dir / 'dependence_plot_data.parquet'}",
        ]
        (biome_dir / "dependence_plots_summary.txt").write_text("\n".join(summary_lines), encoding="utf-8")
        print(f"[DONE] {config.name} | {biome}")


def main() -> None:
    args = parse_args()
    for dataset_name in args.datasets:
        run_dataset(
            config=DATASET_CONFIGS[dataset_name],
            biomes=args.biomes,
            max_missing_rate=args.max_missing_rate,
            random_state=args.random_state,
        )


if __name__ == "__main__":
    main()
