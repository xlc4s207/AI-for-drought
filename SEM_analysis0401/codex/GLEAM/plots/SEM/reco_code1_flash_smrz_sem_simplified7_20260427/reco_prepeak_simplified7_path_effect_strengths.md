# Reco_Prepeak_Simplified7 Path Effect Strengths

Columns: `biome`, `from`, `to`, `estimate`, `abs_estimate`, `significance`

## R2 Summary

| biome | rows | holdout_r2 | train_r2 | predictor_count |
|---|---:|---:|---:|---:|
| Cropland | 270509 | 0.042959 | 0.041195 | 4 |
| Forest | 514956 | 0.061084 | 0.061758 | 4 |
| Grassland | 474240 | 0.113763 | 0.110284 | 4 |
| Savanna | 526286 | 0.062196 | 0.063657 | 4 |
| Shrubland | 208557 | 0.110850 | 0.115846 | 4 |
| Wetland | 20906 | 0.144997 | 0.141105 | 4 |

## Cropland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.397408 | 0.397408 | *** |
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | 0.005984 | 0.005984 | *** |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.782124 | 0.782124 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.152509 | 0.152509 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.696496 | 0.696496 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.343476 | 0.343476 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.252446 | 0.252446 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | 0.004414 | 0.004414 | * |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.352092 | 0.352092 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.304295 | 0.304295 | *** |
| prepeak_VPD_mean | t_recover_to_baseline_abs_peak | -0.070133 | 0.070133 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | -0.060807 | 0.060807 | *** |

## Forest

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.367870 | 0.367870 | *** |
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | 0.002309 | 0.002309 |  |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.710891 | 0.710891 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.211154 | 0.211154 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.786402 | 0.786402 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.243160 | 0.243160 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.463779 | 0.463779 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | -0.002494 | 0.002494 | * |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.395505 | 0.395505 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.150402 | 0.150402 | *** |
| prepeak_VPD_mean | t_recover_to_baseline_abs_peak | 0.079132 | 0.079132 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | -0.042406 | 0.042406 | *** |

## Grassland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.364977 | 0.364977 | *** |
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | 0.003888 | 0.003888 | ** |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.807498 | 0.807498 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.124803 | 0.124803 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.764611 | 0.764611 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.270040 | 0.270040 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.188367 | 0.188367 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | 0.019637 | 0.019637 | *** |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.361876 | 0.361876 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.175501 | 0.175501 | *** |
| prepeak_VPD_mean | t_recover_to_baseline_abs_peak | -0.138804 | 0.138804 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | -0.037000 | 0.037000 | *** |

## Savanna

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.192706 | 0.192706 | *** |
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | 0.006144 | 0.006144 | *** |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.730016 | 0.730016 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.169272 | 0.169272 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.768424 | 0.768424 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.256930 | 0.256930 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.384913 | 0.384913 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | -0.003935 | 0.003935 | ** |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.454023 | 0.454023 | *** |
| prepeak_VPD_mean | t_recover_to_baseline_abs_peak | 0.171428 | 0.171428 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.138878 | 0.138878 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | -0.004457 | 0.004457 | *** |

## Shrubland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | 0.363952 | 0.363952 | *** |
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.041494 | 0.041494 | *** |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.852684 | 0.852684 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.074452 | 0.074452 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.685606 | 0.685606 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.327252 | 0.327252 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | -0.405832 | 0.405832 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.069896 | 0.069896 | *** |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.387091 | 0.387091 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.040869 | 0.040869 | *** |
| prepeak_VPD_mean | t_recover_to_baseline_abs_peak | 0.017034 | 0.017034 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | -0.005396 | 0.005396 | ** |

## Wetland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | -0.038521 | 0.038521 | *** |
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.037132 | 0.037132 | *** |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.785730 | 0.785730 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.145747 | 0.145747 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.852998 | 0.852998 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.193908 | 0.193908 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.676382 | 0.676382 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | -0.238649 | 0.238649 | *** |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.486013 | 0.486013 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.153844 | 0.153844 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | 0.090789 | 0.090789 | *** |
| prepeak_VPD_mean | t_recover_to_baseline_abs_peak | 0.050371 | 0.050371 | *** |
