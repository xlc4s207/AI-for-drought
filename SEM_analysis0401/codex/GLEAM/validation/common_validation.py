#!/usr/bin/env python3
"""Shared utilities for GLEAM SHAP validation analyses."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split

try:
    from lightgbm import LGBMRegressor
except Exception:  # pragma: no cover
    LGBMRegressor = None


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
VALIDATION_ROOT = ROOT / "validation"
TARGET = "t_recover_to_baseline_abs_peak"
BIOMES = ["Forest", "Grassland", "Savanna", "Cropland", "Shrubland"]
METRICS = ["GPP", "RECO"]
FEATURES = [
    "prepeak_total_precipitation_mean",
    "prepeak_total_evaporation_mean",
    "prepeak_temperature_2m_mean",
    "prepeak_VPD_mean",
    "prepeak_SMrz_mean",
    "prepeak_lai_total_mean",
    "prepeak_ssrd_mean",
    "prepeak_strd_mean",
    "prepeak_wind_speed_mean",
    "event_duration",
]
TABLES = {
    "GPP": ROOT / "data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet",
    "RECO": ROOT / "data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet",
}
SHAP_ROOTS = {
    "GPP": ROOT
    / "results/gpp_code1_flash_smrz_v20260401_onsetpeak_clean/prepeak_event_shap_sem_20260424/shap_by_biome",
    "RECO": ROOT
    / "results/reco_code1_flash_smrz_v20260401_mswepE_clean/prepeak_event_shap_sem_20260424/shap_by_biome",
}
SHORT_LABELS = {
    "prepeak_total_precipitation_mean": "PRE",
    "prepeak_total_evaporation_mean": "|EVA|",
    "prepeak_temperature_2m_mean": "TMP",
    "prepeak_VPD_mean": "VPD",
    "prepeak_SMrz_mean": "SMrz",
    "prepeak_lai_total_mean": "LAI",
    "prepeak_ssrd_mean": "SSRD",
    "prepeak_strd_mean": "STRD",
    "prepeak_wind_speed_mean": "WIND",
    "event_duration": "Duration",
}


@dataclass
class ModelBundle:
    metric: str
    biome: str
    model: object
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    r2_train: float
    r2_test: float


def short_label(feature: str) -> str:
    return SHORT_LABELS.get(feature, feature)


def feature_unit(feature: str) -> str:
    if "precipitation" in feature or "evaporation" in feature:
        return "mm"
    if feature == "prepeak_temperature_2m_mean":
        return "K"
    if feature == "prepeak_VPD_mean":
        return "kPa"
    if feature == "prepeak_SMrz_mean":
        return "m3/m3"
    if feature == "event_duration":
        return "days"
    return ""


def display_values(feature: str, values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if "precipitation" in feature:
        finite = values[np.isfinite(values)]
        if len(finite) and np.nanquantile(np.abs(finite), 0.99) < 1.0:
            return values * 1000.0
        return values
    if "evaporation" in feature:
        vals = np.abs(values)
        finite = vals[np.isfinite(vals)]
        if len(finite) and np.nanquantile(np.abs(finite), 0.99) < 1.0:
            return vals * 1000.0
        return vals
    if feature == "prepeak_VPD_mean":
        return values / 10.0
    return values


def axis_label(feature: str) -> str:
    unit = feature_unit(feature)
    label = short_label(feature)
    return f"{label} ({unit})" if unit else label


def load_metric_biome_frame(metric: str, biome: str, columns: list[str] | None = None) -> pd.DataFrame:
    read_columns = ["biome", TARGET, "lat", "lon"] + FEATURES
    if columns is not None:
        read_columns = list(dict.fromkeys(["biome", TARGET, "lat", "lon"] + columns))
    df = pd.read_parquet(TABLES[metric], columns=read_columns)
    df = df[df["biome"] == biome].copy()
    return df


def prepare_xy(metric: str, biome: str, max_rows: int, random_state: int) -> tuple[pd.DataFrame, pd.Series]:
    df = load_metric_biome_frame(metric, biome)
    cols = [c for c in FEATURES if c in df.columns]
    frame = df[cols + [TARGET]].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna(axis=0, how="any")
    if max_rows > 0 and len(frame) > max_rows:
        frame = frame.sample(n=max_rows, random_state=random_state).sort_index()
    X = frame[cols].copy()
    y = frame[TARGET].copy()
    return X, y


def fit_model(metric: str, biome: str, max_rows: int, random_state: int, n_estimators: int) -> ModelBundle:
    if LGBMRegressor is None:
        raise ImportError("lightgbm is required for validation response-curve analyses.")
    X, y = prepare_xy(metric, biome, max_rows=max_rows, random_state=random_state)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=random_state)
    model = LGBMRegressor(
        objective="regression",
        n_estimators=n_estimators,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=30,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=random_state,
        n_jobs=8,
        verbosity=-1,
    )
    model.fit(X_train, y_train)
    return ModelBundle(
        metric=metric,
        biome=biome,
        model=model,
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        r2_train=float(r2_score(y_train, model.predict(X_train))),
        r2_test=float(r2_score(y_test, model.predict(X_test))),
    )


def top_features(metric: str, biome: str, top_n: int) -> list[str]:
    path = SHAP_ROOTS[metric] / biome / "feature_importance.csv"
    imp = pd.read_csv(path)
    feats = [f for f in imp["feature"].tolist() if f in FEATURES]
    return feats[:top_n]


def quantile_grid(values: pd.Series, grid_size: int, low_q: float = 0.02, high_q: float = 0.98) -> np.ndarray:
    finite = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    finite = finite[np.isfinite(finite)]
    if len(finite) == 0:
        return np.array([], dtype=float)
    qs = np.linspace(low_q, high_q, grid_size)
    grid = np.unique(np.nanquantile(finite, qs))
    return grid.astype(float)


def save_curve_plot(
    path: Path,
    x: np.ndarray,
    y: np.ndarray,
    feature: str,
    title: str,
    ylabel: str,
    extra_lines: list[tuple[np.ndarray, np.ndarray]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    if extra_lines:
        for xs, ys in extra_lines:
            ax.plot(display_values(feature, xs), ys, color="#9fb7cc", alpha=0.18, linewidth=0.8)
    ax.plot(display_values(feature, x), y, color="#c83349", linewidth=2.2)
    ax.axhline(0.0, color="#777777", linestyle="--", linewidth=0.9, alpha=0.8)
    ax.set_xlabel(axis_label(feature))
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.16, linestyle="--")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def write_readme(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
