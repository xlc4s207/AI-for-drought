#!/usr/bin/env python3
"""Build an enhanced SHAP-informed PLS-SEM model for prepeak recovery time."""

from __future__ import annotations

from pathlib import Path
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

import build_pls_sem_prepeak_20260514 as base


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
OUT = ROOT / "plots2/SEM/sem_prepeak_pls_sem_enhanced_20260515"
TARGET = base.TARGET
BIOMES = base.BIOMES
METRICS = base.METRICS
TABLES = {
    "GPP": ROOT / "data/feature_table_merged_GPP_code1_flash_SMrz_0401.parquet",
    "RECO": ROOT / "data/feature_table_merged_RECO_code1_flash_SMrz_0401_mswepE.parquet",
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
    "OnsetRate": "event_onset_rate",
    "DaysBelowP20": "event_days_below_p20",
    "SeasonPhase": "season_phase",
    "LAI": "prepeak_lai_total_mean",
    "FluxBaseline": "flux_baseline_abs",
    "FluxVariability": "flux_baseline_std_abs",
    "Pre30SMrz": "pre30_SMrz_mean",
    "Pre30VPD": "pre30_VPD_mean",
    "PostSMrz": "postpeak30_SMrz_mean",
    "PostVPD": "postpeak30_VPD_mean",
    "PostTMP": "postpeak30_temperature_2m_mean",
    "PostPre": "postpeak30_total_precipitation_sum",
}

BLOCKS = {
    "Energy": ["SSRD", "STRD", "TMP"],
    "AtmosDemand": ["VPD", "Wind"],
    "WaterAvailability": ["Pre", "SMrz", "EVA"],
    "DroughtSeverity": ["Duration", "Intensity", "OnsetRate", "DaysBelowP20"],
    "PhenologyTiming": ["SeasonPhase", "LAI"],
    "PreDroughtState": ["FluxBaseline", "FluxVariability", "Pre30SMrz", "Pre30VPD"],
    "RecoveryClimate": ["PostSMrz", "PostVPD", "PostTMP", "PostPre"],
    "RecoveryTime": [TARGET],
}

STRUCTURAL_EDGES = [
    ("Energy", "AtmosDemand"),
    ("Energy", "WaterAvailability"),
    ("AtmosDemand", "WaterAvailability"),
    ("DroughtSeverity", "WaterAvailability"),
    ("PhenologyTiming", "WaterAvailability"),
    ("PreDroughtState", "WaterAvailability"),
    ("Energy", "RecoveryClimate"),
    ("AtmosDemand", "RecoveryClimate"),
    ("WaterAvailability", "RecoveryClimate"),
    ("DroughtSeverity", "RecoveryClimate"),
    ("PhenologyTiming", "RecoveryClimate"),
    ("Energy", "RecoveryTime"),
    ("AtmosDemand", "RecoveryTime"),
    ("WaterAvailability", "RecoveryTime"),
    ("DroughtSeverity", "RecoveryTime"),
    ("PhenologyTiming", "RecoveryTime"),
    ("PreDroughtState", "RecoveryTime"),
    ("RecoveryClimate", "RecoveryTime"),
]

EQUATION_SPECS = {
    "AtmosDemand": ["Energy"],
    "WaterAvailability": [
        "Energy",
        "AtmosDemand",
        "DroughtSeverity",
        "PhenologyTiming",
        "PreDroughtState",
    ],
    "RecoveryClimate": [
        "Energy",
        "AtmosDemand",
        "WaterAvailability",
        "DroughtSeverity",
        "PhenologyTiming",
    ],
    "RecoveryTime": [
        "Energy",
        "AtmosDemand",
        "WaterAvailability",
        "DroughtSeverity",
        "PhenologyTiming",
        "PreDroughtState",
        "RecoveryClimate",
    ],
}

NODE_POS = {
    "Energy": (0.08, 0.82),
    "AtmosDemand": (0.31, 0.72),
    "WaterAvailability": (0.34, 0.47),
    "DroughtSeverity": (0.08, 0.20),
    "PhenologyTiming": (0.08, 0.52),
    "PreDroughtState": (0.33, 0.14),
    "RecoveryClimate": (0.62, 0.52),
    "RecoveryTime": (0.88, 0.42),
}

BLOCK_LABELS = {
    "Energy": "Energy supply",
    "AtmosDemand": "Atmospheric demand",
    "WaterAvailability": "Pre-peak water",
    "DroughtSeverity": "Drought severity",
    "PhenologyTiming": "Phenology/timing",
    "PreDroughtState": "Pre-drought state",
    "RecoveryClimate": "Recovery climate",
    "RecoveryTime": "Recovery time",
}

