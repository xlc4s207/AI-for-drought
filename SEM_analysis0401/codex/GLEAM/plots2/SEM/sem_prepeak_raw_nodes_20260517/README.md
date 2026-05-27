# Raw-node observed-variable SEM for prepeak recovery time

This folder tests the alternative SEM design requested after the composite PLS-SEM results: original variables are kept as observed path nodes instead of being collapsed into latent/composite blocks.

Model type: observed-variable path SEM fitted by standardized OLS equations. It is not a latent-variable PLS-SEM, because no Energy/Water/Severity composite scores are formed.

Raw nodes:
- SSRD, STRD, TMP, VPD, Wind, Pre, SMrz, EVA, Duration, Intensity, RecoveryTime

Structural equations:
- TMP ~ SSRD + STRD
- VPD ~ SSRD + STRD + TMP + Wind
- SMrz ~ Pre + TMP + VPD + Duration + Intensity
- EVA ~ SSRD + STRD + TMP + VPD + Pre + SMrz
- RecoveryTime ~ SSRD + STRD + TMP + VPD + Wind + Pre + SMrz + EVA + Duration + Intensity

This design preserves direct effects of each original variable on recovery time while still representing hydrothermal mediation among temperature, vapor pressure deficit, soil moisture, and evaporation.

Summary:
```csv
metric,biome,n,rows_used,avg_r2,recovery_r2,direct_predictors
GPP,AllBiomes,24998,24998,0.6401239871526421,0.11956875645640597,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
GPP,Cropland,24997,24997,0.6055406589253429,0.07229039585799013,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
GPP,Forest,24986,24986,0.6028688557217438,0.08153760438599233,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
GPP,Grassland,24997,24997,0.6065089011975573,0.1620589434105575,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
GPP,Savanna,25000,25000,0.6113610420878841,0.18699080898303744,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
GPP,Shrubland,24994,24994,0.6491761683381861,0.12535297554130742,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
RECO,AllBiomes,24982,24982,0.6385667735744455,0.16552642129613726,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
RECO,Cropland,24978,24978,0.6012638992361891,0.13344590804463408,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
RECO,Forest,24992,24992,0.5978979136752238,0.09638834121307904,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
RECO,Grassland,24972,24972,0.6018302631584236,0.20345902516109426,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
RECO,Savanna,24986,24986,0.6060013932987536,0.20100957682786447,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
RECO,Shrubland,24988,24988,0.6481279700646914,0.23081197528823272,"['SSRD', 'STRD', 'TMP', 'VPD', 'Wind', 'Pre', 'SMrz', 'EVA', 'Duration', 'Intensity']"
```

Comparison with previous PLS-SEM runs:
```csv
metric,biome,raw_node_recovery_r2,composite_pls_recovery_r2,raw_minus_composite_pls,enhanced_pls_recovery_r2,raw_minus_enhanced_pls
GPP,AllBiomes,0.11956875645640597,0.0380490893740537,0.08151966708235227,0.2059626754806794,-0.08639391902427343
GPP,Cropland,0.07229039585799013,0.0230302763014167,0.04926011955657343,0.2295257455995669,-0.15723534974157677
GPP,Forest,0.08153760438599233,0.0078714905916001,0.07366611379439224,0.0940730647191434,-0.01253546033315106
GPP,Grassland,0.1620589434105575,0.0345073436266338,0.1275515997839237,0.2914668107322099,-0.12940786732165244
GPP,Savanna,0.18699080898303744,0.0590142387596483,0.12797657022338915,0.2927224506570393,-0.10573164167400184
GPP,Shrubland,0.12535297554130742,0.1074057504968791,0.01794722504442832,0.1467179722365658,-0.021364996695258376
RECO,AllBiomes,0.16552642129613726,0.0539415714744381,0.11158484982169917,0.2170169165417483,-0.05149049524561103
RECO,Cropland,0.13344590804463408,0.0355344881842693,0.09791141986036478,0.3002235694708632,-0.16677766142622913
RECO,Forest,0.09638834121307904,0.0264925472037755,0.06989579400930354,0.1640202968956626,-0.06763195568258357
RECO,Grassland,0.20345902516109426,0.0503758615567574,0.15308316360433688,0.2686374365772956,-0.06517841141620134
RECO,Savanna,0.20100957682786447,0.0913713427764261,0.10963823405143837,0.3054182724743799,-0.10440869564651545
RECO,Shrubland,0.23081197528823272,0.1215849863159668,0.10922698897226592,0.1504690760177147,0.08034289927051802
```