#!/usr/bin/env python3
"""Fit and plot SSRD-required SEM models for pre-peak GPP and RECO."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
import numpy as np
import pandas as pd
from semopy import Model
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
SOURCE_ROOT = ROOT / "results/SEM_conclusion/sem_halfunified_20260502"
OUT = ROOT / "plots2/SEM/sem_prepeak_ssrd_required_20260505"
TARGET = "t_recover_to_baseline_abs_peak"

BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
METRICS = {
    "GPP": SOURCE_ROOT / "gpp_code1_flash_smrz_v20260401_halfunified/sem_prepeak/by_biome",
    "RECO": SOURCE_ROOT / "reco_code1_flash_smrz_v20260401_halfunified/sem_prepeak/by_biome",
}
LABELS = {
    "prepeak_total_precipitation_mean": "PRE",
    "prepeak_total_evaporation_mean": "|EVA|",
    "prepeak_temperature_2m_mean": "TMP",
    "prepeak_VPD_mean": "VPD",
    "prepeak_SMrz_mean": "SMrz",
    "prepeak_ssrd_mean": "SSRD",
    "prepeak_wind_speed_mean": "WIND",
    TARGET: "Recovery time",
}
SPECS = {
    "GPP": f"""
prepeak_VPD_mean ~ prepeak_temperature_2m_mean + prepeak_wind_speed_mean
prepeak_total_evaporation_mean ~ prepeak_ssrd_mean + prepeak_total_precipitation_mean + prepeak_VPD_mean
prepeak_SMrz_mean ~ prepeak_total_precipitation_mean + prepeak_total_evaporation_mean
{TARGET} ~ prepeak_ssrd_mean + prepeak_temperature_2m_mean + prepeak_VPD_mean + prepeak_total_evaporation_mean + prepeak_SMrz_mean
""".strip(),
    "RECO": f"""
