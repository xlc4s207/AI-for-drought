# Primary SEM Mechanism Summary

- result_root: /home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/sem_candidate_models_all_biomes_strict_process
- note: all SEM variables were z-score standardized before fitting, so coefficients can be read as standardized path coefficients.
- selection rule: exclude `M0_direct`, then choose the lowest `fit_rank_score` within each biome as the primary mechanism model.

## Primary Models

| biome | model_id | CFI | TLI | RMSEA | AIC | BIC | top_direct_path | strongest_total_driver |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cropland | M1_water | 1.0000016581393638 | 1.000006632557455 | 0.0 | 9.999999896842834 | 60.397612602791554 | postpeak30_SMrz_mean (negative, -0.323) | postpeak30_SMrz_mean (negative, -0.017) |
| Forest | M1_water | 1.0000105938780943 | 1.0000423755123773 | 0.0 | 9.999999933849594 | 63.35500451839523 | postpeak30_p_minus_et (negative, -0.301) | postpeak30_p_minus_et (negative, -0.324) |
| Grassland | M1_water | 1.0000008927122328 | 1.0000035708489314 | 0.0 | 9.999999986176505 | 63.52875179434682 | postpeak60_SMrz_mean (positive, 0.299) | postpeak30_SMrz_mean (positive, 0.020) |
| Savanna | M1_water | 1.000000666191326 | 1.0000026647653038 | 0.0 | 9.999999094593129 | 63.471897179297706 | postpeak30_SMrz_mean (negative, -0.202) | postpeak30_SMrz_mean (negative, -0.123) |
| Shrubland | M1_water | 1.0000018532395225 | 1.0000074129580898 | 0.0 | 9.999999414493644 | 60.12314293209206 | postpeak30_SMrz_mean (negative, -0.091) | postpeak30_SMrz_mean (negative, -0.035) |
| Wetland | M1_water | 1.0000765552242348 | 1.000306220896939 | 0.0 | 9.99999976998511 | 43.48505785994548 | postpeak30_SMs_mean (negative, -0.987) | postpeak30_SMrz_mean (negative, -0.031) |

## Baseline Comparison

| biome | model_id | CFI | TLI | RMSEA | AIC | BIC |
| --- | --- | --- | --- | --- | --- | --- |
| Cropland | M0_direct | 1.000014734297234 | 1.0000206280161277 | 0.0 | 9.999999602141362 | 60.39761230809009 |
| Forest | M0_direct | 1.0000407449118096 | 1.0000611173677143 | 0.0 | 7.999999999670959 | 50.68400366730747 |
| Grassland | M0_direct | 1.000007363024128 | 1.000010308233779 | 0.0 | 9.99999961186746 | 63.52875142003777 |
| Savanna | M0_direct | 1.000007063161023 | 1.000009888425432 | 0.0 | 9.99999976270366 | 63.47189784740824 |
| Shrubland | M0_direct | 1.0000176082997048 | 1.0000246516195863 | 0.0 | 9.999999864762682 | 60.1231433823611 |
| Wetland | M0_direct | 1.0001709869302482 | 1.0002564803953724 | 0.0 | 7.999999948058374 | 34.78804642002667 |

## Biome Notes

### Cropland

- selected mechanism model: `M1_water`
- direct target paths: postpeak30_SMrz_mean (negative, -0.323, p=0); postpeak60_SMrz_mean (positive, 0.311, p=0)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_SMrz_mean | -0.3233295349925182 | 0.30594943013583004 | -0.017380104856688172 | 1 |

### Forest

- selected mechanism model: `M1_water`
- direct target paths: postpeak30_p_minus_et (negative, -0.301, p=0); postpeak30_SMrz_mean (negative, -0.057, p=0)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_p_minus_et | -0.301492199662326 | -0.02299959832039586 | -0.3244917979827219 | 1 |

### Grassland

- selected mechanism model: `M1_water`
- direct target paths: postpeak60_SMrz_mean (positive, 0.299, p=0); postpeak30_SMrz_mean (negative, -0.274, p=0)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_SMrz_mean | -0.2737984546934374 | 0.29407567924719274 | 0.020277224553755357 | 1 |

### Savanna

- selected mechanism model: `M1_water`
- direct target paths: postpeak30_SMrz_mean (negative, -0.202, p=0); postpeak60_SMrz_mean (positive, 0.079, p=1.03e-10)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_SMrz_mean | -0.2017678505795547 | 0.07854437840829293 | -0.12322347217126178 | 1 |

### Shrubland

- selected mechanism model: `M1_water`
- direct target paths: postpeak30_SMrz_mean (negative, -0.091, p=1.78e-15); postpeak60_SMrz_mean (positive, 0.057, p=7e-07)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_SMrz_mean | -0.0906315380851995 | 0.05519275538156867 | -0.03543878270363083 | 1 |

### Wetland

- selected mechanism model: `M1_water`
- direct target paths: postpeak30_SMs_mean (negative, -0.987, p=0); postpeak30_SMrz_mean (positive, 0.890, p=0)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_SMrz_mean | 0.8900276238795594 | -0.9206615049586686 | -0.03063388107910925 | 1 |
