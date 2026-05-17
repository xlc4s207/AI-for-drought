#!/usr/bin/env python
"""Render SEM path diagrams for biome-specific single-equation models."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd


POSITIVE_COLOR = "#c26a2d"
NEGATIVE_COLOR = "#2d6f8e"
TARGET_FACE = "#f6d7b8"
TARGET_EDGE = "#8a4b08"
PREDICTOR_FACE = "#dbe9f4"
PREDICTOR_EDGE = "#355c7d"
EDGE_LABEL_FONTSIZE = 10.5
NODE_FONTSIZE = 11
TITLE_FONTSIZE = 13
SUPTITLE_FONTSIZE = 17
LABEL_MAP = {
    "temperature_2m_mean": "TMP",
    "total_evaporation_mean": "EVA",
    "total_precipitation_mean": "PRE",
    "total_evaporation_sum": "EVA_sum",
    "total_precipitation_sum": "PRE_sum",
    "lai_total_mean": "LAI",
    "VPD_mean": "VPD",
    "SMrz_mean": "SMrz",
    "SMrz_delta": "dSMrz",
    "ssrd_mean": "SSRD",
    "strd_mean": "STRD",
    "wind_speed_mean": "WIND",
    "event_onset_days": "ONS",
    "event_duration": "DUR",
    "event_intensity": "INT",
    "t_recover_to_baseline_abs_peak": "t_recover",
}
MECHANISM_LAYOUT_X = {
    "left": 0.10,
    "mid_left": 0.40,
    "mid_right": 0.56,
    "right": 0.86,
}
MECHANISM_LAYOUT_Y = {
    "TMP": 0.88,
    "STRD": 0.67,
    "EVA": 0.45,
    "SSRD": 0.22,
    "PRE": 0.06,
    "VPD": 0.88,
    "LAI": 0.45,
    "SMrz": 0.06,
    "t_recover": 0.45,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sem-dir", required=True, help="Directory containing *_sem_summary.txt and *_estimates.csv files.")
    parser.add_argument("--output-dir", default=None, help="Directory for overview outputs; defaults to sem-dir parent.")
    parser.add_argument(
        "--target-only-mediators",
        action="store_true",
        help="When drawing edges into the target, keep only mediator-to-target links and hide direct exogenous-to-target links.",
    )
    parser.add_argument(
        "--target-direct-min-abs",
        type=float,
        default=0.20,
        help="If --target-only-mediators is set, direct exogenous-to-target links are only kept when |estimate| reaches this threshold.",
    )
    return parser.parse_args()


def parse_summary_metrics(path: Path) -> dict[str, str]:
    metrics: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        metrics[key.strip()] = value.strip()
    return metrics


def derive_overview_metadata(sem_dir: Path) -> tuple[str, str]:
    if sem_dir.name in {"sem_by_biome", "by_biome"}:
        scope_name = sem_dir.parent.name
    else:
        scope_name = sem_dir.name
    scope_name = re.sub(r"_shap_sem_\d{8}$", "", scope_name)
    scope_name = re.sub(r"_sem_\d{8}$", "", scope_name)
    scope_name = re.sub(r"_\d{8}$", "", scope_name)
    if not scope_name:
        scope_name = "sem"
    title = f"{scope_name.replace('_', ' ').title()} SEM Path Diagrams"
    basename = f"{scope_name}_sem_path_diagrams_overview.png"
    return basename, title


def build_edge_records(estimates: pd.DataFrame) -> list[dict[str, object]]:
    required = {"lval", "op", "rval", "Estimate"}
    if not required.issubset(estimates.columns):
        raise ValueError(f"Estimates table missing required columns: {sorted(required - set(estimates.columns))}")

    subset = estimates[estimates["op"].astype(str) == "~"].copy()
    if subset.empty:
        return []
    subset["Estimate"] = pd.to_numeric(subset["Estimate"], errors="coerce")
    subset = subset[subset["Estimate"].notna()].copy()
    if "p-value" in subset.columns:
        subset["p-value"] = pd.to_numeric(subset["p-value"], errors="coerce")
    else:
        subset["p-value"] = pd.NA
    subset["abs_estimate"] = subset["Estimate"].abs()
    subset = subset.sort_values(["abs_estimate", "rval"], ascending=[False, True]).reset_index(drop=True)

    edges: list[dict[str, object]] = []
    for _, row in subset.iterrows():
        estimate = float(row["Estimate"])
        p_value = row.get("p-value", pd.NA)
        if pd.isna(p_value):
            label = f"{estimate:+.3f}"
        elif float(p_value) < 0.001:
            label = f"{estimate:+.3f}***"
        elif float(p_value) < 0.01:
            label = f"{estimate:+.3f}**"
        elif float(p_value) < 0.05:
            label = f"{estimate:+.3f}*"
        else:
            label = f"{estimate:+.3f}"
        edges.append(
            {
                "src": str(row["rval"]),
                "dst": str(row["lval"]),
                "estimate": estimate,
                "abs_estimate": abs(estimate),
                "label": label,
                "color": POSITIVE_COLOR if estimate >= 0 else NEGATIVE_COLOR,
            }
        )
    return edges


def filter_edges_for_target_mediators_only(
    edges: list[dict[str, object]],
    target: str,
    target_direct_min_abs: float = 0.20,
) -> list[dict[str, object]]:
    if not edges:
        return edges
    # A mediator/endogenous node is any non-target node that is itself explained by
    # another node somewhere in the SEM.
    mediator_nodes = {str(edge["dst"]) for edge in edges if str(edge["dst"]) != target}
    keep: list[dict[str, object]] = []
    for edge in edges:
        src = str(edge["src"])
        dst = str(edge["dst"])
        if dst != target:
            keep.append(edge)
            continue
        if src in mediator_nodes:
            keep.append(edge)
            continue
        if float(edge.get("abs_estimate", 0.0)) >= float(target_direct_min_abs):
            keep.append(edge)
    return keep


def build_layers(edges: list[dict[str, object]]) -> list[list[str]]:
    nodes: list[str] = []
    indegree: dict[str, int] = {}
    children: dict[str, list[str]] = {}
    for edge in edges:
        src = str(edge["src"])
        dst = str(edge["dst"])
        if src not in nodes:
            nodes.append(src)
        if dst not in nodes:
            nodes.append(dst)
        indegree.setdefault(src, 0)
        indegree.setdefault(dst, 0)
        children.setdefault(src, []).append(dst)
        indegree[dst] += 1
    layers: list[list[str]] = []
    remaining = set(nodes)
    current = [node for node in nodes if indegree.get(node, 0) == 0]
    while current:
        layers.append(current)
        next_nodes: list[str] = []
        for node in current:
            remaining.discard(node)
            for child in children.get(node, []):
                indegree[child] -= 1
                if indegree[child] == 0:
                    next_nodes.append(child)
        current = [node for node in nodes if node in next_nodes]
    if remaining:
        layers.append([node for node in nodes if node in remaining])
    return layers


def format_biome_title(metrics: dict[str, str]) -> str:
    biome = metrics.get("biome", "Unknown")
    rows = metrics.get("rows", "NA")
    r2 = metrics.get("target_equation_r2_holdout_split", "NA")
    try:
        r2_text = f"{float(r2):.3f}"
    except (TypeError, ValueError):
        r2_text = str(r2)
    return f"{biome}\nN={rows}, holdout R2={r2_text}"


def format_node_label(name: str) -> str:
    label = str(name)
    for prefix in ("recoverywin_", "prepeak_", "shock_"):
        if label.startswith(prefix):
            label = label[len(prefix) :]
            break
    return LABEL_MAP.get(label, label)


def build_mechanism_layout(nodes: list[str], target: str) -> dict[str, tuple[float, float]] | None:
    expected = {"PRE", "EVA", "TMP", "STRD", "SSRD", "VPD", "LAI", "SMrz", "t_recover"}
    simplified4_expected = {"PRE", "EVA", "TMP", "STRD", "SSRD", "VPD", "SMrz", "t_recover"}
    simplified5_expected = {"PRE", "EVA", "TMP", "STRD", "SSRD", "VPD", "WIND", "SMrz", "t_recover"}
    labels = {node: format_node_label(node) for node in nodes}
    label_values = set(labels.values())
    if format_node_label(target) != "t_recover":
        return None
    if label_values == simplified5_expected:
        positions: dict[str, tuple[float, float]] = {}
        custom = {
            "STRD": (0.08, 0.84),
            "SSRD": (0.08, 0.16),
            "PRE": (0.30, 0.16),
            "WIND": (0.30, 0.84),
            "TMP": (0.52, 0.84),
            "VPD": (0.52, 0.52),
            "EVA": (0.52, 0.16),
            "SMrz": (0.76, 0.16),
            "t_recover": (0.92, 0.50),
        }
        for node, short in labels.items():
            positions[node] = custom[short]
        return positions
    if label_values == simplified4_expected:
        positions: dict[str, tuple[float, float]] = {}
        custom = {
            "STRD": (0.10, 0.82),
            "SSRD": (0.10, 0.18),
            "PRE": (0.34, 0.18),
            "VPD": (0.34, 0.82),
            "TMP": (0.58, 0.82),
            "EVA": (0.58, 0.18),
            "SMrz": (0.78, 0.18),
            "t_recover": (0.92, 0.50),
        }
        for node, short in labels.items():
            positions[node] = custom[short]
        return positions
    if not {"VPD", "LAI", "SMrz", "t_recover"}.issubset(label_values):
        return None
    if not label_values.issubset(expected):
        return None

    positions: dict[str, tuple[float, float]] = {}
    for node, short in labels.items():
        if short in {"TMP", "STRD", "EVA", "SSRD", "PRE"}:
            positions[node] = (MECHANISM_LAYOUT_X["left"], MECHANISM_LAYOUT_Y[short])
        elif short == "VPD":
            positions[node] = (MECHANISM_LAYOUT_X["mid_left"], MECHANISM_LAYOUT_Y[short])
        elif short in {"LAI", "SMrz"}:
            positions[node] = (MECHANISM_LAYOUT_X["mid_right"], MECHANISM_LAYOUT_Y[short])
        elif short == "t_recover":
            positions[node] = (MECHANISM_LAYOUT_X["right"], MECHANISM_LAYOUT_Y[short])
    return positions


def get_connection_rad(src: str, dst: str) -> float:
    src_label = format_node_label(src)
    dst_label = format_node_label(dst)
    specific = {
        ("EVA", "t_recover"): -0.18,
        ("VPD", "t_recover"): 0.06,
        ("SMrz", "t_recover"): 0.10,
        ("LAI", "t_recover"): 0.00,
        ("TMP", "t_recover"): -0.08,
        ("PRE", "t_recover"): 0.05,
        ("SSRD", "t_recover"): -0.12,
        ("PRE", "EVA"): 0.00,
        ("VPD", "EVA"): 0.10,
        ("PRE", "SMrz"): -0.10,
        ("EVA", "SMrz"): 0.08,
        ("SMrz", "EVA"): 0.08,
        ("VPD", "SMrz"): -0.08,
        ("STRD", "TMP"): 0.08,
        ("SSRD", "TMP"): -0.08,
        ("TMP", "VPD"): 0.10,
        ("WIND", "VPD"): -0.10,
        ("VPD", "EVA"): 0.10,
        ("STRD", "LAI"): 0.10,
        ("SSRD", "LAI"): -0.08,
        ("SMrz", "LAI"): -0.06,
        ("VPD", "LAI"): 0.06,
        ("EVA", "VPD"): -0.10,
        ("STRD", "VPD"): 0.10,
        ("PRE", "SMrz"): 0.00,
        ("EVA", "SMrz"): -0.10,
        ("TMP", "SMrz"): 0.10,
    }
    if (src_label, dst_label) in specific:
        return specific[(src_label, dst_label)]
    return 0.0


def choose_connectionstyle(src: str, dst: str, src_pos: tuple[float, float], dst_pos: tuple[float, float]) -> str:
    rad = get_connection_rad(src, dst)
    if rad != 0.0:
        return f"arc3,rad={rad}"
    x1, y1 = src_pos
    x2, y2 = dst_pos
    x_span = abs(x2 - x1)
    y_span = abs(y2 - y1)
    if x_span >= 0.70 and y_span <= 0.12:
        return "arc3,rad=0.22"
    return "arc3,rad=0.0"


def compute_edge_label_position(
    src_pos: tuple[float, float],
    dst_pos: tuple[float, float],
    rad: float,
) -> tuple[float, float]:
    x1, y1 = src_pos
    x2, y2 = dst_pos
    mx = x1 + (x2 - x1) * 0.5
    my = y1 + (y2 - y1) * 0.5
    dx = x2 - x1
    dy = y2 - y1
    dist = (dx * dx + dy * dy) ** 0.5
    if dist == 0:
        return mx, my
    nx = -dy / dist
    ny = dx / dist
    offset = rad * dist * 0.55
    return mx + nx * offset, my + ny * offset


def get_edge_label_params(src: str, dst: str) -> tuple[float, float]:
    src_label = format_node_label(src)
    dst_label = format_node_label(dst)
    specific = {
        ("EVA", "t_recover"): (0.72, 1.00),
        ("VPD", "t_recover"): (0.66, 0.95),
        ("SMrz", "t_recover"): (0.66, 0.92),
        ("LAI", "t_recover"): (0.62, 0.88),
        ("TMP", "t_recover"): (0.58, 0.92),
        ("PRE", "t_recover"): (0.58, 0.86),
        ("SSRD", "t_recover"): (0.42, 0.96),
        ("PRE", "EVA"): (0.48, 0.92),
        ("VPD", "EVA"): (0.56, 0.95),
        ("PRE", "SMrz"): (0.64, 0.95),
        ("EVA", "SMrz"): (0.54, 0.92),
        ("SMrz", "EVA"): (0.58, 0.92),
        ("VPD", "SMrz"): (0.60, 0.92),
        ("STRD", "TMP"): (0.52, 0.92),
        ("SSRD", "TMP"): (0.46, 0.94),
        ("TMP", "VPD"): (0.48, 0.95),
        ("WIND", "VPD"): (0.55, 0.94),
        ("VPD", "EVA"): (0.52, 0.92),
        ("STRD", "LAI"): (0.40, 0.90),
        ("SSRD", "LAI"): (0.34, 0.92),
        ("SMrz", "LAI"): (0.54, 0.90),
        ("VPD", "LAI"): (0.44, 0.92),
    }
    return specific.get((src_label, dst_label), (0.50, 1.00))


def compute_edge_label_position_for_nodes(
    src: str,
    dst: str,
    src_pos: tuple[float, float],
    dst_pos: tuple[float, float],
) -> tuple[float, float]:
    rad = get_connection_rad(src, dst)
    t, offset_scale = get_edge_label_params(src, dst)
    x1, y1 = src_pos
    x2, y2 = dst_pos
    dx = x2 - x1
    dy = y2 - y1
    dist = (dx * dx + dy * dy) ** 0.5
    if dist == 0:
        return x1, y1
    nx = -dy / dist
    ny = dx / dist
    control_x = x1 + dx * 0.5 + nx * (rad * dist)
    control_y = y1 + dy * 0.5 + ny * (rad * dist)
    omt = 1.0 - t
    curve_x = omt * omt * x1 + 2.0 * omt * t * control_x + t * t * x2
    curve_y = omt * omt * y1 + 2.0 * omt * t * control_y + t * t * y2
    label_offset = rad * dist * 0.22 * offset_scale
    return curve_x + nx * label_offset, curve_y + ny * label_offset


def format_edge_label(label: str) -> str:
    match = re.fullmatch(r"([+-]?\d*\.?\d+)(\*+)?", str(label))
    if not match:
        return str(label)
    value, stars = match.groups()
    if stars:
        return f"{value}\n{stars}"
    return value


def compute_edge_linewidth(abs_estimate: float, max_abs_estimate: float) -> float:
    if max_abs_estimate <= 0:
        return 1.6
    ratio = max(0.0, min(1.0, float(abs_estimate) / float(max_abs_estimate)))
    return 1.4 + 2.0 * ratio


def add_sem_legend(ax: plt.Axes) -> None:
    handles = [
        Line2D([0], [0], color=POSITIVE_COLOR, lw=2.6, label="Positive effect"),
        Line2D([0], [0], color=NEGATIVE_COLOR, lw=2.6, label="Negative effect"),
    ]
    ax.legend(
        handles=handles,
        loc="lower right",
        bbox_to_anchor=(0.99, 0.01),
        frameon=False,
        fontsize=8.5,
        title="Edges",
        title_fontsize=9,
    )


def draw_path_diagram(ax: plt.Axes, edges: list[dict[str, object]], metrics: dict[str, str], target: str) -> None:
    ax.set_axis_off()
    if not edges:
        ax.text(0.5, 0.5, "No SEM paths", ha="center", va="center", fontsize=11)
        return

    nodes = []
    for edge in edges:
        for node in (str(edge["src"]), str(edge["dst"])):
            if node not in nodes:
                nodes.append(node)
    positions = build_mechanism_layout(nodes, target)
    if positions is None:
        layers = build_layers(edges)
        positions = {}
        for x_idx, layer in enumerate(layers):
            count = len(layer)
            x = 0.12 if len(layers) == 1 else 0.10 + (0.80 * x_idx / max(1, len(layers) - 1))
            for y_idx, node in enumerate(layer):
                y = 0.5 if count == 1 else 0.90 - (0.80 * y_idx / max(1, count - 1))
                positions[node] = (x, y)

    max_abs_estimate = max((float(edge["abs_estimate"]) for edge in edges), default=0.0)
    for edge in edges:
        src = str(edge["src"])
        dst = str(edge["dst"])
        x1, y1 = positions[src]
        x2, y2 = positions[dst]
        connectionstyle = choose_connectionstyle(src, dst, (x1, y1), (x2, y2))
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="->",
                color=str(edge["color"]),
                lw=compute_edge_linewidth(float(edge["abs_estimate"]), max_abs_estimate),
                shrinkA=0,
                shrinkB=0,
                connectionstyle=connectionstyle,
            ),
        )
        label_x, label_y = compute_edge_label_position_for_nodes(src, dst, (x1, y1), (x2, y2))
        ax.text(
            label_x,
            label_y,
            format_edge_label(str(edge["label"])),
            fontsize=8.8,
            color=str(edge["color"]),
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.14", facecolor="white", edgecolor="none", alpha=0.92),
        )
    for node, (x, y) in positions.items():
        is_target = node == target
        has_incoming = any(str(edge["dst"]) == node for edge in edges)
        if is_target:
            facecolor = TARGET_FACE
            edgecolor = TARGET_EDGE
        elif has_incoming:
            facecolor = "#f8edb8"
            edgecolor = "#9b7a08"
        else:
            facecolor = PREDICTOR_FACE
            edgecolor = PREDICTOR_EDGE
        ax.text(
            x,
            y,
            format_node_label(node),
            ha="center",
            va="center",
            fontsize=NODE_FONTSIZE,
            bbox=dict(boxstyle="round,pad=0.26", facecolor=facecolor, edgecolor=edgecolor, linewidth=1.2),
        )
    ax.text(0.5, 1.02, format_biome_title(metrics), ha="center", va="bottom", fontsize=TITLE_FONTSIZE, transform=ax.transAxes)
    add_sem_legend(ax)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def iter_sem_triplets(sem_dir: Path) -> Iterable[tuple[Path, Path, Path]]:
    for summary_path in sorted(sem_dir.glob("*_sem_summary.txt")):
        prefix = summary_path.name.replace("_sem_summary.txt", "")
        estimates_path = sem_dir / f"{prefix}_estimates.csv"
        spec_path = sem_dir / f"{prefix}_model_spec.txt"
        if estimates_path.exists() and spec_path.exists():
            yield summary_path, estimates_path, spec_path


def main() -> None:
    args = parse_args()
    sem_dir = Path(args.sem_dir)
    output_dir = Path(args.output_dir) if args.output_dir else sem_dir.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    panel_records: list[tuple[str, list[dict[str, object]], dict[str, str], str, Path]] = []
    for summary_path, estimates_path, spec_path in iter_sem_triplets(sem_dir):
        metrics = parse_summary_metrics(summary_path)
        estimates = pd.read_csv(estimates_path)
        target = metrics.get("target", "t_recover_to_baseline_abs_peak")
        edges = build_edge_records(estimates)
        if args.target_only_mediators:
            edges = filter_edges_for_target_mediators_only(
                edges,
                target=target,
                target_direct_min_abs=args.target_direct_min_abs,
            )
        prefix = summary_path.name.replace("_sem_summary.txt", "")
        single_output = sem_dir / f"{prefix}_path_diagram.png"

        edge_layers = build_layers(edges)
        max_nodes_in_layer = max((len(layer) for layer in edge_layers), default=1)
        fig_height = max(4.6, 1.35 * max_nodes_in_layer + 0.75 * max(1, len(edge_layers) - 1))
        fig, ax = plt.subplots(figsize=(9.2, fig_height))
        draw_path_diagram(ax, edges=edges, metrics=metrics, target=target)
        fig.tight_layout()
        fig.savefig(single_output, dpi=220, bbox_inches="tight")
        plt.close(fig)

        panel_records.append((metrics.get("biome", prefix), edges, metrics, target, single_output))

    if not panel_records:
        raise FileNotFoundError(f"No SEM summary bundles found in {sem_dir}")

    panel_records.sort(key=lambda item: item[0])
    ncols = 2
    nrows = (len(panel_records) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(16, max(5.2, 4.8 * nrows)))
    axes_flat = list(axes.flat) if hasattr(axes, "flat") else [axes]
    for ax, (_, edges, metrics, target, _) in zip(axes_flat, panel_records):
        draw_path_diagram(ax, edges=edges, metrics=metrics, target=target)
    for ax in axes_flat[len(panel_records) :]:
        ax.set_axis_off()
    overview_basename, overview_title = derive_overview_metadata(sem_dir)
    fig.suptitle(overview_title, fontsize=SUPTITLE_FONTSIZE, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    overview_path = output_dir / overview_basename
    fig.savefig(overview_path, dpi=220, bbox_inches="tight")
    plt.close(fig)

    print(f"[DONE] single-panel diagrams saved under {sem_dir}")
    print(f"[DONE] overview diagram saved to {overview_path}")


if __name__ == "__main__":
    main()