prepeak_VPD_mean ~ prepeak_temperature_2m_mean + prepeak_wind_speed_mean
prepeak_total_evaporation_mean ~ prepeak_ssrd_mean + prepeak_total_precipitation_mean + prepeak_VPD_mean
prepeak_SMrz_mean ~ prepeak_total_precipitation_mean + prepeak_total_evaporation_mean
{TARGET} ~ prepeak_ssrd_mean + prepeak_temperature_2m_mean + prepeak_VPD_mean + prepeak_total_evaporation_mean + prepeak_SMrz_mean
""".strip(),
}
NODE_POS = {
    "SSRD": (0.10, 0.82),
    "PRE": (0.10, 0.50),
    "WIND": (0.10, 0.18),
    "TMP": (0.34, 0.74),
    "VPD": (0.34, 0.42),
    "|EVA|": (0.58, 0.62),
    "SMrz": (0.58, 0.30),
    "Recovery time": (0.88, 0.50),
}
EDGE_RAD = {
    ("TMP", "VPD"): -0.12,
    ("WIND", "VPD"): 0.16,
    ("SSRD", "|EVA|"): -0.12,
    ("PRE", "|EVA|"): 0.16,
    ("VPD", "|EVA|"): -0.16,
    ("PRE", "SMrz"): -0.18,
    ("|EVA|", "SMrz"): -0.18,
    ("SSRD", "Recovery time"): -0.30,
    ("TMP", "Recovery time"): -0.18,
    ("VPD", "Recovery time"): 0.26,
    ("|EVA|", "Recovery time"): 0.16,
    ("SMrz", "Recovery time"): -0.20,
}


def label(name: str) -> str:
    return LABELS.get(name, name)


def dataset_path(metric: str, biome: str) -> Path:
    prefix = f"{metric}_code1_{biome}_flash_SMrz"
    return METRICS[metric] / f"{prefix}_sem_dataset.parquet"


def target_predictors(metric: str) -> list[str]:
    for line in SPECS[metric].splitlines():
        lhs, rhs = [part.strip() for part in line.split("~", 1)]
        if lhs == TARGET:
            return [part.strip() for part in rhs.split("+")]
    raise ValueError(f"No target equation in {metric} spec.")


def fit_one(metric: str, biome: str) -> tuple[pd.DataFrame, dict[str, object]]:
    data = pd.read_parquet(dataset_path(metric, biome))
    variables = sorted({TARGET} | {v for line in SPECS[metric].splitlines() for side in line.split("~") for v in side.replace("+", " ").split()})
    data = data[variables].apply(pd.to_numeric, errors="coerce").dropna(axis=0, how="any")
    model = Model(SPECS[metric])
    model.fit(data)
    estimates = model.inspect()
    preds = target_predictors(metric)
    train, test = train_test_split(data[[TARGET] + preds], test_size=0.2, random_state=42)
    reg = LinearRegression()
    reg.fit(train[preds], train[TARGET])
    r2 = {
        "metric": metric,
        "biome": biome,
        "scope": "prepeak_ssrd_required_20260505",
        "rows": len(data),
        "holdout_r2": float(reg.score(test[preds], test[TARGET])),
        "train_r2": float(reg.score(train[preds], train[TARGET])),
        "predictor_count": len(preds),
    }
    return estimates, r2


def normalize_estimates(estimates: pd.DataFrame, metric: str, biome: str) -> pd.DataFrame:
    work = estimates.copy()
    work = work[work["op"] == "~"].copy()
    work = work.rename(columns={"lval": "to", "rval": "from", "Estimate": "estimate", "p-value": "p_value"})
    work.insert(0, "metric", metric)
    work.insert(1, "biome", biome)
    work.insert(2, "scope", "prepeak_ssrd_required_20260505")
    work["abs_estimate"] = work["estimate"].abs()
    work["significance"] = np.select(
        [work["p_value"] < 0.001, work["p_value"] < 0.01, work["p_value"] < 0.05],
        ["***", "**", "*"],
        default="",
    )
    work["from_label"] = work["from"].map(label)
    work["to_label"] = work["to"].map(label)
    return work[["metric", "biome", "scope", "from", "to", "estimate", "abs_estimate", "p_value", "significance", "from_label", "to_label"]]


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
    for (metric, biome), group in paths.groupby(["metric", "biome"], sort=False):
        children: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for _, rec in group.iterrows():
            children[str(rec["from"])].append((str(rec["to"]), float(rec["estimate"])))
        for source in sorted(set(group["from"]) | set(group["to"])):
            if source == TARGET:
                continue
            all_paths = enumerate_paths(children, source)
            if not all_paths:
                continue
            direct = 0.0
            indirect = 0.0
            direct_n = 0
            indirect_n = 0
            for path in all_paths:
                effect = float(np.prod([edge[2] for edge in path]))
                if len(path) == 1:
                    direct += effect
                    direct_n += 1
                else:
                    indirect += effect
                    indirect_n += 1
            rows.append(
                {
                    "metric": metric,
                    "biome": biome,
                    "source": source,
                    "source_label": label(source),
                    "direct_effect": direct,
                    "indirect_effect": indirect,
                    "total_effect": direct + indirect,
                    "direct_path_count": direct_n,
                    "indirect_path_count": indirect_n,
                }
            )
    return pd.DataFrame(rows)


def draw_node(ax: plt.Axes, name: str, x: float, y: float) -> None:
    is_target = name == "Recovery time"
    ax.text(
        x,
        y,
        name,
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="bold" if is_target else "normal",
        bbox={
            "boxstyle": "round,pad=0.24,rounding_size=0.04",
            "facecolor": "#fff2cc" if is_target else "#f4f7fb",
            "edgecolor": "#c27c0e" if is_target else "#4f81bd",
            "linewidth": 1.15,
        },
        zorder=4,
    )


def draw_edge(ax: plt.Axes, source: str, target: str, estimate: float, max_abs: float, compact: bool) -> None:
    x1, y1 = NODE_POS[source]
    x2, y2 = NODE_POS[target]
    color = "#d95f02" if estimate >= 0 else "#1f78b4"
    width = 0.8 + 2.9 * min(abs(estimate) / max_abs, 1.0)
    rad = EDGE_RAD.get((source, target), 0.0)
    arrow = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle="-|>",
        mutation_scale=10 if compact else 12,
        linewidth=width,
        color=color,
        alpha=0.88,
        shrinkA=16,
        shrinkB=18,
        connectionstyle=f"arc3,rad={rad}",
        zorder=2,
    )
    ax.add_patch(arrow)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    norm = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    offset = 0.032 if compact else 0.038
    ax.text(
        mx - dy / norm * offset + rad * 0.04,
        my + dx / norm * offset + rad * 0.04,
        f"{estimate:+.2f}",
        ha="center",
        va="center",
        fontsize=7.8 if compact else 8.4,
        color=color,
        bbox={"boxstyle": "round,pad=0.10", "facecolor": "white", "edgecolor": "none", "alpha": 0.86},
        zorder=5,
    )


def draw_panel(ax: plt.Axes, group: pd.DataFrame, metric: str, biome: str, compact: bool = False) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(f"{metric} - {biome}", fontsize=11 if compact else 13, pad=8)
    group = group.copy()
    max_abs = max(float(group["estimate"].abs().max()), 0.01)
    for _, rec in group.sort_values("abs_estimate").iterrows():
        source = str(rec["from_label"])
        target = str(rec["to_label"])
        if source in NODE_POS and target in NODE_POS:
            draw_edge(ax, source, target, float(rec["estimate"]), max_abs, compact)
    for name, (x, y) in NODE_POS.items():
        draw_node(ax, name, x, y)
    ax.text(0.02, 0.02, "orange: positive  blue: negative", fontsize=7.8, color="#555555")


def save_diagrams(paths: pd.DataFrame) -> None:
    out_dir = OUT / "figures/clear_path_diagrams"
    out_dir.mkdir(parents=True, exist_ok=True)
    for metric in ["GPP", "RECO"]:
        fig, axes = plt.subplots(len(BIOMES), 1, figsize=(10.8, 18.5))
        for ax, biome in zip(axes, BIOMES, strict=True):
            group = paths[(paths["metric"] == metric) & (paths["biome"] == biome)]
            draw_panel(ax, group, metric, biome, compact=True)
            single_fig, single_ax = plt.subplots(figsize=(11.0, 6.2))
            draw_panel(single_ax, group, metric, biome)
            single_fig.tight_layout()
            single_fig.savefig(out_dir / f"{metric.lower()}_{biome}_ssrd_required_path_diagram.png", dpi=300)
            plt.close(single_fig)
        fig.tight_layout(h_pad=2.0)
        fig.savefig(OUT / "figures" / f"{metric.lower()}_ssrd_required_path_diagrams_overview.png", dpi=300)
        plt.close(fig)


def heatmap(data: pd.DataFrame, value_col: str, output: Path, title: str) -> None:
    work = data.copy()
    if "source_label" not in work.columns and "from_label" in work.columns:
        work["source_label"] = work["from_label"]
    work["row"] = work["metric"] + " " + work["biome"]
    pivot = work.pivot_table(index="row", columns="source_label", values=value_col, aggfunc="first")
    cols = [c for c in ["SSRD", "PRE", "WIND", "TMP", "VPD", "|EVA|", "SMrz"] if c in pivot.columns]
    pivot = pivot.reindex(columns=cols)
    max_abs = max(float(np.nanmax(np.abs(pivot.to_numpy()))), 0.01)
    fig, ax = plt.subplots(figsize=(9.5, 6.2))
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
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7.5)
    fig.colorbar(im, ax=ax, shrink=0.82, label="Standardized effect")
    fig.tight_layout()
    fig.savefig(output, dpi=300)
    plt.close(fig)


def save_r2_plot(r2: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    x = np.arange(len(BIOMES))
    width = 0.36
    for offset, metric, color in [(-width / 2, "GPP", "#2b8cbe"), (width / 2, "RECO", "#f03b20")]:
        vals = [r2[(r2["metric"] == metric) & (r2["biome"] == biome)]["holdout_r2"].iloc[0] for biome in BIOMES]
        ax.bar(x + offset, vals, width=width, label=metric, color=color, alpha=0.88)
    ax.set_xticks(x)
    ax.set_xticklabels(BIOMES, rotation=25, ha="right")
    ax.set_ylabel("Holdout R2")
    ax.set_title("SSRD-required pre-peak SEM explanatory strength")
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#dddddd", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(OUT / "figures/sem_prepeak_ssrd_required_holdout_r2_gpp_reco.png", dpi=300)
    plt.close(fig)


def write_readme(r2: pd.DataFrame, paths: pd.DataFrame, total: pd.DataFrame) -> None:
    ssrd_target = paths[(paths["from_label"] == "SSRD") & (paths["to"] == TARGET)].copy()
    lines = [
        "# SSRD-required SHAP-informed SEM",
        "",
        "This version is fitted because SSRD is a stable top SHAP feature and must be represented directly in SEM.",
        "",
        "Key design change from the previous half-unified model:",
        "",
        "- STRD is removed from the fitted SEM skeleton.",
        "- SSRD is inserted as a required energy-input variable.",
        "- SSRD affects recovery time directly and indirectly through |EVA|.",
        "- GPP and RECO are still fitted separately by biome.",
        "",
        "## Implemented path skeleton",
        "",
        "```text",
        "VPD  ~ TMP + WIND",
        "|EVA| ~ SSRD + PRE + VPD",
        "SMrz ~ PRE + |EVA|",
        "Recovery time ~ SSRD + TMP + VPD + |EVA| + SMrz",
        "```",
        "",
        "## Holdout R2",
        "",
        r2.to_csv(index=False),
        "",
        "## Direct SSRD paths to recovery time",
        "",
        ssrd_target[["metric", "biome", "estimate", "p_value", "significance"]].to_csv(index=False),
        "",
        "## Interpretation note",
        "",
        "This model should be used when the manuscript needs SEM to reflect the SHAP finding that SSRD is a dominant driver. It is not a rejection of STRD; rather, it is an SSRD-prioritized alternative that aligns the SEM mechanism layer with the SHAP importance ranking.",
    ]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    (OUT / "specs").mkdir(parents=True, exist_ok=True)
    all_paths = []
    all_r2 = []
    for metric in ["GPP", "RECO"]:
        (OUT / "specs" / f"{metric.lower()}_prepeak_ssrd_required_v20260505.txt").write_text(SPECS[metric] + "\n", encoding="utf-8")
        for biome in BIOMES:
            estimates, r2 = fit_one(metric, biome)
            estimates.to_csv(OUT / "tables" / f"{metric.lower()}_{biome}_ssrd_required_estimates.csv", index=False)
            paths = normalize_estimates(estimates, metric, biome)
            all_paths.append(paths)
            all_r2.append(r2)
    paths_df = pd.concat(all_paths, ignore_index=True)
    r2_df = pd.DataFrame(all_r2)
    target_direct = paths_df[paths_df["to"] == TARGET].copy()
    total = compute_total_effects(paths_df)
    paths_df.to_csv(OUT / "tables/sem_prepeak_ssrd_required_all_structural_paths.csv", index=False)
    target_direct.to_csv(OUT / "tables/sem_prepeak_ssrd_required_target_direct_paths.csv", index=False)
    total.to_csv(OUT / "tables/sem_prepeak_ssrd_required_total_effects.csv", index=False)
    r2_df.to_csv(OUT / "tables/sem_prepeak_ssrd_required_r2_gpp_reco.csv", index=False)
    save_diagrams(paths_df)
    save_r2_plot(r2_df)
    heatmap(target_direct, "estimate", OUT / "figures/sem_prepeak_ssrd_required_target_direct_coefficients_heatmap.png", "SSRD-required SEM direct effects")
    heatmap(total, "total_effect", OUT / "figures/sem_prepeak_ssrd_required_total_effects_heatmap.png", "SSRD-required SEM total effects")
    write_readme(r2_df, paths_df, total)
    print(OUT)


if __name__ == "__main__":
    main()
