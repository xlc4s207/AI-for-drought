# PLS-SEM for prepeak recovery time

This folder contains a composite-based PLS-SEM style mechanism analysis for GPP and RECO prepeak recovery time.

Latent constructs:
- Energy: SSRD, STRD, TMP
- Atmospheric demand: VPD, Wind
- Water availability: Pre, SMrz, EVA
- Drought severity: Duration, Intensity
- Recovery time: single-indicator latent variable

Structural model:
- Energy -> Atmospheric demand
- Energy -> Water availability
- Atmospheric demand -> Water availability
- Drought severity -> Water availability
- Energy -> Recovery time
- Atmospheric demand -> Recovery time
- Water availability -> Recovery time
- Drought severity -> Recovery time

Outputs include outer weights/loadings, structural paths, bootstrap confidence intervals, R² summaries, total effects, and path diagrams.

Summary:
```csv
metric,biome,n,rows_used,avg_r2,recovery_r2
GPP,AllBiomes,24998,24998,0.2972093485730056,0.03804908937405371
GPP,Cropland,24997,24997,0.23812418052099496,0.02303027630141674
GPP,Forest,24986,24986,0.22008035885349597,0.007871490591600194
GPP,Grassland,24997,24997,0.3093605447742138,0.03450734362663388
GPP,Savanna,25000,25000,0.27382303773983446,0.059014238759648396
GPP,Shrubland,24994,24994,0.39409777628393794,0.10740575049687917
RECO,AllBiomes,24982,24982,0.2968575669496702,0.05394157147443812
RECO,Cropland,24978,24978,0.229879091302765,0.0355344881842693
RECO,Forest,24992,24992,0.24154608502078234,0.026492547203775585
RECO,Grassland,24972,24972,0.30424337595924683,0.05037586155675744
RECO,Savanna,24986,24986,0.2750693699727481,0.09137134277642611
RECO,Shrubland,24988,24988,0.37001642546491675,0.12158498631596681
```