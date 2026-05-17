#!/usr/bin/env python3
"""Redraw prepeak SHAP beeswarm/dependence figures for GPP and RECO into plots2."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
RESULT_ROOT = ROOT / "results"
OUTPUT_ROOT = ROOT / "plots2/prepeak_shap_summary_20260502"

GPP_ROOT = RESULT_ROOT / "gpp_code1_flash_smrz_v20260401_onsetpeak_clean/prepeak_event_shap_sem_20260424/shap_by_biome"
RECO_ROOT = RESULT_ROOT / "reco_code1_flash_smrz_v20260401_mswepE_clean/prepeak_event_shap_sem_20260424/shap_by_biome"
GPP_TABLE = ROOT / "data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet"
RECO_TABLE = ROOT / "data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet"
RECOVERY_TIME_FEATURE = "t_recover_to_baseline_abs_peak"

BIOMES = ["Forest", "Grassland", "Savanna", "Cropland", "Shrubland"]
METRICS = {
    "GPP": GPP_ROOT,
    "RECO": RECO_ROOT,
}
FEATURE_TABLES = {
    "GPP": GPP_TABLE,
    "RECO": RECO_TABLE,
}

SHORT_LABELS = {
    "prepeak_total_precipitation_mean": "PRE",
    "prepeak_total_evaporation_mean": "EVA",
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

FIXED_BEESWARM_FEATURES = [
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

FIXED_BEESWARM_LABELS = {
    "prepeak_ssrd_mean": "SSRD",
    "prepeak_total_evaporation_mean": "|EVA|",
    "prepeak_temperature_2m_mean": "TMP",
    "prepeak_strd_mean": "STRD",
    "prepeak_SMrz_mean": "SMrz",
    "prepeak_wind_speed_mean": "Wind",
    "prepeak_VPD_mean": "VPD",
    "event_duration": "Duration",
    "prepeak_total_precipitation_mean": "Pre",
    "event_intensity": "Intensity",
}


@dataclass
class BiomeData:
    sample: pd.DataFrame
    shap: pd.DataFrame
    importance: pd.DataFrame


def short_label(name: str) -> str:
    return SHORT_LABELS.get(name, name.replace("prepeak_", ""))


def is_precip_feature(name: str) -> bool:
    return "precipitation" in name


def is_eva_feature(name: str) -> bool:
    return "evaporation" in name


def maybe_to_mm(values: np.ndarray) -> tuple[np.ndarray, str]:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return values, "mm"
    if np.nanquantile(np.abs(finite), 0.99) < 1.0:
        return values * 1000.0, "mm"
    return values, "mm"


def convert_feature_units(feature: str, values: np.ndarray) -> tuple[np.ndarray, str]:
    if is_precip_feature(feature) or is_eva_feature(feature):
        return maybe_to_mm(values)
    if feature == "prepeak_SMrz_mean":
        return values, "m3/m3"
    if feature == "prepeak_temperature_2m_mean":
        return values, "K"
    if feature == "prepeak_VPD_mean":
        return values / 10.0, "kPa"
    if feature == "event_duration":
        return values, "days"
    if feature == RECOVERY_TIME_FEATURE:
        return values, "days"
    return values, ""


def transform_beeswarm_display_values(feature: str, values: np.ndarray) -> np.ndarray:
    # EVA is stored as negative evaporation; use absolute magnitude for beeswarm color mapping
    # so that "larger evaporation" visually corresponds to larger displayed values.
    if is_eva_feature(feature):
        return np.abs(values)
    return values


def transform_dependence_display_values(feature: str, values: np.ndarray) -> np.ndarray:
    # Keep dependence plot display consistent with beeswarm:
    # EVA is shown as absolute evaporation magnitude.
    if is_eva_feature(feature):
        return np.abs(values)
    return values


def clip_two_sided_color_tail(values: np.ndarray, low_q: float = 0.05, high_q: float = 0.95) -> np.ndarray:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return values
    low, high = np.nanquantile(finite, [low_q, high_q])
    clipped = values.copy()
    clipped[(clipped <= low) | (clipped >= high)] = np.nan
    return clipped


def load_biome(metric: str, biome: str) -> BiomeData:
    root = METRICS[metric] / biome
    return BiomeData(
        sample=pd.read_parquet(root / "dependence_sample_features.parquet"),
        shap=pd.read_parquet(root / "dependence_sample_shap_values.parquet"),
        importance=pd.read_csv(root / "feature_importance.csv"),
    )


@lru_cache(maxsize=None)
def load_biome_feature_table(metric: str, biome: str) -> pd.DataFrame:
    table = pd.read_parquet(FEATURE_TABLES[metric])
    return table[table["biome"] == biome].reset_index(drop=True)


def recovery_time_color_values(metric: str, biome: str, sample_index: pd.Index) -> tuple[np.ndarray, str]:
    table = load_biome_feature_table(metric, biome)
    vals = pd.to_numeric(table.loc[sample_index, RECOVERY_TIME_FEATURE], errors="coerce").to_numpy(dtype=float)
    vals, unit = convert_feature_units(RECOVERY_TIME_FEATURE, vals)
    vals = clip_two_sided_color_tail(vals, low_q=0.10, high_q=0.90)
    return vals, unit


def beeswarm_importance_df(importance_df: pd.DataFrame) -> pd.DataFrame:
    return importance_df[importance_df["feature"] != "prepeak_lai_total_mean"].reset_index(drop=True)


def fixed_beeswarm_feature_order(top_n: int) -> list[str]:
    return FIXED_BEESWARM_FEATURES[: min(top_n, len(FIXED_BEESWARM_FEATURES))]


def beeswarm_label(name: str) -> str:
    return FIXED_BEESWARM_LABELS.get(name, short_label(name))


def prepare_beeswarm_inputs(
    sample: pd.DataFrame,
    shap_df: pd.DataFrame,
    importance_df: pd.DataFrame,
    top_n: int,
) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    del importance_df
    top_features = fixed_beeswarm_feature_order(top_n)
    missing = [feature for feature in top_features if feature not in sample.columns or feature not in shap_df.columns]
    if missing:
        raise KeyError(f"Missing fixed beeswarm feature columns: {', '.join(missing)}")
    feature_frame = sample[top_features].copy()
    for feature in top_features:
        vals = pd.to_numeric(feature_frame[feature], errors="coerce").to_numpy(dtype=float)
        vals, _ = convert_feature_units(feature, vals)
        vals = transform_beeswarm_display_values(feature, vals)
        feature_frame[feature] = vals
    shap_matrix = shap_df[top_features].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    feature_names = [beeswarm_label(f) for f in top_features]
    feature_frame.columns = feature_names
    return feature_frame, shap_matrix, feature_names


def plot_single_beeswarm(sample: pd.DataFrame, shap_df: pd.DataFrame, importance_df: pd.DataFrame, title: str, output_path: Path, top_n: int = 10) -> None:
    feature_frame, shap_matrix, feature_names = prepare_beeswarm_inputs(sample, shap_df, importance_df, top_n=top_n)
    plt.figure(figsize=(8, 5.5))
    shap.summary_plot(
        shap_values=shap_matrix,
        features=feature_frame,
        feature_names=feature_names,
        plot_type="dot",
        max_display=min(top_n, len(feature_names)),
        sort=True,
        show=False,
        plot_size=None,
    )
    plt.title(title, fontsize=11)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close()


def make_large_beeswarm_figure() -> None:
    fig, axes = plt.subplots(nrows=len(BIOMES), ncols=2, figsize=(16, 3.2 * len(BIOMES)))
    for row, biome in enumerate(BIOMES):
        for col, metric in enumerate(["GPP", "RECO"]):
            data = load_biome(metric, biome)
            feature_frame, shap_matrix, feature_names = prepare_beeswarm_inputs(
                data.sample,
                data.shap,
                data.importance,
                top_n=10,
            )
            plt.sca(axes[row, col])
            shap.summary_plot(
                shap_values=shap_matrix,
                features=feature_frame,
                feature_names=feature_names,
                plot_type="dot",
                max_display=min(10, len(feature_names)),
                sort=True,
                show=False,
                plot_size=None,
            )
            axes[row, col].set_title(f"{metric} | {biome}", fontsize=11)
            axes[row, col].tick_params(axis="x", labelsize=8)
            axes[row, col].tick_params(axis="y", labelsize=8)
    fig.suptitle("Pre-event SHAP Beeswarm Comparison Across Five Biomes", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    out = OUTPUT_ROOT / "beeswarm_comparison_5biomes_gpp_vs_reco.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=240, bbox_inches="tight")
    plt.close(fig)


def make_per_biome_beeswarms() -> pd.DataFrame:
    rows = []
    for metric, root in METRICS.items():
        for biome in BIOMES:
            data = load_biome(metric, biome)
            out = OUTPUT_ROOT / metric / biome / f"{metric}_{biome}_beeswarm_redraw.png"
            plot_single_beeswarm(data.sample, data.shap, data.importance, f"{metric} | {biome}", out, top_n=10)
            imp_df = beeswarm_importance_df(data.importance)
            top5 = imp_df["feature"].head(5).tolist()
            rows.extend(
                {
                    "metric": metric,
                    "biome": biome,
                    "rank": i + 1,
                    "feature": feat,
                    "label": short_label(feat),
                    "importance": float(imp_df.iloc[i]["importance"]),
                }
                for i, feat in enumerate(top5)
            )
    return pd.DataFrame(rows)


def dependence_color_values(sample: pd.DataFrame, color_feature: str) -> tuple[np.ndarray, str]:
    vals = pd.to_numeric(sample[color_feature], errors="coerce").to_numpy(dtype=float)
    vals, unit = convert_feature_units(color_feature, vals)
    vals = transform_dependence_display_values(color_feature, vals)
    if color_feature in {"prepeak_total_evaporation_mean", "prepeak_SMrz_mean", "prepeak_temperature_2m_mean"}:
        vals = clip_two_sided_color_tail(vals, low_q=0.05, high_q=0.95)
    if color_feature == "event_duration":
        finite = vals[np.isfinite(vals)]
        if len(finite) > 0:
            high = np.nanquantile(finite, 0.95)
            vals = vals.copy()
            vals[vals > high] = np.nan
    return vals, unit


def plot_dependence(ax: plt.Axes, x: np.ndarray, y: np.ndarray, color: np.ndarray, x_label: str, color_label: str, title: str) -> None:
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
    sc = ax.scatter(x, y, c=color, cmap="viridis", s=10, alpha=0.55, linewidths=0, rasterized=True)
    if len(x) >= 30:
        order = np.argsort(x)
        xs = x[order]
        ys = y[order]
        window = max(21, len(xs) // 20)
        trend = pd.Series(ys).rolling(window=window, center=True, min_periods=max(5, window // 5)).median()
        ax.plot(xs, trend.to_numpy(), color="#c83349", linewidth=2.0, alpha=0.9)
    ax.axhline(0.0, color="#666666", linestyle="--", linewidth=0.9, alpha=0.8)
    ax.set_xlabel(x_label, fontsize=10)
    ax.set_ylabel("SHAP value", fontsize=10)
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.16, linestyle="--")
    cbar = plt.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label(color_label, fontsize=9)
    cbar.ax.tick_params(labelsize=8)


def color_specs_for_feature(feature: str) -> list[tuple[str, str]]:
    color_specs = [
        ("prepeak_total_evaporation_mean", "EVA"),
        ("prepeak_SMrz_mean", "SMrz"),
        ("prepeak_temperature_2m_mean", "TMP"),
    ]
    if feature not in {"prepeak_ssrd_mean", "prepeak_strd_mean"}:
        color_specs.extend(
            [
                ("prepeak_ssrd_mean", "SSRD"),
                ("prepeak_strd_mean", "STRD"),
            ]
        )
    if feature in {"prepeak_temperature_2m_mean", "prepeak_total_evaporation_mean"}:
        color_specs.append(("prepeak_VPD_mean", "VPD"))
    if feature == "prepeak_total_precipitation_mean":
        color_specs.append(("event_duration", "Duration"))
        color_specs.append((RECOVERY_TIME_FEATURE, "Recovery"))
    return color_specs


def make_dependence_plots(top5_df: pd.DataFrame) -> None:
    for metric in ["GPP", "RECO"]:
        for biome in BIOMES:
            data = load_biome(metric, biome)
            top_features = top5_df[(top5_df["metric"] == metric) & (top5_df["biome"] == biome)].sort_values("rank")["feature"].tolist()
            all_features = data.importance["feature"].tolist()
            plot_sets = [
                ("dependence_top5", top_features),
                ("dependence_all", all_features),
            ]
            for out_dir, features in plot_sets:
                for feature in features:
                    color_specs = color_specs_for_feature(feature)
                    x = pd.to_numeric(data.sample[feature], errors="coerce").to_numpy(dtype=float)
                    x, x_unit = convert_feature_units(feature, x)
                    x = transform_dependence_display_values(feature, x)
                    y = pd.to_numeric(data.shap[feature], errors="coerce").to_numpy(dtype=float)
                    display_label = short_label(feature)
                    if is_eva_feature(feature):
                        display_label = f"|{display_label}|"
                    x_name = display_label + (f" ({x_unit})" if x_unit else "")
                    for color_feature, color_short in color_specs:
                        if color_feature == RECOVERY_TIME_FEATURE:
                            c, c_unit = recovery_time_color_values(metric, biome, data.sample.index)
                        else:
                            c, c_unit = dependence_color_values(data.sample, color_feature)
                        color_display = f"|{color_short}|" if is_eva_feature(color_feature) else color_short
                        color_label = color_display + (f" ({c_unit})" if c_unit else "")
                        fig, ax = plt.subplots(figsize=(7.6, 5.4))
                        plot_dependence(
                            ax,
                            x=x,
                            y=y,
                            color=c,
                            x_label=x_name,
                            color_label=color_label,
                            title=f"{metric} | {biome} | {display_label} colored by {color_display}",
                        )
                        out = OUTPUT_ROOT / metric / biome / out_dir / f"{short_label(feature)}_colored_by_{color_short}.png"
                        out.parent.mkdir(parents=True, exist_ok=True)
                        fig.savefig(out, dpi=240, bbox_inches="tight")
                        plt.close(fig)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    top5_df = make_per_biome_beeswarms()
    top5_df.to_csv(OUTPUT_ROOT / "top5_feature_index.csv", index=False)
    make_large_beeswarm_figure()
    make_dependence_plots(top5_df)
    summary = (
        top5_df.groupby(["metric", "biome"], as_index=False)
        .agg(top5_labels=("label", lambda s: ", ".join(s.tolist())))
        .sort_values(["metric", "biome"])
    )
    summary.to_csv(OUTPUT_ROOT / "summary_top5_labels.csv", index=False)
    (OUTPUT_ROOT / "README.txt").write_text(
        "\n".join(
            [
                "plots2 prepeak shap redraw summary",
                "units:",
                "- PRE unified to mm",
                "- EVA unified to mm",
                "outputs:",
                "- combined 5-biome GPP vs RECO beeswarm comparison",
                "- per-biome beeswarm redraws",
                "- top5 dependence plots colored by EVA and SMrz",
                "labels remove prepeak field prefix from displayed names",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
