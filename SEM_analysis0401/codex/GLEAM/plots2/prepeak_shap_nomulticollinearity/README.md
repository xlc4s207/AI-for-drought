# Prepeak SHAP without explicit multicollinearity

Source predictors are restricted to: SSRD, EVA, TMP, STRD, SMrz, Wind, VPD, Duration, Pre, Intensity.

Two transformed-input versions are provided:

- `group_pca`: PCA within mechanism groups: Energy(SSRD/STRD/TMP), Water(Pre/EVA/SMrz), AtmosDemand(VPD/Wind), Event(Duration/Intensity). Only PC1 is retained for each group to provide four low-collinearity mechanism axes. Loadings and explained variance are saved per metric/biome.
- `orthogonal_decomposition`: sequential residualization. SSRD, Pre, Duration, Intensity, and Wind are retained as standardized anchors; STRD, TMP, VPD, EVA, and SMrz are residualized following the physical ordering recorded in `orthogonal_decomposition_models.csv`.

Each metric/biome folder contains `feature_importance.csv`, `feature_importance_beeswarm.png`, `feature_importance_bar.png`, `dependence_plots/`, `vif_after_transform.csv`, and `run_summary.txt`.

## Model summary

```csv
method,metric,biome,rows,feature_count,model_backend,n_estimators,shap_sample_rows,r2_train_split,r2_holdout_split,split_train_rows,split_test_rows
group_pca,GPP,Forest,50000,4,lightgbm,120,5000,0.36287975347966916,0.31997718956136245,40000,10000
group_pca,GPP,Grassland,50000,4,lightgbm,120,5000,0.2867905731385778,0.25263492572091306,40000,10000
group_pca,GPP,Savanna,50000,4,lightgbm,120,5000,0.36849838498049403,0.3337308608408913,40000,10000
group_pca,GPP,Cropland,50000,4,lightgbm,120,5000,0.25887416887483605,0.22612483469139133,40000,10000
group_pca,GPP,Shrubland,50000,4,lightgbm,120,5000,0.22625294552585506,0.1899255445332103,40000,10000
orthogonal_decomposition,GPP,Forest,50000,10,lightgbm,120,5000,0.5183446552549369,0.4680111847974142,40000,10000
orthogonal_decomposition,GPP,Grassland,50000,10,lightgbm,120,5000,0.48612424733331494,0.44321792787040726,40000,10000
orthogonal_decomposition,GPP,Savanna,50000,10,lightgbm,120,5000,0.5439239483792853,0.49573507263541994,40000,10000
orthogonal_decomposition,GPP,Cropland,50000,10,lightgbm,120,5000,0.47485214143758303,0.43854329475515974,40000,10000
orthogonal_decomposition,GPP,Shrubland,50000,10,lightgbm,120,5000,0.4083441937103788,0.35459616780977454,40000,10000
group_pca,RECO,Forest,50000,4,lightgbm,120,5000,0.3653949888357134,0.34458351216161553,40000,10000
group_pca,RECO,Grassland,50000,4,lightgbm,120,5000,0.3605628047002202,0.33191385637439186,40000,10000
group_pca,RECO,Savanna,50000,4,lightgbm,120,5000,0.3801400204892307,0.3476651675047797,40000,10000
group_pca,RECO,Cropland,50000,4,lightgbm,120,5000,0.2812867554467454,0.24072951172025903,40000,10000
group_pca,RECO,Shrubland,50000,4,lightgbm,120,5000,0.3374264458180255,0.29856409175853527,40000,10000
orthogonal_decomposition,RECO,Forest,50000,10,lightgbm,120,5000,0.5160460983435033,0.47947971071902495,40000,10000
orthogonal_decomposition,RECO,Grassland,50000,10,lightgbm,120,5000,0.5847465667063834,0.5478769682251989,40000,10000
orthogonal_decomposition,RECO,Savanna,50000,10,lightgbm,120,5000,0.5953856453363053,0.5616571794234423,40000,10000
orthogonal_decomposition,RECO,Cropland,50000,10,lightgbm,120,5000,0.5082683227007039,0.46486822896206526,40000,10000
orthogonal_decomposition,RECO,Shrubland,50000,10,lightgbm,120,5000,0.5648546595307085,0.5239468027228932,40000,10000
```
