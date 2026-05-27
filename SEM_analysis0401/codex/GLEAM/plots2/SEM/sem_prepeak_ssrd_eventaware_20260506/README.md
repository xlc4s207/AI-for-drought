# SSRD event-aware SEM

This model is a higher-explanatory-power SEM variant built because the simpler SSRD-required SEM had limited holdout R2.

Compared with the previous SSRD-required model, this version keeps SSRD and adds STRD, Duration and Intensity in the recovery-time equation.

## Figures

Path diagrams are saved in `figures/path_diagrams/`, with overview panels saved as `gpp_ssrd_eventaware_path_diagrams_overview.png` and `reco_ssrd_eventaware_path_diagrams_overview.png`. To keep the diagrams readable, each panel prioritizes direct recovery-time paths plus the strongest mediator paths, with |standardized coefficient| >= 0.05; the complete path table is preserved in `tables/sem_prepeak_ssrd_eventaware_all_structural_paths.csv`.

## Target equation

```text
Recovery time ~ SSRD + STRD + TMP + VPD + |EVA| + SMrz + Duration + Intensity
```

## R2 comparison

metric,biome,scope,rows,holdout_r2,train_r2,predictor_count,ssrd_required_r2,r2_gain
GPP,Cropland,prepeak_ssrd_eventaware_20260506,190567,0.0764879584312439,0.0729851126670837,8,0.0481337308883667,0.0283542275428771
GPP,Forest,prepeak_ssrd_eventaware_20260506,356257,0.072901964187622,0.0755219459533691,8,0.065604567527771,0.007297396659851
GPP,Grassland,prepeak_ssrd_eventaware_20260506,393388,0.163016676902771,0.1586157083511352,8,0.0746224522590637,0.0883942246437072
GPP,Savanna,prepeak_ssrd_eventaware_20260506,436613,0.1885738968849182,0.184379756450653,8,0.1056352853775024,0.0829386115074158
GPP,Shrubland,prepeak_ssrd_eventaware_20260506,243190,0.1182677149772644,0.1181674003601074,8,0.1097192764282226,0.0085484385490418
RECO,Cropland,prepeak_ssrd_eventaware_20260506,217363,0.135489821434021,0.1293281316757202,8,0.0625038743019104,0.0729859471321106
RECO,Forest,prepeak_ssrd_eventaware_20260506,394637,0.0956072807312011,0.0971384644508361,8,0.090112566947937,0.0054947137832641
RECO,Grassland,prepeak_ssrd_eventaware_20260506,439117,0.1996886730194091,0.1961231827735901,8,0.1153374314308166,0.0843512415885925
RECO,Savanna,prepeak_ssrd_eventaware_20260506,486602,0.1975607275962829,0.1985090374946594,8,0.1394971013069152,0.0580636262893677
RECO,Shrubland,prepeak_ssrd_eventaware_20260506,293501,0.2218310832977295,0.2205222249031067,8,0.2022676467895507,0.0195634365081787


## Direct SSRD paths

metric,biome,estimate,p_value,significance
GPP,Cropland,-0.06853521854031734,4.462069588139388e-30,***
GPP,Forest,-0.22880680868031114,0.0,***
GPP,Grassland,-0.3781336969974619,0.0,***
GPP,Savanna,-0.48120533687356515,0.0,***
GPP,Shrubland,-0.1575145156079426,6.478538262050437e-154,***
RECO,Cropland,-0.4256290521225102,0.0,***
RECO,Forest,-0.28448166553694637,0.0,***
RECO,Grassland,-0.5505472987102341,0.0,***
RECO,Savanna,-0.47049023017608993,0.0,***
RECO,Shrubland,-0.5695906981032067,0.0,***


## Interpretation

The R2 gain quantifies how much explanatory power is recovered by adding event-memory and additional radiation/thermal information. If the gain is still modest, that indicates the recovery-time process is strongly nonlinear and heterogeneous; SEM should then be interpreted primarily as a mechanism test, while SHAP/ALE/ICE carry the nonlinear predictive explanation.