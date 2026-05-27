# Recovery-window SHAP without explicit multicollinearity

This workflow mirrors `prepeak_shap_nomulticollinearity`, but uses recovery-window predictors to explain `t_recover_to_baseline_abs_peak`.

Source predictors are restricted to the same ten conceptual variables:
SSRD, EVA, TMP, STRD, SMrz, Wind, VPD, Duration, Pre, Intensity.

Meteorological and water variables are mapped to `recoverywin_*` fields:
- SSRD: `recoverywin_ssrd_mean`
- EVA: `recoverywin_total_evaporation_mean`
- TMP: `recoverywin_temperature_2m_mean`
- STRD: `recoverywin_strd_mean`
- SMrz: `recoverywin_SMrz_mean`
- Wind: `recoverywin_wind_speed_mean`
- VPD: `recoverywin_VPD_mean`
- Pre: `recoverywin_total_precipitation_mean`

Two transformed-input versions are provided:

- `group_pca`: PCA within mechanism groups: Energy(SSRD/STRD/TMP), Water(Pre/EVA/SMrz), AtmosDemand(VPD/Wind), Event(Duration/Intensity). Only PC1 is retained for each group.
- `orthogonal_decomposition`: sequential residualization using the same physical ordering as the prepeak workflow.

Each metric/biome folder contains `feature_importance.csv`, `feature_importance_beeswarm.png`, `feature_importance_bar.png`, `dependence_plots/`, `vif_after_transform.csv`, and `run_summary.txt`.

## Model summary

```csv
method,metric,biome,rows,feature_count,model_backend,n_estimators,shap_sample_rows,r2_train_split,r2_holdout_split,split_train_rows,split_test_rows
group_pca,GPP,Forest,50000,4,lightgbm,120,5000,0.3457238329207455,0.3027695788567524,40000,10000
group_pca,GPP,Grassland,50000,4,lightgbm,120,5000,0.5649484940431062,0.5216961192146978,40000,10000
group_pca,GPP,Savanna,50000,4,lightgbm,120,5000,0.4657115454048295,0.4389928037154601,40000,10000
group_pca,GPP,Cropland,50000,4,lightgbm,120,5000,0.34369493189112565,0.31987181319452984,40000,10000
group_pca,GPP,Shrubland,50000,4,lightgbm,120,5000,0.5948943242278677,0.5535018850315936,40000,10000
orthogonal_decomposition,GPP,Forest,50000,10,lightgbm,120,5000,0.6497519279291273,0.6112638305774106,40000,10000
orthogonal_decomposition,GPP,Grassland,50000,10,lightgbm,120,5000,0.753772646499326,0.7195792939977568,40000,10000
orthogonal_decomposition,GPP,Savanna,50000,10,lightgbm,120,5000,0.6988821621079007,0.6616672008098663,40000,10000
orthogonal_decomposition,GPP,Cropland,50000,10,lightgbm,120,5000,0.5921872038859233,0.571923476020795,40000,10000
orthogonal_decomposition,GPP,Shrubland,50000,10,lightgbm,120,5000,0.798230204340826,0.7563134853530901,40000,10000
group_pca,RECO,Forest,50000,4,lightgbm,120,5000,0.32590536665756153,0.29880925126953317,40000,10000
group_pca,RECO,Grassland,50000,4,lightgbm,120,5000,0.5489849799863857,0.49728861051595474,40000,10000
group_pca,RECO,Savanna,50000,4,lightgbm,120,5000,0.4833788254707658,0.4573470107780431,40000,10000
group_pca,RECO,Cropland,50000,4,lightgbm,120,5000,0.36200663862443805,0.3264802914575631,40000,10000
group_pca,RECO,Shrubland,50000,4,lightgbm,120,5000,0.5010889107442618,0.4686448850976068,40000,10000
orthogonal_decomposition,RECO,Forest,50000,10,lightgbm,120,5000,0.6651547732632348,0.6292594591483065,40000,10000
orthogonal_decomposition,RECO,Grassland,50000,10,lightgbm,120,5000,0.7865524673757784,0.7490085500892618,40000,10000
orthogonal_decomposition,RECO,Savanna,50000,10,lightgbm,120,5000,0.7338664960190486,0.7107467230806399,40000,10000
orthogonal_decomposition,RECO,Cropland,50000,10,lightgbm,120,5000,0.6714068615450786,0.6438407356719458,40000,10000
orthogonal_decomposition,RECO,Shrubland,50000,10,lightgbm,120,5000,0.7959858655047756,0.7497918485188431,40000,10000
```
