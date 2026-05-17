#!/usr/bin/env python
"""
Structured SHAP+SEM analysis with:
  - Explicit DAG based on mechanism grouping
  - Multicollinearity check (VIF)
  - Mediation structure (climate -> SM deficit (mediator) -> recovery time)
  - Multi-model comparison (direct-only, mediation, full)
  - semopy for full SEM inference
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler

try:
    import semopy
    from semopy import Model
    SEMOPY_OK = True
except ImportError:
    SEMOPY_OK = False


# ── Variable groups (based on SHAP results for GPP code1 flash SMrz) ──────────
# These are the mechanism-based variable groups per the recommended workflow.
# Adjust per future SHAP results.

VAR_GROUPS = {
    "background": [
        "pre30_ssrd_mean",
        "pre30_total_evaporation_sum",
        "pre30_SMs_mean",
        "pre30_temperature_2m_mean",
    ],
    "climate_forcing": [
        "shock_ssrd_mean",
        "shock_strd_mean",
        "shock_temperature_2m_mean",
        "shock_total_evaporation_sum",
    ],
    "drought_intensity": [
        "shock_SMs_min",
        "shock_p_minus_et",
        "shock_SMrz_min",
    ],
    "target": ["t_recover_to_baseline_abs_peak"],
}

# The two mediator variables (drought water deficit, mid-level)
MEDIATORS = ["shock_SMs_min", "shock_p_minus_et"]

TARGET = "t_recover_to_baseline_abs_peak"


# ── Model specifications (lavaan/semopy syntax) ─────────────────────────────
MODEL_SPECS = {
    "direct_only": """
        # All direct effects, no mediation structure
        t_recover_to_baseline_abs_peak ~ pre30_ssrd_mean + pre30_total_evaporation_sum + shock_ssrd_mean + shock_strd_mean + shock_temperature_2m_mean + shock_SMs_min + shock_p_minus_et + shock_total_evaporation_sum
    """,

    "climate_to_sm_mediation": """
        # Climate forcing -> Soil moisture deficit (mediator) -> Recovery time
        # + Direct effects from background and climate
        shock_SMs_min ~ shock_ssrd_mean + shock_strd_mean + shock_temperature_2m_mean
        shock_p_minus_et ~ shock_ssrd_mean + shock_temperature_2m_mean
        t_recover_to_baseline_abs_peak ~ shock_SMs_min + shock_p_minus_et + pre30_ssrd_mean + pre30_total_evaporation_sum + shock_total_evaporation_sum
    """,

    "full_causal": """
        # Full causal chain:
        # Background -> Climate forcing -> SM deficit -> Recovery
        # Background also directly affects recovery
        shock_SMs_min ~ shock_ssrd_mean + shock_strd_mean + shock_temperature_2m_mean + pre30_SMs_mean
        shock_p_minus_et ~ shock_ssrd_mean + shock_temperature_2m_mean + pre30_total_evaporation_sum
        t_recover_to_baseline_abs_peak ~ shock_SMs_min + shock_p_minus_et + shock_total_evaporation_sum + pre30_ssrd_mean + pre30_total_evaporation_sum
    """,

    "background_modulated": """
        # Background state modulates SM deficit response and directly affects recovery
        shock_SMs_min ~ shock_ssrd_mean + shock_temperature_2m_mean + pre30_SMs_mean + pre30_total_evaporation_sum
        shock_p_minus_et ~ shock_ssrd_mean + shock_temperature_2m_mean + pre30_total_evaporation_sum
        t_recover_to_baseline_abs_peak ~ shock_SMs_min + shock_p_minus_et + shock_total_evaporation_sum + shock_temperature_2m_mean + pre30_total_evaporation_sum + pre30_ssrd_mean
    """,
}


def compute_vif(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Compute Variance Inflation Factor for multicollinearity check."""
    from sklearn.linear_model import LinearRegression
    vifs = []
    X = df[features].dropna().values
    for i, feat in enumerate(features):
        X_others = np.delete(X, i, axis=1)
        y = X[:, i]
        try:
            reg = LinearRegression().fit(X_others, y)
            r2 = reg.score(X_others, y)
            vif = 1.0 / (1.0 - r2) if r2 < 1.0 else np.inf
        except Exception:
            vif = np.nan
        vifs.append({"feature": feat, "VIF": round(vif, 2)})
    return pd.DataFrame(vifs)


def load_and_prepare(
    table_path: str,
    biome: str | None,
    metric: str = "GPP",
    code_id: str = "code1",
    drought_type: str = "flash",
    soil_layer: str = "SMrz",
) -> pd.DataFrame:
    """Load, filter and standardize dataset."""
    df = pd.read_parquet(table_path)
    if metric:
        df = df[df["metric"].astype(str) == metric]
    if code_id:
        df = df[df["code_id"].astype(str) == code_id]
    if drought_type:
        df = df[df["drought_type"].astype(str) == drought_type]
    if soil_layer:
        df = df[df["soil_layer"].astype(str) == soil_layer]
    if biome and biome not in ("None", "Global"):
        df = df[df["biome"].astype(str) == biome]

    df = df.reset_index(drop=True)

    # Collect all variables we may need
    all_vars = []
    for g in VAR_GROUPS.values():
        all_vars.extend(g)
    all_vars = list(dict.fromkeys(all_vars))  # deduplicate

    # Filter to variables that actually exist
    avail = [c for c in all_vars if c in df.columns]
    df = df[avail].copy()

    # Convert to numeric and impute median
    for col in avail:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in avail:
        if col != TARGET:
            df[col] = df[col].fillna(df[col].median())

    df = df.dropna(subset=[TARGET]).reset_index(drop=True)

    # Standardize
    scaler = StandardScaler()
    df[avail] = scaler.fit_transform(df[avail])

    return df


