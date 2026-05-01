from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from math import cos, sin, pi

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


BASE = Path(__file__).resolve().parent

EDGE_POS = "#cc6b2c"
EDGE_NEG = "#2f79a8"
EXOG_FACE = "#dce8f2"
EXOG_EDGE = "#426b93"
MID_FACE = "#f8e7a6"
MID_EDGE = "#a88616"
TARGET_FACE = "#f3d7bf"
TARGET_EDGE = "#aa6a2a"
TEXT_COLOR = "#222222"

LABEL_MAP = {
    "prepeak_total_precipitation_mean": "PRE",
    "prepeak_temperature_2m_mean": "TMP",
    "prepeak_total_evaporation_mean": "EVA",
    "prepeak_ssrd_mean": "SSRD",
    "prepeak_strd_mean": "STRD",
    "prepeak_wind_speed_mean": "WIND",
    "prepeak_dewpoint_temperature_mean": "DPT",
    "prepeak_p_minus_et": "P-ET",
    "prepeak_SMrz_mean": "SMrz",
    "prepeak_VPD_mean": "VPD",
    "prepeak_lai_total_mean": "LAI",
    "recoverywin_total_precipitation_mean": "PRE",
    "recoverywin_temperature_2m_mean": "TMP",
    "recoverywin_total_evaporation_mean": "EVA",
    "recoverywin_ssrd_mean": "SSRD",
    "recoverywin_strd_mean": "STRD",
    "recoverywin_wind_speed_mean": "WIND",
    "recoverywin_dewpoint_temperature_mean": "DPT",
    "recoverywin_p_minus_et": "P-ET",
    "recoverywin_SMrz_mean": "SMrz",
    "recoverywin_VPD_mean": "VPD",
    "recoverywin_lai_total_mean": "LAI",
    "t_recover_to_baseline_abs_peak": "t_recover",
}

NODE_ORDER = ["PRE", "TMP", "EVA", "SSRD", "STRD", "WIND", "DPT", "P-ET", "SMrz", "VPD", "LAI", "t_recover"]
MEDIATORS = {"P-ET", "SMrz", "VPD", "LAI"}
EXOGENOUS = {"PRE", "TMP", "EVA", "SSRD", "STRD", "WIND", "DPT"}

T_RAD = {
    "PRE": 0.10,
    "TMP": -0.10,
    "EVA": -0.18,
    "SSRD": 0.18,
    "STRD": 0.10,
    "WIND": -0.14,
    "DPT": 0.14,
    "P-ET": 0.00,
    "SMrz": -0.06,
    "LAI": 0.06,
    "VPD": 0.00,
}


@dataclass
class Edge:
    source: str
    target: str
    estimate: float
    p_value: float
    significance: str
    forced: bool = False

    @property
    def abs_estimate(self) -> float:
        return abs(self.estimate)

    @property
    def color(self) -> str:
        return EDGE_POS if self.estimate >= 0 else EDGE_NEG

    @property
    def linestyle(self) -> str:
        if self.forced and (pd.isna(self.significance) or self.p_value >= 0.05):
            return (0, (4, 3))
        return "solid"


def edge_key(source: str, target: str) -> Tuple[str, str]:
    return (source, target)


