# GPP, NEE and RECO Drought-Response Trend Comparison

## 1. Data Basis
- Source directories:
  - `/home/xulc/flash_drought/process/result_analysis/GPP_trend`
  - `/home/xulc/flash_drought/process/result_analysis/NEE_trend`
  - `/home/xulc/flash_drought/process/result_analysis/RECO_trend`
- Main source tables used in this comparison:
  - `*_response_trend_summary_1980_2024.csv`
  - `*_pixel_trend_spatial_summary_1980_2024.csv`
  - `*_yearly_response_timeseries_1980_2024.csv`
- Effective analysis window is **1982-2022** with **41 valid years** for all three variables. The early years 1980-1981 are present in the files but have no valid events, so the trend fitting is effectively based on 1982-2022.
- Carbon-cycle relationship used for interpretation: **GPP** represents gross carbon uptake, **RECO** represents ecosystem respiration, and **NEE** is the net exchange result of uptake and respiration. In many applications `NEE ≈ RECO - GPP`, but the discussion below focuses on the trend direction of the event-response metrics rather than strict flux closure from the raw flux fields.

## 2. Core Conclusion
The three datasets show a clear common signal: from 1982 to 2022, drought responses become **less frequent in ratio terms**, **slower to fully respond**, but **more abrupt once the impact phase starts**, and **faster to recover after the minimum**. Among the three variables, **NEE tracks GPP more closely than RECO** for the key response-ratio and response-timing indicators, which suggests that the long-term evolution of net carbon-exchange response is more strongly tied to the weakening of photosynthetic response than to a parallel change in respiratory response.

At the same time, GPP, NEE and RECO are not identical. RECO is clearly less sensitive in the ratio-type indicators, especially for the two nonflash scenarios, where `response_ratio` and `response_speed_proxy_mean` are near zero in the global aggregate trend. This means the net carbon-exchange response cannot be explained by respiration alone. In contrast, the common negative trends in `response_ratio` for GPP and NEE, together with the common positive trends in `t_response_mean`, indicate that ecosystem carbon uptake and net carbon exchange are both becoming harder to trigger rapidly under drought events.

## 3. Frequency and Response-Ratio Indicators
### 3.1 Event counts and response counts
- `events` increases strongly in the two nonflash scenarios for all three analyses, while the two flash scenarios do not show significant long-term event-number trends.
- For GPP, `response_count` decreases slightly in flash scenarios but increases strongly in nonflash scenarios.
- For NEE, `response_count` follows the same pattern as GPP.
- For RECO, `response_count` is nearly flat in flash scenarios but increases most strongly in nonflash scenarios.
- This means the event pool is expanding mainly in the nonflash classes, but the fraction of events with a clear response is not keeping pace.

### 3.2 Response-ratio comparison
| Scenario | GPP slope | GPP p | NEE slope | NEE p | RECO slope | RECO p |
| --- | --- | --- | --- | --- | --- | --- |
| Flash-SMrz | -0.006864 | 5.82e-22 | -0.006593 | 2.71e-18 | -0.002320 | 2.60e-06 |
| Flash-SMs | -0.006578 | 7.38e-20 | -0.006858 | 6.91e-20 | -0.002407 | 1.13e-06 |
| Nonflash-SMrz | -0.005976 | 1.14e-19 | -0.004834 | 2.14e-17 | 0.000133 | 0.5912 |
| Nonflash-SMs | -0.005157 | 8.16e-20 | -0.004433 | 9.77e-18 | -0.000117 | 0.6378 |

Interpretation:
- `response_ratio` declines significantly in **all GPP scenarios** and **all NEE scenarios**. The slopes are similar in magnitude, around `-0.0044` to `-0.0069 yr^-1`.
- `RECO response_ratio` declines much more weakly. It is significant only in the two flash scenarios (`-0.002320` and `-0.002407 yr^-1`) and nearly zero in the two nonflash scenarios.
- This is one of the clearest cross-variable signals in the whole comparison: **GPP and NEE co-weaken strongly, while RECO weakens only slightly or not at all**.
- Therefore, the long-term decline in net ecosystem response probability is more consistent with a photosynthesis-dominated change than with a respiration-dominated change.

### 3.3 Response-speed proxy and amplitude
- `response_speed_proxy_mean` is negative for GPP and NEE in all four scenarios, again indicating slower response development through time.
- For RECO, the same indicator is negative only in flash scenarios, and nearly zero in nonflash scenarios.
- `amp_max_mean` moves in opposite directions: it is positive for GPP and RECO in all scenarios, but negative for NEE in all scenarios.
- This opposite sign in `amp_max_mean` suggests that the internal balance between uptake and respiration is changing, rather than all three variables simply strengthening or weakening together.

