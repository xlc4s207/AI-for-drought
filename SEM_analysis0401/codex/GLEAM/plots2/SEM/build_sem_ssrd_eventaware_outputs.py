#!/usr/bin/env python3
"""Fit an SSRD-required event-aware SEM variant and compare explanatory power."""

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
OUT = ROOT / "plots2/SEM/sem_prepeak_ssrd_eventaware_20260506"
BASE_R2 = ROOT / "plots2/SEM/sem_prepeak_ssrd_required_20260505/tables/sem_prepeak_ssrd_required_r2_gpp_reco.csv"
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
PLOT_MIN_ABS_EFFECT = 0.05
PLOT_MAX_EDGES = 14
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


def zscore(df: pd.DataFrame) -> pd.DataFrame:
    numeric = df.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    numeric = numeric.dropna(axis=0, how="any")
    std = numeric.std(ddof=0).replace(0, np.nan)
    return ((numeric - numeric.mean()) / std).dropna(axis=1, how="any")


def fit_equation(data: pd.DataFrame, metric: str, biome: str, lhs: str, rhs: list[str]) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    frame = data[[lhs] + rhs].dropna(axis=0, how="any")
    x = frame[rhs].to_numpy(dtype=float)
    y = frame[lhs].to_numpy(dtype=float)
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
    for feature, coef, stderr in zip(rhs, reg.coef_, se, strict=True):
        z_value = float(coef / stderr) if stderr > 0 else np.nan
        p_value = float(2.0 * stats.norm.sf(abs(z_value))) if np.isfinite(z_value) else np.nan
        rows.append(
            {
                "metric": metric,
                "biome": biome,
                "scope": "prepeak_ssrd_eventaware_20260506",
                "from": feature,
                "to": lhs,
                "estimate": float(coef),
                "std_err": float(stderr),
                "z_value": z_value,
                "p_value": p_value,
                "significance": "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "",
                "from_label": label(feature),
                "to_label": label(lhs),
            }
        )
    r2_row = None
    if lhs == TARGET:
        train, test = train_test_split(frame, test_size=0.2, random_state=42)
        reg2 = LinearRegression()
        reg2.fit(train[rhs], train[lhs])
        r2_row = {
            "metric": metric,
            "biome": biome,
            "scope": "prepeak_ssrd_eventaware_20260506",
            "rows": len(frame),
            "holdout_r2": float(reg2.score(test[rhs], test[lhs])),
            "train_r2": float(reg2.score(train[rhs], train[lhs])),
            "predictor_count": len(rhs),
        }
    return rows, r2_row


def load_metric_biome(metric: str, biome: str) -> pd.DataFrame:
    df = pd.read_parquet(TABLES[metric], columns=COLUMNS)
    df = df[df["biome"] == biome].drop(columns=["biome"]).reset_index(drop=True)
    return zscore(df)


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
            source_paths = enumerate_paths(children, source)
            if not source_paths:
                continue
            direct = 0.0
            indirect = 0.0
            direct_count = 0
            indirect_count = 0
            for path in source_paths:
                effect = float(np.prod([edge[2] for edge in path]))
                if len(path) == 1:
                    direct += effect
                    direct_count += 1
                else:
                    indirect += effect
                    indirect_count += 1
            rows.append(
                {
                    "metric": metric,
                    "biome": biome,
                    "source": source,
                    "source_label": label(source),
                    "direct_effect": direct,
                    "indirect_effect": indirect,
                    "total_effect": direct + indirect,
                    "direct_path_count": direct_count,
                    "indirect_path_count": indirect_count,
                }
            )
    return pd.DataFrame(rows)


def save_r2_comparison(r2: pd.DataFrame) -> None:
    base = pd.read_csv(BASE_R2)
    base = base[["metric", "biome", "holdout_r2"]].rename(columns={"holdout_r2": "ssrd_required_r2"})
    comp = r2.merge(base, on=["metric", "biome"], how="left")
    comp["r2_gain"] = comp["holdout_r2"] - comp["ssrd_required_r2"]
    comp.to_csv(OUT / "tables/sem_prepeak_ssrd_eventaware_r2_comparison.csv", index=False)

    fig, ax = plt.subplots(figsize=(9.4, 5.0))
    labels = [f"{m}\n{b}" for m, b in zip(comp["metric"], comp["biome"], strict=True)]
    x = np.arange(len(comp))
    ax.bar(x - 0.18, comp["ssrd_required_r2"], width=0.36, color="#9ecae1", label="SSRD-required")
    ax.bar(x + 0.18, comp["holdout_r2"], width=0.36, color="#fb6a4a", label="SSRD event-aware")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Holdout R2")
    ax.set_title("Does event-aware SEM improve explanatory power?")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.2, linestyle="--")
    fig.tight_layout()
    fig.savefig(OUT / "figures/sem_prepeak_ssrd_eventaware_r2_comparison.png", dpi=300)
    plt.close(fig)


