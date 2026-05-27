# Orthogonal dependence with ALE/ICE/PDP and OPGD annotations

These figures follow the visual logic of `validation/compared_with_dependenceplot/overlay_redrawn`: SHAP dependence scatter/trend, ALE, ICE mean, and PDP are drawn in each panel.

The curves are recomputed on the orthogonal-decomposition input space, so their x axes match variables such as `SSRD_z` and `TMP_resid_after_SSRD_STRD`.

OPGD q and reliability annotations are mapped from each orthogonal variable to its corresponding raw feature. This tests mechanism-level agreement, not identical feature scale.

Outputs:
- /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/dependenceplot_VPD/Cropland_orthogonal_dependence_ALE_ICE_PDP_OPGD_overlay.png
- /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/dependenceplot_VPD/Forest_orthogonal_dependence_ALE_ICE_PDP_OPGD_overlay.png
- /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/dependenceplot_VPD/Grassland_orthogonal_dependence_ALE_ICE_PDP_OPGD_overlay.png
- /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/dependenceplot_VPD/Savanna_orthogonal_dependence_ALE_ICE_PDP_OPGD_overlay.png
- /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/dependenceplot_VPD/Shrubland_orthogonal_dependence_ALE_ICE_PDP_OPGD_overlay.png

VPD sign convention:
- `VPD_resid_after_SSRD_TMP_Wind` SHAP scatter values and SHAP trend lines are multiplied by `-1` in this separate output set.
- ALE, ICE mean, and PDP curves are also flipped for VPD in this output set so the full panel follows the same sign convention.
- Original overlay figures in `validation_overlay_by_biome` are preserved with the original SHAP sign.
- Beeswarm outputs:
  - /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/dependenceplot_VPD/orthogonal_beeswarm_comparison_5biomes_gpp_vs_reco.png
  - /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/dependenceplot_VPD/orthogonal_beeswarm_comparison_5biomes_gpp_vs_reco_shap_summary.png
