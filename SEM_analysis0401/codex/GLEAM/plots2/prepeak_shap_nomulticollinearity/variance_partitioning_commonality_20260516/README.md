# Prepeak Grouped Variance Partitioning / Commonality Trial

This folder tests mechanism-group variance partitioning as an alternative way to quantify independent and shared contributions under multicollinearity.

Mechanism groups:
- Energy: SSRD, STRD, TMP
- Water: Pre, EVA, SMrz
- AtmosDemand: VPD, Wind
- EventSeverity: Duration, Intensity

For each metric x biome, LightGBM models are trained for all 15 non-empty group combinations. Holdout R2 values are decomposed into commonality coefficients by Mobius inversion.

Important interpretation:
- `unique_commonality` is the component uniquely attributable to one group in the commonality decomposition.
- `shared_commonality` is the sum of commonality components involving the group and at least one other group.
- `drop_group_delta_r2` is the full-model R2 loss when the group is removed; it is often the most intuitive model-performance contribution.
- Negative commonality can occur under suppression or strong multicollinearity.

Summary:
```csv
metric,biome,rows,train_rows,test_rows,full_model_r2,max_single_group_r2,n_estimators,row_limit
GPP,Cropland,15000,12000,3000,0.2982140491295572,0.13510956383826445,100,15000
GPP,Forest,15000,12000,3000,0.23354844619345438,0.13648403212365612,100,15000
GPP,Grassland,15000,12000,3000,0.369730097227126,0.21586555880973257,100,15000
GPP,Savanna,15000,12000,3000,0.34724976863868695,0.23166306065325926,100,15000
GPP,Shrubland,15000,12000,3000,0.23695181873363258,0.14867303388517406,100,15000
RECO,Cropland,15000,12000,3000,0.3491769483363948,0.20426636100249695,100,15000
RECO,Forest,15000,12000,3000,0.24690730002736305,0.14828165486080347,100,15000
RECO,Grassland,15000,12000,3000,0.39593457090547124,0.25792987028413084,100,15000
RECO,Savanna,15000,12000,3000,0.38005255711707,0.2964592390474593,100,15000
RECO,Shrubland,15000,12000,3000,0.4405888367841324,0.26633660833223616,100,15000
```

Key first-pass pattern:

- Energy has the largest drop-group delta R2 in all tested metric-biome combinations.
- Water is generally the second most important mechanism group.
- AtmosDemand and EventSeverity have smaller independent drop-delta values, but can still contribute through shared hydrothermal components.
- Commonality components include negative shared terms, indicating suppression/shared-predictor effects under strong hydrothermal coupling.

Useful summary tables:

- `top_group_by_drop_delta.csv`
- `group_drop_delta_r2_matrix.csv`
- `group_summary_ranked_by_drop_delta.csv`
