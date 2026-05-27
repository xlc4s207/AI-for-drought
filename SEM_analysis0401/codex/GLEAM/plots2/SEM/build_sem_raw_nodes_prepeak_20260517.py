#!/usr/bin/env python3
"""Build an observed-variable raw-node SEM for prepeak recovery time.

This model keeps each original predictor as a path node instead of compressing
them into PLS-style composite constructs.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
import numpy as np
import pandas as pd
import statsmodels.api as sm


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
OUT = ROOT / "plots2/SEM/sem_prepeak_raw_nodes_20260517"
TARGET = "t_recover_to_baseline_abs_peak"
TARGET_NODE = "RecoveryTime"
BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
METRICS = ["GPP", "RECO"]
TABLES = {
    "GPP": ROOT / "data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet",
    "RECO": ROOT / "data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet",
}

RAW_FEATURES = {
    "SSRD": "prepeak_ssrd_mean",
    "STRD": "prepeak_strd_mean",
    "TMP": "prepeak_temperature_2m_mean",
    "VPD": "prepeak_VPD_mean",
    "Wind": "prepeak_wind_speed_mean",
    "Pre": "prepeak_total_precipitation_mean",
    "SMrz": "prepeak_SMrz_mean",
    "EVA": "prepeak_total_evaporation_mean",
    "Duration": "event_duration",
    "Intensity": "event_intensity",
}

NODE_ORDER = [
    "SSRD",
    "STRD",
    "Wind",
    "Pre",
    "Duration",
    "Intensity",
    "TMP",
    "VPD",
    "SMrz",
    "EVA",
    TARGET_NODE,
]

EQUATION_SPECS = {
    "TMP": ["SSRD", "STRD"],
    "VPD": ["SSRD", "STRD", "TMP", "Wind"],
    "SMrz": ["Pre", "TMP", "VPD", "Duration", "Intensity"],
    "EVA": ["SSRD", "STRD", "TMP", "VPD", "Pre", "SMrz"],
    TARGET_NODE: [
        "SSRD",
        "STRD",
        "TMP",
        "VPD",
        "Wind",
        "Pre",
        "SMrz",
        "EVA",
        "Duration",
        "Intensity",
    ],
}

NODE_POS = {
    "SSRD": (0.08, 0.86),
    "STRD": (0.08, 0.74),
    "Wind": (0.08, 0.56),
    "Pre": (0.08, 0.39),
    "Duration": (0.08, 0.22),
    "Intensity": (0.08, 0.10),
    "TMP": (0.34, 0.80),
    "VPD": (0.34, 0.61),
    "SMrz": (0.34, 0.34),
    "EVA": (0.60, 0.48),
    TARGET_NODE: (0.88, 0.48),
}

NODE_LABELS = {
    "SSRD": "SSRD",
    "STRD": "STRD",
    "TMP": "TMP",
    "VPD": "VPD",
    "Wind": "Wind",
    "Pre": "Pre",
    "SMrz": "SMrz",
    "EVA": "EVA",
    "Duration": "Duration",
    "Intensity": "Intensity",
    TARGET_NODE: "Recovery time",
}


def clean_raw(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if "prepeak_total_precipitation_mean" in work.columns:
        pre = pd.to_numeric(work["prepeak_total_precipitation_mean"], errors="coerce")
        work.loc[pre < 0, "prepeak_total_precipitation_mean"] = np.nan
    if "prepeak_total_evaporation_mean" in work.columns:
        work["prepeak_total_evaporation_mean"] = pd.to_numeric(
            work["prepeak_total_evaporation_mean"], errors="coerce"
        ).abs()
    return work


def zscore(frame: pd.DataFrame) -> pd.DataFrame:
    numeric = frame.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    numeric = numeric.dropna(axis=0, how="any")
    std = numeric.std(ddof=0).replace(0, np.nan)
    z = (numeric - numeric.mean()) / std
    return z.dropna(axis=0, how="any")


def load_metric(metric: str, biome: str | None, max_rows: int = 25000, random_state: int = 42) -> pd.DataFrame:
    cols = ["biome", TARGET] + list(RAW_FEATURES.values())
    df = pd.read_parquet(TABLES[metric], columns=cols)
    df = clean_raw(df)
    if biome is not None:
        df = df[df["biome"] == biome].copy()
    df = df.drop(columns=["biome"]).reset_index(drop=True)
    if max_rows > 0 and len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=random_state).sort_index().reset_index(drop=True)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.replace([np.inf, -np.inf], np.nan)
    needed = [TARGET] + list(RAW_FEATURES.values())
    df = df.dropna(subset=needed, how="any").reset_index(drop=True)
    z = zscore(df[needed])
    renamer = {RAW_FEATURES[k]: k for k in RAW_FEATURES}
    return z.rename(columns={**renamer, TARGET: TARGET_NODE})


def significance(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def fit_structural(z: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    path_rows = []
    r2_rows = []
    for lhs, rhs in EQUATION_SPECS.items():
        frame = z[[lhs] + rhs].dropna(axis=0, how="any")
        model = sm.OLS(frame[lhs], sm.add_constant(frame[rhs], has_constant="add")).fit()
        r2_rows.append(
            {
                "endogenous": lhs,
                "r2": float(model.rsquared),
                "adj_r2": float(model.rsquared_adj),
                "n": int(model.nobs),
                "predictors": ", ".join(rhs),
            }
        )
        for pred in rhs:
            p = float(model.pvalues[pred])
            coef = float(model.params[pred])
            path_rows.append(
                {
                    "from": pred,
                    "to": lhs,
                    "estimate": coef,
                    "abs_estimate": abs(coef),
                    "std_err": float(model.bse[pred]),
                    "t_value": float(model.tvalues[pred]),
                    "p_value": p,
                    "significance": significance(p),
                }
            )
    return pd.DataFrame(path_rows), pd.DataFrame(r2_rows)


def bootstrap_summary(z: pd.DataFrame, n_boot: int = 80, random_state: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(random_state)
    path_frames = []
    r2_frames = []
    n = len(z)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        sample = z.iloc[idx].reset_index(drop=True)
        paths, r2 = fit_structural(sample)
        path_frames.append(paths.assign(bootstrap=b))
        r2_frames.append(r2.assign(bootstrap=b))
    boot_paths = pd.concat(path_frames, ignore_index=True)
    boot_r2 = pd.concat(r2_frames, ignore_index=True)
    path_ci = (
        boot_paths.groupby(["from", "to"], as_index=False)
        .agg(
            boot_mean=("estimate", "mean"),
            boot_sd=("estimate", "std"),
            boot_ci_low=("estimate", lambda s: float(np.nanquantile(s, 0.025))),
            boot_ci_high=("estimate", lambda s: float(np.nanquantile(s, 0.975))),
        )
    )
    r2_ci = (
        boot_r2.groupby("endogenous", as_index=False)
        .agg(
            boot_r2_mean=("r2", "mean"),
            boot_r2_sd=("r2", "std"),
            boot_r2_ci_low=("r2", lambda s: float(np.nanquantile(s, 0.025))),
            boot_r2_ci_high=("r2", lambda s: float(np.nanquantile(s, 0.975))),
        )
    )
    return path_ci, r2_ci


def compute_total_effects(path_df: pd.DataFrame) -> pd.DataFrame:
    idx = {node: i for i, node in enumerate(NODE_ORDER)}
    mat = np.zeros((len(NODE_ORDER), len(NODE_ORDER)), dtype=float)
    for _, row in path_df.iterrows():
        mat[idx[row["from"]], idx[row["to"]]] = float(row["estimate"])

    indirect = np.zeros_like(mat)
    power = mat.copy()
    for length in range(2, len(NODE_ORDER)):
        power = power @ mat if length > 2 else mat @ mat
        indirect += power

    rows = []
    target = TARGET_NODE
    for src in NODE_ORDER:
        if src == target:
            continue
        direct = mat[idx[src], idx[target]]
        mediated = indirect[idx[src], idx[target]]
        if abs(direct) > 0 or abs(mediated) > 0:
            rows.append(
                {
                    "source": src,
                    "target": target,
                    "direct_effect": float(direct),
                    "indirect_effect": float(mediated),
                    "total_effect": float(direct + mediated),
                }
            )
    return pd.DataFrame(rows)


def draw_path_diagram(path_df: pd.DataFrame, r2_df: pd.DataFrame, metric: str, model_label: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(13.2, 7.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    for node, (x, y) in NODE_POS.items():
        target = node == TARGET_NODE
        ax.text(
            x,
            y,
            NODE_LABELS[node],
            ha="center",
            va="center",
            fontsize=9.2 if target else 8.5,
            fontweight="bold" if target else "normal",
            bbox={
                "boxstyle": "round,pad=0.25,rounding_size=0.06",
                "facecolor": "#fff7bc" if target else "#f7f7f7",
                "edgecolor": "#4d4d4d",
                "linewidth": 0.8,
            },
            zorder=6,
        )

    for _, row in r2_df.iterrows():
        node = row["endogenous"]
        if node in NODE_POS:
            x, y = NODE_POS[node]
            ax.text(x + 0.055, y + 0.060, f"R²={row['r2']:.2f}", fontsize=7.2, color="#2c3e50")

    for _, row in path_df.iterrows():
        src, dst = row["from"], row["to"]
        if src not in NODE_POS or dst not in NODE_POS:
            continue
        x1, y1 = NODE_POS[src]
        x2, y2 = NODE_POS[dst]
        coef = float(row["estimate"])
        color = "#d7301f" if coef < 0 else "#1a9850"
        alpha = 0.78 if row["to"] == TARGET_NODE else 0.46
        lw = max(0.45, min(3.8, 0.45 + abs(coef) * 3.2))
        rad = 0.0
        if dst == TARGET_NODE:
            rad = (y1 - y2) * 0.16
        arrow = FancyArrowPatch(
            (x1 + 0.045, y1),
            (x2 - 0.055, y2),
            arrowstyle="-|>",
            connectionstyle=f"arc3,rad={rad:.3f}",
            mutation_scale=9.5,
            linewidth=lw,
            color=color,
            alpha=alpha,
            zorder=3 if dst == TARGET_NODE else 2,
        )
        ax.add_patch(arrow)
        if dst == TARGET_NODE and abs(coef) >= 0.025:
            mx = x1 * 0.42 + x2 * 0.58
            my = y1 * 0.42 + y2 * 0.58
            ax.text(
                mx,
                my,
                f"{coef:+.2f}",
                fontsize=6.7,
                ha="center",
                va="center",
                color=color,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.74, "pad": 0.08},
                zorder=7,
            )

    ax.text(0.08, 0.95, "Exogenous drivers", fontsize=8.4, color="#555555", ha="center")
    ax.text(0.34, 0.95, "Hydrothermal mediators", fontsize=8.4, color="#555555", ha="center")
    ax.text(0.60, 0.95, "Evaporation mediator", fontsize=8.4, color="#555555", ha="center")
    ax.text(0.88, 0.95, "Target", fontsize=8.4, color="#555555", ha="center")
    ax.set_title(f"{metric} raw-node SEM ({model_label})", fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=280, bbox_inches="tight")
    plt.close(fig)


def summarize_model(metric: str, biome: str | None, max_rows: int = 25000, n_boot: int = 80) -> dict[str, object]:
    model_label = biome if biome is not None else "AllBiomes"
    stem = f"{metric}_{model_label}".replace(" ", "_")
    model_dir = OUT / "tables" / stem
    fig_dir = OUT / "figures"
    model_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    z = load_metric(metric, biome=biome, max_rows=max_rows)
    paths, r2 = fit_structural(z)
    path_ci, r2_ci = bootstrap_summary(z, n_boot=n_boot)
    paths_ci = paths.merge(path_ci, on=["from", "to"], how="left")
    r2_full = r2.merge(r2_ci, on="endogenous", how="left")
    total = compute_total_effects(paths)

    z.to_parquet(model_dir / "standardized_raw_nodes.parquet", index=False)
    paths_ci.to_csv(model_dir / "structural_paths.csv", index=False)
    r2_full.to_csv(model_dir / "r2_summary.csv", index=False)
    total.to_csv(model_dir / "total_effects.csv", index=False)
    draw_path_diagram(paths, r2, metric, model_label, fig_dir / f"{stem}_raw_node_path_diagram.png")

    recovery_r2 = float(r2.loc[r2["endogenous"] == TARGET_NODE, "r2"].iloc[0])
    return {
        "metric": metric,
        "biome": model_label,
        "n": len(z),
        "rows_used": len(z),
        "avg_r2": float(r2["r2"].mean()),
        "recovery_r2": recovery_r2,
        "direct_predictors": EQUATION_SPECS[TARGET_NODE],
    }


def build_overview(summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.6, 4.8))
    labels = [f"{m}\n{b}" for m, b in zip(summary["metric"], summary["biome"], strict=True)]
    x = np.arange(len(summary))
    colors = np.where(summary["metric"].to_numpy() == "GPP", "#3182bd", "#e6550d")
    ax.bar(x, summary["recovery_r2"], color=colors, alpha=0.84)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("RecoveryTime R²")
    ax.set_title("Raw-node SEM explanatory power for recovery time")
    ax.grid(axis="y", linestyle="--", alpha=0.22)
    fig.tight_layout()
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "figures/raw_node_sem_recovery_r2_overview.png", dpi=300)
    plt.close(fig)


def build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    comp = summary[["metric", "biome", "recovery_r2"]].rename(columns={"recovery_r2": "raw_node_recovery_r2"})
    baseline_path = ROOT / "plots2/SEM/sem_prepeak_pls_sem_20260514/pls_sem_model_summary.csv"
    enhanced_path = ROOT / "plots2/SEM/sem_prepeak_pls_sem_enhanced_20260515/pls_sem_enhanced_model_summary.csv"
    if baseline_path.exists():
        baseline = pd.read_csv(baseline_path)[["metric", "biome", "recovery_r2"]].rename(
            columns={"recovery_r2": "composite_pls_recovery_r2"}
        )
        comp = comp.merge(baseline, on=["metric", "biome"], how="left")
        comp["raw_minus_composite_pls"] = comp["raw_node_recovery_r2"] - comp["composite_pls_recovery_r2"]
    if enhanced_path.exists():
        enhanced = pd.read_csv(enhanced_path)[["metric", "biome", "recovery_r2"]].rename(
            columns={"recovery_r2": "enhanced_pls_recovery_r2"}
        )
        comp = comp.merge(enhanced, on=["metric", "biome"], how="left")
        comp["raw_minus_enhanced_pls"] = comp["raw_node_recovery_r2"] - comp["enhanced_pls_recovery_r2"]
    comp.to_csv(OUT / "raw_node_vs_pls_r2_comparison.csv", index=False)
    return comp


def write_readme(summary: pd.DataFrame, comparison: pd.DataFrame) -> None:
    lines = [
        "# Raw-node observed-variable SEM for prepeak recovery time",
        "",
        "This folder tests the alternative SEM design requested after the composite PLS-SEM results: original variables are kept as observed path nodes instead of being collapsed into latent/composite blocks.",
        "",
        "Model type: observed-variable path SEM fitted by standardized OLS equations. It is not a latent-variable PLS-SEM, because no Energy/Water/Severity composite scores are formed.",
        "",
        "Raw nodes:",
        "- SSRD, STRD, TMP, VPD, Wind, Pre, SMrz, EVA, Duration, Intensity, RecoveryTime",
        "",
        "Structural equations:",
        "- TMP ~ SSRD + STRD",
        "- VPD ~ SSRD + STRD + TMP + Wind",
        "- SMrz ~ Pre + TMP + VPD + Duration + Intensity",
        "- EVA ~ SSRD + STRD + TMP + VPD + Pre + SMrz",
        "- RecoveryTime ~ SSRD + STRD + TMP + VPD + Wind + Pre + SMrz + EVA + Duration + Intensity",
        "",
        "This design preserves direct effects of each original variable on recovery time while still representing hydrothermal mediation among temperature, vapor pressure deficit, soil moisture, and evaporation.",
        "",
        "Summary:",
        "```csv",
        summary.to_csv(index=False).strip(),
        "```",
        "",
        "Comparison with previous PLS-SEM runs:",
        "```csv",
        comparison.to_csv(index=False).strip(),
        "```",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summaries = []
    for metric in METRICS:
        summaries.append(summarize_model(metric, None, n_boot=80))
        for biome in BIOMES:
            summaries.append(summarize_model(metric, biome, n_boot=80))
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / "raw_node_sem_model_summary.csv", index=False)
    build_overview(summary)
    comparison = build_comparison(summary)
    write_readme(summary, comparison)
    print(OUT)


if __name__ == "__main__":
    main()
