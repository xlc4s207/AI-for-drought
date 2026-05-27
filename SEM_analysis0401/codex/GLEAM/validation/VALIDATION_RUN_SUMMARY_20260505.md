# SHAP validation run summary 2026-05-05

## Scope

Validation was run for:

- Metrics: GPP, RECO
- Biomes: Forest, Grassland, Savanna, Cropland, Shrubland
- ALE/PDP/ICE: SHAP top-5 features for each metric-biome subset
- Geodetector: 10 selected prepeak features plus pairwise interactions among SHAP top-5 features

## Data and models

- Feature tables:
  - `data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet`
  - `data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet`
- ALE/PDP/ICE model: LightGBM regressor retrained per metric-biome subset
- ALE/PDP/ICE sample size: max 50,000 rows per metric-biome subset
- Geodetector sample size: max 80,000 rows per metric-biome subset
- Target: `t_recover_to_baseline_abs_peak`

## Outputs

| Step | Index rows | PNG files | Result CSV files | Main index |
|---|---:|---:|---:|---|
| ALE | 50 | 50 | 50 | `01_ALE/ale_validation_index.csv` |
| ICE | 50 | 50 | 50 | `02_ICE/ice_validation_index.csv` |
| PDP | 50 | 50 | 50 | `03_PDP/pdp_validation_index.csv` |
| Geodetector factor q | 100 | 0 | 100 risk tables | `04_Geodetector/geodetector_factor_q.csv` |
| Geodetector interactions | 100 | 0 | - | `04_Geodetector/geodetector_interactions.csv` |

## Model fit check

Holdout R2 values from the LightGBM validation models:

- GPP: Forest 0.277, Grassland 0.416, Savanna 0.409, Cropland 0.352, Shrubland 0.318
- RECO: Forest 0.316, Grassland 0.457, Savanna 0.456, Cropland 0.425, Shrubland 0.503

These models are validation surrogates retrained from the same feature tables because the previous SHAP artifacts did not preserve fitted model objects.

## Highest Geodetector q examples

Top factor q values by metric-biome subset include:

- GPP Cropland: STRD 0.061, TMP 0.036, PRE 0.031
- GPP Forest: |EVA| 0.071, TMP 0.042, STRD 0.035
- GPP Grassland: TMP 0.112, STRD 0.104, SSRD 0.075
- GPP Savanna: STRD 0.133, TMP 0.125, VPD 0.093
- GPP Shrubland: TMP 0.109, VPD 0.105, SMrz 0.093
- RECO Cropland: TMP 0.092, STRD 0.089, VPD 0.070
- RECO Forest: |EVA| 0.090, TMP 0.078, STRD 0.059
- RECO Grassland: TMP 0.129, SSRD 0.118, STRD 0.116
- RECO Savanna: TMP 0.193, STRD 0.188, VPD 0.146
- RECO Shrubland: SSRD 0.214, TMP 0.180, VPD 0.166

## Interpretation note

ALE is the preferred response-curve validation method for this climate-ecology dataset because it avoids unrealistic variable combinations under strong collinearity. PDP is retained as an intuitive average-response supplement, ICE checks within-biome heterogeneity, and Geodetector validates whether SHAP-important variables also explain spatial stratified heterogeneity in recovery time.