## 4. Timing Metrics: Response Becomes Slower to Form but More Abrupt in Its Internal Evolution
| Scenario | GPP t_response | NEE t_response | RECO t_response | GPP t_impact | NEE t_impact | RECO t_impact | GPP t_recover | NEE t_recover | RECO t_recover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Flash-SMrz | 0.155 | 0.139 | 0.089 | -0.298 | -0.464 | -0.296 | -0.214 | -0.183 | -0.142 |
| Flash-SMs | 0.154 | 0.148 | 0.089 | -0.314 | -0.429 | -0.279 | -0.200 | -0.187 | -0.093 |
| Nonflash-SMrz | 0.490 | 0.480 | -0.009 | -1.149 | -1.307 | -0.750 | -0.347 | -0.353 | -0.231 |
| Nonflash-SMs | 0.484 | 0.473 | 0.033 | -0.920 | -1.105 | -0.626 | -0.350 | -0.348 | -0.226 |

Interpretation:
- `t_response_mean` increases for GPP and NEE in all four scenarios. The strongest increase appears in the two nonflash scenarios, especially for GPP (`0.490-0.484 day yr^-1`) and NEE (`0.480-0.473 day yr^-1`).
- RECO behaves differently: `t_response_mean` increases only weakly in flash scenarios (`~0.089 day yr^-1`) and is effectively flat in nonflash scenarios.
- `t_impact_mean` decreases for all three variables in all scenarios, with NEE showing the largest magnitude decreases. This means once the system enters the impact phase, the evolution to stronger anomaly happens more abruptly through time.
- `t_recover_mean` is also negative for all variables and all scenarios. Recovery duration is shortening, but the decrease is largest for GPP and NEE, and smaller for RECO.
- Combining `t_response_mean` and `t_impact_mean`, the dominant pattern is: **it takes longer to enter a full response, but once the response is established, the impact phase evolves faster**.

## 5. Absolute Carbon-Flux Indicators
| Scenario | GPP drop_abs | NEE drop_abs | RECO drop_abs | GPP recovery_abs | NEE recovery_abs | RECO recovery_abs |
| --- | --- | --- | --- | --- | --- | --- |
| Flash-SMrz | 0.0090 | 0.0071 | 0.0025 | 0.0024 | 0.0007 | 0.0014 |
| Flash-SMs | 0.0088 | -0.0002 | 0.0041 | 0.0017 | 0.0005 | 0.0010 |
| Nonflash-SMrz | -0.0185 | 0.0270 | -0.0148 | 0.0022 | 0.0009 | 0.0012 |
| Nonflash-SMs | -0.0053 | 0.0213 | -0.0063 | 0.0022 | 0.0009 | 0.0012 |

Interpretation:
- `*_recovery_rate_abs_mean` is positive in all three variables and all four scenarios. This is one of the most robust shared results. The absolute recovery-rate trend is strongest in GPP, intermediate in RECO, and smallest in NEE.
- `*_min_abs_mean` is negative in the global aggregate trend for all GPP, NEE and RECO scenarios, indicating that the minimum absolute anomaly tends to intensify through time. The strongest decreases are usually in the nonflash scenarios.
- `drop_abs_mean` is more complex:
  - GPP shows positive `drop_abs_mean` trends in flash scenarios, but negative aggregate trends in both nonflash scenarios.
  - NEE shows positive `drop_abs_mean` trends in three of four scenarios, with the strongest increases in nonflash conditions.
  - RECO is positive in flash scenarios but negative in nonflash aggregate trends.
- The NEE result is especially important for carbon-cycle interpretation: the strongest positive `nee_drop_abs_mean` slopes occur in the two nonflash scenarios (`0.0270` and `0.0213 yr^-1`), suggesting that net carbon-exchange anomalies intensify there even when GPP and RECO aggregate trends are not moving in the same direction.

## 6. Pixel-Level Spatial Trends
### 6.1 Response-ratio mean slope and significant area fraction
Format in each cell: `pixel mean slope / fraction of pixels with p < 0.005`

| Scenario | GPP mean_slope / sig_frac | NEE mean_slope / sig_frac | RECO mean_slope / sig_frac |
| --- | --- | --- | --- |
| Flash-SMrz | -0.006654 / 0.204 | -0.006914 / 0.308 | -0.001689 / 0.297 |
| Flash-SMs | -0.006534 / 0.189 | -0.007820 / 0.287 | -0.001338 / 0.272 |
| Nonflash-SMrz | -0.003437 / 0.117 | -0.003449 / 0.168 | -0.000794 / 0.161 |
| Nonflash-SMs | -0.003836 / 0.155 | -0.003813 / 0.207 | -0.000886 / 0.197 |

Interpretation:
- The pixel-level response-ratio trend is negative in **all** variables and **all** scenarios, including RECO nonflash cases where the global aggregate trend was near zero.
- NEE generally has the largest significant-area fraction for `response_ratio`, especially in flash scenarios (`0.308` and `0.287`).
- This means the response-ratio weakening is spatially widespread, even where the event-weighted global aggregate trend looks muted.

### 6.2 `drop_abs_mean` pixel mean slope and significant area fraction
Format in each cell: `pixel mean slope / fraction of pixels with p < 0.005`

