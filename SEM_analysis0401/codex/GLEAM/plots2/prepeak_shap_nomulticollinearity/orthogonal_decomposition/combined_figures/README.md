# Orthogonal decomposition combined figures

These figures are redrawn from `dependence_sample_features.parquet`, `dependence_sample_shap_values.parquet`, and `feature_importance.csv` in each metric-biome folder.

- `orthogonal_beeswarm_comparison_5biomes_gpp_vs_reco.png`: five-biome GPP/RECO beeswarm comparison for orthogonal SHAP inputs.
- `combined_by_biome/*_orthogonal_all_features_gpp_vs_reco.png`: one large dependence figure per biome, with GPP and RECO side by side for all ten transformed features.

Note: x axes are transformed variables: standardized anchors such as `SSRD_z` or residual z-scores such as `TMP_resid_after_SSRD_STRD`. They are intended for collinearity robustness interpretation rather than raw-unit thresholds.

Beeswarm: /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_shap_nomulticollinearity/orthogonal_decomposition/combined_figures/orthogonal_beeswarm_comparison_5biomes_gpp_vs_reco.png
Dependence figures:
- /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_shap_nomulticollinearity/orthogonal_decomposition/combined_figures/combined_by_biome/Forest_orthogonal_all_features_gpp_vs_reco.png
- /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_shap_nomulticollinearity/orthogonal_decomposition/combined_figures/combined_by_biome/Grassland_orthogonal_all_features_gpp_vs_reco.png
- /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_shap_nomulticollinearity/orthogonal_decomposition/combined_figures/combined_by_biome/Savanna_orthogonal_all_features_gpp_vs_reco.png
- /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_shap_nomulticollinearity/orthogonal_decomposition/combined_figures/combined_by_biome/Cropland_orthogonal_all_features_gpp_vs_reco.png
- /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_shap_nomulticollinearity/orthogonal_decomposition/combined_figures/combined_by_biome/Shrubland_orthogonal_all_features_gpp_vs_reco.png
