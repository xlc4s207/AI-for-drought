# GPP Response Trend Analysis (1980-2024)

## Definitions
- `response_ratio` = response_count / events
- `response_speed_proxy_mean` = mean(1 / t_response), only valid responded events
- absolute GPP metrics are scaled by factor `0.01` (DN -> flux)

## Input Files
- `flash_SMrz`: `/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v11_with_abs.nc`
- `flash_SMs`: `/home/xulc/flash_drought/process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v11_with_abs.nc`
- `nonflash_SMrz`: `/home/xulc/flash_drought/process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v11_global_with_abs.nc`
- `nonflash_SMs`: `/home/xulc/flash_drought/process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v11_global_with_abs.nc`

## Significant Trends (p < 0.05)
- Nonflash-SMrz | amp_max_mean: slope=0.006706/yr, p=4.13e-14, R2=0.773
- Nonflash-SMs | amp_max_mean: slope=0.006464/yr, p=7.01e-14, R2=0.766
- Flash-SMs | amp_max_mean: slope=0.004144/yr, p=1.17e-08, R2=0.570
- Flash-SMrz | amp_max_mean: slope=0.003618/yr, p=3.65e-06, R2=0.427
- Nonflash-SMs | events: slope=18548.846772/yr, p=5.68e-05, R2=0.317
- Nonflash-SMrz | events: slope=10330.441502/yr, p=0.000275, R2=0.267
- Nonflash-SMrz | gpp_drop_abs_mean: slope=-0.018524/yr, p=1.26e-06, R2=0.456
- Flash-SMrz | gpp_drop_abs_mean: slope=0.008990/yr, p=0.000335, R2=0.284
- Flash-SMs | gpp_drop_abs_mean: slope=0.008761/yr, p=0.00154, R2=0.229
- Nonflash-SMs | gpp_drop_abs_mean: slope=-0.005277/yr, p=0.0287, R2=0.117
- Nonflash-SMrz | gpp_min_abs_mean: slope=-0.012439/yr, p=1.65e-09, R2=0.611
- Nonflash-SMs | gpp_min_abs_mean: slope=-0.004907/yr, p=9.29e-06, R2=0.400
- Nonflash-SMs | gpp_recovery_rate_abs_mean: slope=0.002192/yr, p=7.16e-16, R2=0.815
- Flash-SMrz | gpp_recovery_rate_abs_mean: slope=0.002351/yr, p=1.33e-15, R2=0.809
- Nonflash-SMrz | gpp_recovery_rate_abs_mean: slope=0.002225/yr, p=3.77e-14, R2=0.774
- Flash-SMs | gpp_recovery_rate_abs_mean: slope=0.001727/yr, p=8.33e-14, R2=0.764
- Flash-SMrz | recovery_rate_mean: slope=0.000431/yr, p=7.86e-09, R2=0.579
- Flash-SMs | recovery_rate_mean: slope=0.000372/yr, p=9.52e-09, R2=0.575
- Nonflash-SMs | recovery_rate_mean: slope=0.000352/yr, p=4.28e-08, R2=0.541
- Nonflash-SMrz | recovery_rate_mean: slope=0.000298/yr, p=1.02e-05, R2=0.397
- Nonflash-SMs | response_count: slope=12516.428063/yr, p=0.000495, R2=0.248
- Nonflash-SMrz | response_count: slope=5947.111726/yr, p=0.00525, R2=0.167
- Flash-SMrz | response_ratio: slope=-0.006864/yr, p=5.82e-22, R2=0.910
- Flash-SMs | response_ratio: slope=-0.006578/yr, p=7.38e-20, R2=0.884
- Nonflash-SMs | response_ratio: slope=-0.005157/yr, p=8.16e-20, R2=0.884
- Nonflash-SMrz | response_ratio: slope=-0.005976/yr, p=1.14e-19, R2=0.882
- Flash-SMs | response_speed_proxy_mean: slope=-0.000642/yr, p=1.79e-10, R2=0.652
- Flash-SMrz | response_speed_proxy_mean: slope=-0.000618/yr, p=5.98e-08, R2=0.533
- Nonflash-SMrz | response_speed_proxy_mean: slope=-0.000487/yr, p=2.27e-06, R2=0.440
- Nonflash-SMs | response_speed_proxy_mean: slope=-0.000415/yr, p=0.000137, R2=0.315
- Nonflash-SMrz | t_impact_mean: slope=-1.149105/yr, p=3.86e-17, R2=0.841
- Nonflash-SMs | t_impact_mean: slope=-0.919775/yr, p=1.51e-16, R2=0.829
- Flash-SMs | t_impact_mean: slope=-0.314233/yr, p=4.23e-09, R2=0.592
- Flash-SMrz | t_impact_mean: slope=-0.298216/yr, p=9.01e-09, R2=0.576
- Nonflash-SMrz | t_min_mean: slope=-0.662164/yr, p=2.63e-07, R2=0.497
- Nonflash-SMs | t_min_mean: slope=-0.438679/yr, p=1.23e-05, R2=0.391
- Flash-SMs | t_min_mean: slope=-0.160280/yr, p=0.000443, R2=0.274
- Flash-SMrz | t_min_mean: slope=-0.144078/yr, p=0.00148, R2=0.231
- Nonflash-SMs | t_recover_mean: slope=-0.349529/yr, p=1.82e-12, R2=0.724
- Nonflash-SMrz | t_recover_mean: slope=-0.346561/yr, p=1.44e-11, R2=0.694
- Flash-SMrz | t_recover_mean: slope=-0.213664/yr, p=1.97e-10, R2=0.650
- Flash-SMs | t_recover_mean: slope=-0.199799/yr, p=1.98e-10, R2=0.650
- Flash-SMs | t_response_mean: slope=0.154473/yr, p=2.89e-17, R2=0.843
- Flash-SMrz | t_response_mean: slope=0.154659/yr, p=3.86e-15, R2=0.798
- Nonflash-SMs | t_response_mean: slope=0.484482/yr, p=6.98e-12, R2=0.705
- Nonflash-SMrz | t_response_mean: slope=0.490211/yr, p=1.87e-11, R2=0.690

## Files Generated
- `gpp_yearly_response_timeseries_1980_2024.csv`
- `gpp_response_trend_summary_1980_2024.csv`
- `plots/gpp_trend_panel_2x2.png`
- `plots/gpp_response_ratio_trend.png`
- `plots/gpp_response_speed_proxy_trend.png`
- `plots/gpp_min_abs_trend.png`
- `plots/t_min_trend.png`
- `plots/t_response_trend.png`
- `plots/t_impact_trend.png`
- `plots/t_recover_trend.png`
- `plots/gpp_drop_abs_trend.png`
- `plots/gpp_recovery_abs_trend.png`
- `plots/gpp_trend_additional_panel_2x2.png`
