#!/usr/bin/env python3
"""Redraw SHAP dependence panels with ALE, ICE, and PDP curves overlaid.

This script rebuilds one large figure per biome from the underlying SHAP
dependence data, then overlays validation response curves in the same feature
coordinate system.  It is intentionally separate from the earlier image-stitching
script: here the validation trajectories are plotted inside each dependence
panel rather than placed beside pre-rendered PNGs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

try:
    from lightgbm import LGBMRegressor
except Exception as exc:  # pragma: no cover
    raise RuntimeError("lightgbm is required to recompute ALE/ICE/PDP overlays") from exc

ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
OUT_ROOT = ROOT / "validation/compared_with_dependenceplot"
OVERLAY_ROOT = OUT_ROOT / "overlay_redrawn"
CURVE_ROOT = OUT_ROOT / "overlay_curves"
SHAP_ROOTS = {
    "GPP": ROOT
    / "results/gpp_code1_flash_smrz_v20260401_onsetpeak_clean/prepeak_event_shap_sem_20260424/shap_by_biome",
    "RECO": ROOT
    / "results/reco_code1_flash_smrz_v20260401_mswepE_clean/prepeak_event_shap_sem_20260424/shap_by_biome",
}
TABLES = {
    "GPP": ROOT / "data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet",
    "RECO": ROOT / "data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet",
}

TARGET = "t_recover_to_baseline_abs_peak"
BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
METRICS = ["GPP", "RECO"]
FEATURES = [
    ("prepeak_ssrd_mean", "SSRD"),
    ("prepeak_total_evaporation_mean", "|EVA|"),
    ("prepeak_temperature_2m_mean", "TMP"),
    ("prepeak_VPD_mean", "VPD"),
    ("prepeak_SMrz_mean", "SMrz"),
    ("prepeak_total_precipitation_mean", "PRE"),
    ("prepeak_strd_mean", "STRD"),
    ("prepeak_wind_speed_mean", "WIND"),
    ("event_duration", "Duration"),
    ("event_intensity", "Intensity"),
]
FEATURE_COLS = [f for f, _ in FEATURES]
LABEL_BY_FEATURE = dict(FEATURES)


@dataclass
class Curves:
    ale: pd.DataFrame | None
    ice_mean: pd.DataFrame | None
    ice_lines: pd.DataFrame | None
    pdp: pd.DataFrame | None


def display_values(feature: str, values: np.ndarray | pd.Series) -> np.ndarray:
    vals = np.asarray(values, dtype=float)
    if "precipitation" in feature:
        finite = vals[np.isfinite(vals)]
        if len(finite) and np.nanquantile(np.abs(finite), 0.99) < 1.0:
            return vals * 1000.0
        return vals
    if "evaporation" in feature:
        vals = np.abs(vals)
        finite = vals[np.isfinite(vals)]
        if len(finite) and np.nanquantile(np.abs(finite), 0.99) < 1.0:
            return vals * 1000.0
        return vals
    if feature == "prepeak_VPD_mean":
        return vals / 10.0
    return vals


def axis_label(feature: str) -> str:
    units = {
        "prepeak_total_precipitation_mean": "mm",
        "prepeak_total_evaporation_mean": "mm",
        "prepeak_temperature_2m_mean": "K",
        "prepeak_VPD_mean": "kPa",
        "prepeak_SMrz_mean": "m3/m3",
        "event_duration": "days",
    }
    label = LABEL_BY_FEATURE.get(feature, feature)
    unit = units.get(feature, "")
    return f"{label} ({unit})" if unit else label


def finite_pair(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def clip_dependence_points(feature: str, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x, y = finite_pair(x, y)
    if len(x) < 5:
        return x, y
    lo_x, hi_x = np.nanquantile(x, [0.01, 0.99])
    lo_y, hi_y = np.nanquantile(y, [0.005, 0.995])
    mask = (x >= lo_x) & (x <= hi_x) & (y >= lo_y) & (y <= hi_y)
    return x[mask], y[mask]


def binned_trend(x: np.ndarray, y: np.ndarray, bins: int = 28) -> tuple[np.ndarray, np.ndarray]:
    x, y = finite_pair(x, y)
    if len(x) < 20:
        order = np.argsort(x)
        return x[order], y[order]
    edges = np.unique(np.nanquantile(x, np.linspace(0, 1, bins + 1)))
    xs: list[float] = []
    ys: list[float] = []
    for left, right in zip(edges[:-1], edges[1:]):
        if right <= left:
            continue
        mask = (x >= left) & (x <= right if right == edges[-1] else x < right)
        if mask.sum() < 5:
            continue
        xs.append(float(np.nanmedian(x[mask])))
        ys.append(float(np.nanmedian(y[mask])))
    return np.asarray(xs), np.asarray(ys)


def quantile_grid(values: pd.Series, grid_size: int = 25, low_q: float = 0.02, high_q: float = 0.98) -> np.ndarray:
    vals = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return np.array([], dtype=float)
    return np.unique(np.nanquantile(vals, np.linspace(low_q, high_q, grid_size))).astype(float)


def compute_ale(model: LGBMRegressor, X: pd.DataFrame, feature: str, bins: int = 20) -> pd.DataFrame:
    values = X[feature].to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    if len(finite) < 20:
        return pd.DataFrame()
    edges = np.unique(np.nanquantile(finite, np.linspace(0, 1, bins + 1)))
    effects: list[float] = []
    centers: list[float] = []
    counts: list[int] = []
    for left, right in zip(edges[:-1], edges[1:]):
        if right <= left:
            continue
        mask = (values >= left) & (values <= right if right == edges[-1] else values < right)
        if not np.any(mask):
            continue
        X_bin = X.loc[mask].copy()
        X_low = X_bin.copy()
        X_high = X_bin.copy()
        X_low[feature] = left
        X_high[feature] = right
        effects.append(float(np.nanmean(model.predict(X_high) - model.predict(X_low))))
        centers.append(float((left + right) / 2))
        counts.append(int(mask.sum()))
    if not effects:
        return pd.DataFrame()
    ale = np.cumsum(np.asarray(effects))
    ale = ale - np.average(ale, weights=np.asarray(counts))
    return pd.DataFrame({"feature_value": centers, "effect": ale, "bin_count": counts})


def compute_pdp(model: LGBMRegressor, X: pd.DataFrame, feature: str, grid_size: int = 25) -> pd.DataFrame:
    grid = quantile_grid(X[feature], grid_size=grid_size)
    if len(grid) < 2:
        return pd.DataFrame()
    eval_X = X.sample(n=min(5000, len(X)), random_state=42).copy()
    baseline = float(np.nanmean(model.predict(eval_X)))
    rows = []
    for value in grid:
        X_mod = eval_X.copy()
        X_mod[feature] = value
        rows.append({"feature_value": float(value), "effect": float(np.nanmean(model.predict(X_mod)) - baseline)})
    return pd.DataFrame(rows)


def compute_ice(model: LGBMRegressor, X: pd.DataFrame, feature: str, grid_size: int = 25) -> tuple[pd.DataFrame, pd.DataFrame]:
    grid = quantile_grid(X[feature], grid_size=grid_size)
    if len(grid) < 2:
        return pd.DataFrame(), pd.DataFrame()
    sample = X.sample(n=min(50, len(X)), random_state=42).copy()
    base = model.predict(sample)
    rows = []
    for sample_pos, (idx, row) in enumerate(sample.iterrows()):
        repeated = pd.DataFrame([row.to_dict()] * len(grid), columns=X.columns)
        repeated[feature] = grid
        effects = model.predict(repeated) - base[sample_pos]
        for value, effect in zip(grid, effects):
            rows.append({"sample_index": idx, "feature_value": float(value), "effect": float(effect)})
    ice = pd.DataFrame(rows)
    mean = ice.groupby("feature_value", as_index=False)["effect"].mean()
    return mean, ice


def fit_validation_model(metric: str, biome: str) -> tuple[LGBMRegressor, pd.DataFrame]:
    columns = ["biome", TARGET] + FEATURE_COLS
    df = pd.read_parquet(TABLES[metric], columns=columns)
    df = df[df["biome"] == biome].copy()
    frame = df[FEATURE_COLS + [TARGET]].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna(axis=0, how="any")
    if len(frame) > 50000:
        frame = frame.sample(n=50000, random_state=42).sort_index()
    X = frame[FEATURE_COLS].copy()
    y = frame[TARGET].copy()
    X_train, X_test, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=42)
    model = LGBMRegressor(
        objective="regression",
        n_estimators=260,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=30,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=8,
        verbosity=-1,
    )
    model.fit(X_train, y_train)
    return model, X_test


def load_shap_dependence(metric: str, biome: str) -> pd.DataFrame:
    return pd.read_parquet(SHAP_ROOTS[metric] / biome / "dependence_plot_data.parquet")


def save_curve_tables(metric: str, biome: str, feature: str, curves: Curves) -> None:
    sub = CURVE_ROOT / metric / biome
    sub.mkdir(parents=True, exist_ok=True)
    label = LABEL_BY_FEATURE[feature].replace("|", "")
    if curves.ale is not None and not curves.ale.empty:
        curves.ale.to_csv(sub / f"{label}_ale_overlay_curve.csv", index=False)
    if curves.ice_mean is not None and not curves.ice_mean.empty:
        curves.ice_mean.to_csv(sub / f"{label}_ice_mean_overlay_curve.csv", index=False)
    if curves.ice_lines is not None and not curves.ice_lines.empty:
        curves.ice_lines.to_csv(sub / f"{label}_ice_sample_overlay_curves.csv", index=False)
    if curves.pdp is not None and not curves.pdp.empty:
        curves.pdp.to_csv(sub / f"{label}_pdp_overlay_curve.csv", index=False)


def build_curves() -> dict[tuple[str, str, str], Curves]:
    all_curves: dict[tuple[str, str, str], Curves] = {}
    for metric in METRICS:
        for biome in BIOMES:
            print(f"Fitting validation model: {metric} {biome}", flush=True)
            model, X_test = fit_validation_model(metric, biome)
            for feature in FEATURE_COLS:
                ale = compute_ale(model, X_test, feature)
                ice_mean, ice_lines = compute_ice(model, X_test, feature)
                pdp = compute_pdp(model, X_test, feature)
                curves = Curves(ale=ale, ice_mean=ice_mean, ice_lines=ice_lines, pdp=pdp)
                all_curves[(metric, biome, feature)] = curves
                save_curve_tables(metric, biome, feature, curves)
    return all_curves


def plot_curve(ax: plt.Axes, feature: str, df: pd.DataFrame | None, color: str, label: str, ls: str = "-") -> None:
    if df is None or df.empty:
        return
    x = display_values(feature, df["feature_value"])
    y = df["effect"].to_numpy(dtype=float)
    order = np.argsort(x)
    ax.plot(x[order], y[order], color=color, linewidth=1.65, linestyle=ls, label=label, alpha=0.95)


def plot_ice_samples(ax: plt.Axes, feature: str, df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        return
    for _, sub in list(df.groupby("sample_index"))[:20]:
        x = display_values(feature, sub["feature_value"])
        y = sub["effect"].to_numpy(dtype=float)
        order = np.argsort(x)
        ax.plot(x[order], y[order], color="#66a61e", linewidth=0.45, alpha=0.12)


def plot_panel(ax: plt.Axes, shap_df: pd.DataFrame, curves: Curves, metric: str, feature: str) -> None:
    x_col = f"feature__{feature}"
    y_col = f"shap__{feature}"
    if x_col not in shap_df.columns or y_col not in shap_df.columns:
        ax.text(0.5, 0.5, "SHAP data missing", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return
    x_raw, y = clip_dependence_points(feature, shap_df[x_col].to_numpy(dtype=float), shap_df[y_col].to_numpy(dtype=float))
    x = display_values(feature, x_raw)
    ax.scatter(x, y, s=4, color="#4d4d4d", alpha=0.16, edgecolors="none", rasterized=True)
    tx, ty = binned_trend(x, y)
    if len(tx) > 1:
        ax.plot(tx, ty, color="#000000", linewidth=1.65, label="SHAP trend")
    plot_curve(ax, feature, curves.ale, "#d95f02", "ALE")
    plot_curve(ax, feature, curves.ice_mean, "#1b9e77", "ICE mean")
    plot_curve(ax, feature, curves.pdp, "#7570b3", "PDP", ls="--")
    ax.axhline(0, color="#8a8a8a", linestyle=":", linewidth=0.8)
    if len(x):
        lo, hi = np.nanquantile(x, [0.01, 0.99])
        pad = (hi - lo) * 0.04 if hi > lo else 1.0
        ax.set_xlim(lo - pad, hi + pad)
    ax.set_title(f"{metric} | {LABEL_BY_FEATURE[feature]}", fontsize=9, pad=3)
    ax.set_xlabel(axis_label(feature), fontsize=8)
    ax.set_ylabel("Effect on recovery time (days)", fontsize=8)
    ax.tick_params(labelsize=7, length=2.5)
    ax.grid(alpha=0.16, linestyle="--", linewidth=0.6)


def draw_biome_figure(biome: str, curves: dict[tuple[str, str, str], Curves]) -> Path:
    shap_frames = {metric: load_shap_dependence(metric, biome) for metric in METRICS}
    fig, axes = plt.subplots(
        nrows=len(FEATURES),
        ncols=2,
        figsize=(12.5, 24.0),
        constrained_layout=False,
    )
    for row, (feature, label) in enumerate(FEATURES):
        for col, metric in enumerate(METRICS):
            ax = axes[row, col]
            plot_panel(ax, shap_frames[metric], curves[(metric, biome, feature)], metric, feature)
        axes[row, 0].text(
            -0.28,
            0.5,
            label,
            transform=axes[row, 0].transAxes,
            ha="right",
            va="center",
            fontsize=10,
            fontweight="bold",
        )
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 0.985))
    fig.suptitle(
        f"{biome}: SHAP dependence with ALE, ICE, and PDP overlays",
        fontsize=14,
        fontweight="bold",
        y=0.998,
    )
    fig.subplots_adjust(top=0.968, left=0.10, right=0.985, bottom=0.035, hspace=0.55, wspace=0.25)
    out = OVERLAY_ROOT / f"{biome}_dependence_with_ALE_ICE_PDP_overlay.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=240)
    plt.close(fig)
    return out


def main() -> None:
    OVERLAY_ROOT.mkdir(parents=True, exist_ok=True)
    CURVE_ROOT.mkdir(parents=True, exist_ok=True)
    curves = build_curves()
    rows = []
    for biome in BIOMES:
        out = draw_biome_figure(biome, curves)
        rows.append({"biome": biome, "output_png": str(out)})
    pd.DataFrame(rows).to_csv(OUT_ROOT / "overlay_redrawn_index.csv", index=False)
    (OUT_ROOT / "README_overlay_redrawn.md").write_text(
        "\n".join(
            [
                "# Redrawn dependence plots with validation overlays",
                "",
                "These figures redraw the SHAP dependence panels from the underlying parquet data.",
                "ALE, ICE mean, and PDP curves are recomputed using the same 10-feature set used in the no-LAI-with-Intensity dependence figures.",
                "ICE is shown only as the mean trajectory to avoid stretching the y-axis with individual high-variance curves.",
                "All curves are centered effects on recovery time, so they can be compared with SHAP contribution direction and threshold shape.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
