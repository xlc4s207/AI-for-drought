# Pixel-Level GPP Response Trend Summary (1980-2024)

Indicators:
- response_ratio
- response_speed_proxy_mean
- gpp_min_abs_mean
- t_min_mean
- t_response_mean
- t_impact_mean
- t_recover_mean
- gpp_drop_abs_mean
- gpp_recovery_rate_abs_mean
- absolute GPP metrics use scale factor `0.01` (DN -> flux)

Trend method:
- OLS slope against year for each pixel (minimum 5 valid years).

## Spatial Summary
- Flash-SMrz | gpp_drop_abs_mean: mean_slope=0.0100942, median=0.0064047, p05=-0.109985, p95=0.12867, sig_frac=0.120
- Flash-SMs | gpp_drop_abs_mean: mean_slope=0.0156815, median=0.00866611, p05=-0.120233, p95=0.156557, sig_frac=0.110
- Nonflash-SMrz | gpp_drop_abs_mean: mean_slope=0.00073021, median=-0.000775049, p05=-0.112343, p95=0.113443, sig_frac=0.166
- Nonflash-SMs | gpp_drop_abs_mean: mean_slope=0.0041003, median=0.00181439, p05=-0.0820126, p95=0.0926491, sig_frac=0.160
- Flash-SMrz | gpp_min_abs_mean: mean_slope=-0.00219132, median=0, p05=-0.0413182, p95=0.0247882, sig_frac=0.101
- Flash-SMs | gpp_min_abs_mean: mean_slope=-0.00210492, median=0, p05=-0.0394935, p95=0.0243854, sig_frac=0.089
- Nonflash-SMrz | gpp_min_abs_mean: mean_slope=-0.00224019, median=0, p05=-0.0355028, p95=0.018833, sig_frac=0.112
- Nonflash-SMs | gpp_min_abs_mean: mean_slope=-0.00204969, median=2.49324e-05, p05=-0.0319266, p95=0.0161792, sig_frac=0.126
- Flash-SMrz | gpp_recovery_rate_abs_mean: mean_slope=0.00223134, median=0.000965693, p05=-0.00837861, p95=0.0163979, sig_frac=0.094
- Flash-SMs | gpp_recovery_rate_abs_mean: mean_slope=0.00190198, median=0.000738258, p05=-0.00919477, p95=0.0163191, sig_frac=0.084
- Nonflash-SMrz | gpp_recovery_rate_abs_mean: mean_slope=0.00231649, median=0.00121702, p05=-0.00713554, p95=0.0149617, sig_frac=0.110
- Nonflash-SMs | gpp_recovery_rate_abs_mean: mean_slope=0.00222572, median=0.00128469, p05=-0.00632009, p95=0.0135417, sig_frac=0.129
- Flash-SMrz | response_ratio: mean_slope=-0.00665386, median=-0.00689512, p05=-0.0338078, p95=0.0239631, sig_frac=0.204
- Flash-SMs | response_ratio: mean_slope=-0.00653416, median=-0.00687721, p05=-0.0347741, p95=0.0247272, sig_frac=0.189
- Nonflash-SMrz | response_ratio: mean_slope=-0.00343653, median=0, p05=-0.0232363, p95=0.0126549, sig_frac=0.117
- Nonflash-SMs | response_ratio: mean_slope=-0.00383598, median=-0.00190103, p05=-0.0222857, p95=0.0120028, sig_frac=0.155
- Flash-SMrz | response_speed_proxy_mean: mean_slope=-0.000605187, median=-0.000234322, p05=-0.0133381, p95=0.0109984, sig_frac=0.055
- Flash-SMs | response_speed_proxy_mean: mean_slope=-0.000710643, median=-0.000264045, p05=-0.0142429, p95=0.0114861, sig_frac=0.056
- Nonflash-SMrz | response_speed_proxy_mean: mean_slope=-0.000392237, median=-0.000127301, p05=-0.0105012, p95=0.00867753, sig_frac=0.078
- Nonflash-SMs | response_speed_proxy_mean: mean_slope=-0.00030962, median=-3.0457e-05, p05=-0.00969534, p95=0.00792504, sig_frac=0.081
- Flash-SMrz | t_impact_mean: mean_slope=-0.386836, median=-0.427161, p05=-3.44764, p95=2.84663, sig_frac=0.087
- Flash-SMs | t_impact_mean: mean_slope=-0.447826, median=-0.477719, p05=-3.76829, p95=3.00275, sig_frac=0.083
- Nonflash-SMrz | t_impact_mean: mean_slope=-1.11322, median=-0.88564, p05=-7.30885, p95=4.24384, sig_frac=0.126
- Nonflash-SMs | t_impact_mean: mean_slope=-1.03273, median=-0.853742, p05=-6.01772, p95=3.26746, sig_frac=0.156
- Flash-SMrz | t_min_mean: mean_slope=-0.240643, median=-0.273229, p05=-3.25963, p95=2.90523, sig_frac=0.073
- Flash-SMs | t_min_mean: mean_slope=-0.27641, median=-0.303597, p05=-3.54669, p95=3.09717, sig_frac=0.068
- Nonflash-SMrz | t_min_mean: mean_slope=-0.594027, median=-0.544018, p05=-7.09257, p95=5.73918, sig_frac=0.101
- Nonflash-SMs | t_min_mean: mean_slope=-0.510733, median=-0.470157, p05=-5.88017, p95=4.68977, sig_frac=0.111
- Flash-SMrz | t_recover_mean: mean_slope=-0.243474, median=-0.205837, p05=-2.10103, p95=1.50778, sig_frac=0.108
- Flash-SMs | t_recover_mean: mean_slope=-0.24175, median=-0.206, p05=-2.16157, p95=1.59364, sig_frac=0.097
- Nonflash-SMrz | t_recover_mean: mean_slope=-0.391476, median=-0.274204, p05=-2.94789, p95=1.79246, sig_frac=0.154
- Nonflash-SMs | t_recover_mean: mean_slope=-0.397757, median=-0.275675, p05=-2.69953, p95=1.50255, sig_frac=0.191
- Flash-SMrz | t_response_mean: mean_slope=0.146952, median=0.144414, p05=-0.951246, p95=1.2239, sig_frac=0.109
- Flash-SMs | t_response_mean: mean_slope=0.172193, median=0.164005, p05=-0.980447, p95=1.3273, sig_frac=0.102
- Nonflash-SMrz | t_response_mean: mean_slope=0.52365, median=0.38427, p05=-3.21792, p95=4.76127, sig_frac=0.171
- Nonflash-SMs | t_response_mean: mean_slope=0.52639, median=0.417751, p05=-2.79732, p95=4.26726, sig_frac=0.201

## Outputs
- pixel trend nc: `pixel_trend_maps/gpp_response_pixel_trends_<scenario>_1980_2024.nc`
- map plot: `plots_pixel_trend/response_ratio_pixel_trend_map_2x2.png`
- map plot: `plots_pixel_trend/response_speed_proxy_mean_pixel_trend_map_2x2.png`
- map plot: `plots_pixel_trend/gpp_min_abs_mean_pixel_trend_map_2x2.png`
- map plot: `plots_pixel_trend/t_min_mean_pixel_trend_map_2x2.png`
- map plot: `plots_pixel_trend/t_response_mean_pixel_trend_map_2x2.png`
- map plot: `plots_pixel_trend/t_impact_mean_pixel_trend_map_2x2.png`
- map plot: `plots_pixel_trend/t_recover_mean_pixel_trend_map_2x2.png`
- map plot: `plots_pixel_trend/gpp_drop_abs_mean_pixel_trend_map_2x2.png`
- map plot: `plots_pixel_trend/gpp_recovery_rate_abs_mean_pixel_trend_map_2x2.png`
