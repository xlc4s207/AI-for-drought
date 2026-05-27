#!/usr/bin/env python3
"""Overlay orthogonal SHAP dependence with ALE/ICE/PDP and OPGD annotations."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


WORK_DIR = Path(__file__).resolve().parent
GLEAM = WORK_DIR.parents[1]
ORTHO = GLEAM / "plots2/prepeak_shap_nomulticollinearity/orthogonal_decomposition"
NOMULTI_SCRIPT = GLEAM / "plots2/prepeak_shap_nomulticollinearity/run_prepeak_nomulticollinearity_shap.py"
OUT = WORK_DIR / "orthogonal_comparison" / "validation_overlay_by_biome"

BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
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
PRE_REFERENCE_TICKS = np.array([-1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5], dtype=float)
SHAP_SIGN_FLIP_FEATURES: set[str] = set()
LABELS = {
    "SSRD_z": "SSRD",
    "Pre_z": "PRE",
    "Duration_z": "Duration",
    "Intensity_z": "Intensity",
    "Wind_z": "WIND",
    "STRD_resid_after_SSRD": "STRD_resid",
    "TMP_resid_after_SSRD_STRD": "TMP_resid",
    "VPD_resid_after_SSRD_TMP_Wind": "VPD_resid",
    "EVA_resid_after_SSRD_Pre_VPD": "EVA_resid",
    "SMrz_resid_after_Pre_EVA": "SMrz_resid",
}
RAW_FEATURE_BY_ORTHO = {
    "SSRD_z": "prepeak_ssrd_mean",
    "EVA_resid_after_SSRD_Pre_VPD": "prepeak_total_evaporation_mean",
    "TMP_resid_after_SSRD_STRD": "prepeak_temperature_2m_mean",
    "VPD_resid_after_SSRD_TMP_Wind": "prepeak_VPD_mean",
    "SMrz_resid_after_Pre_EVA": "prepeak_SMrz_mean",
    "Pre_z": "prepeak_total_precipitation_mean",
    "STRD_resid_after_SSRD": "prepeak_strd_mean",
    "Wind_z": "prepeak_wind_speed_mean",
    "Duration_z": "event_duration",
    "Intensity_z": "event_intensity",
}
RAW_LABEL_BY_ORTHO = {
    "SSRD_z": "SSRD",
    "EVA_resid_after_SSRD_Pre_VPD": "|EVA|",
    "TMP_resid_after_SSRD_STRD": "TMP",
    "VPD_resid_after_SSRD_TMP_Wind": "VPD",
    "SMrz_resid_after_Pre_EVA": "SMrz",
    "Pre_z": "PRE",
    "STRD_resid_after_SSRD": "STRD",
    "Wind_z": "WIND",
    "Duration_z": "Duration",
    "Intensity_z": "Intensity",
}


def load_nomulti_module():
    spec = importlib.util.spec_from_file_location("nomulti_shap_module", NOMULTI_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {NOMULTI_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def quantile_grid(values: pd.Series, grid_size: int = 25, low_q: float = 0.02, high_q: float = 0.98) -> np.ndarray:
    vals = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return np.array([], dtype=float)
    return np.unique(np.nanquantile(vals, np.linspace(low_q, high_q, grid_size))).astype(float)


def compute_ale(model, X: pd.DataFrame, feature: str, bins: int = 20) -> pd.DataFrame:
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
        centers.append(float((left + right) / 2.0))
        counts.append(int(mask.sum()))
    if not effects:
        return pd.DataFrame()
    ale = np.cumsum(np.asarray(effects))
    ale = ale - np.average(ale, weights=np.asarray(counts))
    return pd.DataFrame({"feature_value": centers, "effect": ale, "bin_count": counts})


def compute_pdp(model, X: pd.DataFrame, feature: str, grid_size: int = 25) -> pd.DataFrame:
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


def compute_ice_mean(model, X: pd.DataFrame, feature: str, grid_size: int = 25) -> pd.DataFrame:
    ice = compute_ice_curves(model, X, feature, grid_size=grid_size)
    if ice.empty:
        return pd.DataFrame()
    return ice.groupby("feature_value", as_index=False)["effect"].mean()


def compute_ice_curves(model, X: pd.DataFrame, feature: str, grid_size: int = 25, n_samples: int = 60) -> pd.DataFrame:
    grid = quantile_grid(X[feature], grid_size=grid_size)
    if len(grid) < 2:
        return pd.DataFrame()
    sample = X.sample(n=min(n_samples, len(X)), random_state=42).copy()
    base = model.predict(sample)
    rows = []
    for sample_pos, (_, row) in enumerate(sample.iterrows()):
        repeated = pd.DataFrame([row.to_dict()] * len(grid), columns=X.columns)
        repeated[feature] = grid
        effects = model.predict(repeated) - base[sample_pos]
        for value, effect in zip(grid, effects):
            rows.append({"sample_index": int(sample_pos), "feature_value": float(value), "effect": float(effect)})
    return pd.DataFrame(rows)


def build_orthogonal_xy(module, metric: str, biome: str) -> tuple[pd.DataFrame, pd.Series, object]:
    cfg = next(item for item in module.METRICS if item.metric == metric)
    df_metric = module.finalize_feature_table(pd.read_parquet(cfg.table))
    sub = module.filter_analysis_subset(df_metric, metric=metric, code_id="code1", biome=biome, drought_type="flash", soil_layer="SMrz")
    if len(sub) > module.ROW_LIMIT:
        sub = sub.head(module.ROW_LIMIT).copy()
    raw, y = module.prepare_raw_xy(sub)
    # Write transform details to a cache folder; this keeps transformation exactly
    # aligned with the orthogonal SHAP workflow without touching the main result folders.
    cache = OUT / "_transform_cache" / metric / biome
    cache.mkdir(parents=True, exist_ok=True)
    X, _ = module.build_orthogonal_inputs(raw, cache)
    model = module.fit_tree_model(
        X,
        y,
        backend=module.resolve_model_backend("lightgbm"),
        random_state=module.RANDOM_STATE,
        n_estimators=module.N_ESTIMATORS,
        n_jobs=module.N_JOBS,
    )
    return X, y, model


def compute_or_load_curves(module, metric: str, biome: str) -> dict[str, dict[str, pd.DataFrame]]:
    curve_dir = OUT / "curves" / metric / biome
    curve_dir.mkdir(parents=True, exist_ok=True)
    expected = []
    for feature in FEATURE_ORDER:
        expected.extend(
            [
                curve_dir / f"{feature}_ale.csv",
                curve_dir / f"{feature}_ice_mean.csv",
                curve_dir / f"{feature}_ice_samples.csv",
                curve_dir / f"{feature}_pdp.csv",
            ]
        )
    if all(p.exists() for p in expected):
        curves = {}
        for feature in FEATURE_ORDER:
            curves[feature] = {
                "ALE": pd.read_csv(curve_dir / f"{feature}_ale.csv"),
                "ICE mean": pd.read_csv(curve_dir / f"{feature}_ice_mean.csv"),
                "ICE samples": pd.read_csv(curve_dir / f"{feature}_ice_samples.csv"),
                "PDP": pd.read_csv(curve_dir / f"{feature}_pdp.csv"),
            }
        return curves
    X, _, model = build_orthogonal_xy(module, metric, biome)
    curves = {}
    for feature in FEATURE_ORDER:
        ale = compute_ale(model, X, feature)
        ice_samples = compute_ice_curves(model, X, feature)
        ice = ice_samples.groupby("feature_value", as_index=False)["effect"].mean() if not ice_samples.empty else pd.DataFrame()
        pdp = compute_pdp(model, X, feature)
        ale.to_csv(curve_dir / f"{feature}_ale.csv", index=False)
        ice.to_csv(curve_dir / f"{feature}_ice_mean.csv", index=False)
        ice_samples.to_csv(curve_dir / f"{feature}_ice_samples.csv", index=False)
        pdp.to_csv(curve_dir / f"{feature}_pdp.csv", index=False)
        curves[feature] = {"ALE": ale, "ICE mean": ice, "ICE samples": ice_samples, "PDP": pdp}
    return curves


def robust_limits(values: np.ndarray, low: float = 0.01, high: float = 0.99) -> tuple[float, float]:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return -1.0, 1.0
    lo, hi = np.nanquantile(vals, [low, high])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        med = float(np.nanmedian(vals))
        return med - 1.0, med + 1.0
    pad = 0.04 * (hi - lo)
    return float(lo - pad), float(hi + pad)


def binned_trend(x: np.ndarray, y: np.ndarray, bins: int = 30) -> tuple[np.ndarray, np.ndarray]:
    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]
    y = y[ok]
    if len(x) < 30:
        order = np.argsort(x)
        return x[order], y[order]
    edges = np.unique(np.nanquantile(x, np.linspace(0, 1, bins + 1)))
    xs = []
    ys = []
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (x >= left) & (x <= right if right == edges[-1] else x < right)
        if mask.sum() >= 8:
            xs.append(float(np.nanmedian(x[mask])))
            ys.append(float(np.nanmedian(y[mask])))
    return np.asarray(xs), np.asarray(ys)


def plot_curve(
    ax: plt.Axes,
    df: pd.DataFrame,
    color: str,
    label: str,
    ls: str = "-",
    x_transform=None,
    y_multiplier: float = 1.0,
) -> None:
    if df.empty:
        return
    x = pd.to_numeric(df["feature_value"], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(df["effect"], errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]
    y = y[ok]
    y = y * y_multiplier
    if x_transform is not None:
        x = x_transform(x)
    order = np.argsort(x)
    ax.plot(x[order], y[order], color=color, lw=1.55, ls=ls, label=label, alpha=0.95)


def plot_ice_samples(ax: plt.Axes, df: pd.DataFrame, max_lines: int = 30) -> None:
    if df.empty or "sample_index" not in df.columns:
        return
    for _, sub in list(df.groupby("sample_index", sort=True))[:max_lines]:
        x = pd.to_numeric(sub["feature_value"], errors="coerce").to_numpy(dtype=float)
        y = pd.to_numeric(sub["effect"], errors="coerce").to_numpy(dtype=float)
        ok = np.isfinite(x) & np.isfinite(y)
        if np.count_nonzero(ok) < 2:
            continue
        x = x[ok]
        y = y[ok]
        order = np.argsort(x)
        ax.plot(x[order], y[order], color="#66a61e", lw=0.42, alpha=0.14, zorder=1)


def load_opgd_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    opgd = pd.read_csv(WORK_DIR / "opgd_factor_q.csv")
    reliability = pd.read_csv(WORK_DIR / "reliability" / "reliability_score.csv")
    return opgd, reliability


def compute_panel_xlim(dep: pd.DataFrame, feature: str) -> tuple[float, float]:
    x = pd.to_numeric(dep[f"feature__{feature}"], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(dep[f"shap__{feature}"], errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]
    y = y[ok]
    if len(x):
        xlo, xhi = np.nanquantile(x, [0.01, 0.99])
        ylo, yhi = np.nanquantile(y, [0.005, 0.995])
        keep = (x >= xlo) & (x <= xhi) & (y >= ylo) & (y <= yhi)
        x = x[keep]
    return robust_limits(x)


def linear_x_mapper(source_xlim: tuple[float, float], target_xlim: tuple[float, float]):
    src_lo, src_hi = source_xlim
    dst_lo, dst_hi = target_xlim
    if not all(np.isfinite([src_lo, src_hi, dst_lo, dst_hi])) or src_hi <= src_lo or dst_hi <= dst_lo:
        return None

    def mapper(values: np.ndarray) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        return dst_lo + (arr - src_lo) / (src_hi - src_lo) * (dst_hi - dst_lo)

    return mapper


def plot_panel(
    ax: plt.Axes,
    dep: pd.DataFrame,
    feature: str,
    metric: str,
    biome: str,
    curves: dict[str, pd.DataFrame],
    opgd: pd.DataFrame,
    reliability: pd.DataFrame,
    xlim_override: tuple[float, float] | None = None,
    xticks_override: np.ndarray | None = None,
    x_transform=None,
) -> None:
    x = pd.to_numeric(dep[f"feature__{feature}"], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(dep[f"shap__{feature}"], errors="coerce").to_numpy(dtype=float)
    if feature in SHAP_SIGN_FLIP_FEATURES:
        y = -y
    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]
    y = y[ok]
    if len(x):
        xlo, xhi = np.nanquantile(x, [0.01, 0.99])
        ylo, yhi = np.nanquantile(y, [0.005, 0.995])
        keep = (x >= xlo) & (x <= xhi) & (y >= ylo) & (y <= yhi)
        x = x[keep]
        y = y[keep]
    plot_x = x_transform(x) if x_transform is not None else x
    ax.scatter(plot_x, y, s=5, alpha=0.17, color="#4d4d4d", linewidths=0, rasterized=True)
    tx, ty = binned_trend(plot_x, y)
    if len(tx) > 1:
        ax.plot(tx, ty, color="#000000", lw=1.55, label="SHAP trend")
    y_multiplier = -1.0 if feature in SHAP_SIGN_FLIP_FEATURES else 1.0
    plot_curve(ax, curves["ALE"], "#d95f02", "ALE", x_transform=x_transform, y_multiplier=y_multiplier)
    plot_curve(ax, curves["ICE mean"], "#1b9e77", "ICE mean", x_transform=x_transform, y_multiplier=y_multiplier)
    plot_curve(ax, curves["PDP"], "#7570b3", "PDP", ls="--", x_transform=x_transform, y_multiplier=y_multiplier)
    ax.axhline(0, color="#777777", lw=0.75, ls=":", alpha=0.9)
    xlim = xlim_override if xlim_override is not None else robust_limits(plot_x)
    ax.set_xlim(*xlim)
    if xticks_override is not None and len(xticks_override) > 0:
        ticks = np.asarray(xticks_override, dtype=float)
        ticks = ticks[(ticks >= xlim[0]) & (ticks <= xlim[1])]
        if len(ticks) > 0:
            ax.set_xticks(ticks)
            ax.set_xticklabels([f"{value:.1f}" for value in ticks])
    ax.set_ylim(*robust_limits(y, 0.0, 1.0))

    raw = RAW_FEATURE_BY_ORTHO[feature]
    q_row = opgd[(opgd.metric == metric) & (opgd.biome == biome) & (opgd.feature == raw)]
    rel_row = reliability[(reliability.metric == metric) & (reliability.biome == biome) & (reliability.feature == raw)]
    q = float(q_row["q"].iloc[0]) if not q_row.empty else np.nan
    rel = str(rel_row["reliability_grade"].iloc[0]) if not rel_row.empty else "NA"
    ax.set_title(f"{metric} | q={q:.3f} | OPGD {rel}", fontsize=8.5, pad=2.5)
    ax.set_xlabel(LABELS[feature], fontsize=7.6)
    ax.set_ylabel("Effect on recovery time (days)", fontsize=7.3)
    ax.tick_params(labelsize=6.7, length=2.2)
    ax.grid(alpha=0.14, ls="--", lw=0.55)
    color = {"High": "#08519C", "Medium": "#4292C6", "Low": "#A6A6A6"}.get(rel, "#A6A6A6")
    ax.text(
        0.02,
        0.95,
        RAW_LABEL_BY_ORTHO[feature],
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=7.2,
        color=color,
        fontweight="bold",
        bbox={"facecolor": "white", "edgecolor": color, "alpha": 0.86, "boxstyle": "round,pad=0.2", "linewidth": 0.6},
    )


def draw_biome_figures(module) -> list[Path]:
    configure_style()
    OUT.mkdir(parents=True, exist_ok=True)
    opgd, reliability = load_opgd_tables()
    outputs = []
    for biome in BIOMES:
        print(f"[DRAW] {biome}", flush=True)
        dep = {metric: pd.read_parquet(ORTHO / metric / biome / "dependence_plot_data.parquet") for metric in METRICS}
        curves = {metric: compute_or_load_curves(module, metric, biome) for metric in METRICS}
        fig, axes = plt.subplots(len(FEATURE_ORDER), 2, figsize=(12.8, 24.0))
        for i, feature in enumerate(FEATURE_ORDER):
            gpp_pre_xlim = compute_panel_xlim(dep["GPP"], feature) if feature == "Pre_z" else None
            reco_pre_xlim = compute_panel_xlim(dep["RECO"], feature) if feature == "Pre_z" else None
            reco_to_gpp_pre = (
                linear_x_mapper(reco_pre_xlim, gpp_pre_xlim)
                if feature == "Pre_z" and gpp_pre_xlim is not None and reco_pre_xlim is not None
                else None
            )
            for j, metric in enumerate(METRICS):
                use_pre_reference_axis = feature == "Pre_z" and gpp_pre_xlim is not None
                plot_panel(
                    axes[i, j],
                    dep[metric],
                    feature,
                    metric,
                    biome,
                    curves[metric][feature],
                    opgd,
                    reliability,
                    xlim_override=gpp_pre_xlim if use_pre_reference_axis else None,
                    xticks_override=PRE_REFERENCE_TICKS if use_pre_reference_axis else None,
                    x_transform=reco_to_gpp_pre if feature == "Pre_z" and metric == "RECO" else None,
                )
            axes[i, 0].text(
                -0.30,
                0.5,
                LABELS[feature],
                transform=axes[i, 0].transAxes,
                ha="right",
                va="center",
                fontsize=9.4,
                fontweight="bold",
            )
        handles = [
            Line2D([0], [0], color="#000000", lw=1.6, label="SHAP trend"),
            Line2D([0], [0], color="#d95f02", lw=1.6, label="ALE"),
            Line2D([0], [0], color="#1b9e77", lw=1.6, label="ICE mean"),
            Line2D([0], [0], color="#7570b3", lw=1.6, ls="--", label="PDP"),
        ]
        fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.52, 0.986), fontsize=8.5)
        fig.suptitle(
            f"{biome}: orthogonal SHAP dependence with ALE/ICE/PDP and OPGD reliability",
            fontsize=14,
            fontweight="bold",
            y=0.998,
        )
        fig.subplots_adjust(left=0.105, right=0.985, top=0.965, bottom=0.035, hspace=0.60, wspace=0.24)
        out = OUT / f"{biome}_orthogonal_dependence_ALE_ICE_PDP_OPGD_overlay.png"
        fig.savefig(out, dpi=250)
        plt.close(fig)
        outputs.append(out)
    pd.DataFrame({"biome": BIOMES, "output_png": [str(p) for p in outputs]}).to_csv(OUT / "orthogonal_validation_opgd_overlay_index.csv", index=False)
    return outputs


def write_readme(outputs: list[Path]) -> None:
    lines = [
        "# Orthogonal dependence with ALE/ICE/PDP and OPGD annotations",
        "",
        "These figures follow the visual logic of `validation/compared_with_dependenceplot/overlay_redrawn`: SHAP dependence scatter/trend, ALE, ICE mean, and PDP are drawn in each panel.",
        "",
        "The curves are recomputed on the orthogonal-decomposition input space, so their x axes match variables such as `SSRD_z` and `TMP_resid_after_SSRD_STRD`.",
        "",
        "OPGD q and reliability annotations are mapped from each orthogonal variable to its corresponding raw feature. This tests mechanism-level agreement, not identical feature scale.",
        "",
        "Outputs:",
    ]
    lines.extend([f"- {p}" for p in outputs])
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    module = load_nomulti_module()
    outputs = draw_biome_figures(module)
    write_readme(outputs)
    for p in outputs:
        print(p)


if __name__ == "__main__":
    main()
