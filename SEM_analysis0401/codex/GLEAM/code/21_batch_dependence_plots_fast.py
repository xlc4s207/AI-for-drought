#!/usr/bin/env python
"""Fast biome-wise SHAP dependence plotting using LightGBM and high parallelism."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

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


FEATURE_LABELS = {
    "recoverywin_total_precipitation_mean": "PRE(mean, recoverywin)",
    "recoverywin_total_evaporation_mean": "EVA(mean, recoverywin)",
    "recoverywin_temperature_2m_mean": "TMP(mean, recoverywin)",
    "recoverywin_VPD_mean": "VPD(mean, recoverywin)",
    "recoverywin_SMrz_mean": "SMrz(mean, recoverywin)",
    "recoverywin_lai_total_mean": "LAI(mean, recoverywin)",
    "recoverywin_ssrd_mean": "SSRD(mean, recoverywin)",
    "recoverywin_strd_mean": "STRD(mean, recoverywin)",
    "recoverywin_wind_speed_mean": "WIND(mean, recoverywin)",
    "prepeak_total_precipitation_mean": "PRE(mean, prepeak)",
    "prepeak_total_evaporation_mean": "EVA(mean, prepeak)",
    "prepeak_temperature_2m_mean": "TMP(mean, prepeak)",
    "prepeak_VPD_mean": "VPD(mean, prepeak)",
    "prepeak_SMrz_mean": "SMrz(mean, prepeak)",
    "prepeak_lai_total_mean": "LAI(mean, prepeak)",
    "prepeak_ssrd_mean": "SSRD(mean, prepeak)",
    "prepeak_strd_mean": "STRD(mean, prepeak)",
    "prepeak_wind_speed_mean": "WIND(mean, prepeak)",
    "shock_total_precipitation_mean": "PRE(mean, shock)",
    "shock_total_evaporation_mean": "EVA(mean, shock)",
    "shock_temperature_2m_mean": "TMP(mean, shock)",
    "shock_VPD_mean": "VPD(mean, shock)",
    "shock_SMrz_mean": "SMrz(mean, shock)",
    "shock_lai_total_mean": "LAI(mean, shock)",
    "shock_ssrd_mean": "SSRD(mean, shock)",
    "shock_strd_mean": "STRD(mean, shock)",
    "shock_wind_speed_mean": "WIND(mean, shock)",
    "event_onset_days": "Onset days",
    "event_duration": "Event duration",
    "event_intensity": "Event intensity",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--metric", default="GPP")
    parser.add_argument("--code-id", default="code1")
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", default="SMrz")
    parser.add_argument("--feature-scope", default="process_recoverywin")
    parser.add_argument("--target", default="t_recover_to_baseline_abs_peak")
    parser.add_argument("--biomes", nargs="+", default=["Forest", "Grassland", "Savanna", "Cropland", "Shrubland", "Wetland"])
    parser.add_argument("--include-features", nargs="+", required=True)
    parser.add_argument("--exclude-features", nargs="+", default=[])
    parser.add_argument("--limit", type=int, default=50000)
    parser.add_argument("--model-backend", choices=("lightgbm", "random_forest"), default="lightgbm")
    parser.add_argument("--n-estimators", type=int, default=500)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--shap-sample-size", type=int, default=5000)
    parser.add_argument("--max-missing-rate", type=float, default=0.3)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--event-duration-max", type=float, default=1000.0)
    parser.add_argument("--event-intensity-max", type=float, default=50.0)
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


def filter_plotting_outliers(
    sample: pd.DataFrame,
    shap_df: pd.DataFrame,
    event_duration_max: float,
    event_intensity_max: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = pd.Series(True, index=sample.index)
    if "event_duration" in sample.columns:
        duration = pd.to_numeric(sample["event_duration"], errors="coerce")
        mask &= duration.notna() & (duration <= event_duration_max)
    if "event_intensity" in sample.columns:
        intensity = pd.to_numeric(sample["event_intensity"], errors="coerce")
        mask &= intensity.notna() & (intensity <= event_intensity_max)
    kept_index = sample.index[mask]
    return sample.loc[kept_index].copy(), shap_df.loc[kept_index].copy()


def save_dependence_plot(sample: pd.DataFrame, shap_df: pd.DataFrame, feature: str, output_path: Path, title: str) -> tuple[int, int]:
    values = pd.to_numeric(sample[feature], errors="coerce").to_numpy(dtype=float)
    shap_values = pd.to_numeric(shap_df[feature], errors="coerce").to_numpy(dtype=float)
    x, y, removed_count = filter_local_vertical_shap_outliers(values, shap_values)
    if len(x) == 0:
        return 0, removed_count

    order = np.argsort(x)
    x = x[order]
    y = y[order]

    density = None
    if len(x) >= 20:
        try:
            bins = min(40, max(10, len(x) // 100))
            counts, xedges, yedges = np.histogram2d(x, y, bins=bins)
            x_idx = np.clip(np.digitize(x, xedges) - 1, 0, counts.shape[0] - 1)
            y_idx = np.clip(np.digitize(y, yedges) - 1, 0, counts.shape[1] - 1)
            density = counts[x_idx, y_idx]
        except Exception:
            density = None

    plt.figure(figsize=(7.8, 5.8))
    plt.axhline(0.0, color="#6e6e6e", linewidth=1.0, linestyle="--", alpha=0.8, zorder=1)
    scatter = plt.scatter(
        x,
        y,
        c=density if density is not None else "#2f6b8a",
        cmap="viridis" if density is not None else None,
        s=12,
        alpha=0.55,
        edgecolors="none",
        zorder=2,
    )
    if density is not None:
        cbar = plt.colorbar(scatter)
        cbar.set_label("Local point density", fontsize=11)
        cbar.ax.tick_params(labelsize=10)
    if len(x) >= 20:
        window = max(9, len(x) // 30)
        trend = pd.Series(y).rolling(window=window, center=True, min_periods=1).mean()
        plt.plot(x, trend.to_numpy(), color="#c83349", linewidth=2.0, alpha=0.9, zorder=3)

    plt.xlabel(FEATURE_LABELS.get(feature, feature), fontsize=12)
    plt.ylabel(f"SHAP value for {FEATURE_LABELS.get(feature, feature)}", fontsize=12)
    plt.title(title, fontsize=13)
    plt.xticks(fontsize=10)
    plt.yticks(fontsize=10)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=220)
    plt.close()
    return int(len(x)), int(removed_count)


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    backend = resolve_model_backend(args.model_backend)

    df = pd.read_parquet(args.table)
    df = finalize_feature_table(df)

    for biome in args.biomes:
        biome_dir = output_root / biome
        dependence_dir = biome_dir / "dependence_plots"
        dependence_dir.mkdir(parents=True, exist_ok=True)

        sub = filter_analysis_subset(
            df,
            metric=args.metric,
            code_id=args.code_id,
            biome=biome,
            drought_type=args.drought_type,
            soil_layer=args.soil_layer,
        )
        if args.limit and len(sub) > args.limit:
            sub = sub.head(args.limit).copy()

        X, y, feature_names = prepare_model_inputs(
            sub,
            target=args.target,
            max_missing_rate=args.max_missing_rate,
            feature_scope=args.feature_scope,
            include_features=args.include_features,
            exclude_features=args.exclude_features,
        )

        split_metrics = compute_split_r2(
            X,
            y,
            backend=backend,
            random_state=args.random_state,
            n_estimators=args.n_estimators,
            n_jobs=args.n_jobs,
        )
        model = fit_tree_model(
            X,
            y,
            backend=backend,
            random_state=args.random_state,
            n_estimators=args.n_estimators,
            n_jobs=args.n_jobs,
        )
        sample = sample_for_shap(X, sample_size=args.shap_sample_size, random_state=args.random_state)
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(sample)
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        shap_df = pd.DataFrame(np.asarray(shap_values), columns=sample.columns, index=sample.index)
        raw_sample_rows = len(sample)
        sample, shap_df = filter_plotting_outliers(
            sample,
            shap_df,
            event_duration_max=args.event_duration_max,
            event_intensity_max=args.event_intensity_max,
        )

        sample.to_parquet(biome_dir / "dependence_sample_features.parquet", index=True)
        shap_df.to_parquet(biome_dir / "dependence_sample_shap_values.parquet", index=True)
        merged = sample.add_prefix("feature__").join(shap_df.add_prefix("shap__"), how="left")
        merged.to_parquet(biome_dir / "dependence_plot_data.parquet", index=True)

        filter_records: list[dict[str, object]] = []
        removed_total = 0
        for feature in feature_names:
            points_used, removed_count = save_dependence_plot(
                sample=sample,
                shap_df=shap_df,
                feature=feature,
                output_path=dependence_dir / f"{sanitize_feature_name(feature)}.png",
                title=f"fast_lgbm | {biome} | {FEATURE_LABELS.get(feature, feature)}",
            )
            removed_total += removed_count
            filter_records.append(
                {
                    "feature": feature,
                    "points_used": points_used,
                    "local_tail_removed": removed_count,
                    "plot_path": str(dependence_dir / f"{sanitize_feature_name(feature)}.png"),
                }
            )

        pd.DataFrame(filter_records).to_csv(biome_dir / "dependence_plot_filter_index.csv", index=False)
        summary_lines = [
            "fast biome-wise dependence analysis",
            f"biome={biome}",
            f"filtered_rows={len(sub)}",
            f"rows_before_plot_filter={raw_sample_rows}",
            f"rows={len(sample)}",
            f"plot_filter_removed={raw_sample_rows - len(sample)}",
            f"feature_count={len(feature_names)}",
            "local_vertical_shap_outlier_filter=enabled",
            f"local_tail_removed_total={removed_total}",
            f"feature_names={','.join(feature_names)}",
            f"model_backend={backend}",
            f"n_estimators={args.n_estimators}",
            f"n_jobs={args.n_jobs}",
            f"shap_sample_size={args.shap_sample_size}",
            f"event_duration_max={args.event_duration_max}",
            f"event_intensity_max={args.event_intensity_max}",
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
        print(f"[DONE] fast biome={biome}")


if __name__ == "__main__":
    main()
