#!/usr/bin/env python3
"""Compare direct SEM candidate sets: SHAP top5 vs top3 environmental + event timing."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
OUT = ROOT / "plots2/SEM/sem_prepeak_direct_candidate_comparison_20260506"
IMPORTANCE = ROOT / "plots2/prepeak_shap_summary_20260502/shap_importance_percent_bars_5biomes_gpp_vs_reco.csv"
TOP5_R2 = ROOT / "plots2/SEM/sem_prepeak_shap_top5_direct_20260506/tables/sem_prepeak_shap_top5_direct_r2_gpp_reco.csv"
EVENT_R2 = ROOT / "plots2/SEM/sem_prepeak_ssrd_eventaware_20260506/tables/sem_prepeak_ssrd_eventaware_r2_gpp_reco.csv"
TARGET = "t_recover_to_baseline_abs_peak"
BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
METRICS = ["GPP", "RECO"]
TABLES = {
    "GPP": ROOT / "data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet",
    "RECO": ROOT / "data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet",
}
EVENT_FEATURES = ["event_duration", "event_intensity"]
ENV_FEATURES = {
    "prepeak_total_precipitation_mean",
    "prepeak_total_evaporation_mean",
    "prepeak_temperature_2m_mean",
    "prepeak_VPD_mean",
    "prepeak_SMrz_mean",
    "prepeak_ssrd_mean",
    "prepeak_strd_mean",
    "prepeak_wind_speed_mean",
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
}


def label(name: str) -> str:
    return LABELS.get(name, name)


def zscore(frame: pd.DataFrame) -> pd.DataFrame:
    numeric = frame.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    numeric = numeric.dropna(axis=0, how="any")
    std = numeric.std(ddof=0).replace(0, np.nan)
    return ((numeric - numeric.mean()) / std).dropna(axis=1, how="any")


def select_top3_env_plus_events(importance: pd.DataFrame, metric: str, biome: str) -> list[str]:
    subset = importance[(importance["metric"] == metric) & (importance["biome"] == biome)].copy()
    env = subset[subset["feature"].isin(ENV_FEATURES)].sort_values("rank")
    features = list(env.head(3)["feature"]) + EVENT_FEATURES
    return features


def load_metric_biome(metric: str, biome: str, features: list[str]) -> pd.DataFrame:
    columns = sorted(set([TARGET, "biome"] + features))
    df = pd.read_parquet(TABLES[metric], columns=columns)
    df = df[df["biome"] == biome].drop(columns=["biome"]).reset_index(drop=True)
    return zscore(df)


def fit(data: pd.DataFrame, features: list[str], metric: str, biome: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    frame = data[[TARGET] + features].dropna(axis=0, how="any")
    x = frame[features].to_numpy(dtype=float)
    y = frame[TARGET].to_numpy(dtype=float)
    reg = LinearRegression()
    reg.fit(x, y)
    pred = reg.predict(x)
    resid = y - pred
    n, p = x.shape
    sigma2 = float(np.sum(resid**2) / max(n - p - 1, 1))
    x_design = np.column_stack([np.ones(n), x])
    xtx_inv = np.linalg.pinv(x_design.T @ x_design)
    se = np.sqrt(np.diag(xtx_inv)[1:] * sigma2)
    paths = []
    for rank, (feature, coef, stderr) in enumerate(zip(features, reg.coef_, se, strict=True), start=1):
        z_value = float(coef / stderr) if stderr > 0 else np.nan
        p_value = float(2.0 * stats.norm.sf(abs(z_value))) if np.isfinite(z_value) else np.nan
        paths.append(
            {
                "metric": metric,
                "biome": biome,
                "model": "top3_env_plus_duration_intensity",
                "rank": rank,
                "feature": feature,
                "label": label(feature),
                "estimate": float(coef),
                "std_err": float(stderr),
                "z_value": z_value,
                "p_value": p_value,
                "significance": "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "",
            }
        )
    train, test = train_test_split(frame, test_size=0.2, random_state=42)
    reg2 = LinearRegression()
    reg2.fit(train[features], train[TARGET])
    r2 = {
        "metric": metric,
        "biome": biome,
        "model": "top3_env_plus_duration_intensity",
        "rows": len(frame),
        "holdout_r2": float(reg2.score(test[features], test[TARGET])),
        "train_r2": float(reg2.score(train[features], train[TARGET])),
        "predictor_count": len(features),
        "features": ", ".join(label(f) for f in features),
    }
    return paths, r2


def save_comparison(r2: pd.DataFrame) -> pd.DataFrame:
    comp = r2.copy()
    top5 = pd.read_csv(TOP5_R2)[["metric", "biome", "holdout_r2", "top5_features"]].rename(
        columns={"holdout_r2": "top5_direct_r2"}
    )
    event = pd.read_csv(EVENT_R2)[["metric", "biome", "holdout_r2"]].rename(columns={"holdout_r2": "eventaware_r2"})
    comp = comp.merge(top5, on=["metric", "biome"], how="left").merge(event, on=["metric", "biome"], how="left")
    comp["gain_vs_top5_direct"] = comp["holdout_r2"] - comp["top5_direct_r2"]
    comp["gain_vs_eventaware"] = comp["holdout_r2"] - comp["eventaware_r2"]
    comp.to_csv(OUT / "tables/sem_prepeak_direct_candidate_r2_comparison.csv", index=False)

    fig, ax = plt.subplots(figsize=(10.6, 5.2))
    labels = [f"{m}\n{b}" for m, b in zip(comp["metric"], comp["biome"], strict=True)]
    x = np.arange(len(comp))
    width = 0.25
    ax.bar(x - width, comp["top5_direct_r2"], width=width, color="#74c476", label="SHAP top5 direct")
    ax.bar(x, comp["holdout_r2"], width=width, color="#fdae6b", label="Top3 env + event")
    ax.bar(x + width, comp["eventaware_r2"], width=width, color="#fb6a4a", label="Event-aware")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Holdout R2")
    ax.set_title("Direct SEM candidate comparison")
    ax.grid(axis="y", linestyle="--", alpha=0.22)
    ax.legend(frameon=False, ncol=3)
    fig.tight_layout()
    fig.savefig(OUT / "figures/sem_prepeak_direct_candidate_r2_comparison.png", dpi=300)
    plt.close(fig)
    return comp


def write_readme(comp: pd.DataFrame) -> None:
    lines = [
        "# Direct SEM candidate comparison",
        "",
        "This folder compares two compact SHAP-informed direct SEM candidates against the event-aware model.",
        "",
        "Candidate A: `Recovery time ~ SHAP top5 predictors`.",
        "",
        "Candidate B: `Recovery time ~ SHAP top3 environmental predictors + Duration + Intensity`.",
        "",
        "The event-aware model generally retains the highest explanatory power because it includes a broader but still interpretable predictor set. The compact direct candidates are useful for a clearer confirmatory path interpretation.",
        "",
        "## R2 comparison",
        "",
        comp.to_csv(index=False),
    ]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    importance = pd.read_csv(IMPORTANCE)
    paths_all = []
    r2_rows = []
    for metric in METRICS:
        for biome in BIOMES:
            features = select_top3_env_plus_events(importance, metric, biome)
            data = load_metric_biome(metric, biome, features)
            paths, r2 = fit(data, features, metric, biome)
            paths_all.extend(paths)
            r2_rows.append(r2)
    paths = pd.DataFrame(paths_all)
    r2 = pd.DataFrame(r2_rows)
    paths.to_csv(OUT / "tables/sem_prepeak_top3_env_plus_event_paths.csv", index=False)
    r2.to_csv(OUT / "tables/sem_prepeak_top3_env_plus_event_r2.csv", index=False)
    comp = save_comparison(r2)
    write_readme(comp)
    print(OUT)


if __name__ == "__main__":
    main()