INDICATOR_LABELS = {
    **base.INDICATOR_LABELS,
    "OnsetRate": "Onset rate",
    "DaysBelowP20": "Days < P20",
    "SeasonPhase": "Season phase",
    "LAI": "LAI",
    "FluxBaseline": "Flux baseline",
    "FluxVariability": "Flux variability",
    "Pre30SMrz": "Pre30 SMrz",
    "Pre30VPD": "Pre30 VPD",
    "PostSMrz": "Post30 SMrz",
    "PostVPD": "Post30 VPD",
    "PostTMP": "Post30 TMP",
    "PostPre": "Post30 Pre",
}

PATH_RAD = {edge: 0.0 for edge in STRUCTURAL_EDGES}
PATH_RAD.update(
    {
        ("Energy", "AtmosDemand"): 0.10,
        ("Energy", "WaterAvailability"): -0.10,
        ("AtmosDemand", "WaterAvailability"): 0.08,
        ("DroughtSeverity", "WaterAvailability"): 0.14,
        ("PhenologyTiming", "WaterAvailability"): -0.10,
        ("PreDroughtState", "WaterAvailability"): 0.10,
        ("Energy", "RecoveryClimate"): -0.14,
        ("AtmosDemand", "RecoveryClimate"): 0.08,
        ("WaterAvailability", "RecoveryClimate"): -0.06,
        ("DroughtSeverity", "RecoveryClimate"): 0.16,
        ("PhenologyTiming", "RecoveryClimate"): -0.08,
        ("Energy", "RecoveryTime"): -0.24,
        ("AtmosDemand", "RecoveryTime"): 0.16,
        ("WaterAvailability", "RecoveryTime"): -0.18,
        ("DroughtSeverity", "RecoveryTime"): 0.22,
        ("PhenologyTiming", "RecoveryTime"): -0.12,
        ("PreDroughtState", "RecoveryTime"): 0.14,
        ("RecoveryClimate", "RecoveryTime"): 0.08,
    }
)


def install_model() -> None:
    base.OUT = OUT
    base.TABLES = TABLES
    base.RAW_FEATURES = RAW_FEATURES
    base.BLOCKS = BLOCKS
    base.STRUCTURAL_EDGES = STRUCTURAL_EDGES
    base.NODE_POS = NODE_POS
    base.BLOCK_LABELS = BLOCK_LABELS
    base.INDICATOR_LABELS = INDICATOR_LABELS
    base.PATH_RAD = PATH_RAD
    base.load_metric = load_metric
    base.standardize_inputs = standardize_inputs
    base.fit_structural = fit_structural
    base.compute_total_effects = compute_total_effects
    base.draw_path_diagram = draw_path_diagram
    base.write_readme = write_readme


def clean_raw(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for col in [c for c in work.columns if "precipitation" in c.lower()]:
        work.loc[pd.to_numeric(work[col], errors="coerce") < 0, col] = np.nan
    for col in [c for c in work.columns if "evaporation" in c.lower()]:
        work[col] = pd.to_numeric(work[col], errors="coerce").abs()
    if {"lat", "onset_doy"}.issubset(work.columns):
        doy = pd.to_numeric(work["onset_doy"], errors="coerce")
        lat = pd.to_numeric(work["lat"], errors="coerce")
        local_doy = doy.where(lat >= 0, ((doy + 182.5 - 1) % 365.25) + 1)
        work["season_phase"] = np.cos(2.0 * np.pi * (local_doy - 200.0) / 365.25)
    return work


def load_metric(metric: str, biome: str | None = None, max_rows: int = 25000, random_state: int = 42) -> pd.DataFrame:
    cols = ["biome", "lat", "onset_doy", TARGET] + [
        col for key, col in RAW_FEATURES.items() if key != "SeasonPhase"
    ]
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
    needed = [TARGET] + list(RAW_FEATURES.values())
    df = df.dropna(subset=needed, how="any").reset_index(drop=True)
    return df


def standardize_inputs(df: pd.DataFrame) -> pd.DataFrame:
    raw_cols = list(RAW_FEATURES.values())
    z = base.zscore_frame(df[[TARGET] + raw_cols])
    renamer = {RAW_FEATURES[k]: k for k in RAW_FEATURES}
    return z.rename(columns=renamer)


def fit_structural(scores: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    path_rows = []
    r2_rows = []
    for lhs, rhs in EQUATION_SPECS.items():
        X = scores[rhs]
        y = scores[lhs]
        model = sm.OLS(y, sm.add_constant(X, has_constant="add")).fit()
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
                    "significance": "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "",
                }
            )
    return pd.DataFrame(path_rows), pd.DataFrame(r2_rows)


