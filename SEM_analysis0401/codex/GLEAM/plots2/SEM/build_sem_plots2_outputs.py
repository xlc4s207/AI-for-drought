#!/usr/bin/env python3
"""Build SEM presentation outputs under plots2/SEM.

This script turns the existing half-unified SEM result tables into a
SHAP-informed SEM package aligned with writing3/05 design notes.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
import numpy as np
import pandas as pd


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
SEM_ROOT = ROOT / "results/SEM_conclusion/sem_halfunified_20260502"
OUT = ROOT / "plots2/SEM/sem_prepeak_shap_informed_20260505"
TARGET = "t_recover_to_baseline_abs_peak"

BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
SCENARIOS = {
    "GPP": {
        "dir": SEM_ROOT / "gpp_code1_flash_smrz_v20260401_halfunified/sem_prepeak",
        "scope": "gpp_prepeak_halfunified_0401",
    },
    "RECO": {
        "dir": SEM_ROOT / "reco_code1_flash_smrz_v20260401_halfunified/sem_prepeak",
        "scope": "reco_prepeak_halfunified_0401",
    },
}

LABELS = {
    "prepeak_total_precipitation_mean": "PRE",
    "prepeak_total_evaporation_mean": "|EVA|",
    "prepeak_temperature_2m_mean": "TMP",
    "prepeak_VPD_mean": "VPD",
    "prepeak_SMrz_mean": "SMrz",
    "prepeak_lai_total_mean": "LAI",
    "prepeak_ssrd_mean": "SSRD",
    "prepeak_strd_mean": "STRD",
    "prepeak_wind_speed_mean": "WIND",
    "event_duration": "Duration",
    TARGET: "Recovery time",
}

NODE_POS = {
    "STRD": (0.11, 0.82),
    "PRE": (0.11, 0.50),
    "WIND": (0.11, 0.18),
    "TMP": (0.35, 0.82),
    "VPD": (0.35, 0.50),
    "|EVA|": (0.60, 0.64),
    "SMrz": (0.60, 0.34),
    "Recovery time": (0.88, 0.50),
}

EDGE_RAD = {
    ("STRD", "TMP"): 0.00,
    ("TMP", "VPD"): -0.10,
    ("WIND", "VPD"): 0.12,
    ("PRE", "|EVA|"): 0.12,
    ("VPD", "|EVA|"): -0.12,
    ("PRE", "SMrz"): -0.18,
    ("|EVA|", "SMrz"): -0.20,
    ("TMP", "Recovery time"): -0.24,
    ("VPD", "Recovery time"): 0.28,
    ("|EVA|", "Recovery time"): 0.18,
    ("SMrz", "Recovery time"): -0.22,
}


def label(name: str) -> str:
    return LABELS.get(name, name)


def read_r2() -> pd.DataFrame:
    frames = []
    for metric, cfg in SCENARIOS.items():
        path = cfg["dir"] / f"{metric.lower()}_prepeak_halfunified_0401_r2_summary.csv"
        df = pd.read_csv(path)
        df.insert(0, "metric", metric)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out = out[out["biome"].isin(BIOMES)].copy()
    return out


def read_paths() -> pd.DataFrame:
    frames = []
    for metric, cfg in SCENARIOS.items():
        path = cfg["dir"] / f"{metric.lower()}_prepeak_halfunified_0401_path_effect_strengths.csv"
        df = pd.read_csv(path)
        df.insert(0, "metric", metric)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out = out[out["biome"].isin(BIOMES)].copy()
    out["from_label"] = out["from"].map(label)
    out["to_label"] = out["to"].map(label)
    return out


def enumerate_paths(children: dict[str, list[tuple[str, float]]], source: str, target: str) -> list[list[tuple[str, str, float]]]:
    stack: list[tuple[str, list[tuple[str, str, float]]]] = [(source, [])]
    paths: list[list[tuple[str, str, float]]] = []
    while stack:
        node, path = stack.pop()
        for child, coeff in children.get(node, []):
            next_path = path + [(node, child, coeff)]
            if child == target:
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
        sources = sorted(set(group["from"]) | set(group["to"]))
        for source in sources:
            if source == TARGET:
                continue
            all_paths = enumerate_paths(children, source, TARGET)
            if not all_paths:
                continue
            direct = 0.0
            indirect = 0.0
            direct_paths = 0
            indirect_paths = 0
            for path in all_paths:
                effect = float(np.prod([edge[2] for edge in path]))
                if len(path) == 1:
                    direct += effect
                    direct_paths += 1
                else:
                    indirect += effect
                    indirect_paths += 1
            rows.append(
                {
                    "metric": metric,
                    "biome": biome,
                    "source": source,
                    "source_label": label(source),
                    "direct_effect": direct,
                    "indirect_effect": indirect,
                    "total_effect": direct + indirect,
                    "direct_path_count": direct_paths,
                    "indirect_path_count": indirect_paths,
                }
            )
    return pd.DataFrame(rows)


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
    ax.set_title("Pre-peak SHAP-informed SEM explanatory strength")
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#dddddd", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(OUT / "figures/sem_prepeak_holdout_r2_gpp_reco.png", dpi=300)
    plt.close(fig)


def heatmap(data: pd.DataFrame, value_col: str, output: Path, title: str) -> None:
    data = data.copy()
    data["row"] = data["metric"] + " " + data["biome"]
    pivot = data.pivot_table(index="row", columns="source_label", values=value_col, aggfunc="first")
    preferred = ["STRD", "WIND", "PRE", "TMP", "VPD", "|EVA|", "SMrz"]
    cols = [c for c in preferred if c in pivot.columns] + [c for c in pivot.columns if c not in preferred]
    pivot = pivot.reindex(columns=cols)
    max_abs = float(np.nanmax(np.abs(pivot.to_numpy()))) if pivot.size else 1.0
    max_abs = max(max_abs, 0.01)

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
    cbar = fig.colorbar(im, ax=ax, shrink=0.82)
    cbar.set_label("Standardized effect")
    fig.tight_layout()
    fig.savefig(output, dpi=300)
    plt.close(fig)


def draw_node(ax: plt.Axes, name: str, x: float, y: float) -> None:
    is_target = name == "Recovery time"
    ax.text(
        x,
        y,
        name,
        ha="center",
        va="center",
        fontsize=9.5 if not is_target else 9,
        fontweight="bold" if is_target else "normal",
        bbox={
            "boxstyle": "round,pad=0.24,rounding_size=0.04",
            "facecolor": "#f4f7fb" if not is_target else "#fff2cc",
            "edgecolor": "#4f81bd" if not is_target else "#c27c0e",
            "linewidth": 1.15,
        },
        zorder=4,
    )


def draw_edge(
    ax: plt.Axes,
    source: str,
    target: str,
    estimate: float,
    max_abs: float,
    compact: bool = False,
) -> None:
    x1, y1 = NODE_POS[source]
    x2, y2 = NODE_POS[target]
    color = "#d95f02" if estimate >= 0 else "#1f78b4"
    rad = EDGE_RAD.get((source, target), 0.0)
    width = 0.8 + 2.9 * min(abs(estimate) / max_abs, 1.0)
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

    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    dx = x2 - x1
    dy = y2 - y1
    norm = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    offset = 0.035 if not compact else 0.028
    label_x = mx - dy / norm * offset + rad * 0.04
    label_y = my + dx / norm * offset + rad * 0.04
    ax.text(
        label_x,
        label_y,
        f"{estimate:+.2f}",
        ha="center",
        va="center",
        fontsize=7.5 if compact else 8.2,
        color=color,
        bbox={
            "boxstyle": "round,pad=0.10",
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.86,
        },
        zorder=5,
    )


def draw_sem_panel(ax: plt.Axes, group: pd.DataFrame, metric: str, biome: str, compact: bool = False) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(f"{metric} - {biome}", fontsize=11 if compact else 13, pad=8)

    group = group.copy()
    group["source_label"] = group["from"].map(label)
    group["target_label"] = group["to"].map(label)
    group = group[group["source_label"].isin(NODE_POS) & group["target_label"].isin(NODE_POS)]
    max_abs = max(float(group["estimate"].abs().max()), 0.01)

    # Draw arrows first, then nodes so labels remain readable.
    for _, rec in group.sort_values("abs_estimate", ascending=True).iterrows():
        draw_edge(
            ax,
            str(rec["source_label"]),
            str(rec["target_label"]),
            float(rec["estimate"]),
            max_abs=max_abs,
            compact=compact,
        )

    for name, (x, y) in NODE_POS.items():
        draw_node(ax, name, x, y)

    ax.text(
        0.02,
        0.02,
        "orange: positive  blue: negative",
        fontsize=7.5 if compact else 8.5,
        color="#555555",
        ha="left",
        va="bottom",
    )


def save_clear_path_diagrams(paths: pd.DataFrame) -> None:
    out_dir = OUT / "figures/clear_path_diagrams"
    out_dir.mkdir(parents=True, exist_ok=True)
    for metric in SCENARIOS:
        metric_paths = paths[paths["metric"] == metric].copy()
        fig, axes = plt.subplots(len(BIOMES), 1, figsize=(10.8, 18.5))
        if len(BIOMES) == 1:
            axes = [axes]
        for ax, biome in zip(axes, BIOMES):
            group = metric_paths[metric_paths["biome"] == biome]
            draw_sem_panel(ax, group, metric, biome, compact=True)
            single_fig, single_ax = plt.subplots(figsize=(11.0, 6.2))
            draw_sem_panel(single_ax, group, metric, biome, compact=False)
            single_fig.tight_layout()
            single_fig.savefig(out_dir / f"{metric.lower()}_{biome}_clear_path_diagram.png", dpi=300)
            plt.close(single_fig)
        fig.tight_layout(h_pad=2.0)
        # Overwrite the previous crowded overview names with the clearer layout.
        fig.savefig(OUT / "figures" / f"{metric.lower()}_sem_prepeak_path_diagrams_overview.png", dpi=300)
        fig.savefig(out_dir / f"{metric.lower()}_all_biomes_clear_path_diagrams_overview.png", dpi=300)
        plt.close(fig)


def build_alignment_table(paths: pd.DataFrame) -> pd.DataFrame:
    design_rows = [
        ("Water supply", "PRE -> SMrz", "主模型建议路径；当前用 PRE -> |EVA| 与 PRE -> SMrz 表达水分补给。"),
        ("Energy-thermal", "STRD -> TMP", "扩展热量背景路径；当前作为半统一骨架的上游路径。"),
        ("Atmospheric dryness", "TMP + WIND -> VPD", "当前用 TMP 和 WIND 解释 VPD，符合大气干旱调节设计。"),
        ("Evaporation coupling", "PRE + VPD -> |EVA|", "当前将蒸散作为水分和大气干旱共同作用的中介。"),
        ("Root-zone mediation", "PRE + |EVA| -> SMrz", "当前将 SMrz 作为根区水分中介，符合 05 文档主干。"),
        ("GPP target", "TMP + VPD + |EVA| + SMrz -> recovery", "GPP 保留 |EVA| 直接路径，用于表示蒸散-光合恢复耦合。"),
        ("RECO target", "TMP + VPD + SMrz -> recovery", "RECO 不保留 |EVA| 直接终点路径，更强调温度和水分对呼吸恢复的控制。"),
        ("LAI", "Sensitivity only", "05 文档建议弱化 LAI；当前主模型未加入 LAI。"),
        ("Duration", "Event memory", "05 文档建议加入；当前 half-unified 版本未加入，后续可做 event-aware 扩展模型。"),
        ("SSRD", "Shortwave radiation", "05 文档建议作为主变量；当前为控制共线性未直接入主模型，使用 STRD/TMP 表达热量背景。"),
    ]
    return pd.DataFrame(design_rows, columns=["mechanism", "planned_path", "implementation_note"])


def df_to_markdown(df: pd.DataFrame, floatfmt: str = ".3f") -> str:
    def clean(value: object) -> str:
        if isinstance(value, float):
            text = format(value, floatfmt)
        else:
            text = str(value)
        return text.replace("|", "\\|")

    if df.empty:
        return "_No rows._"
    work = df.copy()
    headers = [str(c) for c in work.columns]
    rows = []
    for _, rec in work.iterrows():
        row = []
        for value in rec.tolist():
            row.append(clean(value))
        rows.append(row)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_report(r2: pd.DataFrame, paths: pd.DataFrame, total: pd.DataFrame, alignment: pd.DataFrame) -> None:
    target = paths[paths["to"] == TARGET].copy()
    top_target = (
        target.sort_values(["metric", "biome", "abs_estimate"], ascending=[True, True, False])
        .groupby(["metric", "biome"], sort=False)
        .head(2)
    )
    lines = [
        "# 基于 SHAP 规划的 GPP 与 RECO 恢复时间 SEM 结果包",
        "",
        "本目录按照 `process/SEM_analysis0401/codex/writing3/05_SHAP_SEM_path_analysis_design_cn.docx` 中的设计逻辑，整理 pre-peak 阶段 GPP 与 RECO 恢复时间的 SEM 结果。",
        "",
        "## 模型角色",
        "",
        "SHAP 用于筛选变量、识别阈值和提出机制假设；SEM 用于把这些变量组织成直接路径和中介路径。GPP 与 RECO 作为两个独立响应系统分别建模，不设置 GPP 指向 RECO 或 RECO 指向 GPP 的路径。",
        "",
        "## 文件说明",
        "",
        "- `tables/sem_prepeak_r2_gpp_reco.csv`：不同 metric 和 biome 的训练集与 holdout R2。",
        "- `tables/sem_prepeak_all_structural_paths.csv`：所有标准化结构路径系数。",
        "- `tables/sem_prepeak_target_direct_paths.csv`：直接指向恢复时间的路径系数。",
        "- `tables/sem_prepeak_total_effects.csv`：由有向 SEM 路径计算的直接效应、间接效应和总效应。",
        "- `tables/sem_prepeak_design_alignment.csv`：05 文档规划与当前 half-unified 实现之间的对应关系。",
        "- `figures/sem_prepeak_holdout_r2_gpp_reco.png`：GPP 与 RECO 的解释力对比。",
        "- `figures/sem_prepeak_target_direct_coefficients_heatmap.png`：恢复时间直接路径系数热图。",
        "- `figures/sem_prepeak_total_effects_heatmap.png`：包含中介路径后的总效应热图。",
        "",
        "## 与 05 文档设计的对应关系",
        "",
        df_to_markdown(alignment),
        "",
        "## Holdout R2",
        "",
        df_to_markdown(r2[["metric", "biome", "rows", "holdout_r2", "train_r2", "predictor_count"]]),
        "",
        "## 指向恢复时间的最强直接路径",
        "",
        df_to_markdown(top_target[["metric", "biome", "from_label", "estimate", "p_value", "significance"]]),
        "",
        "## 结果解释",
        "",
        "当前实现采用较保守的 half-unified 骨架：STRD 作为 TMP 的上游热量/长波辐射背景；TMP 和 WIND 共同解释 VPD；PRE 和 VPD 调节 |EVA|；PRE 和 |EVA| 进一步调节 SMrz；最后由温度、大气干旱、蒸散和根区水分变量解释恢复时间。这样既保持 GPP 与 RECO 模型之间的可比性，也控制了 SHAP-to-SEM 规划文档中反复提到的共线性风险。",
        "",
        "GPP 模型保留 |EVA| 到恢复时间的直接路径，符合 05 文档中“实际蒸散可代表水分-能量耦合并影响光合恢复”的设计。RECO 模型不保留 |EVA| 的终点直接路径，而更强调 TMP、VPD 和 SMrz，这与生态系统呼吸恢复受温度激活、水分可用性和大气干旱共同控制的机制更一致。LAI 按照 05 文档建议未进入主模型，仅适合作为后续敏感性分析变量。",
        "",
        "写作时需要明确两点与 05 文档完整设计的差异：第一，Duration 尚未进入当前 half-unified 主模型，后续应作为 event-aware 扩展模型中的事件记忆路径处理；第二，SSRD 在当前主模型中没有直接进入，而是为了降低共线性风险，暂时使用 STRD/TMP 表达热量背景。若后续共线性诊断允许，可把 SSRD 作为 STRD/TMP 热量路径的替代或扩展版本单独检验。",
    ]
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)

    r2 = read_r2()
    paths = read_paths()
    target_direct = paths[paths["to"] == TARGET].copy()
    total = compute_total_effects(paths)
    alignment = build_alignment_table(paths)

    r2.to_csv(OUT / "tables/sem_prepeak_r2_gpp_reco.csv", index=False)
    paths.to_csv(OUT / "tables/sem_prepeak_all_structural_paths.csv", index=False)
    target_direct.to_csv(OUT / "tables/sem_prepeak_target_direct_paths.csv", index=False)
    total.to_csv(OUT / "tables/sem_prepeak_total_effects.csv", index=False)
    alignment.to_csv(OUT / "tables/sem_prepeak_design_alignment.csv", index=False)

    save_r2_plot(r2)
    heatmap(
        target_direct.rename(columns={"from_label": "source_label"}),
        "estimate",
        OUT / "figures/sem_prepeak_target_direct_coefficients_heatmap.png",
        "Direct SEM effects on recovery time",
    )
    heatmap(
        total,
        "total_effect",
        OUT / "figures/sem_prepeak_total_effects_heatmap.png",
        "Total SEM effects on recovery time",
    )
    save_clear_path_diagrams(paths)
    write_report(r2, paths, total, alignment)
    print(OUT)


if __name__ == "__main__":
    main()
