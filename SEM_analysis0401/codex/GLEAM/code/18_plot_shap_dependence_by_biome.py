#!/usr/bin/env python
"""Create per-feature SHAP dependence plots for each biome result directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from sem_gleam_common import column_allowed_by_scope, finalize_feature_table, normalize_feature_scope

try:
    import shap  # type: ignore
except Exception as exc:  # pragma: no cover
    raise ImportError("shap is required for dependence plotting.") from exc


META_COLUMNS = {
    "event_uid",
    "metric",
    "code_id",
    "biome",
    "soil_layer",
    "drought_type",
    "lat",
    "lon",
    "event_id",
    "onset_year",
    "onset_doy",
    "drought_start_year",
    "drought_start_doy",
    "onset_start_date",
    "drought_start_date",
}

LEAKAGE_COLUMNS = {
    "actual_window_after",
    "lu_event_valid",
    "response_detected",
    "t_response_onset_start",
    "t_response_drought_start",
    "t_peak",
    "t_peak_abs",
    "t_peak_drought_start",
    "t_peak_abs_drought_start",
    "t_impact",
    "amp_max",
    "legacy_duration",
    "t_recover_to_baseline",
    "t_recover_to_baseline_abs_peak",
    "t_recover_onset_start",
    "t_recover_drought_start",
    "t_recover_post_drought",
    "recovery_rate_to_baseline",
}

LEAKAGE_PREFIXES = (
    "flux_",
    "gpp_",
    "nee_",
    "reco_",
)

LEAKAGE_SUBSTRINGS = (
    "recover",
    "response",
)

FEATURE_LABELS = {
    "recoverywin_total_precipitation_mean": "PRE",
    "recoverywin_total_evaporation_mean": "EVA",
    "recoverywin_SMrz_mean": "SMrz",
    "recoverywin_temperature_2m_mean": "TMP",
    "recoverywin_VPD_mean": "VPD",
    "recoverywin_wind_speed_mean": "WIND",
    "recoverywin_lai_total_mean": "LAI",
    "recoverywin_ssrd_mean": "SSRD",
    "recoverywin_strd_mean": "STRD",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--result-root", required=True)
    parser.add_argument("--metric", default="RECO")
    parser.add_argument("--code-id", default="code1")
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", default="SMrz")
    parser.add_argument("--feature-scope", default="process_recoverywin")
    parser.add_argument("--target", default="t_recover_to_baseline_abs_peak")
    parser.add_argument("--include-features", nargs="+", required=True)
    parser.add_argument("--exclude-features", nargs="+", default=[])
    parser.add_argument("--biomes", nargs="+", default=["Forest", "Grassland", "Savanna", "Cropland", "Shrubland", "Wetland"])
    parser.add_argument("--limit", type=int, default=50000)
    parser.add_argument("--shap-sample-size", type=int, default=5000)
    parser.add_argument("--n-estimators", type=int, default=60)
    parser.add_argument("--n-jobs", type=int, default=4)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def filter_analysis_subset(
    df: pd.DataFrame,
    metric: str | None = None,
    code_id: str | None = None,
    biome: str | None = None,
    drought_type: str | None = None,
    soil_layer: str | None = None,
) -> pd.DataFrame:
    out = df
    if metric:
        out = out[out["metric"].astype(str) == str(metric)]
    if code_id:
        out = out[out["code_id"].astype(str) == str(code_id)]
    if biome:
        out = out[out["biome"].astype(str) == str(biome)]
    if drought_type:
        out = out[out["drought_type"].astype(str) == str(drought_type)]
    if soil_layer:
        out = out[out["soil_layer"].astype(str) == str(soil_layer)]
    return out.reset_index(drop=True)


def filter_feature_names(
    feature_names: Sequence[str],
    include_features: Sequence[str] | None = None,
    exclude_features: Sequence[str] | None = None,
) -> list[str]:
    exclude_set = {str(name) for name in (exclude_features or [])}
    if include_features:
        available = {str(name) for name in feature_names}
        return [str(name) for name in include_features if str(name) in available and str(name) not in exclude_set]
    return [str(name) for name in feature_names if str(name) not in exclude_set]


def prepare_model_inputs(
    df: pd.DataFrame,
    target: str,
    feature_scope: str,
    include_features: Sequence[str],
    exclude_features: Sequence[str],
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    work = df.copy()
    feature_scope = normalize_feature_scope(feature_scope)
    work[target] = pd.to_numeric(work[target], errors="coerce")
    work = work[work[target].notna()].reset_index(drop=True)

    feature_names: list[str] = []
    for col in work.columns:
        if col == target or col in META_COLUMNS:
            continue
        if not column_allowed_by_scope(col, feature_scope):
            continue
        if col in LEAKAGE_COLUMNS:
            continue
        if col.startswith(LEAKAGE_PREFIXES):
            continue
        if not col.startswith("recoverywin_") and any(token in col.lower() for token in LEAKAGE_SUBSTRINGS):
            continue
        if not pd.api.types.is_numeric_dtype(work[col]):
            continue
        series = pd.to_numeric(work[col], errors="coerce")
        if series.nunique(dropna=True) <= 1:
            continue
        feature_names.append(col)

    feature_names = filter_feature_names(
        feature_names,
        include_features=include_features,
        exclude_features=exclude_features,
    )
    if not feature_names:
        raise ValueError("No usable numeric features remained after filtering.")

    X = work[feature_names].apply(pd.to_numeric, errors="coerce")
    X = X.fillna(X.median(numeric_only=True))
    X = X.loc[:, X.nunique(dropna=True) > 1].astype(np.float32)
    feature_names = X.columns.tolist()
    y = work[target].astype(np.float32)
    return X, y, feature_names


def sample_for_shap(X: pd.DataFrame, sample_size: int, random_state: int) -> pd.DataFrame:
    if sample_size <= 0 or len(X) <= sample_size:
        return X.copy()
    return X.sample(n=sample_size, random_state=random_state).sort_index()


def fit_model(
    X: pd.DataFrame,
    y: pd.Series,
    n_estimators: int,
    n_jobs: int,
    random_state: int,
) -> RandomForestRegressor:
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        random_state=random_state,
        n_jobs=n_jobs,
        min_samples_leaf=2,
    )
    model.fit(X, y)
    return model


def sanitize_feature_name(feature_name: str) -> str:
    return feature_name.replace("/", "_").replace(" ", "_")


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
        if is_lower_shifted or is_vertically_stretched:
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


def rolling_mean_line(x: np.ndarray, y: np.ndarray, n_bins: int = 30) -> tuple[np.ndarray, np.ndarray]:
    if len(x) == 0:
        return np.array([]), np.array([])
    order = np.argsort(x)
    x_sorted = x[order]
    y_sorted = y[order]
    edges = np.linspace(0, len(x_sorted), num=min(n_bins, len(x_sorted)) + 1, dtype=int)
    xs: list[float] = []
    ys: list[float] = []
    for start, end in zip(edges[:-1], edges[1:]):
        if end <= start:
            continue
        xs.append(float(np.nanmean(x_sorted[start:end])))
        ys.append(float(np.nanmean(y_sorted[start:end])))
    return np.asarray(xs), np.asarray(ys)


def save_dependence_plot(
    feature_name: str,
    feature_values: np.ndarray,
    shap_values: np.ndarray,
    biome: str,
    output_path: Path,
) -> int:
    finite = np.isfinite(feature_values) & np.isfinite(shap_values)
    x = feature_values[finite]
    y = shap_values[finite]
    x, y, _ = filter_local_vertical_shap_outliers(x, y)
    label = FEATURE_LABELS.get(feature_name, feature_name)

    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    ax.scatter(x, y, s=18, alpha=0.35, color="#2f6b8a", linewidths=0)
    ax.axhline(0.0, color="#444444", linewidth=1.0, linestyle="--", alpha=0.8)
    line_x, line_y = rolling_mean_line(x, y)
    if len(line_x) > 1:
        ax.plot(line_x, line_y, color="#d77a61", linewidth=2.0)
    ax.set_title(f"{biome}: {label}", fontsize=12)
    ax.set_xlabel(label, fontsize=10)
    ax.set_ylabel("SHAP value", fontsize=10)
    ax.grid(alpha=0.18, linewidth=0.6)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return int(len(x))


def build_dependence_points_frame(
    feature_name: str,
    feature_values: np.ndarray,
    shap_values: np.ndarray,
) -> pd.DataFrame:
    finite = np.isfinite(feature_values) & np.isfinite(shap_values)
    x = feature_values[finite]
    y = shap_values[finite]
    return pd.DataFrame(
        {
            "feature": feature_name,
            "label": FEATURE_LABELS.get(feature_name, feature_name),
            "point_index": np.arange(len(x), dtype=int),
            "feature_value": x.astype(float),
            "shap_value": y.astype(float),
        }
    )


def main() -> None:
    args = parse_args()
    result_root = Path(args.result_root)
    base = pd.read_parquet(args.table)
    base = finalize_feature_table(base)

    for biome in args.biomes:
        subset = filter_analysis_subset(
            base,
            metric=args.metric,
            code_id=args.code_id,
            biome=biome,
            drought_type=args.drought_type,
            soil_layer=args.soil_layer,
        )
        if subset.empty:
            continue
        if args.limit and len(subset) > args.limit:
            subset = subset.sample(n=args.limit, random_state=args.random_state).reset_index(drop=True)

        X, y, feature_names = prepare_model_inputs(
            subset,
            target=args.target,
            feature_scope=args.feature_scope,
            include_features=args.include_features,
            exclude_features=args.exclude_features,
        )
        model = fit_model(
            X,
            y,
            n_estimators=args.n_estimators,
            n_jobs=args.n_jobs,
            random_state=args.random_state,
        )
        sample = sample_for_shap(
            X,
            sample_size=args.shap_sample_size,
            random_state=args.random_state,
        )
        print(
            f"[INFO] biome={biome} rows={len(X)} sample_rows={len(sample)} features={len(sample.columns)}",
            flush=True,
        )
        explainer = shap.TreeExplainer(model)
        try:
            shap_values = explainer.shap_values(sample, approximate=True, check_additivity=False)
        except TypeError:
            shap_values = explainer.shap_values(sample)
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        shap_array = np.asarray(shap_values, dtype=float)

        biome_dir = result_root / biome / "dependence_plots"
        biome_dir.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, object]] = []
        point_frames: list[pd.DataFrame] = []
        for idx, feature_name in enumerate(sample.columns.tolist()):
            out_path = biome_dir / f"{idx + 1:02d}_{sanitize_feature_name(feature_name)}_dependence.png"
            feature_values = sample[feature_name].to_numpy(dtype=float)
            feature_shap = shap_array[:, idx].astype(float)
            point_count = save_dependence_plot(
                feature_name=feature_name,
                feature_values=feature_values,
                shap_values=feature_shap,
                biome=biome,
                output_path=out_path,
            )
            point_frames.append(build_dependence_points_frame(feature_name, feature_values, feature_shap))
            records.append(
                {
                    "feature": feature_name,
                    "label": FEATURE_LABELS.get(feature_name, feature_name),
                    "sample_rows_used": int(len(sample)),
                    "plot_point_count": int(point_count),
                    "plot_path": str(out_path),
                }
            )

        pd.DataFrame(records).to_csv(biome_dir / "dependence_plot_index.csv", index=False)
        pd.concat(point_frames, ignore_index=True).to_csv(biome_dir / "dependence_plot_points.csv", index=False)
        metadata = {
            "biome": biome,
            "rows_available_after_filters": int(len(X)),
            "requested_shap_sample_size": int(args.shap_sample_size),
            "sample_rows_used": int(len(sample)),
            "feature_count": int(len(sample.columns)),
            "feature_names": sample.columns.tolist(),
            "total_points_written": int(sum(len(frame) for frame in point_frames)),
            "points_per_feature": {record["feature"]: record["plot_point_count"] for record in records},
        }
        (biome_dir / "dependence_plot_meta.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        print(f"[DONE] biome={biome} plots={len(records)} dir={biome_dir}", flush=True)


if __name__ == "__main__":
    main()
