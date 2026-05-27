# Pixel-Level NEE Response Trend Summary (1980-2024)

Indicators:
- response_ratio
- response_speed_proxy_mean
- nee_min_abs_mean
- t_min_mean
- t_response_mean
- t_impact_mean
- t_recover_mean
- nee_drop_abs_mean
- nee_recovery_rate_abs_mean
- absolute NEE metrics use scale factor `0.01`

Trend method: OLS slope against year for each pixel (minimum 5 valid years).

## Spatial Summary
- Flash-SMrz | nee_drop_abs_mean: mean_slope=0.00476981, median=0.00482323, p05=-0.0833252, p95=0.0893527, sig_frac=0.151
- Flash-SMs | nee_drop_abs_mean: mean_slope=0.00457378, median=0.00470182, p05=-0.0988863, p95=0.101701, sig_frac=0.132
- Nonflash-SMrz | nee_drop_abs_mean: mean_slope=0.0119968, median=0.00839644, p05=-0.0630609, p95=0.0921118, sig_frac=0.214
- Nonflash-SMs | nee_drop_abs_mean: mean_slope=0.0113118, median=0.00814843, p05=-0.0594605, p95=0.0858352, sig_frac=0.250
- Flash-SMrz | nee_min_abs_mean: mean_slope=-0.000206528, median=0, p05=-0.00826296, p95=0.0067002, sig_frac=0.065
- Flash-SMs | nee_min_abs_mean: mean_slope=-0.000272189, median=0, p05=-0.00827476, p95=0.00653878, sig_frac=0.070
- Nonflash-SMrz | nee_min_abs_mean: mean_slope=9.56231e-05, median=0, p05=-0.00500831, p95=0.00496729, sig_frac=0.076
- Nonflash-SMs | nee_min_abs_mean: mean_slope=9.93826e-05, median=0, p05=-0.00483833, p95=0.00484829, sig_frac=0.065
- Flash-SMrz | nee_recovery_rate_abs_mean: mean_slope=0.000721413, median=0.000223843, p05=-0.00459996, p95=0.00781278, sig_frac=0.089
- Flash-SMs | nee_recovery_rate_abs_mean: mean_slope=0.000691183, median=0.000224481, p05=-0.00461032, p95=0.00763535, sig_frac=0.080
- Nonflash-SMrz | nee_recovery_rate_abs_mean: mean_slope=0.000845172, median=0.000270835, p05=-0.00344125, p95=0.00724457, sig_frac=0.095
- Nonflash-SMs | nee_recovery_rate_abs_mean: mean_slope=0.000856829, median=0.000311838, p05=-0.00316631, p95=0.00687466, sig_frac=0.113
- Flash-SMrz | response_ratio: mean_slope=-0.00691399, median=-0.00664339, p05=-0.0383454, p95=0.0306138, sig_frac=0.308
- Flash-SMs | response_ratio: mean_slope=-0.00781961, median=-0.00779266, p05=-0.039758, p95=0.0301716, sig_frac=0.287
- Nonflash-SMrz | response_ratio: mean_slope=-0.00344922, median=0, p05=-0.0297115, p95=0.0173756, sig_frac=0.168
- Nonflash-SMs | response_ratio: mean_slope=-0.00381282, median=0, p05=-0.0293625, p95=0.0164177, sig_frac=0.207
- Flash-SMrz | response_speed_proxy_mean: mean_slope=-0.000424822, median=-0.000211033, p05=-0.0132245, p95=0.0117951, sig_frac=0.056
- Flash-SMs | response_speed_proxy_mean: mean_slope=-0.000521306, median=-0.000255519, p05=-0.013183, p95=0.011383, sig_frac=0.056
- Nonflash-SMrz | response_speed_proxy_mean: mean_slope=-0.000390114, median=-0.00019351, p05=-0.0112936, p95=0.00960937, sig_frac=0.106
- Nonflash-SMs | response_speed_proxy_mean: mean_slope=-0.000665874, median=-0.000288259, p05=-0.0105132, p95=0.00775154, sig_frac=0.118
- Flash-SMrz | t_impact_mean: mean_slope=-0.514814, median=-0.485426, p05=-4.3227, p95=3.14901, sig_frac=0.111
- Flash-SMs | t_impact_mean: mean_slope=-0.485091, median=-0.461938, p05=-4.45494, p95=3.36245, sig_frac=0.094
- Nonflash-SMrz | t_impact_mean: mean_slope=-1.26861, median=-1.18574, p05=-7.5712, p95=4.62541, sig_frac=0.186
- Nonflash-SMs | t_impact_mean: mean_slope=-1.28165, median=-1.20945, p05=-6.62855, p95=3.7107, sig_frac=0.237
- Flash-SMrz | t_min_mean: mean_slope=-0.0890909, median=-0.0763522, p05=-3.91318, p95=3.66726, sig_frac=0.074
- Flash-SMs | t_min_mean: mean_slope=-0.0302005, median=-0.00815202, p05=-4.02602, p95=3.87638, sig_frac=0.065
- Nonflash-SMrz | t_min_mean: mean_slope=-0.485941, median=-0.414818, p05=-6.86341, p95=5.58989, sig_frac=0.087
- Nonflash-SMs | t_min_mean: mean_slope=-0.457132, median=-0.427224, p05=-5.6995, p95=4.68362, sig_frac=0.100
- Flash-SMrz | t_recover_mean: mean_slope=-0.221587, median=-0.161809, p05=-1.92743, p95=1.3142, sig_frac=0.100
- Flash-SMs | t_recover_mean: mean_slope=-0.229925, median=-0.160754, p05=-1.93982, p95=1.27497, sig_frac=0.087
- Nonflash-SMrz | t_recover_mean: mean_slope=-0.308376, median=-0.199186, p05=-2.29401, p95=1.35798, sig_frac=0.156
- Nonflash-SMs | t_recover_mean: mean_slope=-0.340327, median=-0.230015, p05=-2.17846, p95=1.14493, sig_frac=0.195
- Flash-SMrz | t_response_mean: mean_slope=0.153019, median=0.117193, p05=-0.926714, p95=1.30699, sig_frac=0.123
- Flash-SMs | t_response_mean: mean_slope=0.162736, median=0.12474, p05=-0.968073, p95=1.37802, sig_frac=0.108
- Nonflash-SMrz | t_response_mean: mean_slope=0.571342, median=0.369912, p05=-3.05047, p95=4.64013, sig_frac=0.212
- Nonflash-SMs | t_response_mean: mean_slope=0.628624, median=0.448643, p05=-2.83262, p95=4.50903, sig_frac=0.262
