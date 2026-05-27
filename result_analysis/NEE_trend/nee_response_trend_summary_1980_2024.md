# NEE Response Trend Analysis (1980-2024)

## Definitions
- `response_ratio` = response_count / events
- `response_speed_proxy_mean` = mean(1 / t_response), only valid responded events
- absolute NEE metrics are scaled by factor `0.01`

## Input Files
- `flash_SMrz`: `/home/xulc/flash_drought/process/NEE-draught-analysis/code1SMrz/result/nee_response_events_global_v11_with_abs.nc`
- `flash_SMs`: `/home/xulc/flash_drought/process/NEE-draught-analysis/code2SMs/result/nee_response_SMs_events_global_v11_with_abs.nc`
- `nonflash_SMrz`: `/home/xulc/flash_drought/process/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v11_global_with_abs.nc`
- `nonflash_SMs`: `/home/xulc/flash_drought/process/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v11_global_with_abs.nc`

## Significant Trends (p < 0.05)
- Flash-SMs | amp_max_mean: slope=-0.005642/yr, p=2.22e-09, R2=0.605
- Nonflash-SMs | amp_max_mean: slope=-0.006794/yr, p=7.37e-09, R2=0.580
- Flash-SMrz | amp_max_mean: slope=-0.005265/yr, p=7.3e-08, R2=0.529
- Nonflash-SMrz | amp_max_mean: slope=-0.006315/yr, p=1.9e-07, R2=0.505
- Nonflash-SMs | events: slope=18548.507378/yr, p=5.67e-05, R2=0.317
- Nonflash-SMrz | events: slope=10329.024506/yr, p=0.000275, R2=0.267
- Nonflash-SMrz | nee_drop_abs_mean: slope=0.027037/yr, p=3.66e-13, R2=0.746
- Nonflash-SMs | nee_drop_abs_mean: slope=0.021261/yr, p=1.76e-11, R2=0.691
- Flash-SMrz | nee_drop_abs_mean: slope=0.007129/yr, p=0.00135, R2=0.234
- Nonflash-SMs | nee_min_abs_mean: slope=-0.018394/yr, p=4.52e-13, R2=0.743
- Nonflash-SMrz | nee_min_abs_mean: slope=-0.019906/yr, p=5.67e-13, R2=0.740
- Flash-SMrz | nee_min_abs_mean: slope=-0.010782/yr, p=1.69e-06, R2=0.448
- Flash-SMrz | nee_recovery_rate_abs_mean: slope=0.000728/yr, p=4.59e-11, R2=0.675
- Nonflash-SMs | nee_recovery_rate_abs_mean: slope=0.000867/yr, p=1.63e-10, R2=0.654
- Flash-SMs | nee_recovery_rate_abs_mean: slope=0.000541/yr, p=5.15e-10, R2=0.633
- Nonflash-SMrz | nee_recovery_rate_abs_mean: slope=0.000856/yr, p=6.44e-10, R2=0.629
- Nonflash-SMrz | recovery_rate_mean: slope=0.000444/yr, p=4.22e-05, R2=0.353
- Nonflash-SMs | recovery_rate_mean: slope=0.000380/yr, p=0.000187, R2=0.304
- Nonflash-SMs | response_count: slope=13357.490382/yr, p=0.000251, R2=0.270
- Nonflash-SMrz | response_count: slope=6770.878920/yr, p=0.00221, R2=0.198
- Flash-SMs | response_ratio: slope=-0.006858/yr, p=6.91e-20, R2=0.885
- Flash-SMrz | response_ratio: slope=-0.006593/yr, p=2.71e-18, R2=0.861
- Nonflash-SMs | response_ratio: slope=-0.004433/yr, p=9.77e-18, R2=0.851
- Nonflash-SMrz | response_ratio: slope=-0.004834/yr, p=2.14e-17, R2=0.845
- Nonflash-SMs | response_speed_proxy_mean: slope=-0.000760/yr, p=3.34e-10, R2=0.641
- Nonflash-SMrz | response_speed_proxy_mean: slope=-0.000676/yr, p=1.74e-09, R2=0.610
- Flash-SMs | response_speed_proxy_mean: slope=-0.000609/yr, p=5.28e-07, R2=0.480
- Flash-SMrz | response_speed_proxy_mean: slope=-0.000541/yr, p=2.96e-05, R2=0.364
- Nonflash-SMrz | t_impact_mean: slope=-1.306538/yr, p=1.17e-15, R2=0.810
- Nonflash-SMs | t_impact_mean: slope=-1.105092/yr, p=3.33e-15, R2=0.800
- Flash-SMs | t_impact_mean: slope=-0.428830/yr, p=5.61e-15, R2=0.795
- Flash-SMrz | t_impact_mean: slope=-0.463563/yr, p=1.11e-13, R2=0.761
- Nonflash-SMrz | t_min_mean: slope=-0.712102/yr, p=3.22e-07, R2=0.492
- Nonflash-SMs | t_min_mean: slope=-0.525194/yr, p=2.72e-06, R2=0.435
- Flash-SMrz | t_min_mean: slope=-0.084675/yr, p=0.0255, R2=0.122
- Nonflash-SMrz | t_recover_mean: slope=-0.352687/yr, p=1.23e-14, R2=0.786
- Nonflash-SMs | t_recover_mean: slope=-0.348239/yr, p=1.39e-14, R2=0.785
- Flash-SMs | t_recover_mean: slope=-0.186876/yr, p=1.37e-10, R2=0.657
- Flash-SMrz | t_recover_mean: slope=-0.183087/yr, p=2.15e-09, R2=0.605
- Nonflash-SMs | t_response_mean: slope=0.472643/yr, p=1.85e-15, R2=0.806
- Nonflash-SMrz | t_response_mean: slope=0.479560/yr, p=4.81e-14, R2=0.771
- Flash-SMs | t_response_mean: slope=0.147667/yr, p=4.58e-13, R2=0.743
- Flash-SMrz | t_response_mean: slope=0.138710/yr, p=9.82e-11, R2=0.662

## Files Generated
- `nee_yearly_response_timeseries_1980_2024.csv`
- `nee_response_trend_summary_1980_2024.csv`
- `plots/nee_trend_panel_2x2.png`
- `plots/nee_trend_additional_panel.png`
- `plots/nee_response_ratio_trend.png`
- `plots/nee_response_speed_proxy_trend.png`
- `plots/nee_min_abs_trend.png`
- `plots/nee_t_min_trend.png`
- `plots/nee_t_response_trend.png`
- `plots/nee_t_impact_trend.png`
- `plots/nee_t_recover_trend.png`
- `plots/nee_drop_abs_trend.png`
- `plots/nee_recovery_abs_trend.png`
