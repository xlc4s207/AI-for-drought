# Reco_Prepeak_Simplified5 Path Effect Strengths

Columns: `biome`, `from`, `to`, `estimate`, `abs_estimate`, `significance`

## R2 Summary

| biome | rows | holdout_r2 | train_r2 | predictor_count |
|---|---:|---:|---:|---:|
| Cropland | 270509 | 0.041579 | 0.039838 | 4 |
| Forest | 514956 | 0.058099 | 0.059114 | 4 |
| Grassland | 474240 | 0.108581 | 0.105687 | 4 |
| Savanna | 526286 | 0.051738 | 0.053846 | 4 |
| Shrubland | 208557 | 0.113130 | 0.117742 | 4 |
| Wetland | 20906 | 0.150120 | 0.146576 | 4 |

## Cropland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.397544 | 0.397544 | *** |
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | 0.005982 | 0.005982 | *** |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.782138 | 0.782138 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.152549 | 0.152549 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.696463 | 0.696463 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.343509 | 0.343509 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.252093 | 0.252093 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | 0.004368 | 0.004368 | * |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.380802 | 0.380802 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.275923 | 0.275923 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | -0.042588 | 0.042588 | *** |
| prepeak_total_precipitation_mean | t_recover_to_baseline_abs_peak | 0.002053 | 0.002053 |  |

## Forest

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.367397 | 0.367397 | *** |
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | 0.002308 | 0.002308 |  |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.710836 | 0.710836 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.211139 | 0.211139 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.786506 | 0.786506 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.243006 | 0.243006 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.463677 | 0.463677 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | -0.002495 | 0.002495 | * |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.351853 | 0.351853 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.169624 | 0.169624 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | -0.063518 | 0.063518 | *** |
| prepeak_total_precipitation_mean | t_recover_to_baseline_abs_peak | 0.001055 | 0.001055 |  |

## Grassland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.364820 | 0.364820 | *** |
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | 0.003967 | 0.003967 | ** |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.807425 | 0.807425 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.124665 | 0.124665 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.764678 | 0.764678 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.270011 | 0.270011 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.188505 | 0.188505 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | 0.019678 | 0.019678 | *** |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.399492 | 0.399492 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.096632 | 0.096632 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | -0.008157 | 0.008157 | *** |
| prepeak_total_precipitation_mean | t_recover_to_baseline_abs_peak | 0.003572 | 0.003572 | ** |

## Savanna

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.192850 | 0.192850 | *** |
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | 0.006128 | 0.006128 | *** |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.729967 | 0.729967 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.169184 | 0.169184 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.768489 | 0.768489 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.256852 | 0.256852 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.385157 | 0.385157 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | -0.003920 | 0.003920 | ** |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.373580 | 0.373580 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.190856 | 0.190856 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | -0.047261 | 0.047261 | *** |
| prepeak_total_precipitation_mean | t_recover_to_baseline_abs_peak | -0.003222 | 0.003222 | * |

## Shrubland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | 0.364060 | 0.364060 | *** |
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.041727 | 0.041727 | *** |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.852812 | 0.852812 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.074661 | 0.074661 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.685664 | 0.685664 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.327440 | 0.327440 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | -0.406126 | 0.406126 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.069855 | 0.069855 | *** |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.377614 | 0.377614 | *** |
| prepeak_total_precipitation_mean | t_recover_to_baseline_abs_peak | 0.049076 | 0.049076 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.043860 | 0.043860 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | -0.025860 | 0.025860 | *** |

## Wetland

| from | to | estimate | abs_estimate | significance |
|---|---|---:|---:|---|
| prepeak_total_precipitation_mean | prepeak_SMrz_mean | -0.038521 | 0.038521 | *** |
| prepeak_total_evaporation_mean | prepeak_SMrz_mean | -0.037130 | 0.037130 | *** |
| prepeak_temperature_2m_mean | prepeak_VPD_mean | 0.785751 | 0.785751 | *** |
| prepeak_wind_speed_mean | prepeak_VPD_mean | 0.145716 | 0.145716 | *** |
| prepeak_strd_mean | prepeak_temperature_2m_mean | 0.853016 | 0.853016 | *** |
| prepeak_ssrd_mean | prepeak_temperature_2m_mean | 0.193903 | 0.193903 | *** |
| prepeak_VPD_mean | prepeak_total_evaporation_mean | -0.676379 | 0.676379 | *** |
| prepeak_total_precipitation_mean | prepeak_total_evaporation_mean | -0.238656 | 0.238656 | *** |
| prepeak_ssrd_mean | t_recover_to_baseline_abs_peak | -0.493434 | 0.493434 | *** |
| prepeak_temperature_2m_mean | t_recover_to_baseline_abs_peak | 0.222736 | 0.222736 | *** |
| prepeak_total_precipitation_mean | t_recover_to_baseline_abs_peak | -0.084019 | 0.084019 | *** |
| prepeak_SMrz_mean | t_recover_to_baseline_abs_peak | 0.081613 | 0.081613 | *** |
