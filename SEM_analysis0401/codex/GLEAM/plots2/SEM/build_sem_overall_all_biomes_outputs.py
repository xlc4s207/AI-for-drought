#!/usr/bin/env python3
"""Fit pooled all-biome SSRD event-aware SEM with biome fixed effects."""

from __future__ import annotations

from collections import defaultdict
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
OUT = ROOT / "plots2/SEM/sem_prepeak_overall_all_biomes_20260506"
TARGET = "t_recover_to_baseline_abs_peak"
BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
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
EQUATIONS = [
    ("prepeak_temperature_2m_mean", ["prepeak_ssrd_mean", "prepeak_strd_mean"]),
    ("prepeak_VPD_mean", ["prepeak_temperature_2m_mean", "prepeak_wind_speed_mean", "prepeak_ssrd_mean"]),
    (
        "prepeak_total_evaporation_mean",
        [
            "prepeak_ssrd_mean",
            "prepeak_strd_mean",
            "prepeak_total_precipitation_mean",
            "prepeak_temperature_2m_mean",
            "prepeak_VPD_mean",
        ],
    ),
    (
        "prepeak_SMrz_mean",
        [
            "prepeak_total_precipitation_mean",
            "prepeak_total_evaporation_mean",
            "event_duration",
            "event_intensity",
        ],
    ),
    (
        TARGET,
        [
            "prepeak_ssrd_mean",
            "prepeak_strd_mean",
            "prepeak_temperature_2m_mean",
            "prepeak_VPD_mean",
            "prepeak_total_evaporation_mean",
            "prepeak_SMrz_mean",
            "event_duration",
            "event_intensity",
        ],
    ),
]
COLUMNS = sorted({TARGET, "biome"} | {lhs for lhs, _ in EQUATIONS} | {rhs for _, rhs_list in EQUATIONS for rhs in rhs_list})
NODE_POS = {
    "SSRD": (0.08, 0.86),
    "STRD": (0.08, 0.72),
    "PRE": (0.08, 0.54),
    "WIND": (0.08, 0.36),
    "Duration": (0.08, 0.20),
    "Intensity": (0.08, 0.08),
    "TMP": (0.32, 0.77),
    "VPD": (0.32, 0.47),
    "|EVA|": (0.58, 0.64),
    "SMrz": (0.58, 0.30),
    "Recovery time": (0.89, 0.50),
}
EDGE_RAD = {
    ("SSRD", "TMP"): 0.10,
    ("STRD", "TMP"): -0.10,
    ("TMP", "VPD"): -0.10,
    ("WIND", "VPD"): 0.16,
    ("SSRD", "VPD"): 0.24,
    ("SSRD", "|EVA|"): -0.10,
    ("STRD", "|EVA|"): -0.18,
    ("PRE", "|EVA|"): 0.16,
    ("TMP", "|EVA|"): 0.06,
    ("VPD", "|EVA|"): -0.16,
    ("PRE", "SMrz"): -0.16,
    ("|EVA|", "SMrz"): -0.18,
    ("Duration", "SMrz"): 0.16,
    ("Intensity", "SMrz"): -0.12,
    ("SSRD", "Recovery time"): -0.34,
    ("STRD", "Recovery time"): -0.26,
    ("TMP", "Recovery time"): -0.18,
    ("VPD", "Recovery time"): 0.24,
    ("|EVA|", "Recovery time"): 0.14,
    ("SMrz", "Recovery time"): -0.20,
    ("Duration", "Recovery time"): 0.28,
    ("Intensity", "Recovery time"): -0.28,
}


def label(name: str) -> str:
    return LABELS.get(name, name)


def zscore_numeric(df: pd.DataFrame) -> pd.DataFrame:
    numeric = df.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    numeric = numeric.dropna(axis=0, how="any")
    std = numeric.std(ddof=0).replace(0, np.nan)
    return ((numeric - numeric.mean()) / std).dropna(axis=1, how="any")