def prettify(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["source"] = out["from"].map(LABEL_MAP)
    out["target"] = out["to"].map(LABEL_MAP)
    return out


def incoming_edges(sub: pd.DataFrame, target: str) -> pd.DataFrame:
    return sub[sub["target"] == target].sort_values("abs_estimate", ascending=False)


def direct_t_edges(sub: pd.DataFrame) -> pd.DataFrame:
    return sub[sub["target"] == "t_recover"].sort_values("abs_estimate", ascending=False)


def select_edges(sub: pd.DataFrame, scope: str) -> List[Edge]:
    kept: Dict[Tuple[str, str], Edge] = {}

    def keep_rows(rows: Iterable[pd.Series], forced: bool = False) -> None:
        for row in rows:
            key = (row["source"], row["target"])
            kept[key] = Edge(
                source=row["source"],
                target=row["target"],
                estimate=float(row["estimate"]),
                p_value=float(row["p_value"]),
                significance="" if pd.isna(row["significance"]) else str(row["significance"]),
                forced=forced,
            )

    # Always keep mediator -> t_recover edges.
    forced_edges = sub[(sub["target"] == "t_recover") & (sub["source"].isin(MEDIATORS))]
    keep_rows(forced_edges.to_dict("records"), forced=True)

    # Keep top incoming edges for mediator nodes and remove tiny clutter.
    for mediator in ["P-ET", "SMrz", "VPD", "LAI"]:
        inc = incoming_edges(sub, mediator)
        if inc.empty:
            continue
        top2 = inc.head(2)
        keep_rows(top2.to_dict("records"))
        extra = inc[(inc["p_value"] < 0.05) & (inc["abs_estimate"] >= 0.18)]
        if mediator == "LAI":
            extra = inc[(inc["p_value"] < 0.05) & (inc["abs_estimate"] >= 0.15)]
        keep_rows(extra.to_dict("records"))

    # Scope-specific rescue paths to preserve mechanism readability.
    if scope == "prepeak":
        rescue = {
            ("PRE", "P-ET"),
            ("EVA", "P-ET"),
            ("P-ET", "SMrz"),
            ("PRE", "SMrz"),
            ("TMP", "SMrz"),
            ("TMP", "VPD"),
            ("SMrz", "LAI"),
            ("VPD", "LAI"),
            ("SSRD", "LAI"),
        }
    else:
        rescue = {
            ("PRE", "P-ET"),
            ("EVA", "P-ET"),
            ("PRE", "SMrz"),
            ("TMP", "SMrz"),
            ("P-ET", "SMrz"),
            ("TMP", "VPD"),
            ("DPT", "VPD"),
            ("STRD", "VPD"),
            ("SMrz", "LAI"),
            ("VPD", "LAI"),
        }

    rescue_rows = sub[sub.apply(lambda r: (r["source"], r["target"]) in rescue, axis=1)]
    keep_rows(rescue_rows.to_dict("records"))

    # Guarantee every exogenous feature appears with at least one edge.
    for feature in sorted(EXOGENOUS):
        if not any(e.source == feature or e.target == feature for e in kept.values()):
            candidates = sub[(sub["source"] == feature) & (sub["target"].isin(MEDIATORS))].sort_values(["p_value", "abs_estimate"], ascending=[True, False])
            if not candidates.empty:
                row = candidates.iloc[0]
                keep_rows([row.to_dict()])

    return list(sorted(kept.values(), key=lambda e: (NODE_ORDER.index(e.target), NODE_ORDER.index(e.source), -e.abs_estimate)))


def build_node_positions(edges: List[Edge]) -> Dict[str, Tuple[float, float]]:
    center = (0.50, 0.50)
    positions: Dict[str, Tuple[float, float]] = {"t_recover": center}

    mediator_degree = {}
    for node in MEDIATORS:
        mediator_degree[node] = sum(1 for e in edges if e.source == node or e.target == node)
    mediator_order = sorted(MEDIATORS, key=lambda n: (-mediator_degree[n], ["P-ET", "SMrz", "VPD", "LAI"].index(n)))
    inner_slots = [
        (0.50, 0.80),  # top
        (0.78, 0.50),  # right
        (0.50, 0.20),  # bottom
        (0.22, 0.50),  # left
    ]
    for node, pos in zip(mediator_order, inner_slots):
        positions[node] = pos

    # Determine each exogenous node's main target to place it on the outer ring near that sector.
    target_angles = {}
    for node in MEDIATORS:
        x, y = positions[node]
        if y > 0.65:
            target_angles[node] = 90
        elif y < 0.35:
            target_angles[node] = -90
        elif x > 0.50:
            target_angles[node] = 0
        else:
            target_angles[node] = 180

    preferred = {}
    for node in EXOGENOUS:
        outgoing = [e for e in edges if e.source == node]
        if outgoing:
            strongest = sorted(outgoing, key=lambda e: (-e.abs_estimate, e.p_value))[0]
            preferred[node] = strongest.target
        else:
            preferred[node] = "P-ET"

    # Unique non-overlapping outer-ring slots.
    outer_slot_angles = [160, 130, 100, 55, 20, -20, -55, -100, -130, -160]
    outer_slots = list(outer_slot_angles)
    radius = 0.43

    def desired_angle(node: str) -> float:
        base = target_angles.get(preferred[node], 90)
        nudges = {
            "PRE": -18,
            "TMP": 18,
            "EVA": 28,
            "SSRD": -28,
            "STRD": 20,
            "WIND": -20,
            "DPT": 32,
        }
        return base + nudges.get(node, 0)

    assigned = {}
    for node in sorted(EXOGENOUS, key=lambda n: desired_angle(n)):
        want = desired_angle(node)
        best_slot = min(outer_slots, key=lambda a: min(abs(a - want), 360 - abs(a - want)))
        assigned[node] = best_slot
        outer_slots.remove(best_slot)

    for node, angle_deg in assigned.items():
        theta = angle_deg * pi / 180.0
        positions[node] = (center[0] + radius * cos(theta), center[1] + radius * sin(theta))

    return positions


def build_mediator_summaries(edges: List[Edge]) -> Dict[str, float]:
    summary: Dict[str, float] = {m: 0.0 for m in MEDIATORS}
    for mediator in MEDIATORS:
        direct = next((e.estimate for e in edges if e.source == mediator and e.target == "t_recover"), 0.0)
        incoming_sum = sum(e.estimate for e in edges if e.target == mediator and e.source != "t_recover")
        summary[mediator] = direct + incoming_sum
    return summary


def node_style(name: str) -> Tuple[str, str]:
    if name == "t_recover":
        return TARGET_FACE, TARGET_EDGE
    if name in MEDIATORS:
        return MID_FACE, MID_EDGE
    return EXOG_FACE, EXOG_EDGE


def node_size(name: str) -> Tuple[float, float]:
    if name in {"DPT", "t_recover"}:
        return 0.15, 0.075
    return 0.10, 0.07


def draw_node(ax, name: str, node_pos: Dict[str, Tuple[float, float]]) -> None:
    x, y = node_pos[name]
    w, h = node_size(name)
    face, edge = node_style(name)
    box = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        linewidth=1.5,
        edgecolor=edge,
        facecolor=face,
        zorder=5,
    )
    ax.add_patch(box)
    ax.text(x, y, name, ha="center", va="center", fontsize=11, color=TEXT_COLOR, zorder=6)


