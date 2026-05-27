#!/usr/bin/env python3
"""Build PLS-SEM using orthogonal-decomposition prepeak variables.

The construct layout follows the baseline PLS-SEM, but the indicators are the
low-collinearity variables used in
`plots2/prepeak_shap_nomulticollinearity/orthogonal_decomposition`.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_pls_sem_prepeak_20260514 as base  # noqa: E402


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
OUT = ROOT / "plots2/SEM/sem_prepeak_pls_sem_orthogonal_20260517"
TARGET = base.TARGET
BIOMES = base.BIOMES
METRICS = base.METRICS
TABLES = base.TABLES
DATA_CACHE: dict[str, pd.DataFrame] = {}
N_BOOT = 20

SOURCE_RAW_FEATURES = {
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

ORTHO_FEATURES = {
    "SSRD": "SSRD_z",
    "STRD": "STRD_resid_after_SSRD",
    "TMP": "TMP_resid_after_SSRD_STRD",
    "VPD": "VPD_resid_after_SSRD_TMP_Wind",
    "Wind": "Wind_z",
    "Pre": "Pre_z",
    "SMrz": "SMrz_resid_after_Pre_EVA",
    "EVA": "EVA_resid_after_SSRD_Pre_VPD",
    "Duration": "Duration_z",
    "Intensity": "Intensity_z",
}

BLOCKS = {
    "Energy": ["SSRD", "STRD", "TMP"],
    "AtmosDemand": ["VPD", "Wind"],
    "WaterAvailability": ["Pre", "SMrz", "EVA"],
    "DroughtSeverity": ["Duration", "Intensity"],
    "RecoveryTime": [TARGET],
}

INDICATOR_LABELS = {
    "SSRD": "SSRD_z",
    "STRD": "STRD_resid",
    "TMP": "TMP_resid",
    "VPD": "VPD_resid",
    "Wind": "Wind_z",
    "Pre": "Pre_z",
    "SMrz": "SMrz_resid",
    "EVA": "EVA_resid",
    "Duration": "Duration_z",
    "Intensity": "Intensity_z",
    TARGET: "Recovery",
}


def standardize_raw(raw: pd.DataFrame) -> pd.DataFrame:
    scaler = StandardScaler()
    arr = scaler.fit_transform(raw.astype(float))
    return pd.DataFrame(arr, columns=raw.columns, index=raw.index)


def prepare_raw_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    work = df.copy()
    work[TARGET] = pd.to_numeric(work[TARGET], errors="coerce")
    cols = [SOURCE_RAW_FEATURES[label] for label in RAW_ORDER]
    for col in cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    precip_col = SOURCE_RAW_FEATURES["Pre"]
    work.loc[work[precip_col] < 0, precip_col] = np.nan
    work = work.dropna(subset=[TARGET]).reset_index(drop=True)
    raw = pd.DataFrame({label: work[SOURCE_RAW_FEATURES[label]] for label in RAW_ORDER})
    raw = raw.replace([np.inf, -np.inf], np.nan)
    raw = raw.fillna(raw.median(numeric_only=True))
    raw = raw.astype(np.float32)
    y = work[TARGET].astype(np.float32)
    valid = raw.notna().all(axis=1) & y.notna()
    return raw.loc[valid].reset_index(drop=True), y.loc[valid].reset_index(drop=True)


def build_orthogonal_inputs(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
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
            for predictor, coef in zip(predictors, model.coef_, strict=True):
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
    return X, pd.DataFrame(records)


def load_metric(metric: str, biome: str | None = None, max_rows: int = 25000, random_state: int = 42) -> pd.DataFrame:
    cols = ["biome", TARGET] + list(SOURCE_RAW_FEATURES.values())
    if metric not in DATA_CACHE:
        DATA_CACHE[metric] = pd.read_parquet(TABLES[metric], columns=cols)
    df = DATA_CACHE[metric].copy()
    if biome is not None:
        df = df[df["biome"] == biome].copy()
    df = df.drop(columns=["biome"]).reset_index(drop=True)
    df = df.dropna(subset=[TARGET]).reset_index(drop=True)
    if max_rows > 0 and len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=random_state).sort_index().reset_index(drop=True)
    raw, y = prepare_raw_xy(df)
    X, detail = build_orthogonal_inputs(raw)
    detail.attrs["rows"] = len(X)
    out = X.copy()
    out[TARGET] = y.to_numpy(dtype=float)
    return out


def standardize_inputs(df: pd.DataFrame) -> pd.DataFrame:
    z = base.zscore_frame(df[[TARGET] + list(ORTHO_FEATURES.values())])
    renamer = {v: k for k, v in ORTHO_FEATURES.items()}
    return z.rename(columns=renamer)


def write_transform_details(metric: str, biome: str | None, max_rows: int = 25000) -> None:
    label = biome if biome is not None else "AllBiomes"
    cols = ["biome", TARGET] + list(SOURCE_RAW_FEATURES.values())
    if metric not in DATA_CACHE:
        DATA_CACHE[metric] = pd.read_parquet(TABLES[metric], columns=cols)
    df = DATA_CACHE[metric].copy()
    if biome is not None:
        df = df[df["biome"] == biome].copy()
    df = df.drop(columns=["biome"]).dropna(subset=[TARGET]).reset_index(drop=True)
    if max_rows > 0 and len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=42).sort_index().reset_index(drop=True)
    raw, _ = prepare_raw_xy(df)
    X, detail = build_orthogonal_inputs(raw)
    model_dir = OUT / "tables" / f"{metric}_{label}"
    model_dir.mkdir(parents=True, exist_ok=True)
    detail.to_csv(model_dir / "orthogonal_transform_detail.csv", index=False)
    X.corr(method="spearman").to_csv(model_dir / "orthogonal_spearman_corr.csv")


def install_model() -> None:
    base.OUT = OUT
    base.RAW_FEATURES = ORTHO_FEATURES
    base.BLOCKS = BLOCKS
    base.INDICATOR_LABELS = INDICATOR_LABELS
    base.load_metric = load_metric
    base.standardize_inputs = standardize_inputs
    base.write_readme = write_readme


def build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    comp = summary[["metric", "biome", "recovery_r2"]].rename(columns={"recovery_r2": "orthogonal_pls_recovery_r2"})
    for name, path, col in [
        (
            "composite",
            ROOT / "plots2/SEM/sem_prepeak_pls_sem_20260514/pls_sem_model_summary.csv",
            "composite_pls_recovery_r2",
        ),
        (
            "enhanced",
            ROOT / "plots2/SEM/sem_prepeak_pls_sem_enhanced_20260515/pls_sem_enhanced_model_summary.csv",
            "enhanced_pls_recovery_r2",
        ),
        (
            "raw_node",
            ROOT / "plots2/SEM/sem_prepeak_raw_nodes_20260517/raw_node_sem_model_summary.csv",
            "raw_node_recovery_r2",
        ),
    ]:
        if path.exists():
            other = pd.read_csv(path)[["metric", "biome", "recovery_r2"]].rename(columns={"recovery_r2": col})
            comp = comp.merge(other, on=["metric", "biome"], how="left")
            comp[f"orthogonal_minus_{name}"] = comp["orthogonal_pls_recovery_r2"] - comp[col]
    comp.to_csv(OUT / "orthogonal_pls_vs_existing_r2_comparison.csv", index=False)
    return comp


def write_readme(summary: pd.DataFrame) -> None:
    comparison = build_comparison(summary)
    lines = [
        "# Orthogonal-decomposition PLS-SEM for prepeak recovery time",
        "",
        "This folder reruns the baseline PLS-SEM after applying the same sequential residualization used in `prepeak_shap_nomulticollinearity/orthogonal_decomposition`.",
        "",
        "Constructs are kept consistent with the baseline PLS-SEM:",
        "- Energy: SSRD_z, STRD_resid, TMP_resid",
        "- Atmospheric demand: VPD_resid, Wind_z",
        "- Water availability: Pre_z, SMrz_resid, EVA_resid",
        "- Drought severity: Duration_z, Intensity_z",
        "- Recovery time: standardized recovery duration",
        "",
        "Interpretation:",
        "The model asks whether the mechanism blocks remain useful after removing the dominant linear dependence among energy, atmospheric-demand, water, and event-severity features.",
        "",
        "Summary:",
        "```csv",
        summary.to_csv(index=False).strip(),
        "```",
        "",
        "R2 comparison:",
        "```csv",
        comparison.to_csv(index=False).strip(),
        "```",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    install_model()
    OUT.mkdir(parents=True, exist_ok=True)
    summaries = []
    for metric in METRICS:
        cols = ["biome", TARGET] + list(SOURCE_RAW_FEATURES.values())
        DATA_CACHE[metric] = pd.read_parquet(TABLES[metric], columns=cols)
        summaries.append(base.summarize_model(metric, None, n_boot=N_BOOT))
        write_transform_details(metric, None)
        for biome in BIOMES:
            summaries.append(base.summarize_model(metric, biome, n_boot=N_BOOT))
            write_transform_details(metric, biome)
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / "orthogonal_pls_sem_model_summary.csv", index=False)
    base.build_overview(summary)
    write_readme(summary)
    print(OUT)


if __name__ == "__main__":
    main()
