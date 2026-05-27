# GLEAM SHAP validation workflow

This directory contains four validation steps for the prepeak SHAP analysis.

## Folders

- `01_ALE/`: validates SHAP dependence directions and thresholds with ALE curves.
- `02_ICE/`: checks within-biome response heterogeneity with centered ICE curves.
- `03_PDP/`: provides average model-response trends as a supplementary view.
- `04_Geodetector/`: validates spatial stratified heterogeneity with q statistics, interactions, and risk tables.
- `05_OPGD_Geodetector/`: tests an optimized-parameter Geodetector that searches discretization methods and bin counts.

## Data and model convention

The scripts reuse the prepeak GPP/RECO feature tables and SHAP by-biome feature-importance outputs under `results/*/prepeak_event_shap_sem_20260424/shap_by_biome`.

ALE/PDP/ICE retrain a lightweight LightGBM regressor for each metric-biome subset because the previous SHAP artifacts did not preserve fitted model objects. The default scope is GPP/RECO x five biomes x SHAP top-5 features.

Geodetector uses the same feature tables directly and evaluates the selected prepeak features within each metric-biome subset.

OPGD Geodetector reuses the same target, features, biome subsets, and SHAP top-feature interaction scope as `04_Geodetector`, but replaces the fixed six-quantile strata with optimized strata selected from multiple discretization methods and bin counts.

## Run

```bash
/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python 01_ALE/run_ale_validation.py
/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python 02_ICE/run_ice_validation.py
/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python 03_PDP/run_pdp_validation.py
/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python 04_Geodetector/run_geodetector_validation.py
/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python 05_OPGD_Geodetector/run_opgd_geodetector_validation.py
```

Each subfolder writes its own README, index CSV, model summary where applicable, and results under `results/`.