def load_metric(metric: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_parquet(TABLES[metric], columns=COLUMNS)
    df = df[df["biome"].isin(BIOMES)].reset_index(drop=True)
    biomes = df["biome"].copy()
    numeric = zscore_numeric(df.drop(columns=["biome"]))
    biomes = biomes.loc[numeric.index].reset_index(drop=True)
    numeric = numeric.reset_index(drop=True)
    dummies = pd.get_dummies(biomes.astype(str), prefix="biome", drop_first=True, dtype=float)
    return numeric, dummies


def fit_equation(
    data: pd.DataFrame,
    controls: pd.DataFrame,
    metric: str,
    lhs: str,
    rhs: list[str],
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    frame = pd.concat([data[[lhs] + rhs], controls], axis=1).dropna(axis=0, how="any")
    control_cols = list(controls.columns)
    x_cols = rhs + control_cols
    x = frame[x_cols].to_numpy(dtype=float)
    y = frame[lhs].to_numpy(dtype=float)
    reg = LinearRegression()
    reg.fit(x, y)
    pred = reg.predict(x)
    resid = y - pred
    n, p = x.shape
    sigma2 = float(np.sum(resid**2) / max(n - p - 1, 1))
    x_design = np.column_stack([np.ones(n), x])
    xtx_inv = np.linalg.pinv(x_design.T @ x_design)
    se_var = np.diag(xtx_inv)[1:] * sigma2
    se = np.sqrt(np.maximum(se_var, 0.0))
    rows = []
    for feature, coef, stderr in zip(x_cols, reg.coef_, se, strict=True):
        z_value = float(coef / stderr) if stderr > 0 else np.nan
        p_value = float(2.0 * stats.norm.sf(abs(z_value))) if np.isfinite(z_value) else np.nan
        rows.append(
            {
                "metric": metric,
                "scope": "overall_all_biomes_fixed_effects",
                "from": feature,
                "to": lhs,
                "estimate": float(coef),
                "abs_estimate": float(abs(coef)),
                "std_err": float(stderr),
                "z_value": z_value,
                "p_value": p_value,
                "significance": "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "",
                "from_label": label(feature),
                "to_label": label(lhs),
                "is_biome_control": feature.startswith("biome_"),
            }
        )
    r2_row = None
    if lhs == TARGET:
        train, test = train_test_split(frame, test_size=0.2, random_state=42)
        reg2 = LinearRegression()
        reg2.fit(train[x_cols], train[lhs])
        r2_row = {
            "metric": metric,
            "scope": "overall_all_biomes_fixed_effects",
            "rows": len(frame),
            "holdout_r2": float(reg2.score(test[x_cols], test[lhs])),
            "train_r2": float(reg2.score(train[x_cols], train[lhs])),
            "predictor_count": len(rhs),
            "biome_control_count": len(control_cols),
        }
    return rows, r2_row


def enumerate_paths(children: dict[str, list[tuple[str, float]]], source: str) -> list[list[tuple[str, str, float]]]:
    stack = [(source, [])]
    paths = []
    while stack:
        node, path = stack.pop()
        for child, coeff in children.get(node, []):
            next_path = path + [(node, child, coeff)]
            if child == TARGET:
                paths.append(next_path)
            elif child not in [edge[0] for edge in next_path]:
                stack.append((child, next_path))
    return paths


def compute_total_effects(paths: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric, group in paths.groupby("metric", sort=False):
        group = group[~group["is_biome_control"]]
        children: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for _, rec in group.iterrows():
            children[str(rec["from"])].append((str(rec["to"]), float(rec["estimate"])))
        for source in sorted(set(group["from"]) | set(group["to"])):
            if source == TARGET:
                continue
            source_paths = enumerate_paths(children, source)
            if not source_paths:
                continue
            direct = 0.0
            indirect = 0.0
            for path in source_paths:
                effect = float(np.prod([edge[2] for edge in path]))
                if len(path) == 1:
                    direct += effect
                else:
                    indirect += effect
            rows.append(
                {
                    "metric": metric,
                    "source": source,
                    "source_label": label(source),
                    "direct_effect": direct,
                    "indirect_effect": indirect,
                    "total_effect": direct + indirect,
                }
            )
    return pd.DataFrame(rows)


def heatmap(data: pd.DataFrame, value_col: str, output: Path, title: str) -> None:
    work = data.copy()
    if "source_label" not in work.columns and "from_label" in work.columns:
        work["source_label"] = work["from_label"]
    pivot = work.pivot_table(index="metric", columns="source_label", values=value_col, aggfunc="first")
    cols = [c for c in ["SSRD", "STRD", "TMP", "VPD", "|EVA|", "SMrz", "Duration", "Intensity", "PRE", "WIND"] if c in pivot.columns]
    pivot = pivot.reindex(columns=cols)
    max_abs = max(float(np.nanmax(np.abs(pivot.to_numpy()))), 0.01)
    fig, ax = plt.subplots(figsize=(10.2, 2.7))
    im = ax.imshow(pivot.fillna(0).to_numpy(), cmap="RdBu_r", vmin=-max_abs, vmax=max_abs, aspect="auto")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title(title)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.iloc[i, j]
            if pd.notna(value):
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.75, label="Standardized effect")
    fig.tight_layout()
    fig.savefig(output, dpi=300)
    plt.close(fig)


def draw_node(ax: plt.Axes, text: str, xy: tuple[float, float]) -> None:
    target = text == "Recovery time"
    ax.text(
        xy[0],
        xy[1],
        text,
        ha="center",
        va="center",
        fontsize=8.4,
        fontweight="bold" if target else "normal",
        bbox={
            "boxstyle": "round,pad=0.34,rounding_size=0.08",
            "facecolor": "#fff7bc" if target else "#f7f7f7",
            "edgecolor": "#4d4d4d",
            "linewidth": 0.9,
        },
        zorder=5,
    )


def draw_path_panel(ax: plt.Axes, paths: pd.DataFrame, metric: str) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(f"{metric} overall SEM", fontsize=12, fontweight="bold")
    visible = paths[(paths["metric"] == metric) & (~paths["is_biome_control"]) & (paths["abs_estimate"] >= 0.05)].copy()
    target = visible[visible["to"] == TARGET]
    mediator = visible[visible["to"] != TARGET].sort_values("abs_estimate", ascending=False).head(max(14 - len(target), 0))
    visible = pd.concat([target, mediator], ignore_index=True)
    max_abs = max(float(visible["abs_estimate"].max()) if not visible.empty else 0.05, 0.05)
    for _, row in visible.sort_values("abs_estimate").iterrows():
        src = row["from_label"]
        dst = row["to_label"]
        start = NODE_POS[src]
        end = NODE_POS[dst]
        coef = float(row["estimate"])
        color = "#b2182b" if coef > 0 else "#2166ac"
        width = 0.8 + 3.0 * min(abs(coef) / max_abs, 1.0)
        arrow = FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=10,
            linewidth=width,
            color=color,
            alpha=0.84,
            shrinkA=20,
            shrinkB=25 if dst == "Recovery time" else 20,
            connectionstyle=f"arc3,rad={EDGE_RAD.get((src, dst), 0.0)}",
            zorder=2,
        )
        ax.add_patch(arrow)
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2 + EDGE_RAD.get((src, dst), 0.0) * 0.10
        ax.text(
            mid_x,
            mid_y,
            f"{coef:+.2f}",
            ha="center",
            va="center",
            fontsize=7,
            color=color,
            bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "none", "alpha": 0.8},
            zorder=4,
        )
    for node, pos in NODE_POS.items():
        draw_node(ax, node, pos)
    ax.text(0.03, 0.99, "Red: positive\nBlue: negative\nBiome fixed effects controlled, not drawn", ha="left", va="top", fontsize=8)