def compute_total_effects(path_df: pd.DataFrame) -> pd.DataFrame:
    nodes = list(BLOCKS)
    idx = {node: i for i, node in enumerate(nodes)}
    mat = np.zeros((len(nodes), len(nodes)), dtype=float)
    for _, row in path_df.iterrows():
        mat[idx[row["from"]], idx[row["to"]]] = float(row["estimate"])
    total_indirect = np.zeros_like(mat)
    power = mat.copy()
    for length in range(2, len(nodes) + 1):
        power = power @ mat if length > 2 else mat @ mat
        total_indirect += power
    rows = []
    target = "RecoveryTime"
    for src in nodes:
        if src == target:
            continue
        direct = mat[idx[src], idx[target]]
        indirect = total_indirect[idx[src], idx[target]]
        if abs(direct) > 0 or abs(indirect) > 0:
            rows.append(
                {
                    "source": src,
                    "target": target,
                    "direct_effect": float(direct),
                    "indirect_effect": float(indirect),
                    "total_effect": float(direct + indirect),
                }
            )
    return pd.DataFrame(rows)


def draw_path_diagram(path_df: pd.DataFrame, r2_df: pd.DataFrame, metric: str, label_suffix: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(12.4, 7.0))
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
            fontsize=9.8 if target else 8.8,
            fontweight="bold" if target else "normal",
            bbox={
                "boxstyle": "round,pad=0.30,rounding_size=0.08",
                "facecolor": "#fff7bc" if target else "#f7f7f7",
                "edgecolor": "#4d4d4d",
                "linewidth": 0.85,
            },
            zorder=6,
        )
    for _, row in r2_df.iterrows():
        if row["endogenous"] in NODE_POS:
            x, y = NODE_POS[row["endogenous"]]
            ax.text(x + 0.075, y + 0.075, f"R²={row['r2']:.2f}", fontsize=7.5, color="#2c3e50")
    for _, row in path_df.iterrows():
        src, dst = row["from"], row["to"]
        if src not in NODE_POS or dst not in NODE_POS:
            continue
        x1, y1 = NODE_POS[src]
        x2, y2 = NODE_POS[dst]
        coef = float(row["estimate"])
        color = "#d7301f" if coef < 0 else "#1a9850"
        lw = max(0.6, min(4.0, 0.55 + abs(coef) * 3.7))
        arrow = base.FancyArrowPatch(
            (x1 + 0.045, y1),
            (x2 - 0.055, y2),
            arrowstyle="-|>",
            connectionstyle=f"arc3,rad={PATH_RAD.get((src, dst), 0.0)}",
            mutation_scale=10.5,
            linewidth=lw,
            color=color,
            alpha=0.86,
            zorder=3,
        )
        ax.add_patch(arrow)
        mx = (x1 + x2) / 2.0
        my = (y1 + y2) / 2.0 + 0.025
        if abs(coef) >= 0.03:
            ax.text(
                mx,
                my,
                f"{coef:+.2f}",
                fontsize=7.0,
                ha="center",
                va="center",
                color=color,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 0.10},
                zorder=7,
            )
    ax.set_title(f"{metric} enhanced PLS-SEM ({label_suffix})", fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=280, bbox_inches="tight")
    plt.close(fig)


def write_readme(summary: pd.DataFrame) -> None:
    lines = [
        "# Enhanced SHAP-informed PLS-SEM for prepeak recovery time",
        "",
        "This folder contains an enhanced composite-based PLS-SEM analysis for GPP and RECO recovery time.",
        "It extends the baseline PLS-SEM by adding phenology/timing, pre-drought state, and post-peak recovery climate blocks.",
        "",
        "Latent/composite constructs:",
        "- Energy: SSRD, STRD, TMP",
        "- Atmospheric demand: VPD, Wind",
        "- Pre-peak water availability: Pre, SMrz, EVA",
        "- Drought severity: Duration, Intensity, OnsetRate, DaysBelowP20",
        "- Phenology/timing: hemisphere-adjusted season phase, LAI",
        "- Pre-drought state: flux baseline, flux variability, pre30 SMrz, pre30 VPD",
        "- Recovery climate: postpeak30 SMrz, VPD, TMP, Pre",
        "- Recovery time: single-indicator recovery duration",
        "",
        "Interpretation note:",
        "The added blocks are intended to test whether the weak RecoveryTime R² in the baseline model mainly came from omitted event timing, antecedent ecosystem state, and recovery-period hydrothermal conditions.",
        "",
        "Summary:",
        "```csv",
        summary.to_csv(index=False).strip(),
        "```",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    install_model()
    OUT.mkdir(parents=True, exist_ok=True)
    summaries = []
    for metric in METRICS:
        summaries.append(base.summarize_model(metric, None, n_boot=80))
        for biome in BIOMES:
            summaries.append(base.summarize_model(metric, biome, n_boot=80))
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT / "pls_sem_enhanced_model_summary.csv", index=False)
    base.build_overview(summary_df)
    write_readme(summary_df)
    print(OUT)


if __name__ == "__main__":
    main()
