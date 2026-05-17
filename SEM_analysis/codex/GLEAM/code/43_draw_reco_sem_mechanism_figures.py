#!/usr/bin/env python
"""Draw RECO SEM mechanism figures in the custom black-background style."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


POS_COLOR = "#ff9440"
NEG_COLOR = "#3d74d8"
BG_COLOR = "#000000"
TEXT_POS = "#ff5f7f"
TEXT_NEG = "#3d74d8"
NODE_STYLES = {
    "TMP": ("#ffe89a", "#b08a00"),
    "STRD": ("#f6b8c5", "#b66b7c"),
    "SSRD": ("#efb1bc", "#b56a77"),
    "Wind": ("#8edfe1", "#3e9ca0"),
    "VPD": ("#f7c79d", "#bc8c60"),
    "EVA": ("#9ed9d7", "#5ca7a4"),
    "PRE": ("#43b8d7", "#1f7f96"),
    "SMrz": ("#8ea7db", "#5773a7"),
    "RECO-RT": ("#bfe3a2", "#7da45a"),
}

LAYOUT = {
    "STRD": (0.12, 0.12),
    "TMP": (0.12, 0.46),
    "SSRD": (0.48, 0.82),
    "Wind": (0.48, 0.06),
    "VPD": (0.46, 0.26),
    "EVA": (0.78, 0.26),
    "PRE": (0.94, 0.46),
    "SMrz": (0.78, 0.60),
    "RECO-RT": (0.50, 0.60),
}

LABEL_OVERRIDES = {
    ("STRD", "TMP"): {"t": 0.26, "nx": -0.032, "ny": 0.0, "rotation": 90},
    ("SSRD", "TMP"): {"t": 0.52, "nx": 0.0, "ny": 0.036, "rotation": 32},
    ("TMP", "VPD"): {"t": 0.54, "nx": 0.0, "ny": -0.036, "rotation": -24},
    ("Wind", "VPD"): {"t": 0.32, "nx": -0.016, "ny": 0.008, "rotation": 82},
    ("VPD", "EVA"): {"t": 0.50, "nx": 0.0, "ny": -0.032, "rotation": 0},
    ("PRE", "EVA"): {"t": 0.60, "nx": 0.028, "ny": -0.026, "rotation": -45},
    ("EVA", "SMrz"): {"t": 0.52, "nx": 0.026, "ny": 0.0, "rotation": 90},
    ("PRE", "SMrz"): {"t": 0.56, "nx": 0.02, "ny": 0.03, "rotation": -36},
    ("SSRD", "RECO-RT"): {"t": 0.58, "nx": 0.0, "ny": 0.036, "rotation": 90},
    ("TMP", "RECO-RT"): {"t": 0.55, "nx": 0.0, "ny": 0.03, "rotation": 16},
    ("SMrz", "RECO-RT"): {"t": 0.48, "nx": 0.0, "ny": -0.03, "rotation": 0},
    ("PRE", "RECO-RT"): {"t": 0.48, "nx": 0.012, "ny": -0.032, "rotation": -17},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepeak-csv", required=True)
    parser.add_argument("--recovery-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def short_name(raw: str, target_label: str = "RECO-RT") -> str:
    text = str(raw)
    for prefix in ("prepeak_", "recoverywin_"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    mapping = {
        "temperature_2m_mean": "TMP",
        "strd_mean": "STRD",
        "ssrd_mean": "SSRD",
        "wind_speed_mean": "Wind",
        "VPD_mean": "VPD",
        "total_evaporation_mean": "EVA",
        "total_precipitation_mean": "PRE",
        "SMrz_mean": "SMrz",
        "t_recover_to_baseline_abs_peak": target_label,
    }
    return mapping.get(text, text)


def add_node(ax: plt.Axes, label: str, x: float, y: float) -> None:
    face, edge = NODE_STYLES[label]
    box = FancyBboxPatch(
        (x - 0.055, y - 0.035),
        0.11,
        0.07,
        boxstyle="round,pad=0.012,rounding_size=0.008",
        linewidth=1.6,
        edgecolor=edge,
        facecolor=face,
        zorder=3,
    )
    ax.add_patch(box)
    txt = ax.text(
        x,
        y,
        label,
        ha="center",
        va="center",
        fontsize=20,
        color="black",
        zorder=4,
    )
    txt.set_path_effects([pe.withStroke(linewidth=3, foreground=face, alpha=0.15)])


def _label_position(src: str, dst: str) -> tuple[float, float, float]:
    x1, y1 = LAYOUT[src]
    x2, y2 = LAYOUT[dst]
    cfg = LABEL_OVERRIDES.get((src, dst), {})
    t = cfg.get("t", 0.5)
    mx = x1 + (x2 - x1) * t
    my = y1 + (y2 - y1) * t
    mx += cfg.get("nx", 0.0)
    my += cfg.get("ny", 0.0)
    rotation = cfg.get("rotation", 0.0)
    return mx, my, rotation


def draw_edge(ax: plt.Axes, src: str, dst: str, estimate: float, significance: str) -> None:
    x1, y1 = LAYOUT[src]
    x2, y2 = LAYOUT[dst]
    color = POS_COLOR if estimate >= 0 else NEG_COLOR
    text_color = TEXT_POS if estimate >= 0 else TEXT_NEG
    lw = 2.6 + 7.5 * min(abs(estimate), 1.0)
    arrow = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle="->",
        mutation_scale=26,
        linewidth=lw,
        color=color,
        shrinkA=26,
        shrinkB=28,
        zorder=2,
        joinstyle="round",
        capstyle="round",
    )
    arrow.set_path_effects(
        [
            pe.Stroke(linewidth=lw + 2.8, foreground="#ffd65c" if estimate >= 0 else "#1e4086", alpha=0.9),
            pe.Normal(),
        ]
    )
    ax.add_patch(arrow)

    label = f"{estimate:.3f}{significance}"
    mx, my, angle = _label_position(src, dst)
    ax.text(
        mx,
        my,
        label,
        color=text_color,
        fontsize=16,
        rotation=angle,
        rotation_mode="anchor",
        ha="center",
        va="center",
        zorder=5,
        bbox={
            "boxstyle": "round,pad=0.18",
            "facecolor": BG_COLOR,
            "edgecolor": "none",
            "alpha": 0.55,
        },
        clip_on=False,
    )


def plot_biome(df: pd.DataFrame, biome: str, output: Path) -> None:
    subset = df[df["biome"] == biome].copy()
    fig, ax = plt.subplots(figsize=(16, 10), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(-0.06, 1.06)
    ax.set_ylim(-0.10, 1.04)
    ax.axis("off")

    for _, row in subset.iterrows():
        src = short_name(row["from"])
        dst = short_name(row["to"])
        if src not in LAYOUT or dst not in LAYOUT:
            continue
        draw_edge(ax, src, dst, float(row["estimate"]), str(row["significance"] or ""))

    for label, (x, y) in LAYOUT.items():
        add_node(ax, label, x, y)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, facecolor=BG_COLOR, bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    keep = ["biome", "from", "to", "estimate", "significance"]
    return df.loc[:, keep].copy()


def main() -> None:
    args = parse_args()
    outdir = Path(args.output_dir)
    pre_df = load_csv(Path(args.prepeak_csv))
    rec_df = load_csv(Path(args.recovery_csv))
    biomes = sorted(set(pre_df["biome"]).union(set(rec_df["biome"])))
    for biome in biomes:
        stem = biome.lower()
        plot_biome(pre_df, biome, outdir / f"{stem}_prepeak.png")
        plot_biome(rec_df, biome, outdir / f"{stem}_recovery.png")


if __name__ == "__main__":
    main()