def heatmap(data: pd.DataFrame, value_col: str, output: Path, title: str) -> None:
    work = data.copy()
    if "source_label" not in work.columns and "from_label" in work.columns:
        work["source_label"] = work["from_label"]
    work["row"] = work["metric"] + " " + work["biome"]
    pivot = work.pivot_table(index="row", columns="source_label", values=value_col, aggfunc="first")
    cols = [c for c in ["SSRD", "STRD", "TMP", "VPD", "|EVA|", "SMrz", "Duration", "Intensity", "PRE", "WIND"] if c in pivot.columns]
    pivot = pivot.reindex(columns=cols)
    max_abs = max(float(np.nanmax(np.abs(pivot.to_numpy()))), 0.01)
    fig, ax = plt.subplots(figsize=(10.5, 6.3))
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
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7.2)
    fig.colorbar(im, ax=ax, shrink=0.82, label="Standardized effect")
    fig.tight_layout()
    fig.savefig(output, dpi=300)
    plt.close(fig)


def draw_node(ax: plt.Axes, text: str, xy: tuple[float, float]) -> None:
    is_target = text == "Recovery time"
    ax.text(
        xy[0],
        xy[1],
        text,
        ha="center",
        va="center",
        fontsize=8.3 if not is_target else 8.0,
        fontweight="bold" if is_target else "normal",
        bbox={
            "boxstyle": "round,pad=0.34,rounding_size=0.08",
            "facecolor": "#fff7bc" if is_target else "#f7f7f7",
            "edgecolor": "#4d4d4d",
            "linewidth": 0.9,
        },
        zorder=5,
    )


def draw_edge(ax: plt.Axes, row: pd.Series, max_abs: float) -> None:
    src = str(row["from_label"])
    dst = str(row["to_label"])
    coef = float(row["estimate"])
    start = NODE_POS[src]
    end = NODE_POS[dst]
    color = "#b2182b" if coef > 0 else "#2166ac"
    width = 0.8 + 3.0 * min(abs(coef) / max_abs, 1.0)
    rad = EDGE_RAD.get((src, dst), 0.0)
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=9.5,
        linewidth=width,
        color=color,
        alpha=0.82,
        shrinkA=20,
        shrinkB=25 if dst == "Recovery time" else 20,
        connectionstyle=f"arc3,rad={rad}",
        zorder=2,
    )
    ax.add_patch(arrow)

    mid_x = (start[0] + end[0]) / 2
    mid_y = (start[1] + end[1]) / 2 + rad * 0.10
    ax.text(
        mid_x,
        mid_y,
        f"{coef:+.2f}",
        ha="center",
        va="center",
        fontsize=6.8,
        color=color,
        bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "none", "alpha": 0.78},
        zorder=4,
    )


def draw_path_panel(ax: plt.Axes, panel_paths: pd.DataFrame, title: str, show_legend: bool = False) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(title, fontsize=10.5, fontweight="bold", pad=6)
    eligible = panel_paths[panel_paths["abs_estimate"] >= PLOT_MIN_ABS_EFFECT].copy()
    target_paths = eligible[eligible["to"] == TARGET].copy()
    mediator_paths = eligible[eligible["to"] != TARGET].copy()
    mediator_keep = max(PLOT_MAX_EDGES - len(target_paths), 0)
    visible = pd.concat(
        [
            target_paths,
            mediator_paths.sort_values("abs_estimate", ascending=False).head(mediator_keep),
        ],
        ignore_index=True,
    )
    max_abs = max(float(visible["abs_estimate"].max()) if not visible.empty else PLOT_MIN_ABS_EFFECT, PLOT_MIN_ABS_EFFECT)
    for _, row in visible.sort_values("abs_estimate").iterrows():
        draw_edge(ax, row, max_abs)
    for node, pos in NODE_POS.items():
        draw_node(ax, node, pos)
    if visible.empty:
        ax.text(0.5, 0.02, f"No path >= {PLOT_MIN_ABS_EFFECT:.2f}", ha="center", va="bottom", fontsize=7.5, color="#666666")
    if show_legend:
        ax.text(0.03, 0.99, "Red: positive path\nBlue: negative path", ha="left", va="top", fontsize=8, color="#333333")
        ax.text(
            0.03,
            0.01,
            f"Shown: recovery paths plus strongest mediator paths\nMinimum |standardized coefficient| >= {PLOT_MIN_ABS_EFFECT:.2f}",
            ha="left",
            va="bottom",
            fontsize=7.3,
            color="#555555",
        )