def save_path_diagrams(paths: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14.8, 5.2))
    for ax, metric in zip(axes, ["GPP", "RECO"], strict=True):
        draw_path_panel(ax, paths, metric)
    fig.suptitle("Overall all-biome SSRD event-aware SEM path mechanism", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(OUT / "figures/overall_all_biomes_sem_path_mechanism_gpp_vs_reco.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    for metric in ["GPP", "RECO"]:
        fig, ax = plt.subplots(figsize=(7.4, 5.3))
        draw_path_panel(ax, paths, metric)
        fig.tight_layout()
        fig.savefig(OUT / "figures" / f"{metric.lower()}_overall_all_biomes_sem_path_mechanism.png", dpi=300)
        plt.close(fig)


def main() -> None:
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    all_rows = []
    r2_rows = []
    for metric in ["GPP", "RECO"]:
        data, controls = load_metric(metric)
        for lhs, rhs in EQUATIONS:
            rows, r2 = fit_equation(data, controls, metric, lhs, rhs)
            all_rows.extend(rows)
            if r2 is not None:
                r2_rows.append(r2)
    paths = pd.DataFrame(all_rows)
    r2 = pd.DataFrame(r2_rows)
    total = compute_total_effects(paths)
    target = paths[(paths["to"] == TARGET) & (~paths["is_biome_control"])].copy()
    paths.to_csv(OUT / "tables/overall_all_biomes_all_structural_paths_with_biome_controls.csv", index=False)
    target.to_csv(OUT / "tables/overall_all_biomes_target_direct_paths.csv", index=False)
    total.to_csv(OUT / "tables/overall_all_biomes_total_effects.csv", index=False)
    r2.to_csv(OUT / "tables/overall_all_biomes_sem_r2.csv", index=False)
    heatmap(target, "estimate", OUT / "figures/overall_all_biomes_target_direct_coefficients_heatmap.png", "Overall direct paths to recovery time")
    heatmap(total, "total_effect", OUT / "figures/overall_all_biomes_total_effects_heatmap.png", "Overall total effects")
    save_path_diagrams(paths)
    (OUT / "README.md").write_text(
        "\n".join(
            [
                "# Overall all-biome SEM",
                "",
                "Pooled GPP/RECO SEM across the five main biomes.",
                "",
                "The model uses the SSRD event-aware mechanism and controls biome fixed effects in every structural equation. Biome controls are saved in the full path CSV but are not drawn in the ecological path diagrams.",
                "",
                "Main outputs:",
                "- figures/overall_all_biomes_sem_path_mechanism_gpp_vs_reco.png",
                "- figures/overall_all_biomes_target_direct_coefficients_heatmap.png",
                "- figures/overall_all_biomes_total_effects_heatmap.png",
                "- tables/overall_all_biomes_all_structural_paths_with_biome_controls.csv",
                "- tables/overall_all_biomes_sem_r2.csv",
            ]
        ),
        encoding="utf-8",
    )
    print(OUT)


if __name__ == "__main__":
    main()
