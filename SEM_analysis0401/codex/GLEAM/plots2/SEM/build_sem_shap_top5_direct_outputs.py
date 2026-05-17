#!/usr/bin/env python3
"""Fit SHAP-informed top-5 direct SEM models for pre-peak recovery time."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
OUT = ROOT / "plots2/SEM/sem_prepeak_shap_top5_direct_20260506"
TOP5 = ROOT / "plots2/prepeak_shap_summary_20260502/top5_feature_index.csv"
BASE_R2 = ROOT / "plots2/SEM/sem_prepeak_ssrd_required_20260505/tables/sem_prepeak_ssrd_required_r2_gpp_reco.csv"
EVENT_R2 = ROOT / "plots2/SEM/sem_prepeak_ssrd_eventaware_20260506/tables/sem_prepeak_ssrd_eventaware_r2_gpp_reco.csv"
TARGET = "t_recover_to_baseline_abs_peak"
BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
METRICS = ["GPP", "RECO"]
TABLES = {
    "GPP": ROOT / "data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet",
    "RECO": ROOT / "data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet",
}
LABELS = {
    "prepeak_total_precipitation_mean": "PRE",
    "prepeak_total_evaporation_mean": "|EVA|",
    "prepeak_temperature_2m_mean": "TMP",
    "prepeak_VPD_mean": "VPD",
    "prepeak_SMrz_mean": "SMrz",
    "prepeak_ssrd_mean": "SSRD",
    "prepeak_strd_mean": "STRD",
    "prepeak_wind_speed_mean": "WIND",
    "event_duration": "Duration",
    "event_intensity": "Intensity",
    TARGET: "Recovery time",
}
NODE_POS = {
    1: (0.10, 0.82),
    2: (0.10, 0.66),
    3: (0.10, 0.50),
    4: (0.10, 0.34),
    5: (0.10, 0.18),
    "Recovery time": (0.82, 0.50),
}
EDGE_RAD = {
    1: 0.20,
    2: 0.10,
    3: 0.00,
    4: -0.10,
    5: -0.20,
}


def label(name: str) -> str:
    return LABELS.get(name, name)


def zscore(frame: pd.DataFrame) -> pd.DataFrame:
    numeric = frame.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    numeric = numeric.dropna(axis=0, how="any")
    std = numeric.std(ddof=0).replace(0, np.nan)
    return ((numeric - numeric.mean()) / std).dropna(axis=1, how="any")


def load_top5() -> pd.DataFrame:
    top5 = pd.read_csv(TOP5)
    return top5[top5["rank"] <= 5].copy()


def get_features(top5: pd.DataFrame, metric: str, biome: str) -> list[str]:
    subset = top5[(top5["metric"] == metric) & (top5["biome"] == biome)].sort_values("rank")
    return list(subset["feature"])


def fit_direct_model(data: pd.DataFrame, metric: str, biome: str, features: list[str]) -> tuple[list[dict[str, object]], dict[str, object]]:
    frame = data[[TARGET] + features].dropna(axis=0, how="any")
    x = frame[features].to_numpy(dtype=float)
    y = frame[TARGET].to_numpy(dtype=float)
    reg = LinearRegression()
    reg.fit(x, y)
    pred = reg.predict(x)
    resid = y - pred
    n, p = x.shape
    sigma2 = float(np.sum(resid**2) / max(n - p - 1, 1))
    x_design = np.column_stack([np.ones(n), x])
    xtx_inv = np.linalg.pinv(x_design.T @ x_design)
    se = np.sqrt(np.diag(xtx_inv)[1:] * sigma2)

    rows = []
    for rank, (feature, coef, stderr) in enumerate(zip(features, reg.coef_, se, strict=True), start=1):
        z_value = float(coef / stderr) if stderr > 0 else np.nan
        p_value = float(2.0 * stats.norm.sf(abs(z_value))) if np.isfinite(z_value) else np.nan
        rows.append(
            {
                "metric": metric,
                "biome": biome,
                "scope": "prepeak_shap_top5_direct_20260506",
                "rank": rank,
                "from": feature,
                "to": TARGET,
                "estimate": float(coef),
                "abs_estimate": float(abs(coef)),
                "std_err": float(stderr),
                "z_value": z_value,
                "p_value": p_value,
                "significance": "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "",
                "from_label": label(feature),
                "to_label": label(TARGET),
            }
        )

    train, test = train_test_split(frame, test_size=0.2, random_state=42)
    reg2 = LinearRegression()
    reg2.fit(train[features], train[TARGET])
    r2 = {
        "metric": metric,
        "biome": biome,
        "scope": "prepeak_shap_top5_direct_20260506",
        "rows": len(frame),
        "holdout_r2": float(reg2.score(test[features], test[TARGET])),
        "train_r2": float(reg2.score(train[features], train[TARGET])),
        "predictor_count": len(features),
        "top5_features": ", ".join(label(f) for f in features),
    }
    return rows, r2


def load_metric_biome(metric: str, biome: str, features: list[str]) -> pd.DataFrame:
    columns = sorted(set([TARGET, "biome"] + features))
    df = pd.read_parquet(TABLES[metric], columns=columns)
    df = df[df["biome"] == biome].drop(columns=["biome"]).reset_index(drop=True)
    return zscore(df)


def save_r2_comparison(r2: pd.DataFrame) -> None:
    comp = r2.copy()
    if BASE_R2.exists():
        base = pd.read_csv(BASE_R2)[["metric", "biome", "holdout_r2"]].rename(columns={"holdout_r2": "ssrd_required_r2"})
        comp = comp.merge(base, on=["metric", "biome"], how="left")
    if EVENT_R2.exists():
        event = pd.read_csv(EVENT_R2)[["metric", "biome", "holdout_r2"]].rename(columns={"holdout_r2": "ssrd_eventaware_r2"})
        comp = comp.merge(event, on=["metric", "biome"], how="left")
    if "ssrd_required_r2" in comp.columns:
        comp["top5_gain_vs_ssrd_required"] = comp["holdout_r2"] - comp["ssrd_required_r2"]
    if "ssrd_eventaware_r2" in comp.columns:
        comp["top5_gain_vs_eventaware"] = comp["holdout_r2"] - comp["ssrd_eventaware_r2"]
    comp.to_csv(OUT / "tables/sem_prepeak_shap_top5_direct_r2_comparison.csv", index=False)

    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    labels = [f"{m}\n{b}" for m, b in zip(comp["metric"], comp["biome"], strict=True)]
    x = np.arange(len(comp))
    width = 0.24
    if "ssrd_required_r2" in comp.columns:
        ax.bar(x - width, comp["ssrd_required_r2"], width=width, color="#9ecae1", label="SSRD-required")
    if "ssrd_eventaware_r2" in comp.columns:
        ax.bar(x, comp["ssrd_eventaware_r2"], width=width, color="#fb6a4a", label="SSRD event-aware")
        top_x = x + width
    else:
        top_x = x
    ax.bar(top_x, comp["holdout_r2"], width=width, color="#74c476", label="SHAP top5 direct")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Holdout R2")
    ax.set_title("SEM explanatory power comparison")
    ax.grid(axis="y", linestyle="--", alpha=0.22)
    ax.legend(frameon=False, ncol=3)
    fig.tight_layout()
    fig.savefig(OUT / "figures/sem_prepeak_shap_top5_direct_r2_comparison.png", dpi=300)
    plt.close(fig)


def heatmap(paths: pd.DataFrame) -> None:
    work = paths.copy()
    work["row"] = work["metric"] + " " + work["biome"]
    pivot = work.pivot_table(index="row", columns="from_label", values="estimate", aggfunc="first")
    cols = [c for c in ["SSRD", "STRD", "TMP", "VPD", "|EVA|", "SMrz", "PRE", "WIND", "Duration", "Intensity"] if c in pivot.columns]
    pivot = pivot.reindex(columns=cols)
    max_abs = max(float(np.nanmax(np.abs(pivot.to_numpy()))), 0.01)
    fig, ax = plt.subplots(figsize=(10.0, 6.2))
    im = ax.imshow(pivot.fillna(0).to_numpy(), cmap="RdBu_r", vmin=-max_abs, vmax=max_abs, aspect="auto")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("SHAP top5 direct standardized paths to recovery time")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.iloc[i, j]
            if pd.notna(value):
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7.5)
    fig.colorbar(im, ax=ax, shrink=0.82, label="Standardized coefficient")
    fig.tight_layout()
    fig.savefig(OUT / "figures/sem_prepeak_shap_top5_direct_coefficients_heatmap.png", dpi=300)
    plt.close(fig)


def draw_node(ax: plt.Axes, text: str, xy: tuple[float, float], target: bool = False) -> None:
    ax.text(
        xy[0],
        xy[1],
        text,
        ha="center",
        va="center",
        fontsize=8.2,
        fontweight="bold" if target else "normal",
        bbox={
            "boxstyle": "round,pad=0.34,rounding_size=0.08",
            "facecolor": "#fff7bc" if target else "#f7f7f7",
            "edgecolor": "#4d4d4d",
            "linewidth": 0.9,
        },
        zorder=5,
    )


def draw_path_panel(ax: plt.Axes, panel: pd.DataFrame, title: str) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(title, fontsize=10.5, fontweight="bold", pad=6)
    max_abs = max(float(panel["abs_estimate"].max()), 0.01)
    target_pos = NODE_POS["Recovery time"]
    draw_node(ax, "Recovery time", target_pos, target=True)
    for _, row in panel.sort_values("rank", ascending=False).iterrows():
        rank = int(row["rank"])
        src_pos = NODE_POS[rank]
        coef = float(row["estimate"])
        color = "#b2182b" if coef > 0 else "#2166ac"
        width = 1.0 + 3.0 * min(abs(coef) / max_abs, 1.0)
        arrow = FancyArrowPatch(
            src_pos,
            target_pos,
            arrowstyle="-|>",
            mutation_scale=11,
            linewidth=width,
            color=color,
            alpha=0.84,
            shrinkA=24,
            shrinkB=30,
            connectionstyle=f"arc3,rad={EDGE_RAD[rank]}",
            zorder=2,
        )
        ax.add_patch(arrow)
        mid_x = (src_pos[0] + target_pos[0]) / 2
        mid_y = (src_pos[1] + target_pos[1]) / 2 + EDGE_RAD[rank] * 0.09
        ax.text(
            mid_x,
            mid_y,
            f"{coef:+.2f}",
            ha="center",
            va="center",
            fontsize=7.3,
            color=color,
            bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "none", "alpha": 0.8},
            zorder=4,
        )
    for _, row in panel.sort_values("rank").iterrows():
        rank = int(row["rank"])
        draw_node(ax, f"{rank}. {row['from_label']}", NODE_POS[rank])
    ax.text(0.02, 0.98, "Red: positive\nBlue: negative", ha="left", va="top", fontsize=7.5, color="#333333")


def save_path_diagrams(paths: pd.DataFrame) -> None:
    diagram_dir = OUT / "figures/path_diagrams"
    diagram_dir.mkdir(parents=True, exist_ok=True)
    for metric in METRICS:
        fig, axes = plt.subplots(1, len(BIOMES), figsize=(18.8, 4.4))
        for i, biome in enumerate(BIOMES):
            panel = paths[(paths["metric"] == metric) & (paths["biome"] == biome)].copy()
            draw_path_panel(axes[i], panel, biome)
            single_fig, single_ax = plt.subplots(figsize=(6.7, 4.9))
            draw_path_panel(single_ax, panel, f"{metric} {biome}")
            single_fig.tight_layout()
            single_fig.savefig(diagram_dir / f"{metric.lower()}_{biome}_shap_top5_direct_path_diagram.png", dpi=300)
            plt.close(single_fig)
        fig.suptitle(f"{metric} SHAP Top5 Direct SEM Path Diagrams", fontsize=13.5, fontweight="bold", y=1.02)
        fig.tight_layout()
        fig.savefig(OUT / "figures" / f"{metric.lower()}_shap_top5_direct_path_diagrams_overview.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def write_readme(r2: pd.DataFrame, paths: pd.DataFrame) -> None:
    comp = pd.read_csv(OUT / "tables/sem_prepeak_shap_top5_direct_r2_comparison.csv")
    top5 = paths.sort_values(["metric", "biome", "rank"])[["metric", "biome", "rank", "from_label", "estimate", "p_value", "significance"]]
    lines = [
        "# SHAP top5 direct SEM",
        "",
        "This version uses the top five SHAP-ranked predictors for each GPP/RECO x biome group as direct predictors of recovery time.",
        "",
        "## Model form",
        "",
        "```text",
        "Recovery time ~ SHAP top5 predictors",
        "```",
        "",
        "This is the clearest confirmatory SEM for testing whether the dominant variables identified by SHAP retain direct standardized effects in a linear structural model. It is intentionally simpler than the event-aware SEM and avoids forcing every biome into the same predictor set.",
        "",
        "## Figures",
        "",
        "Path diagrams are saved in `figures/path_diagrams/`; GPP and RECO overview panels are saved in `figures/`.",
        "",
        "## R2 comparison",
        "",
        comp.to_csv(index=False),
        "",
        "## Direct paths",
        "",
        top5.to_csv(index=False),
        "",
        "## Recommended interpretation",
        "",
        "Use this model as the primary SHAP-informed SEM. The event-aware SEM remains useful as a theory-driven sensitivity model, especially when discussing event memory and mechanistic mediation.",
    ]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    top5 = load_top5()
    top5.to_csv(OUT / "tables/sem_prepeak_shap_top5_feature_selection.csv", index=False)
    all_paths = []
    r2_rows = []
    for metric in METRICS:
        for biome in BIOMES:
            features = get_features(top5, metric, biome)
            data = load_metric_biome(metric, biome, features)
            paths, r2 = fit_direct_model(data, metric, biome, features)
            pd.DataFrame(paths).to_csv(OUT / "tables" / f"{metric.lower()}_{biome}_shap_top5_direct_paths.csv", index=False)
            all_paths.extend(paths)
            r2_rows.append(r2)
    paths = pd.DataFrame(all_paths)
    r2 = pd.DataFrame(r2_rows)
    paths.to_csv(OUT / "tables/sem_prepeak_shap_top5_direct_paths.csv", index=False)
    r2.to_csv(OUT / "tables/sem_prepeak_shap_top5_direct_r2_gpp_reco.csv", index=False)
    save_r2_comparison(r2)
    heatmap(paths)
    save_path_diagrams(paths)
    write_readme(r2, paths)
    print(OUT)


if __name__ == "__main__":
    main()
