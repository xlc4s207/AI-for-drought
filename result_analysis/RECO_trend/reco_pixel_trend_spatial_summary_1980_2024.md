# Pixel-Level RECO Response Trend Summary (1980-2024)

Indicators:
- response_ratio
- response_speed_proxy_mean
- reco_min_abs_mean
- t_min_mean
- t_response_mean
- t_impact_mean
- t_recover_mean
- reco_drop_abs_mean
- reco_recovery_rate_abs_mean
- absolute RECO metrics use scale factor `0.01`

Trend method: OLS slope against year for each pixel (minimum 5 valid years).

## Spatial Summary
- Flash-SMrz | reco_drop_abs_mean: mean_slope=0.00788808, median=0.00487526, p05=-0.0665476, p95=0.087895, sig_frac=0.112
- Flash-SMs | reco_drop_abs_mean: mean_slope=0.0122793, median=0.00710901, p05=-0.0693074, p95=0.103521, sig_frac=0.101
- Nonflash-SMrz | reco_drop_abs_mean: mean_slope=0.00202477, median=0.000499667, p05=-0.0721523, p95=0.0815903, sig_frac=0.187
- Nonflash-SMs | reco_drop_abs_mean: mean_slope=0.00328767, median=0.00132759, p05=-0.0529722, p95=0.0678622, sig_frac=0.184
- Flash-SMrz | reco_min_abs_mean: mean_slope=-0.00340612, median=0, p05=-0.0392739, p95=0.0194998, sig_frac=0.164
- Flash-SMs | reco_min_abs_mean: mean_slope=-0.00309398, median=0, p05=-0.0377402, p95=0.0195632, sig_frac=0.145
- Nonflash-SMrz | reco_min_abs_mean: mean_slope=-0.00262883, median=0.000107564, p05=-0.0349411, p95=0.0166645, sig_frac=0.203
- Nonflash-SMs | reco_min_abs_mean: mean_slope=-0.00234576, median=0.000210275, p05=-0.0324521, p95=0.0145432, sig_frac=0.232
- Flash-SMrz | reco_recovery_rate_abs_mean: mean_slope=0.00160939, median=0.000678028, p05=-0.00553242, p95=0.0118866, sig_frac=0.095
- Flash-SMs | reco_recovery_rate_abs_mean: mean_slope=0.00134088, median=0.00050968, p05=-0.00567723, p95=0.0111811, sig_frac=0.083
- Nonflash-SMrz | reco_recovery_rate_abs_mean: mean_slope=0.00148707, median=0.00069293, p05=-0.00447667, p95=0.0102901, sig_frac=0.103
- Nonflash-SMs | reco_recovery_rate_abs_mean: mean_slope=0.00146863, median=0.000726436, p05=-0.00402611, p95=0.00969318, sig_frac=0.124
- Flash-SMrz | response_ratio: mean_slope=-0.00168942, median=-0.00246855, p05=-0.0343401, p95=0.0356862, sig_frac=0.297
- Flash-SMs | response_ratio: mean_slope=-0.00133774, median=-0.00196796, p05=-0.0347351, p95=0.0359793, sig_frac=0.272
- Nonflash-SMrz | response_ratio: mean_slope=-0.00079371, median=0, p05=-0.0229206, p95=0.0221084, sig_frac=0.161
- Nonflash-SMs | response_ratio: mean_slope=-0.000885739, median=0, p05=-0.0224208, p95=0.0222479, sig_frac=0.197
- Flash-SMrz | response_speed_proxy_mean: mean_slope=-0.000404984, median=-9.66488e-05, p05=-0.013844, p95=0.0120488, sig_frac=0.054
- Flash-SMs | response_speed_proxy_mean: mean_slope=-0.000644584, median=-0.000225625, p05=-0.0151841, p95=0.0126511, sig_frac=0.055
- Nonflash-SMrz | response_speed_proxy_mean: mean_slope=-8.36163e-06, median=0.00013264, p05=-0.0106284, p95=0.00981979, sig_frac=0.083
- Nonflash-SMs | response_speed_proxy_mean: mean_slope=0.000216215, median=0.000311663, p05=-0.0099706, p95=0.00970344, sig_frac=0.089
- Flash-SMrz | t_impact_mean: mean_slope=-0.375483, median=-0.405473, p05=-3.83739, p95=3.20521, sig_frac=0.100
- Flash-SMs | t_impact_mean: mean_slope=-0.355758, median=-0.376898, p05=-4.00508, p95=3.38878, sig_frac=0.088
- Nonflash-SMrz | t_impact_mean: mean_slope=-0.849794, median=-0.78594, p05=-7.12237, p95=4.99726, sig_frac=0.160
- Nonflash-SMs | t_impact_mean: mean_slope=-0.770103, median=-0.763672, p05=-5.92805, p95=4.15739, sig_frac=0.198
- Flash-SMrz | t_min_mean: mean_slope=-0.291124, median=-0.308696, p05=-3.64653, p95=3.15596, sig_frac=0.080
- Flash-SMs | t_min_mean: mean_slope=-0.245423, median=-0.262262, p05=-3.78487, p95=3.37198, sig_frac=0.071
- Nonflash-SMrz | t_min_mean: mean_slope=-0.756976, median=-0.655513, p05=-7.12816, p95=5.22868, sig_frac=0.108
- Nonflash-SMs | t_min_mean: mean_slope=-0.665854, median=-0.638654, p05=-5.87784, p95=4.43249, sig_frac=0.128
- Flash-SMrz | t_recover_mean: mean_slope=-0.193385, median=-0.12891, p05=-2.01574, p95=1.39005, sig_frac=0.113
- Flash-SMs | t_recover_mean: mean_slope=-0.170476, median=-0.112545, p05=-2.01803, p95=1.47222, sig_frac=0.100
- Nonflash-SMrz | t_recover_mean: mean_slope=-0.24698, median=-0.119239, p05=-2.47791, p95=1.49741, sig_frac=0.156
- Nonflash-SMs | t_recover_mean: mean_slope=-0.263994, median=-0.126823, p05=-2.46887, p95=1.39506, sig_frac=0.203
- Flash-SMrz | t_response_mean: mean_slope=0.0849813, median=0.0819371, p05=-1.03436, p95=1.1648, sig_frac=0.124
- Flash-SMs | t_response_mean: mean_slope=0.11086, median=0.101837, p05=-1.0533, p95=1.24993, sig_frac=0.118
- Nonflash-SMrz | t_response_mean: mean_slope=0.0945206, median=0.167545, p05=-3.95586, p95=3.87027, sig_frac=0.239
- Nonflash-SMs | t_response_mean: mean_slope=0.105842, median=0.157743, p05=-3.6778, p95=3.70298, sig_frac=0.282
