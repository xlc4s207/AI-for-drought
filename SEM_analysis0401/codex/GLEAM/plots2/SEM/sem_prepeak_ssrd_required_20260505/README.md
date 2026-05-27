# SSRD-required SHAP-informed SEM

This version is fitted because SSRD is a stable top SHAP feature and must be represented directly in SEM.

Key design change from the previous half-unified model:

- STRD is removed from the fitted SEM skeleton.
- SSRD is inserted as a required energy-input variable.
- SSRD affects recovery time directly and indirectly through |EVA|.
- GPP and RECO are still fitted separately by biome.

## Implemented path skeleton

```text
VPD  ~ TMP + WIND
|EVA| ~ SSRD + PRE + VPD
SMrz ~ PRE + |EVA|
Recovery time ~ SSRD + TMP + VPD + |EVA| + SMrz
```

## Holdout R2

metric,biome,scope,rows,holdout_r2,train_r2,predictor_count
GPP,Cropland,prepeak_ssrd_required_20260505,190590,0.0481337308883667,0.05035519599914551,5
GPP,Forest,prepeak_ssrd_required_20260505,356455,0.065604567527771,0.06894886493682861,5
GPP,Grassland,prepeak_ssrd_required_20260505,393445,0.07462245225906372,0.07689309120178223,5
GPP,Savanna,prepeak_ssrd_required_20260505,436636,0.10563528537750244,0.10843557119369507,5
GPP,Shrubland,prepeak_ssrd_required_20260505,243279,0.10971927642822266,0.10971397161483765,5
RECO,Cropland,prepeak_ssrd_required_20260505,217386,0.0625038743019104,0.06159418821334839,5
RECO,Forest,prepeak_ssrd_required_20260505,394850,0.09011256694793701,0.08820247650146484,5
RECO,Grassland,prepeak_ssrd_required_20260505,439163,0.11533743143081665,0.11642122268676758,5
RECO,Savanna,prepeak_ssrd_required_20260505,486666,0.13949710130691528,0.13985973596572876,5
RECO,Shrubland,prepeak_ssrd_required_20260505,293653,0.20226764678955078,0.20072811841964722,5


## Direct SSRD paths to recovery time

metric,biome,estimate,p_value,significance
GPP,Cropland,0.16043852771338762,0.0,***
GPP,Forest,-0.12740522181976002,0.0,***
GPP,Grassland,-0.21191345616867546,0.0,***
GPP,Savanna,-0.08013738409430297,0.0,***
GPP,Shrubland,-0.08358672893651493,0.0,***
RECO,Cropland,-0.05335563910768878,0.0,***
RECO,Forest,-0.14968324700841046,0.0,***
RECO,Grassland,-0.34243736263360525,0.0,***
RECO,Savanna,-0.12343716319174698,0.0,***
RECO,Shrubland,-0.44839732565998885,0.0,***


## Interpretation note

This model should be used when the manuscript needs SEM to reflect the SHAP finding that SSRD is a dominant driver. It is not a rejection of STRD; rather, it is an SSRD-prioritized alternative that aligns the SEM mechanism layer with the SHAP importance ranking.