def fit_model(model_name: str, spec: str, dataset: pd.DataFrame) -> dict:
    """Fit one candidate SEM model, return summary dict."""
    result = {"model_name": model_name, "spec": spec.strip()}

    try:
        # Check which variables are actually available in the dataset
        model = Model(spec)
        model.fit(dataset)
        estimates = model.inspect()
        stats_obj = semopy.calc_stats(model)

        result["status"] = "ok"
        result["estimates"] = estimates
        result["stats"] = stats_obj
    except Exception as e:
        result["status"] = f"failed: {e}"
        result["estimates"] = pd.DataFrame()
        result["stats"] = None

    return result


def filter_spec_to_available(spec: str, available_cols: list[str]) -> str:
    """Remove from model spec any variables not in dataset."""
    import re
    lines = spec.strip().splitlines()
    new_lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            new_lines.append(line)
            continue
        # Replace variables not in available with nothing
        # Simple approach: keep line if all vars on rhs exist
        # Parse LHS ~ RHS
        if "~" in line:
            parts = line.split("~", 1)
            lhs = parts[0].strip()
            rhs = parts[1].strip()
            rhs_vars = [v.strip() for v in re.split(r"[\+\s]+", rhs) if v.strip()]
            rhs_ok = [v for v in rhs_vars if v in available_cols]
            lhs_ok = lhs in available_cols
            if lhs_ok and rhs_ok:
                new_lines.append(f"{lhs} ~ {' + '.join(rhs_ok)}")
            # else skip the line
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--biome", default="None")
    parser.add_argument("--metric", default="GPP")
    parser.add_argument("--code-id", default="code1")
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", default="SMrz")
    args = parser.parse_args()

    if not SEMOPY_OK:
        raise RuntimeError("semopy is not installed. Run: pip install semopy")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    biome_label = args.biome if args.biome not in ("None", "Global") else "Global"
    tag = f"GPP_{args.code_id}_{biome_label}_{args.drought_type}_{args.soil_layer}"

    print(f"[{tag}] Loading and preparing data...")
    df = load_and_prepare(
        args.table,
        biome=args.biome,
        metric=args.metric,
        code_id=args.code_id,
        drought_type=args.drought_type,
        soil_layer=args.soil_layer,
    )
    print(f"[{tag}] Dataset: {len(df)} rows x {len(df.columns)} cols")

    # Step 1: VIF check
    all_features = [c for c in df.columns if c != TARGET]
    vif_df = compute_vif(df, all_features)
    vif_path = out / f"{tag}_vif.csv"
    vif_df.to_csv(vif_path, index=False)
    high_vif = vif_df[vif_df["VIF"] > 10]
    print(f"[{tag}] High VIF features (>10): {high_vif['feature'].tolist()}")

    # Step 2: Fit all candidate models
    avail_cols = df.columns.tolist()
    all_estimates = []
    all_stats_rows = []

    for model_name, spec in MODEL_SPECS.items():
        spec_filtered = filter_spec_to_available(spec, avail_cols)
        if not spec_filtered.strip():
            print(f"[{tag}][{model_name}] No variables available, skipping.")
            continue

        print(f"[{tag}][{model_name}] Fitting SEM...")
        res = fit_model(model_name, spec_filtered, df)

        est_path = out / f"{tag}_{model_name}_estimates.csv"
        spec_path = out / f"{tag}_{model_name}_spec.txt"
        spec_path.write_text(spec_filtered, encoding="utf-8")

        if res["status"] == "ok" and not res["estimates"].empty:
            res["estimates"]["model"] = model_name
            res["estimates"].to_csv(est_path, index=False)
            all_estimates.append(res["estimates"])

            # Collect fit statistics
            if res["stats"] is not None:
                stats_series = res["stats"]
                row = {"model": model_name}
                try:
                    # semopy calc_stats returns a Series or DataFrame
                    if hasattr(stats_series, "to_dict"):
                        row.update(stats_series.to_dict())
                    else:
                        row["stats_str"] = str(stats_series)
                except Exception:
                    pass
                all_stats_rows.append(row)
                print(f"[{tag}][{model_name}] Fit stats: {row}")
        else:
            print(f"[{tag}][{model_name}] FAILED: {res['status']}")

    # Combine all estimates
    if all_estimates:
        combined = pd.concat(all_estimates, ignore_index=True)
        combined.to_csv(out / f"{tag}_all_estimates.csv", index=False)

    if all_stats_rows:
        stats_df = pd.DataFrame(all_stats_rows)
        stats_df.to_csv(out / f"{tag}_model_comparison.csv", index=False)
        print(f"\n[{tag}] Model comparison:")
        print(stats_df.to_string())

    # Summary
    summary = (
        f"tag={tag}\n"
        f"biome={args.biome}\n"
        f"rows={len(df)}\n"
        f"models_run={len(all_estimates)}\n"
        f"semopy_version={semopy.__version__}\n"
        f"vif_high_features={high_vif['feature'].tolist()}\n"
    )
    (out / f"{tag}_summary.txt").write_text(summary, encoding="utf-8")
    print(f"[DONE] Results in {out}")


if __name__ == "__main__":
    main()
