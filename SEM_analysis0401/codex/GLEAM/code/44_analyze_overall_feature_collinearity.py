#!/usr/bin/env python3
"""Analyze feature collinearity for 0401 overall SHAP sample tables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
RESULT_ROOT = PROJECT_ROOT / "results"
INPUT_ROOT = RESULT_ROOT / "overall_shap_results_20260502"
OUTPUT_ROOT = INPUT_ROOT / "collinearity_analysis_20260502"

SCENARIOS = {
    "gpp_prepeak": INPUT_ROOT / "gpp_prepeak/overall_dependence_sample_features.parquet",
    "gpp_recovery": INPUT_ROOT / "gpp_recovery/overall_dependence_sample_features.parquet",
    "reco_prepeak": INPUT_ROOT / "reco_prepeak/overall_dependence_sample_features.parquet",
    "reco_recovery": INPUT_ROOT / "reco_recovery/overall_dependence_sample_features.parquet",
}

FEATURE_LABELS = {
    "prepeak_total_precipitation_mean": "PRE",
    "prepeak_total_evaporation_mean": "EVA",
    "prepeak_temperature_2m_mean": "TMP",
    "prepeak_VPD_mean": "VPD",
    "prepeak_SMrz_mean": "SMrz",
    "prepeak_lai_total_mean": "LAI",
    "prepeak_ssrd_mean": "SSRD",
    "prepeak_strd_mean": "STRD",
    "prepeak_wind_speed_mean": "WIND",
    "recoverywin_total_precipitation_mean": "PRE",
    "recoverywin_total_evaporation_mean": "EVA",
    "recoverywin_temperature_2m_mean": "TMP",
    "recoverywin_VPD_mean": "VPD",
    "recoverywin_SMrz_mean": "SMrz",
    "recoverywin_lai_total_mean": "LAI",
    "recoverywin_ssrd_mean": "SSRD",
    "recoverywin_strd_mean": "STRD",
    "recoverywin_wind_speed_mean": "WIND",
    "event_onset_days": "ONS",
    "event_duration": "DUR",
    "event_intensity": "INT",
}


@dataclass
class CollinearityBundle:
    pearson: pd.DataFrame
    spearman: pd.DataFrame
    vif: pd.DataFrame
    summary: pd.DataFrame
    condition: pd.DataFrame
    top_pairs: pd.DataFrame


def short_name(name: str) -> str:
    return FEATURE_LABELS.get(name, name)


def numeric_feature_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        if col == "biome":
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            cols.append(col)
    return cols


def standardize(values: np.ndarray) -> np.ndarray:
    x = values.astype(float, copy=True)
    mean = np.nanmean(x, axis=0)
    std = np.nanstd(x, axis=0, ddof=0)
    std[std < 1e-12] = np.nan
    return (x - mean) / std


def compute_vif(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    x = df[features].apply(pd.to_numeric, errors="coerce")
    rows: list[dict[str, object]] = []
    for feature in features:
        y = x[feature].to_numpy(dtype=float)
        other_cols = [c for c in features if c != feature]
        if not other_cols:
            rows.append({"feature": feature, "label": short_name(feature), "vif": np.nan, "r2": np.nan})
            continue
        X = x[other_cols].to_numpy(dtype=float)
        valid = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
        yv = y[valid]
        Xv = X[valid]
        if len(yv) <= len(other_cols) + 2:
            rows.append({"feature": feature, "label": short_name(feature), "vif": np.nan, "r2": np.nan})
            continue
        if np.nanstd(yv) < 1e-12:
            rows.append({"feature": feature, "label": short_name(feature), "vif": np.inf, "r2": 1.0})
            continue
        Xv = np.column_stack([np.ones(len(Xv)), Xv])
        coef, *_ = np.linalg.lstsq(Xv, yv, rcond=None)
        pred = Xv @ coef
        sst = float(np.sum((yv - np.mean(yv)) ** 2))
        sse = float(np.sum((yv - pred) ** 2))
        if sst <= 1e-12:
            r2 = 1.0
        else:
            r2 = max(0.0, min(1.0, 1.0 - sse / sst))
        vif = np.inf if r2 >= 0.999999 else 1.0 / max(1e-12, (1.0 - r2))
        rows.append({"feature": feature, "label": short_name(feature), "vif": vif, "r2": r2})
    out = pd.DataFrame(rows).sort_values("vif", ascending=False, na_position="last").reset_index(drop=True)
    out["vif_flag"] = pd.cut(
        out["vif"],
        bins=[-np.inf, 5, 10, np.inf],
        labels=["low", "moderate", "high"],
    )
    return out


def compute_condition_metrics(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    x = df[features].apply(pd.to_numeric, errors="coerce").dropna()
    if x.empty:
        return pd.DataFrame([{"n_rows_used": 0, "condition_number": np.nan, "min_eigenvalue": np.nan, "max_eigenvalue": np.nan}])
    z = standardize(x.to_numpy())
    valid_cols = np.all(np.isfinite(z), axis=0)
    z = z[:, valid_cols]
    if z.shape[1] == 0:
        return pd.DataFrame([{"n_rows_used": len(x), "condition_number": np.nan, "min_eigenvalue": np.nan, "max_eigenvalue": np.nan}])
    corr = np.corrcoef(z, rowvar=False)
    eigvals = np.linalg.eigvalsh(corr)
    min_eig = float(np.min(eigvals))
    max_eig = float(np.max(eigvals))
    cond = np.inf if min_eig <= 1e-12 else float(np.sqrt(max_eig / min_eig))
    return pd.DataFrame(
        [
            {
                "n_rows_used": len(x),
                "n_features_used": int(z.shape[1]),
                "condition_number": cond,
                "min_eigenvalue": min_eig,
                "max_eigenvalue": max_eig,
            }
        ]
    )


def flatten_top_pairs(corr: pd.DataFrame, method: str, top_n: int = 15) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    cols = list(corr.columns)
    for i, left in enumerate(cols):
        for j in range(i + 1, len(cols)):
            right = cols[j]
            value = float(corr.iloc[i, j])
            rows.append(
                {
                    "method": method,
                    "feature_1": left,
                    "label_1": short_name(left),
                    "feature_2": right,
                    "label_2": short_name(right),
                    "correlation": value,
                    "abs_correlation": abs(value),
                }
            )
    out = pd.DataFrame(rows).sort_values("abs_correlation", ascending=False).reset_index(drop=True)
    return out.head(top_n)


def build_summary(
    df: pd.DataFrame,
    features: list[str],
    vif_df: pd.DataFrame,
    pearson_pairs: pd.DataFrame,
    spearman_pairs: pd.DataFrame,
    condition_df: pd.DataFrame,
) -> pd.DataFrame:
    near_high = vif_df.loc[vif_df["vif"] >= 10, "label"].tolist()
    near_mid = vif_df.loc[(vif_df["vif"] >= 5) & (vif_df["vif"] < 10), "label"].tolist()
    top_vif = vif_df.iloc[0]
    top_p = pearson_pairs.iloc[0] if not pearson_pairs.empty else None
    top_s = spearman_pairs.iloc[0] if not spearman_pairs.empty else None
    cond = condition_df.iloc[0]
    return pd.DataFrame(
        [
            {
                "n_samples": len(df),
                "n_features": len(features),
                "top_vif_feature": top_vif["feature"],
                "top_vif_label": top_vif["label"],
                "top_vif": float(top_vif["vif"]),
                "top_pearson_pair": "" if top_p is None else f"{top_p['label_1']} vs {top_p['label_2']}",
                "top_pearson_abs_r": np.nan if top_p is None else float(top_p["abs_correlation"]),
                "top_spearman_pair": "" if top_s is None else f"{top_s['label_1']} vs {top_s['label_2']}",
                "top_spearman_abs_rho": np.nan if top_s is None else float(top_s["abs_correlation"]),
                "high_vif_features": "; ".join(near_high),
                "moderate_vif_features": "; ".join(near_mid),
                "condition_number": float(cond["condition_number"]),
            }
        ]
    )


def compute_bundle(df: pd.DataFrame, features: list[str]) -> CollinearityBundle:
    numeric_df = df[features].apply(pd.to_numeric, errors="coerce")
    pearson = numeric_df.corr(method="pearson")
    spearman = numeric_df.corr(method="spearman")
    vif_df = compute_vif(df, features)
    condition_df = compute_condition_metrics(df, features)
    pearson_pairs = flatten_top_pairs(pearson, method="pearson")
    spearman_pairs = flatten_top_pairs(spearman, method="spearman")
    pair_df = pd.concat([pearson_pairs, spearman_pairs], ignore_index=True)
    summary = build_summary(df, features, vif_df, pearson_pairs, spearman_pairs, condition_df)
    return CollinearityBundle(
        pearson=pearson,
        spearman=spearman,
        vif=vif_df,
        summary=summary,
        condition=condition_df,
        top_pairs=pair_df,
    )


def rename_matrix(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.index = [short_name(x) for x in out.index]
    out.columns = [short_name(x) for x in out.columns]
    return out


def plot_heatmap(corr: pd.DataFrame, output_path: Path, title: str) -> None:
    plot_df = rename_matrix(corr)
    matrix = plot_df.to_numpy(dtype=float)
    labels = list(plot_df.columns)
    fig, ax = plt.subplots(figsize=(0.9 * len(labels) + 2.5, 0.8 * len(labels) + 2.0))
    im = ax.imshow(matrix, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_title(title)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=7)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Correlation")
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_bundle(bundle: CollinearityBundle, out_dir: Path, prefix: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rename_matrix(bundle.pearson).to_csv(out_dir / f"{prefix}_pearson_corr.csv")
    rename_matrix(bundle.spearman).to_csv(out_dir / f"{prefix}_spearman_corr.csv")
    bundle.vif.to_csv(out_dir / f"{prefix}_vif.csv", index=False)
    bundle.condition.to_csv(out_dir / f"{prefix}_condition.csv", index=False)
    bundle.top_pairs.to_csv(out_dir / f"{prefix}_top_pairs.csv", index=False)
    bundle.summary.to_csv(out_dir / f"{prefix}_summary.csv", index=False)
    plot_heatmap(bundle.pearson, out_dir / f"{prefix}_pearson_heatmap.png", f"{prefix} Pearson Correlation")
    plot_heatmap(bundle.spearman, out_dir / f"{prefix}_spearman_heatmap.png", f"{prefix} Spearman Correlation")


def write_readme(scenario: str, scenario_dir: Path, overall_bundle: CollinearityBundle, biome_summaries: pd.DataFrame) -> None:
    overall = overall_bundle.summary.iloc[0]
    pearson_pairs = overall_bundle.top_pairs.loc[overall_bundle.top_pairs["method"] == "pearson"].head(5)
    spearman_pairs = overall_bundle.top_pairs.loc[overall_bundle.top_pairs["method"] == "spearman"].head(5)
    lines = [
        f"# {scenario} collinearity summary",
        "",
        "## Overall",
        f"- Samples: {int(overall['n_samples'])}",
        f"- Features: {int(overall['n_features'])}",
        f"- Top VIF: {overall['top_vif_label']} ({overall['top_vif']:.2f})",
        f"- Strongest Pearson pair: {overall['top_pearson_pair']} (|r|={overall['top_pearson_abs_r']:.3f})",
        f"- Strongest Spearman pair: {overall['top_spearman_pair']} (|rho|={overall['top_spearman_abs_rho']:.3f})",
        f"- Condition number: {overall['condition_number']:.2f}",
        f"- High VIF features: {overall['high_vif_features'] or 'None'}",
        f"- Moderate VIF features: {overall['moderate_vif_features'] or 'None'}",
        "",
        "## Top Pearson pairs",
    ]
    for _, row in pearson_pairs.iterrows():
        lines.append(f"- {row['label_1']} vs {row['label_2']}: r={row['correlation']:.3f}")
    lines.append("")
    lines.append("## Top Spearman pairs")
    for _, row in spearman_pairs.iterrows():
        lines.append(f"- {row['label_1']} vs {row['label_2']}: rho={row['correlation']:.3f}")
    lines.append("")
    lines.append("## By biome")
    for _, row in biome_summaries.sort_values("biome").iterrows():
        lines.append(
            "- "
            f"{row['biome']}: top VIF {row['top_vif_label']}={row['top_vif']:.2f}; "
            f"top Pearson {row['top_pearson_pair']} (|r|={row['top_pearson_abs_r']:.3f}); "
            f"condition={row['condition_number']:.2f}"
        )
    (scenario_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    all_scenario_summary: list[pd.DataFrame] = []
    all_biome_summary: list[pd.DataFrame] = []

    for scenario, parquet_path in SCENARIOS.items():
        scenario_dir = OUTPUT_ROOT / scenario
        by_biome_dir = scenario_dir / "by_biome"
        df = pd.read_parquet(parquet_path)
        features = numeric_feature_columns(df)

        overall_bundle = compute_bundle(df, features)
        write_bundle(overall_bundle, scenario_dir, prefix="overall")

        overall_summary = overall_bundle.summary.copy()
        overall_summary.insert(0, "scenario", scenario)
        overall_summary.insert(1, "scope", "overall")
        all_scenario_summary.append(overall_summary)

        biome_summaries: list[pd.DataFrame] = []
        for biome, biome_df in df.groupby("biome", sort=True):
            biome_bundle = compute_bundle(biome_df, features)
            safe_biome = biome.replace("/", "_")
            biome_dir = by_biome_dir / safe_biome
            write_bundle(biome_bundle, biome_dir, prefix=safe_biome)
            biome_summary = biome_bundle.summary.copy()
            biome_summary.insert(0, "scenario", scenario)
            biome_summary.insert(1, "scope", "biome")
            biome_summary.insert(2, "biome", biome)
            biome_summaries.append(biome_summary)
            all_biome_summary.append(biome_summary)

        biome_summary_df = pd.concat(biome_summaries, ignore_index=True)
        biome_summary_df.to_csv(scenario_dir / "by_biome_summary.csv", index=False)
        write_readme(scenario, scenario_dir, overall_bundle, biome_summary_df)

    combined_overall = pd.concat(all_scenario_summary, ignore_index=True)
    combined_biome = pd.concat(all_biome_summary, ignore_index=True)
    combined_overall.to_csv(OUTPUT_ROOT / "all_scenarios_overall_summary.csv", index=False)
    combined_biome.to_csv(OUTPUT_ROOT / "all_scenarios_by_biome_summary.csv", index=False)


if __name__ == "__main__":
    main()
