# 碳通量 12 个 rec100 结果综合对比分析

## 数据范围与口径

- 本次共对比 12 个结果文件：GPP、NEE、RECO 各 4 个脚本，对应 `code1-code4`。
- 时间趋势统一按 `onset_year` 聚合为逐年均值/中位数后，再拟合线性趋势，单位为 `天/10年`。
- `变化的值` 对应结果文件中的 `*_change_to_peak_abs`，保留原符号。
- `变化幅度` 对应 `abs(*_change_to_peak_abs)`，表示绝对变化量大小。
- `相对峰值幅度` 对应 `amp_max`，是基于相对异常序列识别出的峰值幅度。
- 响应像元/恢复像元占比是相对于该结果文件全部输出事件涉及的唯一像元数计算。

## 综合总表

| 标签 | 输出事件数 | 响应事件数 | 响应事件占比(%) | 响应像元数 | 响应像元占比(%) | 恢复事件数 | 恢复/输出(%) | 恢复/响应(%) | 恢复像元数 | 恢复像元占比(%) | 变化值均值 | 变化幅度均值 | 相对峰值幅度均值 | 响应时间_onset均值 | 响应时间_onset中位数 | 恢复时间_peak均值 | 恢复时间_peak中位数 | 响应时间趋势(天/10年) | 恢复时间趋势(天/10年) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPP_SMrz_flash | 5,550,331 | 2,601,866 | 46.88 | 192,932 | 95.40 | 1,360,259 | 24.51 | 52.28 | 132,040 | 65.29 | -239.56 | 243.31 | -0.95 | 45.66 | 23.00 | 36.20 | 31.00 | 12.19 | 1.33 |
| GPP_SMs_flash | 8,021,635 | 3,860,055 | 48.12 | 202,103 | 97.87 | 2,125,585 | 26.50 | 55.07 | 143,363 | 69.42 | -226.31 | 229.49 | -0.93 | 45.48 | 21.00 | 36.17 | 31.00 | 12.26 | 1.24 |
| GPP_SMrz_slow | 873,564 | 561,342 | 64.26 | 159,577 | 84.96 | 304,250 | 34.83 | 54.20 | 98,606 | 52.50 | -283.54 | 285.96 | -0.98 | 46.24 | 24.00 | 40.03 | 37.00 | 14.79 | 1.97 |
| GPP_SMs_slow | 228,624 | 108,413 | 47.42 | 72,576 | 59.99 | 59,452 | 26.00 | 54.84 | 41,445 | 34.26 | -239.14 | 241.17 | -0.96 | 43.52 | 20.00 | 38.52 | 35.00 | 12.92 | 1.17 |
| NEE_SMrz_flash | 5,555,403 | 2,872,751 | 51.71 | 195,559 | 96.64 | 2,192,276 | 39.46 | 76.31 | 191,993 | 94.88 | 96.19 | 97.66 | 1.04 | 42.96 | 17.00 | 28.17 | 19.00 | 7.80 | -0.43 |
| NEE_SMs_flash | 8,026,560 | 4,346,147 | 54.15 | 203,714 | 98.60 | 3,342,901 | 41.65 | 76.92 | 202,910 | 98.21 | 92.46 | 93.75 | 1.02 | 43.93 | 18.00 | 28.33 | 19.00 | 9.07 | 0.08 |
| NEE_SMrz_slow | 873,656 | 533,251 | 61.04 | 159,727 | 85.02 | 356,177 | 40.77 | 66.79 | 139,798 | 74.41 | 130.98 | 131.88 | 1.13 | 45.84 | 20.00 | 36.41 | 31.00 | 13.17 | 1.78 |
| NEE_SMs_slow | 228,694 | 118,993 | 52.03 | 79,805 | 65.94 | 87,011 | 38.05 | 73.12 | 63,348 | 52.34 | 106.86 | 107.60 | 1.13 | 42.05 | 17.00 | 34.85 | 29.00 | 10.91 | 1.66 |
| RECO_SMrz_flash | 5,554,780 | 3,685,386 | 66.35 | 197,047 | 97.33 | 2,064,477 | 37.17 | 56.02 | 173,710 | 85.80 | -138.04 | 140.54 | -1.07 | 39.67 | 15.00 | 35.13 | 26.00 | 3.71 | 1.02 |
| RECO_SMs_flash | 8,029,545 | 5,475,192 | 68.19 | 204,005 | 98.69 | 3,273,253 | 40.77 | 59.78 | 186,476 | 90.21 | -127.47 | 129.73 | -1.07 | 38.03 | 13.00 | 34.07 | 24.00 | 3.89 | 0.96 |
| RECO_SMrz_slow | 874,815 | 657,904 | 75.20 | 168,745 | 89.73 | 372,852 | 42.62 | 56.67 | 124,776 | 66.35 | -167.84 | 169.74 | -1.16 | 41.12 | 17.00 | 37.31 | 31.00 | 6.70 | 2.25 |
| RECO_SMs_slow | 228,727 | 141,307 | 61.78 | 89,611 | 74.02 | 85,887 | 37.55 | 60.78 | 60,991 | 50.38 | -131.54 | 133.32 | -1.11 | 38.82 | 14.00 | 33.36 | 23.00 | 5.49 | 1.38 |

