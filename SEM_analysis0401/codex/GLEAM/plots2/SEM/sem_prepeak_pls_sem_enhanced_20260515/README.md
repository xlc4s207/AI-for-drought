# Enhanced SHAP-informed PLS-SEM for prepeak recovery time

This folder contains an enhanced composite-based PLS-SEM analysis for GPP and RECO recovery time.
It extends the baseline PLS-SEM by adding phenology/timing, pre-drought state, and post-peak recovery climate blocks.

Latent/composite constructs:
- Energy: SSRD, STRD, TMP
- Atmospheric demand: VPD, Wind
- Pre-peak water availability: Pre, SMrz, EVA
- Drought severity: Duration, Intensity, OnsetRate, DaysBelowP20
- Phenology/timing: hemisphere-adjusted season phase, LAI
- Pre-drought state: flux baseline, flux variability, pre30 SMrz, pre30 VPD
- Recovery climate: postpeak30 SMrz, VPD, TMP, Pre
- Recovery time: single-indicator recovery duration

Interpretation note:
The added blocks are intended to test whether the weak RecoveryTime R² in the baseline model mainly came from omitted event timing, antecedent ecosystem state, and recovery-period hydrothermal conditions.

Summary:
```csv
metric,biome,n,rows_used,avg_r2,recovery_r2
GPP,AllBiomes,24998,24998,0.48501311886819953,0.20596267548067948
GPP,Cropland,24997,24997,0.4454794222872604,0.22952574559956695
GPP,Forest,24986,24986,0.37193966167693754,0.09407306471914345
GPP,Grassland,24997,24997,0.5265632404904378,0.2914668107322099
GPP,Savanna,25000,25000,0.4579772742189593,0.2927224506570393
GPP,Shrubland,24994,24994,0.5885791012714073,0.1467179722365658
RECO,AllBiomes,24982,24982,0.4887332972924687,0.21701691654174837
RECO,Cropland,24977,24977,0.44255814821690287,0.30022356947086326
RECO,Forest,24992,24992,0.44711963864103554,0.16402029689566267
RECO,Grassland,24972,24972,0.5181571259469371,0.26863743657729566
RECO,Savanna,24986,24986,0.47501056916897166,0.3054182724743799
RECO,Shrubland,24988,24988,0.5673176342228923,0.15046907601771475
```