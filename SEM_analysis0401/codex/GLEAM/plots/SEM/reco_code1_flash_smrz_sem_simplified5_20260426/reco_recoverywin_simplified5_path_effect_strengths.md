# Reco_Recoverywin_Simplified5 Path Effect Strengths

Columns: `biome`, `from`, `to`, `estimate`, `abs_estimate`, `significance`

## R2 Summary

| biome | rows | holdout_r2 | train_r2 | predictor_count |
|---|---:|---:|---:|---:|
| Cropland | 270509 | 0.049940 | 0.050934 | 4 |
| Forest | 514956 | 0.077543 | 0.074016 | 4 |
| Grassland | 474240 | 0.065106 | 0.064334 | 4 |
| Savanna | 526286 | 0.057140 | 0.057677 | 4 |
| Shrubland | 208557 | 0.114022 | 0.123644 | 4 |
| Wetland | 20906 | 0.093030 | 0.085735 | 4 |

## Cropland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.233576 | 0.233576 | *** |
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | 0.006103 | 0.006103 | ** |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.774147 | 0.774147 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.092148 | 0.092148 | *** |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.757746 | 0.757746 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.305869 | 0.305869 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.352735 | 0.352735 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | -0.002242 | 0.002242 |  |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.336063 | 0.336063 | *** |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.298736 | 0.298736 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | 0.092213 | 0.092213 | *** |
| recoverywin_total_precipitation_mean | t_recover_to_baseline_abs_peak | 0.003092 | 0.003092 |  |

## Forest

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.307619 | 0.307619 | *** |
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | 0.001801 | 0.001801 |  |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.693893 | 0.693893 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.143722 | 0.143722 | *** |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.831696 | 0.831696 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.210151 | 0.210151 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.522837 | 0.522837 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | 0.002261 | 0.002261 |  |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.424489 | 0.424489 | *** |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.308141 | 0.308141 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | -0.036736 | 0.036736 | *** |
| recoverywin_total_precipitation_mean | t_recover_to_baseline_abs_peak | 0.003362 | 0.003362 | * |

## Grassland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.171206 | 0.171206 | *** |
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | -0.006045 | 0.006045 | *** |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.776122 | 0.776122 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.138833 | 0.138833 | *** |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.810266 | 0.810266 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.239407 | 0.239407 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.233789 | 0.233789 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | -0.011128 | 0.011128 | *** |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.327427 | 0.327427 | *** |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.174289 | 0.174289 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | 0.062398 | 0.062398 | *** |
| recoverywin_total_precipitation_mean | t_recover_to_baseline_abs_peak | 0.006016 | 0.006016 | *** |

## Savanna

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.092934 | 0.092934 | *** |
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | 0.003060 | 0.003060 | * |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.734483 | 0.734483 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.047705 | 0.047705 | *** |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.811049 | 0.811049 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.226453 | 0.226453 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.547959 | 0.547959 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | -0.002422 | 0.002422 | * |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.385252 | 0.385252 | *** |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.290240 | 0.290240 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | -0.046443 | 0.046443 | *** |
| recoverywin_total_precipitation_mean | t_recover_to_baseline_abs_peak | 0.003640 | 0.003640 | ** |

## Shrubland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | 0.128727 | 0.128727 | *** |
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.002678 | 0.002678 |  |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.796908 | 0.796908 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.060740 | 0.060740 | *** |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.694729 | 0.694729 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.329181 | 0.329181 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | 0.452031 | 0.452031 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.071009 | 0.071009 | *** |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.534184 | 0.534184 | *** |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.200876 | 0.200876 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | -0.114678 | 0.114678 | *** |
| recoverywin_total_precipitation_mean | t_recover_to_baseline_abs_peak | -0.007541 | 0.007541 | *** |

## Wetland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.058638 | 0.058638 | *** |
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | -0.030503 | 0.030503 | *** |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.791108 | 0.791108 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.005022 | 0.005022 |  |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.857477 | 0.857477 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.206616 | 0.206616 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.575566 | 0.575566 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | 0.348418 | 0.348418 | *** |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.352577 | 0.352577 | *** |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.169103 | 0.169103 | *** |
| recoverywin_total_precipitation_mean | t_recover_to_baseline_abs_peak | -0.073152 | 0.073152 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | 0.027051 | 0.027051 | *** |
