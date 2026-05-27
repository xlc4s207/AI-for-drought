# Geodetector validation
Purpose: validate whether SHAP-important variables explain spatial stratified heterogeneity in recovery time.
Factor detector: q statistic for each selected prepeak feature within metric-biome subsets.
Interaction detector: pairwise interactions among SHAP top features.
Risk detector: target means by feature strata, saved per metric/biome/feature.
Outputs: geodetector_factor_q.csv, geodetector_interactions.csv, per-feature risk_detector CSV files.