def edge_rad(edge: Edge) -> float:
    src, dst = edge.source, edge.target
    if dst == "t_recover":
        return T_RAD.get(src, 0.0)
    if dst == "P-ET":
        return {"PRE": 0.08, "EVA": -0.10}.get(src, 0.0)
    if dst == "SMrz":
        mapping = {"PRE": 0.10, "TMP": 0.16, "EVA": 0.08, "SSRD": -0.10, "WIND": -0.16, "P-ET": 0.0}
        return mapping.get(src, 0.06)
    if dst == "VPD":
        mapping = {"TMP": -0.12, "DPT": 0.16, "STRD": -0.18, "WIND": -0.08, "SSRD": 0.08}
        return mapping.get(src, -0.06)
    if dst == "LAI":
        mapping = {"SMrz": 0.0, "VPD": 0.08, "SSRD": -0.10, "WIND": 0.14}
        return mapping.get(src, 0.06)
    return 0.0


def anchor_points(name: str, target: bool = False) -> Tuple[float, float]:
    raise RuntimeError("anchor_points requires node positions and should not be called directly")


def anchor_points_with_pos(name: str, node_pos: Dict[str, Tuple[float, float]], toward: Tuple[float, float]) -> Tuple[float, float]:
    x, y = node_pos[name]
    cx, cy = toward
    dx, dy = cx - x, cy - y
    norm = (dx * dx + dy * dy) ** 0.5 or 1.0
    w, h = node_size(name)
    rx, ry = w / 2, h / 2
    scale = 1.0 / max(abs(dx) / rx if rx else 0, abs(dy) / ry if ry else 0, 1e-6)
    return x + dx * scale, y + dy * scale


