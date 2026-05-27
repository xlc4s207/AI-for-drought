# Primary SEM Mechanism Summary

- result_root: /home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/sem_candidate_models_all_biomes_landmark30_v21
- note: all SEM variables were z-score standardized before fitting, so coefficients can be read as standardized path coefficients.
- selection rule: exclude `M0_direct`, then choose the lowest `fit_rank_score` within each biome as the primary mechanism model.

## Primary Models

| biome | model_id | CFI | TLI | RMSEA | AIC | BIC | top_direct_path | strongest_total_driver |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cropland | M2_canopy | 0.998825852006628 | 0.996980762302758 | 0.0186762417921092 | 27.99498753450708 | 162.29094083122104 | postpeak30_total_evaporation_sum (positive, 0.158) | postpeak30_temperature_2m_mean (negative, -0.143) |
| Forest | M2_canopy | 1.0000107189485845 | 1.0000428757943376 | 0.0 | 23.999999285603145 | 141.25584316516802 | postpeak30_total_evaporation_sum (positive, 0.323) | postpeak30_total_evaporation_sum (positive, 0.335) |
| Grassland | M2_canopy | 0.9999784683906884 | 0.9999446330046275 | 0.002695943710853 | 27.99982208178727 | 169.7031087686152 | postpeak30_temperature_2m_mean (negative, -0.245) | postpeak30_temperature_2m_mean (negative, -0.264) |
| Savanna | M2_canopy | 0.9999667184489712 | 0.9999144188687832 | 0.0030420088013749 | 27.99978805366345 | 168.60262072142928 | postpeak30_total_evaporation_sum (positive, 0.226) | postpeak30_total_evaporation_sum (positive, 0.214) |
| Shrubland | M2_canopy | 0.9984871885237367 | 0.996109913346752 | 0.021467633813728 | 27.9933320432892 | 155.10169666005388 | postpeak30_temperature_2m_mean (negative, -0.198) | postpeak30_temperature_2m_mean (negative, -0.194) |
| Wetland | M2_dualwater | 1.000617637742534 | 1.0016470339800907 | 0.0 | 13.99999993849164 | 54.53776651276184 | postpeak30_SMs_mean (negative, -0.856) | postpeak30_SMs_mean (negative, -0.856) |

## Baseline Comparison

| biome | model_id | CFI | TLI | RMSEA | AIC | BIC |
| --- | --- | --- | --- | --- | --- | --- |
| Cropland | M0_direct | 1.0000490627953682 | 1.000063080736902 | 0.0 | 13.999999991091622 | 81.1479766394486 |
| Forest | M0_direct | 1.0000245567334898 | 1.0000327423113196 | 0.0 | 11.999999829041354 | 70.6279217688238 |
| Grassland | M0_direct | 1.0000264898512996 | 1.0000340583802425 | 0.0 | 13.999999652701964 | 84.85164299611593 |
| Savanna | M0_direct | 1.000028953136351 | 1.000037225461023 | 0.0 | 13.99999947312263 | 84.30141580700554 |
| Shrubland | M0_direct | 1.0000824818532987 | 1.0001060480970985 | 0.0 | 13.99999991679626 | 77.5541822251786 |
| Wetland | M0_direct | 1.0006249641590166 | 1.0010416069316943 | 0.0 | 5.9999999991898 | 23.373328531019883 |

## Biome Notes

### Cropland

- selected mechanism model: `M2_canopy`
- direct target paths: postpeak30_total_evaporation_sum (positive, 0.158, p=0); postpeak30_temperature_2m_mean (negative, -0.101, p=0); postpeak30_SMrz_mean (positive, 0.061, p=0); postpeak30_p_minus_et (negative, -0.050, p=0); postpeak30_lai_total_mean (positive, 0.015, p=1.83e-06)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_temperature_2m_mean | -0.1012537256592193 | -0.041799174241674106 | -0.14305289990089343 | 3 |
| postpeak30_total_evaporation_sum | 0.1575574496506935 | -0.03149741262296699 | 0.1260600370277265 | 3 |
| postpeak30_p_minus_et | -0.0499853333766402 | 0.012031931571322435 | -0.03795340180531776 | 2 |

