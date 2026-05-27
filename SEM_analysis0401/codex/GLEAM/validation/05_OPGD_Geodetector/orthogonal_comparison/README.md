# Orthogonal SHAP vs OPGD comparison

This folder compares orthogonal-decomposition SHAP outputs with OPGD Geodetector results.

Important interpretation note: orthogonal SHAP features are standardized anchors or residual components. OPGD q values are computed on the corresponding raw features, so the comparison tests mechanism-level agreement rather than one-to-one equality of feature scales.

- Reliability matrix: /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/orthogonal_shap_opgd_reliability_matrix.png
- Overlay-style dependence figures:
  - /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/overlay_style_by_biome/Cropland_orthogonal_dependence_with_opgd_reliability.png
  - /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/overlay_style_by_biome/Forest_orthogonal_dependence_with_opgd_reliability.png
  - /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/overlay_style_by_biome/Grassland_orthogonal_dependence_with_opgd_reliability.png
  - /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/overlay_style_by_biome/Savanna_orthogonal_dependence_with_opgd_reliability.png
  - /home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/orthogonal_comparison/overlay_style_by_biome/Shrubland_orthogonal_dependence_with_opgd_reliability.png

Marker convention in the reliability matrix:
- black filled circle: Orthogonal SHAP Top3 and OPGD Top3
- blue open circle: Orthogonal SHAP Top3 only
- orange open square: OPGD Top3 only