def label_position(source: str, target: str, rad: float) -> Tuple[float, float]:
    raise RuntimeError("label_position requires node positions and should not be called directly")


def label_position_with_pos(source: str, target: str, rad: float, node_pos: Dict[str, Tuple[float, float]]) -> Tuple[float, float]:
    sx, sy = node_pos[source]
    tx, ty = node_pos[target]
    mx, my = (sx + tx) / 2, (sy + ty) / 2
    dx, dy = tx - sx, ty - sy
    norm = (dx * dx + dy * dy) ** 0.5 or 1.0
    px, py = -dy / norm, dx / norm
    offset = 0.05 + min(abs(rad), 0.28) * 0.10
    sign = 1 if rad >= 0 else -1
    return mx + px * offset * sign, my + py * offset * sign


def draw_edge(ax, edge: Edge, node_pos: Dict[str, Tuple[float, float]]) -> None:
    source_center = node_pos[edge.source]
    target_center = node_pos[edge.target]
    sx, sy = anchor_points_with_pos(edge.source, node_pos, target_center)
    tx, ty = anchor_points_with_pos(edge.target, node_pos, source_center)
    rad = edge_rad(edge)
    arrow = FancyArrowPatch(
        (sx, sy),
        (tx, ty),
        arrowstyle="-|>",
        connectionstyle=f"arc3,rad={rad}",
        mutation_scale=12,
        linewidth=1.0 + min(edge.abs_estimate, 1.5) * 1.8,
        linestyle=edge.linestyle,
        color=edge.color,
        alpha=0.92 if not edge.forced else 0.82,
        zorder=2,
    )
    ax.add_patch(arrow)
    lx, ly = label_position_with_pos(edge.source, edge.target, rad, node_pos)
    sig = edge.significance if edge.significance else ""
    label = f"{edge.estimate:+.2f}{sig}"
    ax.text(
        lx,
        ly,
        label,
        ha="center",
        va="center",
        fontsize=9.5,
        color=edge.color,
        bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.78),
        zorder=7,
    )


def draw_mediator_to_target_label(ax, edge: Edge, node_pos: Dict[str, Tuple[float, float]], combined_value: float) -> None:
    rad = edge_rad(edge)
    lx, ly = label_position_with_pos(edge.source, edge.target, rad, node_pos)
    sig = edge.significance if edge.significance else ""
    label = f"{combined_value:+.2f}{sig}"
    ax.text(
        lx,
        ly,
        label,
        ha="center",
        va="center",
        fontsize=9.5,
        color=edge.color,
        bbox=dict(boxstyle="round,pad=0.16", facecolor="white", edgecolor="none", alpha=0.88),
        zorder=8,
    )


