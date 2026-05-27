# Primary SEM Mechanism Summary

- result_root: /home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/sem_candidate_models_all_biomes_process
- note: all SEM variables were z-score standardized before fitting, so coefficients can be read as standardized path coefficients.
- selection rule: exclude `M0_direct`, then choose the lowest `fit_rank_score` within each biome as the primary mechanism model.

## Primary Models

| biome | model_id | CFI | TLI | RMSEA | AIC | BIC | top_direct_path | strongest_total_driver |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cropland | M1_water | 1.000003786895269 | 1.0000151475810757 | 0.0 | 23.99999896017372 | 144.95426945445064 | postpeak30_SMrz_mean (negative, -0.339) | event_duration (positive, 0.056) |
| Forest | M1_water | 1.0000075356051654 | 1.0000301424206617 | 0.0 | 23.99999942931635 | 152.05201043222587 | postpeak30_p_minus_et (negative, -0.303) | event_duration (positive, 0.027) |
| Grassland | M1_water | 1.0000022220623863 | 1.0000088882495464 | 0.0 | 23.99999993838332 | 152.4690042779921 | postpeak60_SMrz_mean (positive, 0.334) | event_duration (positive, 0.072) |
| Savanna | M1_water | 1.0000019088811698 | 1.000007635524679 | 0.0 | 23.99999991825686 | 152.33255532154786 | postpeak30_SMrz_mean (negative, -0.193) | event_intensity (negative, -0.028) |
| Shrubland | M1_water | 1.000005110353897 | 1.0000204414155875 | 0.0 | 23.999999068213818 | 144.29554351045002 | postpeak30_SMrz_mean (negative, -0.096) | event_duration (positive, 0.062) |
| Wetland | M2_dualwater | 0.9993602786466804 | 0.9978249473987127 | 0.02988305395296 | 31.989400679146677 | 139.14158656701986 | postpeak30_SMs_mean (negative, -1.080) | event_duration (positive, 0.031) |

## Baseline Comparison

| biome | model_id | CFI | TLI | RMSEA | AIC | BIC |
| --- | --- | --- | --- | --- | --- | --- |
| Cropland | M0_direct | 1.000045355809802 | 1.0000583146126023 | 0.0 | 13.999999814116782 | 84.55665760244499 |
| Forest | M0_direct | 1.0000216090646683 | 1.0000277830831454 | 0.0 | 13.999997615427713 | 88.69700403379161 |
| Grassland | M0_direct | 1.0000233333515312 | 1.000030000023397 | 0.0 | 13.999999843244323 | 88.94025237468277 |
| Savanna | M0_direct | 1.000025162574202 | 1.000032351881117 | 0.0 | 13.999999357036709 | 88.8606566756231 |
| Shrubland | M0_direct | 1.0000654156653022 | 1.0000841058553886 | 0.0 | 13.999999286513637 | 84.17240021115143 |
| Wetland | M0_direct | 1.000365321513633 | 1.0004696990889566 | 0.0 | 13.999999205089718 | 60.87908053103424 |

## Biome Notes

### Cropland

- selected mechanism model: `M1_water`
- direct target paths: postpeak30_SMrz_mean (negative, -0.339, p=0); postpeak60_SMrz_mean (positive, 0.339, p=0); event_duration (positive, 0.062, p=0); event_intensity (negative, -0.016, p=3.37e-05)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| event_duration | 0.0621912476474998 | -0.006113644037670734 | 0.056077603609829066 | 3 |
| event_intensity | -0.0155650553071686 | 0.002427924352706342 | -0.01313713095446226 | 3 |

### Forest

- selected mechanism model: `M1_water`
- direct target paths: postpeak30_p_minus_et (negative, -0.303, p=0); postpeak30_SMrz_mean (negative, -0.063, p=0); event_duration (negative, -0.030, p=0)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| event_duration | -0.0302425836039618 | 0.057443816030750876 | 0.027201232426789075 | 3 |
| event_intensity | 0.0 | -0.009800356391446162 | -0.009800356391446162 | 3 |

### Grassland

- selected mechanism model: `M1_water`
- direct target paths: postpeak60_SMrz_mean (positive, 0.334, p=0); postpeak30_SMrz_mean (negative, -0.293, p=0); event_duration (positive, 0.090, p=0); event_intensity (negative, -0.056, p=0)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| event_duration | 0.0901355521976366 | -0.01849825685465758 | 0.07163729534297902 | 3 |
| event_intensity | -0.0556076475950119 | 0.013396663421487837 | -0.04221098417352406 | 3 |

### Savanna

- selected mechanism model: `M1_water`
- direct target paths: postpeak30_SMrz_mean (negative, -0.193, p=0); postpeak60_SMrz_mean (positive, 0.066, p=9.93e-08); event_duration (negative, -0.013, p=2.17e-06); event_intensity (negative, -0.013, p=1.43e-06)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| event_intensity | -0.0125594815473142 | -0.015235656782628336 | -0.027795138329942536 | 3 |
| event_duration | -0.0126347291629972 | 0.040294364955261106 | 0.027659635792263906 | 3 |

### Shrubland

- selected mechanism model: `M1_water`
- direct target paths: postpeak30_SMrz_mean (negative, -0.096, p=0); postpeak60_SMrz_mean (positive, 0.068, p=2.4e-09); event_duration (positive, 0.057, p=0); event_intensity (negative, -0.009, p=0.00167)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| event_duration | 0.0568146863190043 | 0.00477401715744949 | 0.06158870347645379 | 3 |
| event_intensity | -0.0091113960162603 | -0.0061382674067065315 | -0.015249663422966832 | 3 |

### Wetland

- selected mechanism model: `M2_dualwater`
- direct target paths: postpeak30_SMs_mean (negative, -1.080, p=0); postpeak30_SMrz_mean (positive, 0.883, p=0)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| event_duration | 0.0 | 0.03140595225166548 | 0.03140595225166548 | 2 |
| event_intensity | 0.0 | -0.020791026483950453 | -0.020791026483950453 | 2 |
