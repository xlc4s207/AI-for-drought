# ALE validation
Purpose: validate SHAP dependence directions and thresholds using accumulated local effects.
Default scope: GPP/RECO x five biomes x SHAP top-5 features.
Model: LightGBM regressor retrained from the prepeak feature table for each metric-biome subset.
Outputs: per-feature CSV curves, PNG plots, model_fit_summary.csv, ale_validation_index.csv.
