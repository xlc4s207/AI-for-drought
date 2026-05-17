#!/usr/bin/env python3
"""Compare orthogonal-decomposition SHAP results with OPGD Geodetector."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


WORK_DIR = Path(__file__).resolve().parent
GLEAM = WORK_DIR.parents[1]
ORTHO = GLEAM / "plots2/prepeak_shap_nomulticollinearity/orthogonal_decomposition"
OUT = WORK_DIR / "orthogonal_comparison"

BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
METRICS = ["GPP", "RECO"]
ROW_ORDER = [(metric, biome) for metric in METRICS for biome in BIOMES]

ORTHO_FEATURE_ORDER = [
    "SSRD_z",
    "EVA_resid_after_SSRD_Pre_VPD",
    "TMP_resid_after_SSRD_STRD",
    "VPD_resid_after_SSRD_TMP_Wind",
    "SMrz_resid_after_Pre_EVA",
    "Pre_z",
    "STRD_resid_after_SSRD",
    "Wind_z",
    "Duration_z",
    "Intensity_z",
]

ORTHO_LABELS = {
    "SSRD_z": "SSRD",
    "Pre_z": "PRE",
    "Duration_z": "Duration",
    "Intensity_z": "Intensity",
    "Wind_z": "WIND",
    "STRD_resid_after_SSRD": "STRD_resid",
    "TMP_resid_after_SSRD_STRD": "TMP_resid",
    "VPD_resid_after_SSRD_TMP_Wind": "VPD_resid",
    "EVA_resid_after_SSRD_Pre_VPD": "EVA_resid",
    "SMrz_resid_after_Pre_EVA": "SMrz_resid",
}

RAW_FEATURE_BY_ORTHO = {
    "SSRD_z": "prepeak_ssrd_mean",
    "EVA_resid_after_SSRD_Pre_VPD": "prepeak_total_evaporation_mean",
    "TMP_resid_after_SSRD_STRD": "prepeak_temperature_2m_mean",
    "VPD_resid_after_SSRD_TMP_Wind": "prepeak_VPD_mean",
    "SMrz_resid_after_Pre_EVA": "prepeak_SMrz_mean",
    "Pre_z": "prepeak_total_precipitation_mean",
    "STRD_resid_after_SSRD": "prepeak_strd_mean",
    "Wind_z": "prepeak_wind_speed_mean",
    "Duration_z": "event_duration",
    "Intensity_z": "event_intensity",
}

RAW_LABEL_BY_ORTHO = {
    "SSRD_z": "SSRD",
    "EVA_resid_after_SSRD_Pre_VPD": "|EVA|",
    "TMP_resid_after_SSRD_STRD": "TMP",
    "VPD_resid_after_SSRD_TMP_Wind": "VPD",
    "SMrz_resid_after_Pre_EVA": "SMrz",
    "Pre_z": "PRE",
    "STRD_resid_after_SSRD": "STRD",
    "Wind_z": "WIND",
    "Duration_z": "Duration",
    "Intensity_z": "Intensity",
}

RELIABILITY_TO_VALUE = {"Low": 0, "Medium": 1, "High": 2}
TOP3_NONE = 0
TOP3_ORTHO_ONLY = 1
TOP3_OPGD_ONLY = 2
TOP3_BOTH = 3


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
            "font.size": 8,
            "axes.titlesize": 10,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def load_orthogonal_shap() -> pd.DataFrame:
    rows = []
    for metric, biome in ROW_ORDER:
        imp = pd.read_csv(ORTHO / metric / biome / "feature_importance.csv")
        for row in imp.itertuples(index=False):
            raw_feature = RAW_FEATURE_BY_ORTHO[row.feature]
            rows.append(
                {
                    "metric": metric,
                    "biome": biome,
                    "orthogonal_feature": row.feature,
                    "raw_feature": raw_feature,
                    "label": ORTHO_LABELS[row.feature],
                    "raw_label": RAW_LABEL_BY_ORTHO[row.feature],
                    "mean_abs_shap": float(row.mean_abs_shap),
                    "percent": float(row.percent),
                    "rank": int(row.rank),
                }
            )
    return pd.DataFrame(rows)


def load_opgd() -> pd.DataFrame:
    return pd.read_csv(WORK_DIR / "opgd_factor_q.csv")


def load_reliability() -> pd.DataFrame:
    return pd.read_csv(WORK_DIR / "reliability" / "reliability_score.csv")


def row_labels() -> list[str]:
    return [f"{metric} {biome}" for metric, biome in ROW_ORDER]


def matrix_from_orthogonal(table: pd.DataFrame, value_col: str) -> np.ndarray:
    matrix = np.full((len(ROW_ORDER), len(ORTHO_FEATURE_ORDER)), np.nan)
    lookup = {
        (row.metric, row.biome, row.orthogonal_feature): getattr(row, value_col)
        for row in table.itertuples(index=False)
    }
    for i, (metric, biome) in enumerate(ROW_ORDER):
        for j, feature in enumerate(ORTHO_FEATURE_ORDER):
            matrix[i, j] = lookup.get((metric, biome, feature), np.nan)
    return matrix


def opgd_matrix(opgd: pd.DataFrame) -> np.ndarray:
    matrix = np.full((len(ROW_ORDER), len(ORTHO_FEATURE_ORDER)), np.nan)
    lookup = {(row.metric, row.biome, row.feature): row.q for row in opgd.itertuples(index=False)}
    for i, (metric, biome) in enumerate(ROW_ORDER):
        for j, feature in enumerate(ORTHO_FEATURE_ORDER):
            matrix[i, j] = lookup.get((metric, biome, RAW_FEATURE_BY_ORTHO[feature]), np.nan)
    return matrix


def reliability_matrix(reliability: pd.DataFrame) -> np.ndarray:
    matrix = np.full((len(ROW_ORDER), len(ORTHO_FEATURE_ORDER)), np.nan)
    lookup = {
        (row.metric, row.biome, row.feature): RELIABILITY_TO_VALUE.get(row.reliability_grade, np.nan)
        for row in reliability.itertuples(index=False)
    }
    for i, (metric, biome) in enumerate(ROW_ORDER):
        for j, feature in enumerate(ORTHO_FEATURE_ORDER):
            matrix[i, j] = lookup.get((metric, biome, RAW_FEATURE_BY_ORTHO[feature]), np.nan)
    return matrix


def top3_features(group: pd.DataFrame, feature_col: str, value_col: str) -> set[str]:
    return set(group.sort_values(value_col, ascending=False).head(3)[feature_col])


def top3_flags(ortho: pd.DataFrame, opgd: pd.DataFrame) -> np.ndarray:
    flags = np.zeros((len(ROW_ORDER), len(ORTHO_FEATURE_ORDER)), dtype=int)
    for i, (metric, biome) in enumerate(ROW_ORDER):
        o_group = ortho[(ortho["metric"] == metric) & (ortho["biome"] == biome)]
        g_group = opgd[(opgd["metric"] == metric) & (opgd["biome"] == biome)]
        ortho_top = top3_features(o_group, "orthogonal_feature", "mean_abs_shap")
        opgd_top_raw = top3_features(g_group, "feature", "q")
        for j, feature in enumerate(ORTHO_FEATURE_ORDER):
            in_ortho = feature in ortho_top
            in_opgd = RAW_FEATURE_BY_ORTHO[feature] in opgd_top_raw
            if in_ortho and in_opgd:
                flags[i, j] = TOP3_BOTH
            elif in_ortho:
                flags[i, j] = TOP3_ORTHO_ONLY
            elif in_opgd:
                flags[i, j] = TOP3_OPGD_ONLY
    return flags


def setup_heatmap_axis(ax: plt.Axes, title: str, show_y: bool) -> None:
    ax.set_title(title, fontweight="bold", pad=8)
    ax.set_xticks(np.arange(len(ORTHO_FEATURE_ORDER)))
    ax.set_xticklabels([ORTHO_LABELS[f] for f in ORTHO_FEATURE_ORDER], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(ROW_ORDER)))
    ax.set_yticklabels(row_labels() if show_y else [])
    ax.tick_params(length=0)
    ax.set_xticks(np.arange(-0.5, len(ORTHO_FEATURE_ORDER), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(ROW_ORDER), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.85)
    for spine in ax.spines.values():
        spine.set_visible(False)


def overlay_top3_markers(ax: plt.Axes, flags: np.ndarray) -> None:
    for i in range(flags.shape[0]):
        for j in range(flags.shape[1]):
            flag = flags[i, j]
            if flag == TOP3_BOTH:
                ax.scatter(j, i, s=34, marker="o", facecolor="black", edgecolor="black", linewidth=0.7)
            elif flag == TOP3_ORTHO_ONLY:
                ax.scatter(j, i, s=34, marker="o", facecolor="white", edgecolor="#0072B2", linewidth=1.15)
            elif flag == TOP3_OPGD_ONLY:
                ax.scatter(j, i, s=34, marker="s", facecolor="white", edgecolor="#D55E00", linewidth=1.15)


def plot_reliability_matrix() -> Path:
    configure_style()
    OUT.mkdir(parents=True, exist_ok=True)
    ortho = load_orthogonal_shap()
    opgd = load_opgd()
    reliability = load_reliability()

    shap_mat = matrix_from_orthogonal(ortho, "mean_abs_shap")
    q_mat = opgd_matrix(opgd)
    rel_mat = reliability_matrix(reliability)
    flags = top3_flags(ortho, opgd)

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(15.2, 5.9),
        gridspec_kw={"width_ratios": [1.03, 1.0, 1.07], "wspace": 0.16},
    )
    cmap = plt.get_cmap("RdYlGn_r")
    im0 = axes[0].imshow(shap_mat, aspect="auto", cmap=cmap)
    setup_heatmap_axis(axes[0], "A  Orthogonal SHAP mean |value|", True)
    cb0 = fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.02)
    cb0.set_label("mean |SHAP|")

    im1 = axes[1].imshow(q_mat, aspect="auto", cmap=cmap, vmin=0, vmax=np.nanmax(q_mat))
    setup_heatmap_axis(axes[1], "B  OPGD q for raw counterpart", False)
    cb1 = fig.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.02)
    cb1.set_label("q")

    rel_cmap = ListedColormap(["#E5E5E5", "#9ECAE1", "#08519C"])
    rel_norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], rel_cmap.N)
    im2 = axes[2].imshow(rel_mat, aspect="auto", cmap=rel_cmap, norm=rel_norm)
    setup_heatmap_axis(axes[2], "C  Reliability and Top3 overlap", False)
    overlay_top3_markers(axes[2], flags)
    cb2 = fig.colorbar(im2, ax=axes[2], fraction=0.046, pad=0.02, ticks=[0, 1, 2])
    cb2.ax.set_yticklabels(["Low", "Medium", "High"])
    cb2.set_label("raw-feature reliability")

    handles = [
        Line2D([0], [0], marker="o", color="black", markerfacecolor="black", linestyle="None", markersize=5, label="Orthogonal SHAP Top3 + OPGD Top3"),
        Line2D([0], [0], marker="o", color="#0072B2", markerfacecolor="white", linestyle="None", markersize=5, label="Orthogonal SHAP Top3 only"),
        Line2D([0], [0], marker="s", color="#D55E00", markerfacecolor="white", linestyle="None", markersize=5, label="OPGD Top3 only"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.55, -0.02))
    fig.suptitle("Orthogonal SHAP contribution vs. OPGD spatial stratified heterogeneity", y=1.02, fontweight="bold")
    out_png = OUT / "orthogonal_shap_opgd_reliability_matrix.png"
    out_pdf = OUT / "orthogonal_shap_opgd_reliability_matrix.pdf"
    fig.savefig(out_png, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    export_consistency_tables(ortho, opgd, reliability, flags)
    return out_png


def export_consistency_tables(ortho: pd.DataFrame, opgd: pd.DataFrame, reliability: pd.DataFrame, flags: np.ndarray) -> None:
    rows = []
    for i, (metric, biome) in enumerate(ROW_ORDER):
        o_group = ortho[(ortho.metric == metric) & (ortho.biome == biome)].copy()
        g_group = opgd[(opgd.metric == metric) & (opgd.biome == biome)].copy()
        o_top = o_group.sort_values("mean_abs_shap", ascending=False).head(3)
        g_top = g_group.sort_values("q", ascending=False).head(3)
        overlap = []
        for feature in ORTHO_FEATURE_ORDER:
            if flags[i, ORTHO_FEATURE_ORDER.index(feature)] == TOP3_BOTH:
                overlap.append(RAW_LABEL_BY_ORTHO[feature])
        # Compare ranks over the ten shared raw counterparts.
        rank_rows = []
        for feature in ORTHO_FEATURE_ORDER:
            raw = RAW_FEATURE_BY_ORTHO[feature]
            ortho_rank = int(o_group.loc[o_group.orthogonal_feature == feature, "rank"].iloc[0])
            ranked_q = g_group.sort_values("q", ascending=False).reset_index(drop=True)
            match = ranked_q.query("feature == @raw")
            if match.empty:
                continue
            q_rank = int(match.index[0] + 1)
            rank_rows.append((ortho_rank, q_rank))
        x = np.asarray([r[0] for r in rank_rows], dtype=float)
        y = np.asarray([r[1] for r in rank_rows], dtype=float)
        corr = float(np.corrcoef(x, y)[0, 1]) if np.nanstd(x) > 0 and np.nanstd(y) > 0 else np.nan
        rows.append(
            {
                "metric": metric,
                "biome": biome,
                "orthogonal_top3": ", ".join(o_top["label"].tolist()),
                "opgd_top3_raw": ", ".join(g_top["label"].tolist()),
                "top3_overlap_count": len(overlap),
                "top3_overlap_raw_labels": ", ".join(overlap),
                "rank_correlation_on_shared10": corr,
            }
        )
    pd.DataFrame(rows).to_csv(OUT / "orthogonal_shap_opgd_top3_consistency.csv", index=False)

    detail_rows = []
    rel_lookup = {
        (row.metric, row.biome, row.feature): row.reliability_grade
        for row in reliability.itertuples(index=False)
    }
    q_lookup = {(row.metric, row.biome, row.feature): row.q for row in opgd.itertuples(index=False)}
    for row in ortho.itertuples(index=False):
        detail_rows.append(
            {
                "metric": row.metric,
                "biome": row.biome,
                "orthogonal_feature": row.orthogonal_feature,
                "orthogonal_label": row.label,
                "raw_counterpart": row.raw_feature,
                "raw_label": row.raw_label,
                "mean_abs_shap": row.mean_abs_shap,
                "shap_percent": row.percent,
                "orthogonal_shap_rank": row.rank,
                "opgd_q": q_lookup.get((row.metric, row.biome, row.raw_feature), np.nan),
                "opgd_reliability": rel_lookup.get((row.metric, row.biome, row.raw_feature), ""),
            }
        )
    pd.DataFrame(detail_rows).to_csv(OUT / "orthogonal_shap_opgd_feature_comparison.csv", index=False)


def robust_limits(values: np.ndarray, low: float = 0.01, high: float = 0.99) -> tuple[float, float]:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return -1.0, 1.0
    lo, hi = np.nanquantile(vals, [low, high])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        med = float(np.nanmedian(vals))
        return med - 1.0, med + 1.0
    pad = 0.04 * (hi - lo)
    return float(lo - pad), float(hi + pad)


def binned_trend(x: np.ndarray, y: np.ndarray, bins: int = 30) -> tuple[np.ndarray, np.ndarray]:
    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]
    y = y[ok]
    if len(x) < 30:
        order = np.argsort(x)
        return x[order], y[order]
    edges = np.unique(np.nanquantile(x, np.linspace(0, 1, bins + 1)))
    xs = []
    ys = []
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (x >= left) & (x <= right if right == edges[-1] else x < right)
        if mask.sum() >= 8:
            xs.append(float(np.nanmedian(x[mask])))
            ys.append(float(np.nanmedian(y[mask])))
    return np.asarray(xs), np.asarray(ys)


def plot_dependence_panel(ax: plt.Axes, dep: pd.DataFrame, feature: str, metric: str, biome: str, opgd: pd.DataFrame, reliability: pd.DataFrame, is_ortho_top3: bool, is_opgd_top3: bool) -> None:
    x = pd.to_numeric(dep[f"feature__{feature}"], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(dep[f"shap__{feature}"], errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]
    y = y[ok]
    if len(x) > 0:
        xlo, xhi = np.nanquantile(x, [0.01, 0.99])
        ylo, yhi = np.nanquantile(y, [0.005, 0.995])
        keep = (x >= xlo) & (x <= xhi) & (y >= ylo) & (y <= yhi)
        x = x[keep]
        y = y[keep]
    ax.scatter(x, y, s=5, alpha=0.20, color="#315f86", linewidths=0, rasterized=True)
    tx, ty = binned_trend(x, y)
    if len(tx) > 1:
        ax.plot(tx, ty, color="#bf3b3b", lw=1.65, label="orthogonal SHAP trend")
    ax.axhline(0, color="#757575", lw=0.75, ls="--", alpha=0.85)
    ax.set_xlim(*robust_limits(x))
    ax.set_ylim(*robust_limits(y, 0.005, 0.995))

    raw = RAW_FEATURE_BY_ORTHO[feature]
    q_row = opgd[(opgd.metric == metric) & (opgd.biome == biome) & (opgd.feature == raw)]
    rel_row = reliability[(reliability.metric == metric) & (reliability.biome == biome) & (reliability.feature == raw)]
    q = float(q_row["q"].iloc[0]) if not q_row.empty else np.nan
    rel = str(rel_row["reliability_grade"].iloc[0]) if not rel_row.empty else "NA"
    mark = ""
    if is_ortho_top3 and is_opgd_top3:
        mark = " | Top3 both"
    elif is_ortho_top3:
        mark = " | SHAP Top3"
    elif is_opgd_top3:
        mark = " | OPGD Top3"
    ax.set_title(f"{metric} | q={q:.3f} | {rel}{mark}", fontsize=8.4, pad=2.5)
    ax.set_xlabel(ORTHO_LABELS[feature], fontsize=7.6)
    ax.set_ylabel("SHAP value", fontsize=7.6)
    ax.tick_params(labelsize=6.8, length=2.2)
    ax.grid(alpha=0.14, ls="--", lw=0.55)
    color = {"High": "#08519C", "Medium": "#4292C6", "Low": "#A6A6A6"}.get(rel, "#A6A6A6")
    ax.text(
        0.02,
        0.95,
        RAW_LABEL_BY_ORTHO[feature],
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=7.3,
        color=color,
        fontweight="bold",
        bbox={"facecolor": "white", "edgecolor": color, "alpha": 0.85, "boxstyle": "round,pad=0.2", "linewidth": 0.6},
    )


def plot_overlay_style_by_biome() -> list[Path]:
    configure_style()
    opgd = load_opgd()
    reliability = load_reliability()
    ortho = load_orthogonal_shap()
    outputs = []
    out_dir = OUT / "overlay_style_by_biome"
    out_dir.mkdir(parents=True, exist_ok=True)
    for biome in BIOMES:
        fig, axes = plt.subplots(len(ORTHO_FEATURE_ORDER), 2, figsize=(12.8, 24.0))
        dep_cache = {}
        top_cache = {}
        for metric in METRICS:
            dep_cache[metric] = pd.read_parquet(ORTHO / metric / biome / "dependence_plot_data.parquet")
            o_group = ortho[(ortho.metric == metric) & (ortho.biome == biome)]
            g_group = opgd[(opgd.metric == metric) & (opgd.biome == biome)]
            top_cache[metric] = (
                top3_features(o_group, "orthogonal_feature", "mean_abs_shap"),
                top3_features(g_group, "feature", "q"),
            )
        for i, feature in enumerate(ORTHO_FEATURE_ORDER):
            for j, metric in enumerate(METRICS):
                ortho_top, opgd_top = top_cache[metric]
                plot_dependence_panel(
                    axes[i, j],
                    dep_cache[metric],
                    feature,
                    metric,
                    biome,
                    opgd,
                    reliability,
                    feature in ortho_top,
                    RAW_FEATURE_BY_ORTHO[feature] in opgd_top,
                )
            axes[i, 0].text(
                -0.30,
                0.5,
                ORTHO_LABELS[feature],
                transform=axes[i, 0].transAxes,
                ha="right",
                va="center",
                fontsize=9.5,
                fontweight="bold",
            )
        handles = [
            Line2D([0], [0], color="#bf3b3b", lw=1.7, label="Orthogonal SHAP trend"),
            Line2D([0], [0], marker="s", color="#08519C", markerfacecolor="#08519C", linestyle="None", markersize=6, label="High OPGD reliability"),
            Line2D([0], [0], marker="s", color="#4292C6", markerfacecolor="#4292C6", linestyle="None", markersize=6, label="Medium OPGD reliability"),
            Line2D([0], [0], marker="s", color="#A6A6A6", markerfacecolor="#A6A6A6", linestyle="None", markersize=6, label="Low OPGD reliability"),
        ]
        fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.52, 0.986), fontsize=8)
        fig.suptitle(f"{biome}: orthogonal SHAP dependence with OPGD q/reliability annotations", fontsize=14, fontweight="bold", y=0.998)
        fig.subplots_adjust(left=0.105, right=0.985, top=0.965, bottom=0.035, hspace=0.60, wspace=0.24)
        out = out_dir / f"{biome}_orthogonal_dependence_with_opgd_reliability.png"
        fig.savefig(out, dpi=250)
        plt.close(fig)
        outputs.append(out)
    pd.DataFrame({"biome": BIOMES, "output_png": [str(p) for p in outputs]}).to_csv(out_dir / "orthogonal_dependence_opgd_overlay_index.csv", index=False)
    return outputs


def write_readme(matrix_path: Path, overlays: list[Path]) -> None:
    lines = [
        "# Orthogonal SHAP vs OPGD comparison",
        "",
        "This folder compares orthogonal-decomposition SHAP outputs with OPGD Geodetector results.",
        "",
        "Important interpretation note: orthogonal SHAP features are standardized anchors or residual components. OPGD q values are computed on the corresponding raw features, so the comparison tests mechanism-level agreement rather than one-to-one equality of feature scales.",
        "",
        f"- Reliability matrix: {matrix_path}",
        "- Overlay-style dependence figures:",
    ]
    lines.extend([f"  - {p}" for p in overlays])
    lines.extend(
        [
            "",
            "Marker convention in the reliability matrix:",
            "- black filled circle: Orthogonal SHAP Top3 and OPGD Top3",
            "- blue open circle: Orthogonal SHAP Top3 only",
            "- orange open square: OPGD Top3 only",
        ]
    )
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    matrix = plot_reliability_matrix()
    overlays = plot_overlay_style_by_biome()
    write_readme(matrix, overlays)
    print(f"matrix={matrix}")
    for p in overlays:
        print(f"overlay={p}")


if __name__ == "__main__":
    main()
