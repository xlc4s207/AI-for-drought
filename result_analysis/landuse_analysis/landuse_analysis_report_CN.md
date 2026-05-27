# 基于 MODIS 土地利用类型的干旱碳通量分组分析

## 1. 分析范围
- 本轮基于 200 条土地利用分组摘要记录。
- 输入数据为 12 个可用 `nc` 文件，对应 GPP / NEE / RECO × flash / nonflash × SMrz / SMs 组合。
- `1982-2000` 事件统一映射到 `2001` 年 MODIS 土地利用类型；`2001-2021` 使用对应年份土地利用图。
- `GPP/RECO` 的不利变化值使用 `drop_abs`，`NEE` 使用 `rise_abs`。
- 图件与下述文本对比结论统一排除 `Water Bodies`、`Snow and Ice`、`Barren or Sparsely Vegetated` 三类非典型植被下垫面。

## 2. 主体结论
### 2.1 GPP
- 最大不利变化值出现在 `Evergreen Broadleaf Forest` | `nonflash+SMs`，均值为 447.835891。
- 最快响应出现在 `Open Shrublands` | `flash+SMs`，平均 `t_response=7.300316`。
- 最慢恢复出现在 `Closed Shrublands` | `nonflash+SMrz`，平均 `t_recover=35.756649`。

### 2.2 NEE
- 最大不利变化值出现在 `Deciduous Broadleaf Forest` | `flash+SMrz`，均值为 140.380744。
- 最快响应出现在 `Permanent Wetlands` | `flash+SMrz`，平均 `t_response=6.356169`。
- 最慢恢复出现在 `Croplands` | `nonflash+SMrz`，平均 `t_recover=32.477996`。

### 2.3 RECO
- 最大不利变化值出现在 `Evergreen Broadleaf Forest` | `nonflash+SMs`，均值为 403.371519。
- 最快响应出现在 `Urban and Built-up` | `flash+SMs`，平均 `t_response=4.759862`。
- 最慢恢复出现在 `Closed Shrublands` | `nonflash+SMrz`，平均 `t_recover=35.148632`。

