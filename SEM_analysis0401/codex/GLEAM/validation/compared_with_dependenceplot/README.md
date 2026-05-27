# Dependence plot compared with ALE / ICE / PDP

This folder combines existing GPP-vs-RECO SHAP dependence plots with validation trajectories from ALE, ICE, and PDP.

- `by_feature/{biome}/`: one comparison figure per feature.
- `by_biome/`: one compact overview sheet per biome.
- `combined_with_original/`: original all-feature dependence plot plus the validation overview sheet.

Missing ALE/ICE/PDP panels are shown as `not available`, because the validation workflow only generated trajectories for selected high-importance features.