# OPGD Geodetector validation
Purpose: improve the fixed-bin Geodetector by optimizing continuous-variable strata.
Methods: quantile, equal_interval, geometric_interval, standard_deviation.
Bin search: 3-10; min group size: 30.
Factor detector: selects the method/bin count with the highest valid q for each metric-biome-feature.
Interaction detector: reuses the optimized single-factor strata for SHAP top-feature pairs.
Reliability checks: bootstrap q stability, fixed-vs-OPGD-vs-conservative strata sensitivity, SHAP-OPGD rank/Top3 consistency, and feature-level reliability grades.
Figures:
- `figures/shap_opgd_reliability_matrix.png` / `.pdf`: main SHAP-OPGD-reliability comparison figure.
- `figures/opgd_interaction_heatmaps.png` / `.pdf`: supplementary interaction detector heatmaps.
Outputs: opgd_factor_q.csv, opgd_interactions.csv, per-feature OPGD risk detector CSV files, reliability/*.csv, figures/*, and opgd_shap_comparison_cn.docx.
