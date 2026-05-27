# RECO Response Trend Analysis (1980-2024)

## Definitions
- `response_ratio` = response_count / events
- `response_speed_proxy_mean` = mean(1 / t_response), only valid responded events
- absolute RECO metrics are scaled by factor `0.01`

## Input Files
- `flash_SMrz`: `/home/xulc/flash_drought/process/RECO-draught-analysis/code1/results/reco_response_events_global_v11_with_abs.nc`
- `flash_SMs`: `/home/xulc/flash_drought/process/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_events_global_v11_with_abs.nc`
- `nonflash_SMrz`: `/home/xulc/flash_drought/process/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v11_global_with_abs.nc`
- `nonflash_SMs`: `/home/xulc/flash_drought/process/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v11_global_with_abs.nc`

## Significant Trends (p < 0.05)
- Nonflash-SMs | amp_max_mean: slope=0.003551/yr, p=3.39e-07, R2=0.491
- Nonflash-SMrz | amp_max_mean: slope=0.003771/yr, p=4.67e-07, R2=0.483
- Flash-SMs | amp_max_mean: slope=0.002908/yr, p=1.95e-06, R2=0.444
- Flash-SMrz | amp_max_mean: slope=0.002313/yr, p=0.000249, R2=0.294
- Nonflash-SMs | events: slope=18548.507378/yr, p=5.67e-05, R2=0.317
- Nonflash-SMrz | events: slope=10329.024506/yr, p=0.000275, R2=0.267
- Nonflash-SMrz | reco_drop_abs_mean: slope=-0.014834/yr, p=2.76e-07, R2=0.496
- Nonflash-SMs | reco_drop_abs_mean: slope=-0.006264/yr, p=0.000516, R2=0.269
- Flash-SMs | reco_drop_abs_mean: slope=0.004118/yr, p=0.0174, R2=0.137
- Nonflash-SMrz | reco_min_abs_mean: slope=-0.019099/yr, p=2.61e-13, R2=0.750
- Nonflash-SMs | reco_min_abs_mean: slope=-0.013708/yr, p=3.24e-13, R2=0.747
- Flash-SMrz | reco_min_abs_mean: slope=-0.010098/yr, p=1.86e-08, R2=0.560
- Flash-SMs | reco_min_abs_mean: slope=-0.007715/yr, p=7.48e-08, R2=0.528
- Nonflash-SMs | reco_recovery_rate_abs_mean: slope=0.001247/yr, p=1.3e-15, R2=0.809
- Flash-SMrz | reco_recovery_rate_abs_mean: slope=0.001381/yr, p=7.87e-14, R2=0.765
- Flash-SMs | reco_recovery_rate_abs_mean: slope=0.000999/yr, p=8.75e-14, R2=0.764
- Nonflash-SMrz | reco_recovery_rate_abs_mean: slope=0.001216/yr, p=5.5e-13, R2=0.741
- Flash-SMrz | recovery_rate_mean: slope=0.000368/yr, p=1.64e-05, R2=0.382
- Nonflash-SMs | recovery_rate_mean: slope=0.000355/yr, p=3.04e-05, R2=0.363
- Nonflash-SMrz | recovery_rate_mean: slope=0.000319/yr, p=8.27e-05, R2=0.331
- Flash-SMs | recovery_rate_mean: slope=0.000205/yr, p=0.0184, R2=0.134
- Nonflash-SMs | response_count: slope=16636.762055/yr, p=7.85e-05, R2=0.307
- Nonflash-SMrz | response_count: slope=9341.916469/yr, p=0.00032, R2=0.263
- Flash-SMs | response_ratio: slope=-0.002407/yr, p=1.13e-06, R2=0.459
- Flash-SMrz | response_ratio: slope=-0.002320/yr, p=2.6e-06, R2=0.436
- Flash-SMs | response_speed_proxy_mean: slope=-0.000422/yr, p=1.25e-05, R2=0.391
- Flash-SMrz | response_speed_proxy_mean: slope=-0.000382/yr, p=9.34e-05, R2=0.327
- Nonflash-SMrz | t_impact_mean: slope=-0.749658/yr, p=8.17e-12, R2=0.702
- Nonflash-SMs | t_impact_mean: slope=-0.626458/yr, p=1.15e-11, R2=0.697
- Flash-SMrz | t_impact_mean: slope=-0.296264/yr, p=6.24e-10, R2=0.629
- Flash-SMs | t_impact_mean: slope=-0.278843/yr, p=2.69e-09, R2=0.601
- Nonflash-SMrz | t_min_mean: slope=-0.759763/yr, p=7.45e-08, R2=0.528
- Nonflash-SMs | t_min_mean: slope=-0.593940/yr, p=6.61e-07, R2=0.474
- Flash-SMrz | t_min_mean: slope=-0.207474/yr, p=2.1e-06, R2=0.442
- Flash-SMs | t_min_mean: slope=-0.189794/yr, p=6.03e-06, R2=0.412
- Nonflash-SMs | t_recover_mean: slope=-0.226281/yr, p=2.95e-11, R2=0.682
- Nonflash-SMrz | t_recover_mean: slope=-0.230506/yr, p=7.24e-11, R2=0.668
- Flash-SMrz | t_recover_mean: slope=-0.142046/yr, p=1.44e-09, R2=0.613
- Flash-SMs | t_recover_mean: slope=-0.092598/yr, p=9.75e-06, R2=0.398
- Flash-SMs | t_response_mean: slope=0.089442/yr, p=1.46e-11, R2=0.693
- Flash-SMrz | t_response_mean: slope=0.089195/yr, p=9.7e-10, R2=0.621

## Files Generated
- `reco_yearly_response_timeseries_1980_2024.csv`
- `reco_response_trend_summary_1980_2024.csv`
- `plots/reco_trend_panel_2x2.png`
- `plots/reco_trend_additional_panel.png`
- `plots/reco_response_ratio_trend.png`
- `plots/reco_response_speed_proxy_trend.png`
- `plots/reco_min_abs_trend.png`
- `plots/reco_t_min_trend.png`
- `plots/reco_t_response_trend.png`
- `plots/reco_t_impact_trend.png`
- `plots/reco_t_recover_trend.png`
- `plots/reco_drop_abs_trend.png`
- `plots/reco_recovery_abs_trend.png`