## 分变量详细解读

### GPP
- `GPP` 中响应事件占比最高的是 `GPP_SMrz_slow`，为 64.26%。
- `GPP` 中恢复事件占比最高的是 `GPP_SMrz_slow`，为 34.83%。
- `GPP` 中平均绝对变化幅度最大的是 `GPP_SMrz_slow`，均值为 285.96。
- `GPP_SMrz_flash`：响应时间(onset)均值/中位数 45.66/23.00 天，恢复时间(peak)均值/中位数 36.20/31.00 天；响应时间趋势 延长 (12.19 天/10年)，恢复时间趋势 延长 (1.33 天/10年)。
- `GPP_SMs_flash`：响应时间(onset)均值/中位数 45.48/21.00 天，恢复时间(peak)均值/中位数 36.17/31.00 天；响应时间趋势 延长 (12.26 天/10年)，恢复时间趋势 延长 (1.24 天/10年)。
- `GPP_SMrz_slow`：响应时间(onset)均值/中位数 46.24/24.00 天，恢复时间(peak)均值/中位数 40.03/37.00 天；响应时间趋势 延长 (14.79 天/10年)，恢复时间趋势 延长 (1.97 天/10年)。
- `GPP_SMs_slow`：响应时间(onset)均值/中位数 43.52/20.00 天，恢复时间(peak)均值/中位数 38.52/35.00 天；响应时间趋势 延长 (12.92 天/10年)，恢复时间趋势 延长 (1.17 天/10年)。

### NEE
- `NEE` 中响应事件占比最高的是 `NEE_SMrz_slow`，为 61.04%。
- `NEE` 中恢复事件占比最高的是 `NEE_SMs_flash`，为 41.65%。
- `NEE` 中平均绝对变化幅度最大的是 `NEE_SMrz_slow`，均值为 131.88。
- `NEE_SMrz_flash`：响应时间(onset)均值/中位数 42.96/17.00 天，恢复时间(peak)均值/中位数 28.17/19.00 天；响应时间趋势 延长 (7.80 天/10年)，恢复时间趋势 缩短 (-0.43 天/10年)。
- `NEE_SMs_flash`：响应时间(onset)均值/中位数 43.93/18.00 天，恢复时间(peak)均值/中位数 28.33/19.00 天；响应时间趋势 延长 (9.07 天/10年)，恢复时间趋势 基本稳定 (0.08 天/10年)。
- `NEE_SMrz_slow`：响应时间(onset)均值/中位数 45.84/20.00 天，恢复时间(peak)均值/中位数 36.41/31.00 天；响应时间趋势 延长 (13.17 天/10年)，恢复时间趋势 延长 (1.78 天/10年)。
- `NEE_SMs_slow`：响应时间(onset)均值/中位数 42.05/17.00 天，恢复时间(peak)均值/中位数 34.85/29.00 天；响应时间趋势 延长 (10.91 天/10年)，恢复时间趋势 延长 (1.66 天/10年)。

