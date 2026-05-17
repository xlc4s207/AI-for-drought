#!/usr/bin/env python3
"""Run prepeak SHAP with grouped PCA and sequential orthogonalized inputs.

The script follows the original prepeak SHAP workflow, but restricts the source
variables to ten user-selected predictors and rebuilds the model inputs in two
collinearity-reduced forms.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

try:
    import shap  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError("This workflow requires shap.") from exc


ROOT = Path("/home/xulc/flash_drought")
GLEAM = ROOT / "process/SEM_analysis0401/codex/GLEAM"
CODE = GLEAM / "code"
OUT = GLEAM / "plots2/prepeak_shap_nomulticollinearity"
TARGET = "t_recover_to_baseline_abs_peak"
BIOMES = ("Forest", "Grassland", "Savanna", "Cropland", "Shrubland")
RANDOM_STATE = 42
ROW_LIMIT = 50000
SHAP_SAMPLE_SIZE = 5000
N_ESTIMATORS = 120
N_JOBS = 12

SHAP_ANALYSIS_PATH = CODE / "06_shap_analysis.py"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
SPEC = importlib.util.spec_from_file_location("shap_analysis_module", SHAP_ANALYSIS_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to import {SHAP_ANALYSIS_PATH}")
shap_analysis_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = shap_analysis_module
SPEC.loader.exec_module(shap_analysis_module)

COMMON_PATH = CODE / "sem_gleam_common.py"
COMMON_SPEC = importlib.util.spec_from_file_location("sem_gleam_common", COMMON_PATH)
if COMMON_SPEC is None or COMMON_SPEC.loader is None:
    raise RuntimeError(f"Unable to import {COMMON_PATH}")
common_module = importlib.util.module_from_spec(COMMON_SPEC)
sys.modules[COMMON_SPEC.name] = common_module
COMMON_SPEC.loader.exec_module(common_module)

filter_analysis_subset = shap_analysis_module.filter_analysis_subset
fit_tree_model = shap_analysis_module.fit_tree_model
resolve_model_backend = shap_analysis_module.resolve_model_backend
sample_for_shap = shap_analysis_module.sample_for_shap
finalize_feature_table = common_module.finalize_feature_table


@dataclass(frozen=True)
class MetricConfig:
    metric: str
    table: Path


METRICS = (
    MetricConfig("GPP", GLEAM / "data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet"),
    MetricConfig("RECO", GLEAM / "data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet"),
)

RAW_FEATURES = {
    "SSRD": "prepeak_ssrd_mean",
    "EVA": "prepeak_total_evaporation_mean",
    "TMP": "prepeak_temperature_2m_mean",
    "STRD": "prepeak_strd_mean",
    "SMrz": "prepeak_SMrz_mean",
    "Wind": "prepeak_wind_speed_mean",
    "VPD": "prepeak_VPD_mean",
    "Duration": "event_duration",
    "Pre": "prepeak_total_precipitation_mean",
    "Intensity": "event_intensity",
}

RAW_ORDER = ("SSRD", "EVA", "TMP", "STRD", "SMrz", "Wind", "VPD", "Duration", "Pre", "Intensity")

PCA_GROUPS = {
    "Energy": ("SSRD", "STRD", "TMP"),
    "Water": ("Pre", "EVA", "SMrz"),
    "AtmosDemand": ("VPD", "Wind"),
    "Event": ("Duration", "Intensity"),
}

ORTHOGONAL_SPECS = (
    ("SSRD_z", "SSRD", ()),
    ("Pre_z", "Pre", ()),
    ("Duration_z", "Duration", ()),
    ("Intensity_z", "Intensity", ()),
    ("Wind_z", "Wind", ()),
    ("STRD_resid_after_SSRD", "STRD", ("SSRD_z",)),
    ("TMP_resid_after_SSRD_STRD", "TMP", ("SSRD_z", "STRD_resid_after_SSRD")),
    ("VPD_resid_after_SSRD_TMP_Wind", "VPD", ("SSRD_z", "TMP_resid_after_SSRD_STRD", "Wind_z")),
    ("EVA_resid_after_SSRD_Pre_VPD", "EVA", ("SSRD_z", "Pre_z", "VPD_resid_after_SSRD_TMP_Wind")),
    ("SMrz_resid_after_Pre_EVA", "SMrz", ("Pre_z", "EVA_resid_after_SSRD_Pre_VPD")),
)

DISPLAY_LABELS = {
    "SSRD_z": "SSRD",
    "Pre_z": "Pre",
    "Duration_z": "Duration",
    "Intensity_z": "Intensity",
    "Wind_z": "Wind",
    "STRD_resid_after_SSRD": "STRD_resid",
    "TMP_resid_after_SSRD_STRD": "TMP_resid",
    "VPD_resid_after_SSRD_TMP_Wind": "VPD_resid",
    "EVA_resid_after_SSRD_Pre_VPD": "EVA_resid",
    "SMrz_resid_after_Pre_EVA": "SMrz_resid",
}


def standardize_raw(raw: pd.DataFrame) -> pd.DataFrame:
    scaler = StandardScaler()
    arr = scaler.fit_transform(raw.astype(float))
    return pd.DataFrame(arr, columns=raw.columns, index=raw.index)


def prepare_raw_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    work = df.copy()
    work[TARGET] = pd.to_numeric(work[TARGET], errors="coerce")
    cols = [RAW_FEATURES[label] for label in RAW_ORDER]
    for col in cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    precip_col = RAW_FEATURES["Pre"]
    if precip_col in work.columns:
        # Negative precipitation is physically impossible and usually indicates
        # an upstream fill value that survived feature extraction.
        work.loc[work[precip_col] < 0, precip_col] = np.nan
    work = work.dropna(subset=[TARGET]).reset_index(drop=True)
    raw = pd.DataFrame({label: work[RAW_FEATURES[label]] for label in RAW_ORDER})
    raw = raw.fillna(raw.median(numeric_only=True))
    raw = raw.replace([np.inf, -np.inf], np.nan).fillna(raw.median(numeric_only=True))
    raw = raw.astype(np.float32)
    y = work[TARGET].astype(np.float32)
    valid = raw.notna().all(axis=1) & y.notna()
    return raw.loc[valid].reset_index(drop=True), y.loc[valid].reset_index(drop=True)


def build_group_pca_inputs(raw: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    z = standardize_raw(raw)
    frames: list[pd.DataFrame] = []
    records: list[dict[str, object]] = []
    variance_records: list[dict[str, object]] = []
    for group, labels in PCA_GROUPS.items():
        group_z = z.loc[:, list(labels)]
        pca = PCA()
        scores = pca.fit_transform(group_z)
        cum = np.cumsum(pca.explained_variance_ratio_)
        # Keep one interpretable mechanism axis per group. Retaining PC2/PC3 is
        # mathematically orthogonal within each group, but can reintroduce
        # cross-group VIF through ecological coupling.
        n_keep = 1
        score_cols = [f"{group}_PC{i + 1}" for i in range(n_keep)]
        frames.append(pd.DataFrame(scores[:, :n_keep], columns=score_cols, index=raw.index))
        for i in range(len(labels)):
            variance_records.append(
                {
                    "group": group,
                    "component": f"{group}_PC{i + 1}",
                    "explained_variance_ratio": float(pca.explained_variance_ratio_[i]),
                    "cumulative_explained_variance": float(cum[i]),
                    "kept": i < n_keep,
                }
            )
            for label, loading in zip(labels, pca.components_[i]):
                records.append(
                    {
                        "group": group,
                        "component": f"{group}_PC{i + 1}",
                        "source_feature": label,
                        "loading": float(loading),
                        "explained_variance_ratio": float(pca.explained_variance_ratio_[i]),
                        "kept": i < n_keep,
                    }
                )
    X = pd.concat(frames, axis=1).astype(np.float32)
    pd.DataFrame(records).to_csv(out_dir / "pca_loadings.csv", index=False)
    pd.DataFrame(variance_records).to_csv(out_dir / "pca_explained_variance.csv", index=False)
    return X, pd.DataFrame(records)


def build_orthogonal_inputs(raw: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    z = standardize_raw(raw)
    built: dict[str, np.ndarray] = {}
    records: list[dict[str, object]] = []
    for new_name, source_label, predictors in ORTHOGONAL_SPECS:
        y = z[source_label].to_numpy(dtype=float)
        if predictors:
            P = np.column_stack([built[p] for p in predictors])
            model = LinearRegression().fit(P, y)
            pred = model.predict(P)
            resid = y - pred
            ss_res = float(np.sum((y - pred) ** 2))
            ss_tot = float(np.sum((y - np.mean(y)) ** 2))
            r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
            for predictor, coef in zip(predictors, model.coef_):
                records.append(
                    {
                        "orthogonal_feature": new_name,
                        "source_feature": source_label,
                        "predictor": predictor,
                        "coefficient": float(coef),
                        "intercept": float(model.intercept_),
                        "r2_removed_from_source": r2,
                    }
                )
            values = resid
        else:
            records.append(
                {
                    "orthogonal_feature": new_name,
                    "source_feature": source_label,
                    "predictor": "",
                    "coefficient": np.nan,
                    "intercept": 0.0,
                    "r2_removed_from_source": 0.0,
                }
            )
            values = y
        values = (values - np.mean(values)) / (np.std(values) if np.std(values) > 0 else 1.0)
        built[new_name] = values.astype(np.float32)
    X = pd.DataFrame(built, index=raw.index).astype(np.float32)
    model_df = pd.DataFrame(records)
    model_df.to_csv(out_dir / "orthogonal_decomposition_models.csv", index=False)
    return X, model_df


def compute_vif(X: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    values = X.astype(float).to_numpy()
    for i, feature in enumerate(X.columns):
        y = values[:, i]
        others = np.delete(values, i, axis=1)
        if others.shape[1] == 0:
            vif = 1.0
            r2 = 0.0
        else:
            model = LinearRegression().fit(others, y)
            r2 = float(model.score(others, y))
            vif = float(1.0 / max(1.0 - r2, 1e-12))
        rows.append({"feature": feature, "r2_with_other_features": r2, "vif": vif})
    return pd.DataFrame(rows).sort_values("vif", ascending=False).reset_index(drop=True)


def compute_split_metrics(X: pd.DataFrame, y: pd.Series, backend: str) -> dict[str, float | int]:
    test_size = max(1, int(round(len(X) * 0.2)))
    test_size = min(test_size, len(X) - 1)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=RANDOM_STATE)
    model = fit_tree_model(X_train, y_train, backend=backend, random_state=RANDOM_STATE, n_estimators=N_ESTIMATORS, n_jobs=N_JOBS)
    return {
        "r2_train_split": float(model.score(X_train, y_train)),
        "r2_holdout_split": float(model.score(X_test, y_test)),
        "split_train_rows": int(len(X_train)),
        "split_test_rows": int(len(X_test)),
    }


def save_importance_plot(importance: pd.DataFrame, path: Path) -> None:
    top = importance.iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.8, max(4.5, len(top) * 0.38)))
    ax.barh(top["display_label"], top["mean_abs_shap"], color="#386cb0")
    ax.set_xlabel("mean(|SHAP|)")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(path, dpi=240)
    plt.close(fig)


def save_beeswarm(shap_values: np.ndarray, sample: pd.DataFrame, feature_order: list[str], path: Path) -> None:
    original_columns = sample.columns.tolist()
    sample = sample.loc[:, feature_order].copy()
    shap_values = shap_values[:, [original_columns.index(f) for f in feature_order]]
    names = [DISPLAY_LABELS.get(f, f) for f in feature_order]
    fig, ax = plt.subplots(figsize=(8.6, max(4.8, len(feature_order) * 0.38)))
    plt.sca(ax)
    shap.summary_plot(shap_values, sample, feature_names=names, show=False, max_display=len(feature_order), plot_size=None)
    fig.tight_layout()
    fig.savefig(path, dpi=240, bbox_inches="tight")
    plt.close(fig)


def save_dependence_plots(sample: pd.DataFrame, shap_df: pd.DataFrame, feature_order: list[str], out_dir: Path) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old_png in out_dir.glob("*.png"):
        old_png.unlink()
    rows: list[dict[str, object]] = []
    for feature in feature_order:
        x = pd.to_numeric(sample[feature], errors="coerce").to_numpy(dtype=float)
        y = pd.to_numeric(shap_df[feature], errors="coerce").to_numpy(dtype=float)
        finite = np.isfinite(x) & np.isfinite(y)
        x = x[finite]
        y = y[finite]
        order = np.argsort(x)
        x = x[order]
        y = y[order]
        fig, ax = plt.subplots(figsize=(6.4, 4.6))
        ax.axhline(0, color="#777777", lw=0.9, ls="--")
        ax.scatter(x, y, s=10, alpha=0.35, color="#2f6b8a", edgecolors="none")
        if len(x) >= 25:
            window = max(10, len(x) // 35)
            trend = pd.Series(y).rolling(window=window, center=True, min_periods=5).median().to_numpy()
            ax.plot(x, trend, color="#c83349", lw=1.8)
        ax.set_xlabel(DISPLAY_LABELS.get(feature, feature))
        ax.set_ylabel(f"SHAP value for {DISPLAY_LABELS.get(feature, feature)}")
        ax.set_title(DISPLAY_LABELS.get(feature, feature))
        fig.tight_layout()
        path = out_dir / f"{feature}.png"
        fig.savefig(path, dpi=220)
        plt.close(fig)
        rows.append({"feature": feature, "display_label": DISPLAY_LABELS.get(feature, feature), "plot_path": str(path), "points": int(len(x))})
    return pd.DataFrame(rows)


def fit_explain_save(X: pd.DataFrame, y: pd.Series, output_dir: Path, method: str, metric: str, biome: str, transform_note: pd.DataFrame | None = None) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    backend = resolve_model_backend("lightgbm")
    split_metrics = compute_split_metrics(X, y, backend)
    model = fit_tree_model(X, y, backend=backend, random_state=RANDOM_STATE, n_estimators=N_ESTIMATORS, n_jobs=N_JOBS)
    sample = sample_for_shap(X, sample_size=SHAP_SAMPLE_SIZE, random_state=RANDOM_STATE)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(sample)
    if isinstance(shap_values, list):
        shap_values = shap_values[0]
    shap_values = np.asarray(shap_values)
    shap_df = pd.DataFrame(shap_values, columns=sample.columns, index=sample.index)
    importance = pd.DataFrame({"feature": sample.columns, "mean_abs_shap": np.abs(shap_values).mean(axis=0)})
    importance = importance.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
    importance["rank"] = np.arange(1, len(importance) + 1)
    total = float(importance["mean_abs_shap"].sum())
    importance["percent"] = importance["mean_abs_shap"] / total * 100.0 if total > 0 else np.nan
    importance["display_label"] = importance["feature"].map(lambda x: DISPLAY_LABELS.get(x, x))
    feature_order = importance["feature"].tolist()

    sample.to_parquet(output_dir / "dependence_sample_features.parquet", index=True)
    shap_df.to_parquet(output_dir / "dependence_sample_shap_values.parquet", index=True)
    sample.add_prefix("feature__").join(shap_df.add_prefix("shap__"), how="left").to_parquet(output_dir / "dependence_plot_data.parquet", index=True)
    importance.to_csv(output_dir / "feature_importance.csv", index=False)
    compute_vif(X).to_csv(output_dir / "vif_after_transform.csv", index=False)
    X.corr(method="spearman").to_csv(output_dir / "spearman_after_transform.csv")
    save_importance_plot(importance, output_dir / "feature_importance_bar.png")
    save_beeswarm(shap_values, sample, feature_order, output_dir / "feature_importance_beeswarm.png")
    dep_index = save_dependence_plots(sample, shap_df, feature_order, output_dir / "dependence_plots")
    dep_index.to_csv(output_dir / "dependence_plot_index.csv", index=False)

    summary = {
        "method": method,
        "metric": metric,
        "biome": biome,
        "rows": int(len(X)),
        "feature_count": int(X.shape[1]),
        "model_backend": backend,
        "n_estimators": N_ESTIMATORS,
        "shap_sample_rows": int(len(sample)),
        **split_metrics,
    }
    (output_dir / "run_summary.txt").write_text("\n".join(f"{k}={v}" for k, v in summary.items()), encoding="utf-8")
    if transform_note is not None:
        transform_note.to_csv(output_dir / "transform_detail.csv", index=False)
    return summary


def run_one(df_metric: pd.DataFrame, metric: str, biome: str, method: str) -> dict[str, object]:
    sub = filter_analysis_subset(df_metric, metric=metric, code_id="code1", biome=biome, drought_type="flash", soil_layer="SMrz")
    if len(sub) > ROW_LIMIT:
        sub = sub.head(ROW_LIMIT).copy()
    raw, y = prepare_raw_xy(sub)
    method_dir = OUT / method / metric / biome
    method_dir.mkdir(parents=True, exist_ok=True)
    if method == "group_pca":
        X, detail = build_group_pca_inputs(raw, method_dir)
    elif method == "orthogonal_decomposition":
        X, detail = build_orthogonal_inputs(raw, method_dir)
    else:
        raise ValueError(method)
    raw.corr(method="spearman").to_csv(method_dir / "source_raw_spearman_corr.csv")
    return fit_explain_save(X, y, method_dir, method, metric, biome, detail)


def write_readme(summaries: pd.DataFrame) -> None:
    lines = [
        "# Prepeak SHAP without explicit multicollinearity",
        "",
        "Source predictors are restricted to: SSRD, EVA, TMP, STRD, SMrz, Wind, VPD, Duration, Pre, Intensity.",
        "",
        "Two transformed-input versions are provided:",
        "",
        "- `group_pca`: PCA within mechanism groups: Energy(SSRD/STRD/TMP), Water(Pre/EVA/SMrz), AtmosDemand(VPD/Wind), Event(Duration/Intensity). Only PC1 is retained for each group to provide four low-collinearity mechanism axes. Loadings and explained variance are saved per metric/biome.",
        "- `orthogonal_decomposition`: sequential residualization. SSRD, Pre, Duration, Intensity, and Wind are retained as standardized anchors; STRD, TMP, VPD, EVA, and SMrz are residualized following the physical ordering recorded in `orthogonal_decomposition_models.csv`.",
        "",
        "Each metric/biome folder contains `feature_importance.csv`, `feature_importance_beeswarm.png`, `feature_importance_bar.png`, `dependence_plots/`, `vif_after_transform.csv`, and `run_summary.txt`.",
        "",
        "## Model summary",
        "",
        "```csv",
        summaries.to_csv(index=False).strip(),
        "```",
        "",
    ]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    for cfg in METRICS:
        print(f"[LOAD] {cfg.metric}: {cfg.table}")
        df_metric = finalize_feature_table(pd.read_parquet(cfg.table))
        for method in ("group_pca", "orthogonal_decomposition"):
            for biome in BIOMES:
                print(f"[RUN] {method} | {cfg.metric} | {biome}")
                summaries.append(run_one(df_metric, cfg.metric, biome, method))
                print(f"[DONE] {method} | {cfg.metric} | {biome}")
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT / "nomulticollinearity_model_summary.csv", index=False)
    write_readme(summary_df)
    print(f"[DONE] outputs saved under {OUT}")


if __name__ == "__main__":
    main()
