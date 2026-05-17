#!/usr/bin/env python3
"""Build a PLS-SEM style mechanism model for prepeak GPP/RECO recovery time."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
import numpy as np
import pandas as pd
import statsmodels.api as sm


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
OUT = ROOT / "plots2/SEM/sem_prepeak_pls_sem_20260514"
TARGET = "t_recover_to_baseline_abs_peak"
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

BLOCKS = {
    "Energy": ["SSRD", "STRD", "TMP"],
    "AtmosDemand": ["VPD", "Wind"],
    "WaterAvailability": ["Pre", "SMrz", "EVA"],
    "DroughtSeverity": ["Duration", "Intensity"],
    "RecoveryTime": [TARGET],
}

NODE_POS = {
    "Energy": (0.08, 0.78),
    "AtmosDemand": (0.30, 0.58),
    "WaterAvailability": (0.30, 0.24),
    "DroughtSeverity": (0.08, 0.10),
    "RecoveryTime": (0.84, 0.42),
}

BLOCK_LABELS = {
    "Energy": "Energy supply",
    "AtmosDemand": "Atmospheric demand",
    "WaterAvailability": "Water availability",
    "DroughtSeverity": "Drought severity",
    "RecoveryTime": "Recovery time",
}

INDICATOR_LABELS = {
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
    TARGET: "Recovery",
}

STRUCTURAL_EDGES = [
    ("Energy", "AtmosDemand"),
    ("Energy", "WaterAvailability"),
    ("AtmosDemand", "WaterAvailability"),
    ("DroughtSeverity", "WaterAvailability"),
    ("Energy", "RecoveryTime"),
    ("AtmosDemand", "RecoveryTime"),
    ("WaterAvailability", "RecoveryTime"),
    ("DroughtSeverity", "RecoveryTime"),
]

PATH_RAD = {
    ("Energy", "AtmosDemand"): 0.15,
    ("Energy", "WaterAvailability"): -0.12,
    ("AtmosDemand", "WaterAvailability"): 0.10,
    ("DroughtSeverity", "WaterAvailability"): 0.18,
    ("Energy", "RecoveryTime"): -0.26,
    ("AtmosDemand", "RecoveryTime"): 0.18,
    ("WaterAvailability", "RecoveryTime"): -0.18,
    ("DroughtSeverity", "RecoveryTime"): 0.24,
}


@dataclass
class BlockResult:
    score: np.ndarray
    weights: dict[str, float]
    loadings: dict[str, float]
    alpha: float
    cr: float
    ave: float


def zscore_frame(df: pd.DataFrame) -> pd.DataFrame:
    numeric = df.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    numeric = numeric.dropna(axis=0, how="any")
    std = numeric.std(ddof=0).replace(0, np.nan)
    z = (numeric - numeric.mean()) / std
    return z.dropna(axis=1, how="any")


def clean_raw(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if "prepeak_total_precipitation_mean" in work.columns:
        work.loc[pd.to_numeric(work["prepeak_total_precipitation_mean"], errors="coerce") < 0, "prepeak_total_precipitation_mean"] = np.nan
    if "prepeak_total_evaporation_mean" in work.columns:
        work["prepeak_total_evaporation_mean"] = pd.to_numeric(
            work["prepeak_total_evaporation_mean"], errors="coerce"
        ).abs()
    return work


def load_metric(metric: str, biome: str | None = None, max_rows: int = 25000, random_state: int = 42) -> pd.DataFrame:
    cols = ["biome", TARGET] + [RAW_FEATURES[k] for k in RAW_FEATURES]
    df = pd.read_parquet(TABLES[metric], columns=cols)
    df = clean_raw(df)
    if biome is not None:
        df = df[df["biome"] == biome].copy()
    df = df.drop(columns=["biome"]).reset_index(drop=True)
    df = df.dropna(subset=[TARGET]).reset_index(drop=True)
    if max_rows > 0 and len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=random_state).sort_index().reset_index(drop=True)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(axis=0, how="any").reset_index(drop=True)
    return df


def standardize_inputs(df: pd.DataFrame) -> pd.DataFrame:
    raw_cols = [RAW_FEATURES[k] for k in RAW_FEATURES]
    z = zscore_frame(df[[TARGET] + raw_cols])
    renamer = {RAW_FEATURES[k]: k for k in RAW_FEATURES}
    z = z.rename(columns=renamer)
    return z


def cronbach_alpha(z: pd.DataFrame) -> float:
    p = z.shape[1]
    if p <= 1:
        return math.nan
    variances = z.var(ddof=1).sum()
    total_var = z.sum(axis=1).var(ddof=1)
    if not np.isfinite(total_var) or total_var <= 0:
        return math.nan
    return float((p / (p - 1.0)) * (1.0 - variances / total_var))


def composite_reliability(loadings: np.ndarray) -> float:
    loadings = np.asarray(loadings, dtype=float)
    loadings = loadings[np.isfinite(loadings)]
    if loadings.size == 0:
        return math.nan
    denom = (np.sum(loadings) ** 2) + np.sum(1.0 - loadings**2)
    if denom <= 0:
        return math.nan
    return float((np.sum(loadings) ** 2) / denom)


def ave(loadings: np.ndarray) -> float:
    loadings = np.asarray(loadings, dtype=float)
    loadings = loadings[np.isfinite(loadings)]
    if loadings.size == 0:
        return math.nan
    return float(np.mean(loadings**2))


def standardize_vector(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    mu = float(np.nanmean(x))
    sd = float(np.nanstd(x, ddof=0))
    if not np.isfinite(sd) or sd <= 0:
        return x * 0.0
    return (x - mu) / sd


def fit_block_scores(z: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    scores = pd.DataFrame(index=z.index)
    weight_rows = []
    loading_rows = []
    quality_rows = []
    for block, vars_ in BLOCKS.items():
        X = z[vars_].to_numpy(dtype=float)
        if len(vars_) == 1:
            score = standardize_vector(X[:, 0])
            weights = np.array([1.0], dtype=float)
        else:
            w = np.ones(len(vars_), dtype=float) / len(vars_)
            for _ in range(200):
                s = standardize_vector(X @ w)
                corrs = []
                for j in range(X.shape[1]):
                    corr = np.corrcoef(X[:, j], s)[0, 1]
                    if not np.isfinite(corr):
                        corr = 0.0
                    corrs.append(corr)
                corrs = np.asarray(corrs, dtype=float)
                if np.allclose(corrs, 0):
                    break
                new_w = corrs / max(np.linalg.norm(corrs), 1e-12)
                if np.sum(new_w) < 0:
                    new_w = -new_w
                if np.linalg.norm(new_w - w) < 1e-7:
                    w = new_w
                    break
                w = new_w
            score = standardize_vector(X @ w)
            weights = w

        scores[block] = score
        loadings = []
        for var in vars_:
            corr = np.corrcoef(z[var].to_numpy(dtype=float), score)[0, 1]
            if not np.isfinite(corr):
                corr = 0.0
            loadings.append(corr)
        loadings = np.asarray(loadings, dtype=float)
        for var, w, l in zip(vars_, weights, loadings, strict=True):
            weight_rows.append(
                {
                    "construct": block,
                    "indicator": var,
                    "weight": float(w),
                    "loading": float(l),
                }
            )
        alpha = cronbach_alpha(z[vars_]) if len(vars_) > 1 else math.nan
        cr = composite_reliability(loadings)
        av = ave(loadings)
        for var in vars_:
            quality_rows.append(
                {
                    "construct": block,
                    "indicator": var,
                    "cronbach_alpha": alpha,
                    "composite_reliability": cr,
                    "ave": av,
                    "n_indicators": len(vars_),
                }
            )
    return scores, pd.DataFrame(weight_rows), pd.DataFrame(quality_rows)


def fit_structural(scores: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    equation_specs = {
        "AtmosDemand": ["Energy"],
        "WaterAvailability": ["Energy", "AtmosDemand", "DroughtSeverity"],
        "RecoveryTime": ["Energy", "AtmosDemand", "WaterAvailability", "DroughtSeverity"],
    }
    path_rows = []
    r2_rows = []
    for lhs, rhs in equation_specs.items():
        X = scores[rhs]
        y = scores[lhs]
        Xc = sm.add_constant(X, has_constant="add")
        model = sm.OLS(y, Xc).fit()
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
            coef = float(model.params[pred])
            se = float(model.bse[pred])
            t = float(model.tvalues[pred])
            p = float(model.pvalues[pred])
            path_rows.append(
                {
                    "from": pred,
                    "to": lhs,
                    "estimate": coef,
                    "abs_estimate": abs(coef),
                    "std_err": se,
                    "t_value": t,
                    "p_value": p,
                    "significance": "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "",
                }
            )
    return pd.DataFrame(path_rows), pd.DataFrame(r2_rows)


def bootstrap_paths(z: pd.DataFrame, n_boot: int = 80, random_state: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(random_state)
    rows = []
    n = len(z)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        sample = z.iloc[idx].reset_index(drop=True)
        scores, _, _ = fit_block_scores(sample)
        paths, _ = fit_structural(scores)
        paths["bootstrap"] = b
        rows.append(paths)
    return pd.concat(rows, ignore_index=True)


def compute_total_effects(path_df: pd.DataFrame) -> pd.DataFrame:
    direct = {(row["from"], row["to"]): float(row["estimate"]) for _, row in path_df.iterrows()}
    # The model is simple enough to enumerate the relevant mediated paths by hand.
    effects = []
    for target in ["RecoveryTime"]:
        direct_sources = ["Energy", "AtmosDemand", "WaterAvailability", "DroughtSeverity"]
        for src in direct_sources:
            d = direct.get((src, target), 0.0)
            indirect = 0.0
            if src == "Energy":
                indirect += direct.get(("Energy", "AtmosDemand"), 0.0) * direct.get(("AtmosDemand", "WaterAvailability"), 0.0) * direct.get(("WaterAvailability", target), 0.0)
                indirect += direct.get(("Energy", "WaterAvailability"), 0.0) * direct.get(("WaterAvailability", target), 0.0)
                indirect += direct.get(("Energy", "AtmosDemand"), 0.0) * direct.get(("AtmosDemand", target), 0.0)
            elif src == "AtmosDemand":
                indirect += direct.get(("AtmosDemand", "WaterAvailability"), 0.0) * direct.get(("WaterAvailability", target), 0.0)
            elif src == "DroughtSeverity":
                indirect += direct.get(("DroughtSeverity", "WaterAvailability"), 0.0) * direct.get(("WaterAvailability", target), 0.0)
            effects.append(
                {
                    "source": src,
                    "target": target,
                    "direct_effect": d,
                    "indirect_effect": indirect,
                    "total_effect": d + indirect,
                }
            )
    return pd.DataFrame(effects)


def bootstrap_ci(boot_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (frm, to), g in boot_df.groupby(["from", "to"], sort=False):
        vals = g["estimate"].to_numpy(dtype=float)
        rows.append(
            {
                "from": frm,
                "to": to,
                "boot_mean": float(np.nanmean(vals)),
                "boot_ci_low": float(np.nanquantile(vals, 0.025)),
                "boot_ci_high": float(np.nanquantile(vals, 0.975)),
                "boot_sd": float(np.nanstd(vals, ddof=1)),
            }
        )
    return pd.DataFrame(rows)


def outer_bootstrap_ci(boot_rows: list[pd.DataFrame]) -> pd.DataFrame:
    merged = pd.concat(boot_rows, ignore_index=True)
    rows = []
    for (construct, indicator), g in merged.groupby(["construct", "indicator"], sort=False):
        vals = g["loading"].to_numpy(dtype=float)
        rows.append(
            {
                "construct": construct,
                "indicator": indicator,
                "boot_loading_mean": float(np.nanmean(vals)),
                "boot_loading_ci_low": float(np.nanquantile(vals, 0.025)),
                "boot_loading_ci_high": float(np.nanquantile(vals, 0.975)),
            }
        )
    return pd.DataFrame(rows)


def draw_path_diagram(path_df: pd.DataFrame, r2_df: pd.DataFrame, metric: str, label_suffix: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    for block, (x, y) in NODE_POS.items():
        target = block == "RecoveryTime"
        ax.text(
            x,
            y,
            BLOCK_LABELS[block],
            ha="center",
            va="center",
            fontsize=10.5 if target else 9.5,
            fontweight="bold" if target else "normal",
            bbox={
                "boxstyle": "round,pad=0.30,rounding_size=0.08",
                "facecolor": "#fff7bc" if target else "#f7f7f7",
                "edgecolor": "#4d4d4d",
                "linewidth": 0.9,
            },
            zorder=6,
        )

    for _, row in r2_df.iterrows():
        if row["endogenous"] in NODE_POS:
            x, y = NODE_POS[row["endogenous"]]
            ax.text(x + 0.11, y + 0.10, f"R²={row['r2']:.2f}", fontsize=8.3, ha="left", va="center", color="#2c3e50")

    for _, row in path_df.iterrows():
        src = row["from"]
        dst = row["to"]
        if src not in NODE_POS or dst not in NODE_POS:
            continue
        x1, y1 = NODE_POS[src]
        x2, y2 = NODE_POS[dst]
        coef = float(row["estimate"])
        rad = PATH_RAD.get((src, dst), 0.0)
        color = "#d7301f" if coef < 0 else "#1a9850"
        lw = max(0.8, min(5.0, 0.7 + abs(coef) * 4.5))
        arrow = FancyArrowPatch(
            (x1 + 0.06, y1),
            (x2 - 0.06, y2),
            arrowstyle="-|>",
            connectionstyle=f"arc3,rad={rad}",
            mutation_scale=12,
            linewidth=lw,
            color=color,
            alpha=0.92,
            zorder=3,
        )
        ax.add_patch(arrow)
        mx = (x1 + x2) / 2.0
        my = (y1 + y2) / 2.0 + 0.04
        ax.text(
            mx,
            my,
            f"{coef:+.2f}",
            fontsize=8.0,
            ha="center",
            va="center",
            color=color,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 0.12},
            zorder=7,
        )

    ax.set_title(f"{metric} {label_suffix}", fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=280, bbox_inches="tight")
    plt.close(fig)


def summarize_model(metric: str, biome: str | None, max_rows: int = 25000, n_boot: int = 80) -> dict[str, object]:
    df = load_metric(metric, biome=biome, max_rows=max_rows)
    z = standardize_inputs(df)
    scores, weights, quality = fit_block_scores(z)
    paths, r2 = fit_structural(scores)
    total = compute_total_effects(paths)
    boot_rows = []
    boot_r2_rows = []
    rng = np.random.default_rng(42)
    for b in range(n_boot):
        idx = rng.integers(0, len(z), size=len(z))
        sample = z.iloc[idx].reset_index(drop=True)
        s_scores, _, s_quality = fit_block_scores(sample)
        s_paths, s_r2 = fit_structural(s_scores)
        s_paths["bootstrap"] = b
        s_quality["bootstrap"] = b
        boot_rows.append(s_paths)
        boot_r2_rows.append(s_r2.assign(bootstrap=b))
    boot_paths = pd.concat(boot_rows, ignore_index=True)
    boot_r2 = pd.concat(boot_r2_rows, ignore_index=True)
    boot_path_ci = bootstrap_ci(boot_paths)
    boot_r2_summary = boot_r2.groupby("endogenous", as_index=False).agg(
        boot_r2_mean=("r2", "mean"),
        boot_r2_ci_low=("r2", lambda s: float(np.nanquantile(s, 0.025))),
        boot_r2_ci_high=("r2", lambda s: float(np.nanquantile(s, 0.975))),
        boot_r2_sd=("r2", "std"),
    )
    outer_rows = []
    quality_rows = []
    for b in range(n_boot):
        idx = rng.integers(0, len(z), size=len(z))
        sample = z.iloc[idx].reset_index(drop=True)
        _, s_weights, s_quality = fit_block_scores(sample)
        s_weights["bootstrap"] = b
        s_quality["bootstrap"] = b
        outer_rows.append(s_weights)
        quality_rows.append(s_quality)
    boot_outer = outer_bootstrap_ci(outer_rows)
    quality_summary = quality.drop_duplicates(subset=["construct"])

    model_label = biome if biome is not None else "AllBiomes"
    stem = f"{metric}_{model_label}".replace(" ", "_")
    model_dir = OUT / "tables" / stem
    fig_dir = OUT / "figures"
    model_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    df_scores = scores.copy()
    df_scores.to_parquet(model_dir / "latent_scores.parquet", index=True)
    weights.to_csv(model_dir / "outer_weights.csv", index=False)
    quality.to_csv(model_dir / "measurement_quality.csv", index=False)
    paths_ci = paths.merge(boot_path_ci, on=["from", "to"], how="left")
    paths_ci.to_csv(model_dir / "structural_paths.csv", index=False)
    r2.merge(boot_r2_summary, on="endogenous", how="left").to_csv(model_dir / "r2_summary.csv", index=False)
    total.to_csv(model_dir / "total_effects.csv", index=False)
    boot_outer.to_csv(model_dir / "bootstrap_outer_loadings_ci.csv", index=False)
    quality_summary.to_csv(model_dir / "measurement_quality_summary.csv", index=False)

    draw_path_diagram(paths, r2, metric, f"PLS-SEM ({model_label})", fig_dir / f"{stem}_path_diagram.png")

    return {
        "metric": metric,
        "biome": model_label,
        "n": len(z),
        "rows_used": len(df),
        "avg_r2": float(r2["r2"].mean()),
        "recovery_r2": float(r2.loc[r2["endogenous"] == "RecoveryTime", "r2"].iloc[0]),
    }


def build_overview(summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.6, 5.4))
    order = summary.sort_values(["metric", "biome"]).reset_index(drop=True)
    x = np.arange(len(order))
    width = 0.32
    labels = [f"{m}\n{b}" for m, b in zip(order["metric"], order["biome"], strict=True)]
    ax.bar(x - width / 2, order["avg_r2"], width=width, color="#74a9cf", label="Mean endogenous R²")
    ax.bar(x + width / 2, order["recovery_r2"], width=width, color="#dd6b20", label="Recovery R²")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("R²")
    ax.set_title("PLS-SEM explanatory power")
    ax.grid(axis="y", linestyle="--", alpha=0.2)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "pls_sem_r2_overview.png", dpi=280)
    plt.close(fig)


def write_readme(summary: pd.DataFrame) -> None:
    lines = [
        "# PLS-SEM for prepeak recovery time",
        "",
        "This folder contains a composite-based PLS-SEM style mechanism analysis for GPP and RECO prepeak recovery time.",
        "",
        "Latent constructs:",
        "- Energy: SSRD, STRD, TMP",
        "- Atmospheric demand: VPD, Wind",
        "- Water availability: Pre, SMrz, EVA",
        "- Drought severity: Duration, Intensity",
        "- Recovery time: single-indicator latent variable",
        "",
        "Structural model:",
        "- Energy -> Atmospheric demand",
        "- Energy -> Water availability",
        "- Atmospheric demand -> Water availability",
        "- Drought severity -> Water availability",
        "- Energy -> Recovery time",
        "- Atmospheric demand -> Recovery time",
        "- Water availability -> Recovery time",
        "- Drought severity -> Recovery time",
        "",
        "Outputs include outer weights/loadings, structural paths, bootstrap confidence intervals, R² summaries, total effects, and path diagrams.",
        "",
        "Summary:",
        "```csv",
        summary.to_csv(index=False).strip(),
        "```",
    ]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summaries = []
    for metric in METRICS:
        summaries.append(summarize_model(metric, None))
        for biome in BIOMES:
            summaries.append(summarize_model(metric, biome))
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT / "pls_sem_model_summary.csv", index=False)
    build_overview(summary_df)
    write_readme(summary_df)
    print(OUT)


if __name__ == "__main__":
    main()