## 3. 差值对比（按土地利用类型）
- flash_vs_nonflash | GPP | Mixed Forests | directional_change_abs_mean | flash+SMs=315.279173, nonflash+SMs=144.906668, delta=-170.372505
- flash_vs_nonflash | GPP | Mixed Forests | directional_change_abs_mean | flash+SMrz=294.218479, nonflash+SMrz=136.900795, delta=-157.317684
- flash_vs_nonflash | GPP | Deciduous Broadleaf Forest | directional_change_abs_mean | flash+SMs=386.762208, nonflash+SMs=234.694296, delta=-152.067912
- flash_vs_nonflash | GPP | Deciduous Broadleaf Forest | directional_change_abs_mean | flash+SMrz=365.914366, nonflash+SMrz=233.510958, delta=-132.403408
- flash_vs_nonflash | GPP | Deciduous Needleleaf Forest | directional_change_abs_mean | flash+SMs=245.768736, nonflash+SMs=124.748977, delta=-121.019759
- flash_vs_nonflash | GPP | Evergreen Needleleaf Forest | directional_change_abs_mean | flash+SMs=229.078992, nonflash+SMs=114.527952, delta=-114.55104
- flash_vs_nonflash | GPP | Evergreen Needleleaf Forest | directional_change_abs_mean | flash+SMrz=208.370183, nonflash+SMrz=95.583684, delta=-112.786499
- flash_vs_nonflash | GPP | Woody Savannas | directional_change_abs_mean | flash+SMrz=274.931873, nonflash+SMrz=162.649152, delta=-112.282721
- flash_vs_nonflash | GPP | Deciduous Needleleaf Forest | directional_change_abs_mean | flash+SMrz=260.496359, nonflash+SMrz=150.837538, delta=-109.658821
- flash_vs_nonflash | GPP | Woody Savannas | directional_change_abs_mean | flash+SMs=263.751121, nonflash+SMs=167.29759, delta=-96.453531
- flash_vs_nonflash | GPP | Permanent Wetlands | directional_change_abs_mean | flash+SMrz=166.963916, nonflash+SMrz=76.490967, delta=-90.472949
- flash_vs_nonflash | RECO | Mixed Forests | directional_change_abs_mean | flash+SMs=225.167445, nonflash+SMs=134.917128, delta=-90.250317
- flash_vs_nonflash | GPP | Urban and Built-up | directional_change_abs_mean | flash+SMrz=233.354217, nonflash+SMrz=148.870077, delta=-84.48414
- flash_vs_nonflash | GPP | Cropland and Natural Vegetation Mosaic | directional_change_abs_mean | flash+SMrz=331.93554, nonflash+SMrz=247.879375, delta=-84.056165
- flash_vs_nonflash | RECO | Mixed Forests | directional_change_abs_mean | flash+SMrz=208.589122, nonflash+SMrz=127.587962, delta=-81.00116
- flash_vs_nonflash | GPP | Savannas | directional_change_abs_mean | flash+SMrz=266.117697, nonflash+SMrz=193.134957, delta=-72.98274
- flash_vs_nonflash | RECO | Deciduous Broadleaf Forest | directional_change_abs_mean | flash+SMs=228.744275, nonflash+SMs=159.089026, delta=-69.655249
- flash_vs_nonflash | GPP | Permanent Wetlands | directional_change_abs_mean | flash+SMs=157.770715, nonflash+SMs=88.128312, delta=-69.642403
- flash_vs_nonflash | GPP | Croplands | directional_change_abs_mean | flash+SMrz=283.665171, nonflash+SMrz=215.225335, delta=-68.439836
- flash_vs_nonflash | RECO | Woody Savannas | directional_change_abs_mean | flash+SMrz=192.237253, nonflash+SMrz=124.386311, delta=-67.850942
- flash_vs_nonflash | RECO | Evergreen Needleleaf Forest | directional_change_abs_mean | flash+SMs=177.63905, nonflash+SMs=109.880057, delta=-67.758993
- flash_vs_nonflash | RECO | Deciduous Needleleaf Forest | directional_change_abs_mean | flash+SMs=183.540943, nonflash+SMs=115.806295, delta=-67.734648
- flash_vs_nonflash | RECO | Evergreen Needleleaf Forest | directional_change_abs_mean | flash+SMrz=163.945795, nonflash+SMrz=96.394875, delta=-67.55092
- flash_vs_nonflash | RECO | Deciduous Needleleaf Forest | directional_change_abs_mean | flash+SMrz=192.115124, nonflash+SMrz=126.827016, delta=-65.288108
- flash_vs_nonflash | GPP | Savannas | directional_change_abs_mean | flash+SMs=253.920333, nonflash+SMs=190.821084, delta=-63.099249
- flash_vs_nonflash | RECO | Permanent Wetlands | directional_change_abs_mean | flash+SMrz=134.973546, nonflash+SMrz=72.191314, delta=-62.782232
- flash_vs_nonflash | GPP | Cropland and Natural Vegetation Mosaic | directional_change_abs_mean | flash+SMs=328.76993, nonflash+SMs=270.08063, delta=-58.6893
- flash_vs_nonflash | RECO | Woody Savannas | directional_change_abs_mean | flash+SMs=185.793626, nonflash+SMs=128.095419, delta=-57.698207
- flash_vs_nonflash | RECO | Deciduous Broadleaf Forest | directional_change_abs_mean | flash+SMrz=214.851459, nonflash+SMrz=157.525526, delta=-57.325933
- flash_vs_nonflash | NEE | Evergreen Needleleaf Forest | directional_change_abs_mean | flash+SMrz=130.065628, nonflash+SMrz=74.464965, delta=-55.600663

## 4. 解释边界
- `1982-2000` 使用 `2001` 年土地利用图代替，适用于“土地利用总体变化不大”的近似分析，不等同于真实逐年地表覆盖历史。
- MODIS `LC_Type1` 当前实际值域为 `0-16`，其中 `0` 视为 `Water Bodies`。
- 为避免非植被下垫面干扰，图件与文本重点比较均排除了 `0`、`15`、`16` 三类地表类型；完整原始统计仍保留在 CSV 中。
