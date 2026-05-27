# Reco_Recoverywin_Simplified7 Path Effect Strengths

Columns: `biome`, `from`, `to`, `estimate`, `abs_estimate`, `significance`

## R2 Summary

| biome | rows | holdout_r2 | train_r2 | predictor_count |
|---|---:|---:|---:|---:|
| Cropland | 270509 | 0.055797 | 0.056279 | 4 |
| Forest | 514956 | 0.077999 | 0.074276 | 4 |
| Grassland | 474240 | 0.073082 | 0.071716 | 4 |
| Savanna | 526286 | 0.059624 | 0.060022 | 4 |
| Shrubland | 208557 | 0.116632 | 0.126078 | 4 |
| Wetland | 20906 | 0.088730 | 0.081672 | 4 |

## Cropland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.232887 | 0.232887 | *** |
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | 0.005984 | 0.005984 | ** |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.774251 | 0.774251 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.092205 | 0.092205 | *** |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.757759 | 0.757759 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.305896 | 0.305896 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.353147 | 0.353147 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | -0.002866 | 0.002866 |  |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.378807 | 0.378807 | *** |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.227925 | 0.227925 | *** |
| recoverywin_VPD_mean | t_recover_to_baseline_abs_peak | -0.138934 | 0.138934 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | 0.058202 | 0.058202 | *** |

## Forest

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.307849 | 0.307849 | *** |
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | 0.001800 | 0.001800 |  |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.693787 | 0.693787 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.143723 | 0.143723 | *** |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.831690 | 0.831690 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.210107 | 0.210107 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.522753 | 0.522753 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | 0.002270 | 0.002270 |  |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.434239 | 0.434239 | *** |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.296178 | 0.296178 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | -0.028794 | 0.028794 | *** |
| recoverywin_VPD_mean | t_recover_to_baseline_abs_peak | 0.027556 | 0.027556 | *** |

## Grassland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.171208 | 0.171208 | *** |
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | -0.006082 | 0.006082 | *** |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.776163 | 0.776163 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.138869 | 0.138869 | *** |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.810276 | 0.810276 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.239471 | 0.239471 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.233919 | 0.233919 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | -0.011148 | 0.011148 | *** |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.237746 | 0.237746 | *** |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.211953 | 0.211953 | *** |
| recoverywin_VPD_mean | t_recover_to_baseline_abs_peak | -0.157181 | 0.157181 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | 0.032775 | 0.032775 | *** |

## Savanna

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.092684 | 0.092684 | *** |
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | 0.003059 | 0.003059 | * |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.734519 | 0.734519 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.047734 | 0.047734 | *** |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.811024 | 0.811024 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.226478 | 0.226478 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.547969 | 0.547969 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | -0.002434 | 0.002434 | * |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.418128 | 0.418128 | *** |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.257030 | 0.257030 | *** |
| recoverywin_VPD_mean | t_recover_to_baseline_abs_peak | 0.085217 | 0.085217 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | -0.024820 | 0.024820 | *** |

## Shrubland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | 0.128746 | 0.128746 | *** |
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.002755 | 0.002755 |  |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.797019 | 0.797019 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.060749 | 0.060749 | *** |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.694801 | 0.694801 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.329168 | 0.329168 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | 0.451797 | 0.451797 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.070840 | 0.070840 | *** |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.588491 | 0.588491 | *** |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.171110 | 0.171110 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | -0.120390 | 0.120390 | *** |
| recoverywin_VPD_mean | t_recover_to_baseline_abs_peak | 0.092036 | 0.092036 | *** |

## Wetland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| recoverywin_total_evaporation_mean | recoverywin_SMrz_mean | 0.058613 | 0.058613 | *** |
| recoverywin_total_precipitation_mean | recoverywin_SMrz_mean | -0.030420 | 0.030420 | *** |
| recoverywin_temperature_2m_mean | recoverywin_VPD_mean | 0.791214 | 0.791214 | *** |
| recoverywin_wind_speed_mean | recoverywin_VPD_mean | 0.005028 | 0.005028 |  |
| recoverywin_strd_mean | recoverywin_temperature_2m_mean | 0.857532 | 0.857532 | *** |
| recoverywin_ssrd_mean | recoverywin_temperature_2m_mean | 0.206584 | 0.206584 | *** |
| recoverywin_VPD_mean | recoverywin_total_evaporation_mean | 0.575519 | 0.575519 | *** |
| recoverywin_total_precipitation_mean | recoverywin_total_evaporation_mean | 0.348369 | 0.348369 | *** |
| recoverywin_temperature_2m_mean | t_recover_to_baseline_abs_peak | -0.409051 | 0.409051 | *** |
| recoverywin_ssrd_mean | t_recover_to_baseline_abs_peak | 0.166848 | 0.166848 | *** |
| recoverywin_VPD_mean | t_recover_to_baseline_abs_peak | 0.050856 | 0.050856 | *** |
| recoverywin_SMrz_mean | t_recover_to_baseline_abs_peak | 0.034186 | 0.034186 | *** |
