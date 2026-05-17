#!/usr/bin/env python
"""
Advanced SEM Analysis for Flash Drought Recovery
Features:
- Stratified sampling to handle massive N -> Fisher's C / Chi2 over-rejection fix
- Incorporating VPD (Atmospheric Drought) and SM (Soil Drought) as parallel pathways
- Incorporating LAI (Canopy Damage) as a mediator to recovery time
- Full multi-model evaluation
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import semopy

TARGET = "t_recover_to_baseline_abs_peak"

def get_variable_sets(soil_layer: str):
    """Return the variables used in the SEM depending on the soil layer context."""
    sm_pre = f"pre30_{soil_layer}_mean"
    sm_drought = f"shock_{soil_layer}_min"
    
    return {
        "target": TARGET,
        "background": [sm_pre, "pre30_ssrd_mean", "pre30_total_evaporation_sum", "pre30_VPD_mean"],
        "climate": ["shock_ssrd_mean", "shock_temperature_2m_mean"],
        "drought": [sm_drought, "shock_VPD_mean"],
        "mediator": ["shock_lai_total_mean"],
    }

def build_models(soil_layer: str):
    """Construct Lavaan-style syntax for 4 candidate models."""
    sm_pre = f"pre30_{soil_layer}_mean"
    sm_drought = f"shock_{soil_layer}_min"
    
    models = {
        "M1_Direct": f"""
            # M1: Direct effects only
            {TARGET} ~ {sm_drought} + shock_VPD_mean + {sm_pre} + shock_ssrd_mean + shock_temperature_2m_mean
        """,
        
        "M2_DualDrought": f"""
            # M2: Climate -> VPD(Atmosphere) & SM(Soil) -> RT
            {sm_drought} ~ shock_temperature_2m_mean + shock_ssrd_mean
            shock_VPD_mean ~ shock_temperature_2m_mean + shock_ssrd_mean
            {TARGET} ~ {sm_drought} + shock_VPD_mean + {sm_pre} + shock_ssrd_mean
        """,
        
        "M3_CanopyMediator": f"""
            # M3: VPD + SM -> LAI(Damage) -> RT
            shock_lai_total_mean ~ {sm_drought} + shock_VPD_mean + {sm_pre}
            {TARGET} ~ shock_lai_total_mean + {sm_drought} + shock_VPD_mean + {sm_pre}
        """,
        
        "M4_Full": f"""
            # M4: Complete Path (Background -> Climate -> VPD/SM -> LAI -> RT)
            # 1. Climate drivers
            shock_VPD_mean ~ shock_temperature_2m_mean + shock_ssrd_mean + pre30_VPD_mean
            {sm_drought} ~ shock_temperature_2m_mean + shock_ssrd_mean + {sm_pre}
            
            # 2. Canopy damage
            shock_lai_total_mean ~ {sm_drought} + shock_VPD_mean + {sm_pre} + shock_temperature_2m_mean
            
            # 3. Recovery time
            {TARGET} ~ shock_lai_total_mean + {sm_drought} + shock_VPD_mean + {sm_pre} + shock_ssrd_mean
            
            # Covariances
            {sm_drought} ~~ shock_VPD_mean
        """
    }
    return models

def stratified_sample(df: pd.DataFrame, n_per_biome: int = 5000, random_state: int = 42) -> pd.DataFrame:
    """Sample data evenly across biomes to prevent massive N from auto-rejecting chi2."""
    if "biome" not in df.columns:
        return df.sample(n=min(len(df), n_per_biome * 5), random_state=random_state)
    
    sampled = []
    for b, group in df.groupby("biome"):
        n_sample = min(len(group), n_per_biome)
        sampled.append(group.sample(n=n_sample, random_state=random_state))
    
    res = pd.concat(sampled).sample(frac=1.0, random_state=random_state).reset_index(drop=True)
    print(f"Stratified sampling: N_total = {len(res)} (original N = {len(df)})")
    return res

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--metric", default="GPP")
    parser.add_argument("--code-id", default="code1")
    parser.add_argument("--drought-type", default="flash")
    parser.add_argument("--soil-layer", default="SMrz")
    parser.add_argument("--sample-size", type=int, default=8000, help="Samples per biome")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    tag = f"SEM_{args.metric}_{args.code_id}_{args.drought_type}_{args.soil_layer}"

    print(f"[{tag}] Loading dataset from {args.table} ...")
    df = pd.read_parquet(args.table)
    
    # Filter
    if args.metric:
        df = df[df["metric"].astype(str) == args.metric]
    if args.code_id:
        df = df[df["code_id"].astype(str) == args.code_id]
    if args.drought_type:
        df = df[df["drought_type"].astype(str) == args.drought_type]
    if args.soil_layer:
        df = df[df["soil_layer"].astype(str) == args.soil_layer]
        
    print(f"Filters applied. N = {len(df)}")
    
    # Stratified Sampling
    df_sample = stratified_sample(df, n_per_biome=args.sample_size)
    
    # Identify variables
    var_conf = get_variable_sets(args.soil_layer)
    all_vars = [TARGET] + var_conf["background"] + var_conf["climate"] + var_conf["drought"] + var_conf["mediator"]
    all_vars = list(set(all_vars))
    
    # Verify columns exist
    missing = [c for c in all_vars if c not in df_sample.columns]
    if missing:
        raise ValueError(f"Missing required columns in dataset: {missing}")
        
    # Clean and Standardize
    df_clean = df_sample[["biome"] + all_vars].copy()
    for c in all_vars:
        df_clean[c] = pd.to_numeric(df_clean[c], errors="coerce")
        df_clean[c] = df_clean[c].fillna(df_clean[c].median())
        
    scaler = StandardScaler()
    df_clean[all_vars] = scaler.fit_transform(df_clean[all_vars])
    
    # Fit Models
    models = build_models(args.soil_layer)
    stats_rows = []
    
    for m_name, syntax in models.items():
        print(f"\n[{tag}] Fitting {m_name}...")
        try:
            model = semopy.Model(syntax)
            model.fit(df_clean)
            stats = semopy.calc_stats(model)
            
            # Save estimates
            estimates = model.inspect()
            estimates["model"] = m_name
            estimates.to_csv(out / f"{tag}_{m_name}_estimates.csv", index=False)
            
            # Save R2 if exists
            try:
                # Sometimes r2 is missing or differs in versions
                from semopy.inspector import inspect
                r2 = semopy.calc_stats(model)
            except Exception:
                pass
            
            # Append stats
            row = {"model": m_name}
            if hasattr(stats, "to_dict"):
                row.update(stats.to_dict())
            stats_rows.append(row)
            print(f"Summary: Chi2={row.get('chi2', np.nan)[0]:.2f}, RMSEA={row.get('RMSEA', np.nan)[0]:.3f}, CFI={row.get('CFI', np.nan)[0]:.3f}")
        except Exception as e:
            print(f"[{tag}] Error fitting {m_name}: {e}")

    if stats_rows:
        stats_df = pd.DataFrame(stats_rows)
        # semopy stats are returned as 1-row dataframes for each metric, so flatten:
        for col in stats_df.columns:
            if col != "model":
                stats_df[col] = stats_df[col].apply(lambda x: x.iloc[0] if isinstance(x, pd.Series) else x)
        stats_df.to_csv(out / f"{tag}_model_comparison.csv", index=False)
        print("\n--- Model Comparison ---")
        print(stats_df[["model", "DoF", "chi2", "p-value", "RMSEA", "CFI"]].to_string())
        
    print(f"\n[DONE] Saved outputs to {out}")

if __name__ == "__main__":
    main()