def draw_panel(ax, biome: str, scope: str, edges: List[Edge], r2_df: pd.DataFrame) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    node_pos = build_node_positions(edges)
    mediator_summaries = build_mediator_summaries(edges)

    r2 = r2_df[(r2_df["scope"] == scope) & (r2_df["biome"] == biome)]["holdout_r2"].iloc[0]
    ax.text(0.5, 1.02, biome, ha="center", va="bottom", fontsize=16, weight="bold", transform=ax.transAxes)
    ax.text(0.5, 0.96, f"holdout R2 = {r2:.3f}", ha="center", va="bottom", fontsize=12, transform=ax.transAxes, color="#444")

    for edge in edges:
        if edge.target == "t_recover" and edge.source in MEDIATORS:
            # Draw final aggregation lines without a simple numeric label;
            # a richer summary label is added afterward.
            source_center = node_pos[edge.source]
            target_center = node_pos[edge.target]
            sx, sy = anchor_points_with_pos(edge.source, node_pos, target_center)
            tx, ty = anchor_points_with_pos(edge.target, node_pos, source_center)
            rad = edge_rad(edge)
            arrow = FancyArrowPatch(
                (sx, sy),
                (tx, ty),
                arrowstyle="-|>",
                connectionstyle=f"arc3,rad={rad}",
                mutation_scale=16,
                linewidth=1.6 + min(edge.abs_estimate, 1.5) * 2.0,
                linestyle=edge.linestyle,
                color=edge.color,
                alpha=0.95 if not edge.forced else 0.85,
                zorder=4,
            )
            ax.add_patch(arrow)
        else:
            draw_edge(ax, edge, node_pos)
    for node in NODE_ORDER:
        draw_node(ax, node, node_pos)
    for edge in edges:
        if edge.target == "t_recover" and edge.source in MEDIATORS:
            draw_mediator_to_target_label(ax, edge, node_pos, mediator_summaries.get(edge.source, edge.estimate))


def build_scope_figure(scope: str, df: pd.DataFrame, r2_df: pd.DataFrame) -> None:
    biomes = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
    fig, axes = plt.subplots(3, 2, figsize=(18, 16))
    axes = axes.flatten()

    title = "Prepeak" if scope == "prepeak" else "Recoverywin"
    fig.suptitle(f"{title} SEM Path Diagrams (Clean Layout)", fontsize=24, weight="bold", y=0.98)

    for ax, biome in zip(axes, biomes):
        sub = df[(df["scope"] == scope) & (df["biome"] == biome)].copy()
        edges = select_edges(sub, scope)
        draw_panel(ax, biome, scope, edges, r2_df)

    axes[-1].axis("off")
    legend_ax = axes[-1]
    legend_ax.set_xlim(0, 1)
    legend_ax.set_ylim(0, 1)
    legend_ax.text(0.08, 0.80, "Edge color", fontsize=13, weight="bold")
    legend_ax.plot([0.08, 0.18], [0.68, 0.68], color=EDGE_POS, linewidth=3)
    legend_ax.text(0.21, 0.68, "Positive effect", va="center", fontsize=12)
    legend_ax.plot([0.08, 0.18], [0.54, 0.54], color=EDGE_NEG, linewidth=3)
    legend_ax.text(0.21, 0.54, "Negative effect", va="center", fontsize=12)
    legend_ax.plot([0.08, 0.18], [0.40, 0.40], color=EDGE_NEG, linewidth=2, linestyle=(0, (4, 3)))
    legend_ax.text(0.21, 0.40, "Forced weak mediator-to-target edge", va="center", fontsize=12)
    legend_ax.text(0.08, 0.18, "Labels: standardized estimates with significance stars.", fontsize=11, color="#555")
    legend_ax.axis("off")

    out_dir = BASE / f"sem_{scope}"
    out_png = out_dir / f"sem_{scope}_sem_path_diagrams_overview_clean.png"
    out_pdf = out_dir / f"sem_{scope}_sem_path_diagrams_overview_clean.pdf"
    fig.tight_layout(rect=(0.02, 0.02, 0.98, 0.95))
    fig.savefig(out_png, dpi=300)
    fig.savefig(out_pdf)
    plt.close(fig)


def main() -> None:
    effects = []
    for name in ["prepeak_path_effect_strengths.csv", "recoverywin_path_effect_strengths.csv"]:
        df = pd.read_csv(BASE / name)
        effects.append(prettify(df))
    all_effects = pd.concat(effects, ignore_index=True)
    r2_df = pd.read_csv(BASE / "unified11_r2_summary.csv")
    build_scope_figure("prepeak", all_effects, r2_df)
    build_scope_figure("recoverywin", all_effects, r2_df)
    print("Saved clean overview figures for prepeak and recoverywin.")


if __name__ == "__main__":
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "figure.dpi": 150,
            "savefig.dpi": 300,
        }
    )
    main()
