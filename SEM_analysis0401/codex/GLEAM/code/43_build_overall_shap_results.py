#!/usr/bin/env python3
"""Build overall SHAP results across all biome-level outputs for four 0401 scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap


PROJECT_ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
RESULT_ROOT = PROJECT_ROOT / "results"
OUTPUT_ROOT = RESULT_ROOT / "overall_shap_results_20260502"

SCENARIOS: dict[str, Path] = {
    "gpp_prepeak": RESULT_ROOT
    / "gpp_code1_flash_smrz_v20260401_onsetpeak_clean/prepeak_event_shap_sem_20260424/shap_by_biome",
    "gpp_recovery": RESULT_ROOT
    / "gpp_code1_flash_smrz_v20260401_recoverywin_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome",
    "reco_prepeak": RESULT_ROOT
    / "reco_code1_flash_smrz_v20260401_mswepE_clean/prepeak_event_shap_sem_20260424/shap_by_biome",
    "reco_recovery": RESULT_ROOT
    / "reco_code1_flash_smrz_v20260401_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome",
}

FEATURE_LABELS = {
    "prepeak_total_precipitation_mean": "PRE",
    "prepeak_total_evaporation_mean": "EVA",
    "prepeak_temperature_2m_mean": "TMP",
    "prepeak_VPD_mean": "VPD",
    "prepeak_SMrz_mean": "SMrz",
    "prepeak_lai_total_mean": "LAI",
    "prepeak_ssrd_mean": "SSRD",
    "prepeak_strd_mean": "STRD",
    "prepeak_wind_speed_mean": "WIND",
    "recoverywin_total_precipitation_mean": "PRE",
    "recoverywin_total_evaporation_mean": "EVA",
    "recoverywin_temperature_2m_mean": "TMP",
    "recoverywin_VPD_mean": "VPD",
    "recoverywin_SMrz_mean": "SMrz",
    "recoverywin_lai_total_mean": "LAI",
    "recoverywin_ssrd_mean": "SSRD",
    "recoverywin_strd_mean": "STRD",
    "recoverywin_wind_speed_mean": "WIND",
    "event_onset_days": "ONS",
    "event_duration": "DUR",
    "event_intensity": "INT",
}


@dataclass
class ScenarioData:
    sample_df: pd.DataFrame
    shap_df: pd.DataFrame
    dep_df: pd.DataFrame
    summary_df: pd.DataFrame
    features: list[str]


def short_name(name: str) -> str:
    return FEATURE_LABELS.get(name, name)


def biome_dirs(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "dependence_sample_features.parquet").exists()
    )


def load_scenario(root: Path) -> ScenarioData:
    sample_parts: list[pd.DataFrame] = []
    shap_parts: list[pd.DataFrame] = []
    dep_parts: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    feature_order: list[str] | None = None

    for biome_dir in biome_dirs(root):
        biome = biome_dir.name
        sample_df = pd.read_parquet(biome_dir / "dependence_sample_features.parquet")
        shap_df = pd.read_parquet(biome_dir / "dependence_sample_shap_values.parquet")
        dep_df = pd.read_parquet(biome_dir / "dependence_plot_data.parquet")
        imp_df = pd.read_csv(biome_dir / "feature_importance.csv")

        if feature_order is None:
            feature_order = list(sample_df.columns)

        sample_df = sample_df.copy()
        shap_df = shap_df.copy()
        dep_df = dep_df.copy()

        sample_df["biome"] = biome
        shap_df["biome"] = biome
        dep_df["biome"] = biome

        sample_parts.append(sample_df)
        shap_parts.append(shap_df)
        dep_parts.append(dep_df)
        summary_rows.append(
            {
                "biome": biome,
                "sample_count": len(sample_df),
                "top_feature": imp_df.iloc[0]["feature"],
                "top_feature_label": short_name(imp_df.iloc[0]["feature"]),
                "top_importance": float(imp_df.iloc[0]["importance"]),
            }
        )

    if feature_order is None:
        raise RuntimeError(f"No biome directories found under {root}")

    return ScenarioData(
        sample_df=pd.concat(sample_parts, ignore_index=True),
        shap_df=pd.concat(shap_parts, ignore_index=True),
        dep_df=pd.concat(dep_parts, ignore_index=True),
        summary_df=pd.DataFrame(summary_rows),
        features=feature_order,
    )


def aggregate_importance(sample_df: pd.DataFrame, shap_df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    rows = []
    for feature in features:
        vals = pd.to_numeric(shap_df[feature], errors="coerce").to_numpy()
        rows.append(
            {
                "feature": feature,
                "label": short_name(feature),
                "importance": float(np.nanmean(np.abs(vals))),
            }
        )
    out = pd.DataFrame(rows).sort_values("importance", ascending=False).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def plot_beeswarm(sample_df: pd.DataFrame, shap_df: pd.DataFrame, features: list[str], output_path: Path, title: str) -> None:
    shap_matrix = shap_df[features].to_numpy()
    feature_frame = sample_df[features].copy()
    feature_frame.columns = [short_name(c) for c in feature_frame.columns]
    plt.figure(figsize=(10, 7))
    shap.summary_plot(
        shap_values=shap_matrix,
        features=feature_frame,
        feature_names=list(feature_frame.columns),
        show=False,
        max_display=min(12, len(features)),
        plot_size=None,
    )
    plt.title(title, fontsize=13)
    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close()


def plot_topk(importance_df: pd.DataFrame, output_path: Path, title: str, top_k: int = 10) -> None:
    top = importance_df.head(top_k).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    ax.barh(top["label"], top["importance"], color="#2a7fff")
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25, linestyle="--")
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def choose_color_feature(features: list[str], x_feature: str) -> str | None:
    candidates = [
        x
        for x in features
        if x.endswith("SMrz_mean") or x.endswith("total_evaporation_mean") or x.endswith("VPD_mean")
    ]
    for candidate in candidates:
        if candidate != x_feature:
            return candidate
    return None


def _sample_for_plot(df: pd.DataFrame, max_points: int = 12000) -> pd.DataFrame:
    if len(df) <= max_points:
        return df
    return df.sample(n=max_points, random_state=42).sort_index()


def _binned_trend(x: np.ndarray, y: np.ndarray, bins: int = 50) -> tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]
    if len(x) == 0:
        return np.array([]), np.array([])
    edges = np.quantile(x, np.linspace(0, 1, bins + 1))
    edges = np.unique(edges)
    if len(edges) < 3:
        return np.array([]), np.array([])
    mids, meds = [], []
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (x >= left) & (x <= right if right == edges[-1] else x < right)
        if mask.sum() < 20:
            continue
        mids.append((left + right) / 2)
        meds.append(np.nanmedian(y[mask]))
    return np.asarray(mids), np.asarray(meds)


def plot_dependence(dep_df: pd.DataFrame, features: list[str], output_dir: Path, title_prefix: str) -> pd.DataFrame:
    rows = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for feature in features:
        x_col = f"feature__{feature}"
        y_col = f"shap__{feature}"
        if x_col not in dep_df.columns or y_col not in dep_df.columns:
            continue
        color_feature = choose_color_feature(features, feature)
        plot_df = dep_df[[x_col, y_col, "biome"] + ([f"feature__{color_feature}"] if color_feature else [])].copy()
        plot_df = _sample_for_plot(plot_df.dropna())
        fig, ax = plt.subplots(figsize=(7.8, 5.6))
        if color_feature:
            c_col = f"feature__{color_feature}"
            sc = ax.scatter(
                plot_df[x_col],
                plot_df[y_col],
                c=plot_df[c_col],
                cmap="viridis",
                s=11,
                alpha=0.45,
                linewidths=0,
            )
            cb = fig.colorbar(sc, ax=ax, pad=0.02)
            cb.set_label(short_name(color_feature))
        else:
            ax.scatter(plot_df[x_col], plot_df[y_col], s=11, alpha=0.45, linewidths=0, color="#2a7fff")
        mx, my = _binned_trend(plot_df[x_col].to_numpy(), plot_df[y_col].to_numpy())
        if len(mx):
            ax.plot(mx, my, color="#d62728", lw=2.2)
        ax.axhline(0.0, color="black", lw=0.8, alpha=0.5)
        ax.set_xlabel(short_name(feature))
        ax.set_ylabel(f"SHAP({short_name(feature)})")
        ax.set_title(f"{title_prefix} | {short_name(feature)}")
        ax.grid(alpha=0.2, linestyle="--")
        fig.tight_layout()
        suffix = short_name(color_feature) if color_feature else "none"
        out_path = output_dir / f"{short_name(feature)}_colored_by_{suffix}.png"
        fig.savefig(out_path, dpi=220, bbox_inches="tight")
        plt.close(fig)
        rows.append(
            {
                "feature": feature,
                "label": short_name(feature),
                "color_feature": color_feature,
                "color_label": short_name(color_feature) if color_feature else "",
                "points_used": len(plot_df),
                "output_path": str(out_path),
            }
        )
    return pd.DataFrame(rows)


def write_readme(output_dir: Path, scenario: str, summary_df: pd.DataFrame, importance_df: pd.DataFrame, dep_index: pd.DataFrame) -> None:
    title = {
        "gpp_prepeak": "GPP prepeak overall SHAP",
        "gpp_recovery": "GPP recovery overall SHAP",
        "reco_prepeak": "RECO prepeak overall SHAP",
        "reco_recovery": "RECO recovery overall SHAP",
    }[scenario]
    lines = [
        f"# {title}",
        "",
        f"- biomes_included: {', '.join(summary_df['biome'].tolist())}",
        f"- total_samples: {int(summary_df['sample_count'].sum())}",
        "",
        "## Top features",
        "",
    ]
    for _, row in importance_df.head(8).iterrows():
        lines.append(f"- {row['label']}: {row['importance']:.3f}")
    lines += ["", "## Per-biome sample counts", ""]
    for _, row in summary_df.iterrows():
        lines.append(f"- {row['biome']}: {int(row['sample_count'])}")
    lines += ["", "## Dependence plots", ""]
    for _, row in dep_index.iterrows():
        lines.append(f"- {row['label']} colored by {row['color_label'] or 'none'}")
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def build_one(scenario: str, source_root: Path) -> None:
    data = load_scenario(source_root)
    output_dir = OUTPUT_ROOT / scenario
    output_dir.mkdir(parents=True, exist_ok=True)

    importance_df = aggregate_importance(data.sample_df, data.shap_df, data.features)
    importance_df.to_csv(output_dir / "overall_feature_importance.csv", index=False)
    data.summary_df.to_csv(output_dir / "biome_sample_summary.csv", index=False)
    data.sample_df.to_parquet(output_dir / "overall_dependence_sample_features.parquet", index=False)
    data.shap_df.to_parquet(output_dir / "overall_dependence_sample_shap_values.parquet", index=False)
    data.dep_df.to_parquet(output_dir / "overall_dependence_plot_data.parquet", index=False)

    title = scenario.replace("_", " ").upper()
    plot_beeswarm(
        data.sample_df,
        data.shap_df,
        data.features,
        output_dir / "overall_feature_importance_beeswarm.png",
        f"{title} | overall SHAP beeswarm",
    )
    plot_topk(
        importance_df,
        output_dir / "overall_feature_importance_topk.png",
        f"{title} | top SHAP importance",
    )
    dep_index = plot_dependence(
        data.dep_df,
        data.features,
        output_dir / "dependence_plots",
        title,
    )
    dep_index.to_csv(output_dir / "overall_dependence_plot_index.csv", index=False)
    write_readme(output_dir, scenario, data.summary_df, importance_df, dep_index)
    print(f"[DONE] {scenario} -> {output_dir}")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for scenario, source_root in SCENARIOS.items():
        build_one(scenario, source_root)
    print(OUTPUT_ROOT)


if __name__ == "__main__":
    main()