### Forest

- selected mechanism model: `M2_canopy`
- direct target paths: postpeak30_total_evaporation_sum (positive, 0.323, p=0); postpeak30_temperature_2m_mean (negative, -0.057, p=0); postpeak30_SMrz_mean (negative, -0.029, p=0); postpeak30_lai_total_mean (positive, 0.019, p=3.36e-08)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_total_evaporation_sum | 0.3234252253802437 | 0.011753785415372206 | 0.3351790107956159 | 3 |
| postpeak30_temperature_2m_mean | -0.0566666045632735 | 0.021576419357331258 | -0.035090185205942245 | 3 |

### Grassland

- selected mechanism model: `M2_canopy`
- direct target paths: postpeak30_temperature_2m_mean (negative, -0.245, p=0); postpeak30_p_minus_et (negative, -0.135, p=0); postpeak30_SMrz_mean (positive, 0.062, p=0); postpeak30_total_evaporation_sum (positive, 0.048, p=0); postpeak30_lai_total_mean (positive, 0.044, p=0)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_temperature_2m_mean | -0.2450667607866606 | -0.018971440336782885 | -0.26403820112344345 | 3 |
| postpeak30_p_minus_et | -0.1354018677433705 | 0.03963837244897429 | -0.09576349529439622 | 2 |
| postpeak30_total_evaporation_sum | 0.0480854519131826 | -0.011031796607441427 | 0.03705365530574117 | 1 |

### Savanna

- selected mechanism model: `M2_canopy`
- direct target paths: postpeak30_total_evaporation_sum (positive, 0.226, p=0); postpeak30_p_minus_et (negative, -0.111, p=0); postpeak30_SMrz_mean (positive, 0.059, p=0); postpeak30_temperature_2m_mean (negative, -0.053, p=0); postpeak30_lai_total_mean (negative, -0.013, p=4.38e-07)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_total_evaporation_sum | 0.2262382318462697 | -0.011909576246398705 | 0.214328655599871 | 3 |
| postpeak30_p_minus_et | -0.1107138218595074 | 0.013711678326425308 | -0.09700214353308209 | 2 |
| postpeak30_temperature_2m_mean | -0.052926943485186 | -0.032539278365487874 | -0.08546622185067387 | 3 |

### Shrubland

- selected mechanism model: `M2_canopy`
- direct target paths: postpeak30_temperature_2m_mean (negative, -0.198, p=0); postpeak30_p_minus_et (negative, -0.141, p=0); postpeak30_total_evaporation_sum (negative, -0.023, p=0.00738); postpeak30_SMrz_mean (negative, -0.013, p=0.00434)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_temperature_2m_mean | -0.1982569298689753 | 0.0037676103307025138 | -0.19448931953827278 | 1 |
| postpeak30_p_minus_et | -0.141239057154704 | -0.009986561393946138 | -0.15122561854865013 | 1 |
| postpeak30_total_evaporation_sum | -0.0225735170347236 | -0.005195705816877828 | -0.027769222851601428 | 1 |

### Wetland

- selected mechanism model: `M2_dualwater`
- direct target paths: postpeak30_SMs_mean (negative, -0.856, p=0); postpeak30_SMrz_mean (positive, 0.852, p=0); postpeak30_SMs_delta (negative, -0.138, p=2.83e-13)
- total driver effects:
| source | direct_effect | indirect_effect | total_effect | indirect_path_count |
| --- | --- | --- | --- | --- |
| postpeak30_SMs_mean | -0.8560304288417123 | 0.0 | -0.8560304288417123 | 0 |
| postpeak30_SMrz_mean | 0.8522632559295344 | 0.0 | 0.8522632559295344 | 0 |
| postpeak30_SMs_delta | -0.1380483878687257 | 0.0 | -0.1380483878687257 | 0 |