def save_path_diagrams(paths: pd.DataFrame) -> None:
    diagram_dir = OUT / "figures/path_diagrams"
    diagram_dir.mkdir(parents=True, exist_ok=True)

    for metric in ["GPP", "RECO"]:
        fig, axes = plt.subplots(1, len(BIOMES), figsize=(21.5, 5.0))
        for i, biome in enumerate(BIOMES):
            group = paths[(paths["metric"] == metric) & (paths["biome"] == biome)]
            draw_path_panel(axes[i], group, biome, show_legend=i == 0)
            single_fig, single_ax = plt.subplots(figsize=(7.4, 5.3))
            draw_path_panel(single_ax, group, f"{metric} {biome}", show_legend=True)
            single_fig.tight_layout()
            single_fig.savefig(diagram_dir / f"{metric.lower()}_{biome}_ssrd_eventaware_path_diagram.png", dpi=300)
            plt.close(single_fig)
        fig.suptitle(f"{metric} SSRD Event-Aware SEM Path Diagrams", fontsize=14, fontweight="bold", y=1.02)
        fig.tight_layout()
        fig.savefig(OUT / "figures" / f"{metric.lower()}_ssrd_eventaware_path_diagrams_overview.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def write_readme(r2: pd.DataFrame, paths: pd.DataFrame) -> None:
    comp = pd.read_csv(OUT / "tables/sem_prepeak_ssrd_eventaware_r2_comparison.csv")
    ssrd = paths[(paths["to"] == TARGET) & (paths["from"] == "prepeak_ssrd_mean")][["metric", "biome", "estimate", "p_value", "significance"]]
    lines = [
        "# SSRD event-aware SEM",
        "",
        "This model is a higher-explanatory-power SEM variant built because the simpler SSRD-required SEM had limited holdout R2.",
        "",
        "Compared with the previous SSRD-required model, this version keeps SSRD and adds STRD, Duration and Intensity in the recovery-time equation.",
        "",
        "## Figures",
        "",
        f"Path diagrams are saved in `figures/path_diagrams/`, with overview panels saved as `gpp_ssrd_eventaware_path_diagrams_overview.png` and `reco_ssrd_eventaware_path_diagrams_overview.png`. To keep the diagrams readable, each panel prioritizes direct recovery-time paths plus the strongest mediator paths, with |standardized coefficient| >= {PLOT_MIN_ABS_EFFECT:.2f}; the complete path table is preserved in `tables/sem_prepeak_ssrd_eventaware_all_structural_paths.csv`.",
        "",
        "## Target equation",
        "",
        "```text",
        "Recovery time ~ SSRD + STRD + TMP + VPD + |EVA| + SMrz + Duration + Intensity",
        "```",
        "",
        "## R2 comparison",
        "",
        comp.to_csv(index=False),
        "",
        "## Direct SSRD paths",
        "",
        ssrd.to_csv(index=False),
        "",
        "## Interpretation",
        "",
        "The R2 gain quantifies how much explanatory power is recovered by adding event-memory and additional radiation/thermal information. If the gain is still modest, that indicates the recovery-time process is strongly nonlinear and heterogeneous; SEM should then be interpreted primarily as a mechanism test, while SHAP/ALE/ICE carry the nonlinear predictive explanation.",
    ]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    all_paths = []
    r2_rows = []
    for metric in ["GPP", "RECO"]:
        for biome in BIOMES:
            data = load_metric_biome(metric, biome)
            metric_paths = []
            for lhs, rhs in EQUATIONS:
                rows, r2 = fit_equation(data, metric, biome, lhs, rhs)
                metric_paths.extend(rows)
                if r2 is not None:
                    r2_rows.append(r2)
            pd.DataFrame(metric_paths).to_csv(OUT / "tables" / f"{metric.lower()}_{biome}_ssrd_eventaware_paths.csv", index=False)
            all_paths.extend(metric_paths)
    paths = pd.DataFrame(all_paths)
    paths["abs_estimate"] = paths["estimate"].abs()
    r2 = pd.DataFrame(r2_rows)
    target_direct = paths[paths["to"] == TARGET].copy()
    total = compute_total_effects(paths)
    paths.to_csv(OUT / "tables/sem_prepeak_ssrd_eventaware_all_structural_paths.csv", index=False)
    target_direct.to_csv(OUT / "tables/sem_prepeak_ssrd_eventaware_target_direct_paths.csv", index=False)
    total.to_csv(OUT / "tables/sem_prepeak_ssrd_eventaware_total_effects.csv", index=False)
    r2.to_csv(OUT / "tables/sem_prepeak_ssrd_eventaware_r2_gpp_reco.csv", index=False)
    save_r2_comparison(r2)
    heatmap(target_direct, "estimate", OUT / "figures/sem_prepeak_ssrd_eventaware_target_direct_coefficients_heatmap.png", "SSRD event-aware direct effects")
    heatmap(total, "total_effect", OUT / "figures/sem_prepeak_ssrd_eventaware_total_effects_heatmap.png", "SSRD event-aware total effects")
    save_path_diagrams(paths)
    write_readme(r2, paths)
    print(OUT)


if __name__ == "__main__":
    main()