### RECO
- `RECO` 中响应事件占比最高的是 `RECO_SMrz_slow`，为 75.20%。
- `RECO` 中恢复事件占比最高的是 `RECO_SMrz_slow`，为 42.62%。
- `RECO` 中平均绝对变化幅度最大的是 `RECO_SMrz_slow`，均值为 169.74。
- `RECO_SMrz_flash`：响应时间(onset)均值/中位数 39.67/15.00 天，恢复时间(peak)均值/中位数 35.13/26.00 天；响应时间趋势 延长 (3.71 天/10年)，恢复时间趋势 延长 (1.02 天/10年)。
- `RECO_SMs_flash`：响应时间(onset)均值/中位数 38.03/13.00 天，恢复时间(peak)均值/中位数 34.07/24.00 天；响应时间趋势 延长 (3.89 天/10年)，恢复时间趋势 延长 (0.96 天/10年)。
- `RECO_SMrz_slow`：响应时间(onset)均值/中位数 41.12/17.00 天，恢复时间(peak)均值/中位数 37.31/31.00 天；响应时间趋势 延长 (6.70 天/10年)，恢复时间趋势 延长 (2.25 天/10年)。
- `RECO_SMs_slow`：响应时间(onset)均值/中位数 38.82/14.00 天，恢复时间(peak)均值/中位数 33.36/23.00 天；响应时间趋势 延长 (5.49 天/10年)，恢复时间趋势 延长 (1.38 天/10年)。

## 结果文件与字段说明

- `GPP_SMrz_flash`
  数据文件: `/data/BESS_V2/BESS_GPP_1982_2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc`
  绝对基线字段: `gpp_baseline_abs`；峰值字段: `gpp_min_abs`；变化值字段: `gpp_change_to_peak_abs`。
- `GPP_SMs_flash`
  数据文件: `/data/BESS_V2/BESS_GPP_1982_2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc`
  绝对基线字段: `gpp_baseline_abs`；峰值字段: `gpp_min_abs`；变化值字段: `gpp_change_to_peak_abs`。
- `GPP_SMrz_slow`
  数据文件: `/data/BESS_V2/BESS_GPP_1982_2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc`
  绝对基线字段: `gpp_baseline_abs`；峰值字段: `gpp_min_abs`；变化值字段: `gpp_change_to_peak_abs`。
- `GPP_SMs_slow`
  数据文件: `/data/BESS_V2/BESS_GPP_1982_2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc`
  绝对基线字段: `gpp_baseline_abs`；峰值字段: `gpp_min_abs`；变化值字段: `gpp_change_to_peak_abs`。
- `NEE_SMrz_flash`
  数据文件: `/data/BESS_V2/NEE_1982-2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc`
  绝对基线字段: `nee_baseline_abs`；峰值字段: `nee_max_abs`；变化值字段: `nee_change_to_peak_abs`。
- `NEE_SMs_flash`
  数据文件: `/data/BESS_V2/NEE_1982-2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc`
  绝对基线字段: `nee_baseline_abs`；峰值字段: `nee_max_abs`；变化值字段: `nee_change_to_peak_abs`。
- `NEE_SMrz_slow`
  数据文件: `/data/BESS_V2/NEE_1982-2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc`
  绝对基线字段: `nee_baseline_abs`；峰值字段: `nee_max_abs`；变化值字段: `nee_change_to_peak_abs`。
- `NEE_SMs_slow`
  数据文件: `/data/BESS_V2/NEE_1982-2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc`
  绝对基线字段: `nee_baseline_abs`；峰值字段: `nee_max_abs`；变化值字段: `nee_change_to_peak_abs`。
- `RECO_SMrz_flash`
  数据文件: `/data/BESS_V2/BESS_RECO_1982-2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc`
  绝对基线字段: `reco_baseline_abs`；峰值字段: `reco_min_abs`；变化值字段: `reco_change_to_peak_abs`。
- `RECO_SMs_flash`
  数据文件: `/data/BESS_V2/BESS_RECO_1982-2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/flash_lt20_drought_events_v5.4.nc`
  绝对基线字段: `reco_baseline_abs`；峰值字段: `reco_min_abs`；变化值字段: `reco_change_to_peak_abs`。
- `RECO_SMrz_slow`
  数据文件: `/data/BESS_V2/BESS_RECO_1982-2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc`
  绝对基线字段: `reco_baseline_abs`；峰值字段: `reco_min_abs`；变化值字段: `reco_change_to_peak_abs`。
- `RECO_SMs_slow`
  数据文件: `/data/BESS_V2/BESS_RECO_1982-2022_0.25deg.nc`
  事件文件: `/home/xulc/flash_drought/gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/slow_gt20_drought_events_v5.4.nc`
  绝对基线字段: `reco_baseline_abs`；峰值字段: `reco_min_abs`；变化值字段: `reco_change_to_peak_abs`。

完整宽表见: `/home/xulc/flash_drought/process/result_analysis/compare_analysis2/compare_analysis2_rec100_summary_20260325.csv`