| Scenario | GPP mean_slope / sig_frac | NEE mean_slope / sig_frac | RECO mean_slope / sig_frac |
| --- | --- | --- | --- |
| Flash-SMrz | 0.010094 / 0.120 | 0.004770 / 0.151 | 0.007888 / 0.112 |
| Flash-SMs | 0.015682 / 0.110 | 0.004574 / 0.132 | 0.012279 / 0.101 |
| Nonflash-SMrz | 0.000730 / 0.166 | 0.011997 / 0.214 | 0.002025 / 0.187 |
| Nonflash-SMs | 0.004100 / 0.160 | 0.011312 / 0.250 | 0.003288 / 0.184 |

Interpretation:
- At pixel level, `drop_abs_mean` is positive for GPP, NEE and RECO in all four scenarios.
- NEE has the largest positive pixel-level `drop_abs_mean` slopes in the two nonflash scenarios (`0.011997` and `0.011312`) and also the largest significant-area fractions (`0.214` and `0.250`).
- This suggests that spatially, stronger absolute net-exchange response is a broad feature, even when the global mean aggregate trend is weakened by cancellation.

## 7. Global Aggregate Trends versus Pixel-Level Mean Trends
The following indicators show sign differences between the event-weighted global trend and the mean pixel trend:
- GPP Nonflash-SMrz gpp_drop_abs_mean: global slope=-0.018524, pixel mean slope=0.000730, pixel sig frac=0.166
- GPP Nonflash-SMs gpp_drop_abs_mean: global slope=-0.005277, pixel mean slope=0.004100, pixel sig frac=0.160
- NEE Flash-SMs nee_drop_abs_mean: global slope=-0.000198, pixel mean slope=0.004574, pixel sig frac=0.132
- NEE Nonflash-SMrz nee_min_abs_mean: global slope=-0.019906, pixel mean slope=0.000096, pixel sig frac=0.076
- NEE Nonflash-SMs nee_min_abs_mean: global slope=-0.018394, pixel mean slope=0.000099, pixel sig frac=0.065
- RECO Nonflash-SMrz reco_drop_abs_mean: global slope=-0.014834, pixel mean slope=0.002025, pixel sig frac=0.187
- RECO Nonflash-SMs reco_drop_abs_mean: global slope=-0.006264, pixel mean slope=0.003288, pixel sig frac=0.184
- RECO Nonflash-SMrz response_ratio: global slope=0.000133, pixel mean slope=-0.000794, pixel sig frac=0.161
- RECO Nonflash-SMrz response_speed_proxy_mean: global slope=0.000089, pixel mean slope=-0.000008, pixel sig frac=0.083
- RECO Nonflash-SMrz t_response_mean: global slope=-0.009204, pixel mean slope=0.094521, pixel sig frac=0.239

Interpretation:
- The most important mismatches occur for `gpp_drop_abs_mean` and `reco_drop_abs_mean` in the two nonflash scenarios: the **global aggregate trend is negative**, but the **mean pixel trend is positive**.
- This is not a contradiction in the data. It means the two summaries weight space differently:
  - `*_response_trend_summary` is driven by annual aggregated event-level means.
  - `*_pixel_trend_spatial_summary` is the mean of per-pixel slopes.
- Therefore, a small number of high-weight regions can pull the global aggregate trend negative even while most pixels show weak positive tendencies.
- NEE shows the smallest contradiction in `drop_abs_mean`: both the aggregate and pixel-level trends are positive in nonflash scenarios. This strengthens the inference that the long-term strengthening of net carbon-exchange anomaly is spatially coherent.

## 8. Integrated Carbon-Cycle Interpretation
1. **NEE follows GPP more than RECO for response occurrence.**
   - `response_ratio` and `response_speed_proxy_mean` in NEE are much closer to GPP than to RECO across all scenarios.
   - This implies that long-term changes in drought-response occurrence are controlled more by the uptake side than by respiration.
2. **Nonflash droughts produce the strongest structural change.**
   - Nonflash scenarios have the strongest increases in `events`, the strongest increases in `t_response_mean`, and the strongest decreases in `t_impact_mean` and `t_recover_mean`.
   - They also show the largest positive `nee_drop_abs_mean` slopes.
3. **Respiration is comparatively buffered.**
   - RECO shows weaker changes in `response_ratio` and nearly no aggregate trend in nonflash `t_response_mean`.
   - This means respiration response does evolve, but less consistently than uptake and net exchange.
4. **The net effect points to increasing carbon-cycle instability under drought.**
   - GPP response probability declines, NEE response probability also declines, and NEE absolute drop strengthens in many cases.
   - Combined with shorter `t_impact` and `t_recover`, this points to more abrupt but less reliably triggered net carbon anomalies.

## 9. Bottom Line
Across 1982-2022, the clearest common message is that **GPP and NEE are changing together more strongly than RECO**. Photosynthetic drought response is becoming less frequent in ratio terms and slower to fully develop, and the net ecosystem exchange response mirrors that behavior. Respiration changes are present, but they are weaker and more scenario-dependent, especially in the nonflash drought classes. The spatial analyses further show that several apparently weak or negative global aggregate trends actually mask broad areas with positive local strengthening, especially for `drop_abs_mean`. In practical terms, the carbon-cycle response to drought is not simply intensifying or weakening everywhere; instead, it is becoming **more heterogeneous spatially, more abrupt internally, and increasingly dominated by the uptake-side signal in its net outcome**.
