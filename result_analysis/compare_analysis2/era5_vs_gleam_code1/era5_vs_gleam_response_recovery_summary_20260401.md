# ERA5 与 GLEAM 响应时间和恢复时间对比总结

## 1. 分析说明

本次对比基于 `rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100` 版本结果，统一读取 GPP、NEE、RECO 三个碳通量变量在 `code1-code4` 以及对应 `code1_ERA5-code4_ERA5` 的 `nc` 文件，对 GLEAM 与 ERA5 两套土壤湿度驱动下的响应时间与恢复时间进行了年度比较。

本次统计口径为：

- 响应时间使用 `t_response_onset_start`
- 恢复时间使用 `t_recover_to_baseline`
- 以 `onset_year` 为年份分组统计年度均值
- 对 1982-2021 年年度均值序列分别计算线性趋势，单位为 `days/decade`

结果文件位于同一目录下：

- 年度明细表：`annual_response_recovery_comparison_all_codes_era5_vs_gleam.csv`
- 趋势汇总表：`trend_summary_all_codes_era5_vs_gleam.csv`
- 图件：`gpp/nee/reco × code1-code4` 共 12 张

## 2. 情景对应关系

| code | 情景含义 |
| --- | --- |
| code1 | SMrz Flash |
| code2 | SMs Flash |
| code3 | SMrz Slow |
| code4 | SMs Slow |

## 3. 总体特征

从整体上看，ERA5 与 GLEAM 在响应时间上的差异大于恢复时间上的差异，尤其在闪旱情景下更明显。多数情景中，ERA5 给出的响应时间均值更长，或者响应变慢的趋势更强，说明使用 ERA5 事件识别时，碳通量对干旱信号的迟滞性更突出。

恢复时间方面，不同变量之间差异更复杂。GPP 和 RECO 中，GLEAM 在多数情景下表现出更强的恢复时间延长趋势；而 NEE 的闪旱情景中则出现明显分歧，ERA5 表现为恢复时间延长，而 GLEAM 表现为稳定甚至缩短。这说明恢复阶段对事件识别源和土壤湿度产品更敏感。

## 4. GPP 对比结果

### 4.1 响应时间

GPP 四种情景下，响应时间总体都随时间延长。闪旱情景中，ERA5 和 GLEAM 都表现为明显变慢，但 ERA5 增长更强：

- `code1 SMrz Flash`：ERA5 `+11.00 d/dec`，GLEAM `+8.47 d/dec`
- `code2 SMs Flash`：ERA5 `+9.03 d/dec`，GLEAM `+8.48 d/dec`

缓旱情景中，两套资料差异减弱：

- `code3 SMrz Slow`：GLEAM 趋势略强于 ERA5
- `code4 SMs Slow`：GLEAM 与 ERA5 接近，但 GLEAM 仍略强

均值上，ERA5 在 `code1`、`code2`、`code4` 中均高于 GLEAM，仅 `code3` 略低于 GLEAM。

### 4.2 恢复时间

GPP 的恢复时间在四种情景下总体都表现为增加趋势，但多数情景中 GLEAM 的恢复变慢更明显：

- `code1 SMrz Flash`：GLEAM `+1.30 d/dec`，ERA5 `+0.57 d/dec`
- `code2 SMs Flash`：GLEAM `+1.20 d/dec`，ERA5 `+0.56 d/dec`
- `code3 SMrz Slow`：GLEAM `+1.86 d/dec`，ERA5 `+0.69 d/dec`

只有 `code4 SMs Slow` 中 ERA5 的恢复时间增加更快：

- `code4 SMs Slow`：ERA5 `+1.67 d/dec`，GLEAM `+1.07 d/dec`

均值上，GLEAM 的恢复时间普遍长于 ERA5，说明在 GPP 分析中，GLEAM 更容易给出更长且更持续拉长的恢复阶段。

## 5. NEE 对比结果

### 5.1 响应时间

NEE 中，ERA5 在闪旱情景下表现出更明显的响应迟滞：

- `code1 SMrz Flash`：ERA5 `+10.33 d/dec`，GLEAM `+6.72 d/dec`
- `code2 SMs Flash`：ERA5 `+9.39 d/dec`，GLEAM `+7.40 d/dec`

缓旱情景下差异分化：

- `code3 SMrz Slow`：ERA5 与 GLEAM 几乎一致，均约 `+10.5 d/dec`
- `code4 SMs Slow`：GLEAM `+8.96 d/dec` 明显高于 ERA5 `+6.28 d/dec`

均值上，ERA5 在 `code1-code3` 中均高于 GLEAM，而 `code4` 反而低于 GLEAM。

### 5.2 恢复时间

NEE 的恢复时间是本次对比中分歧最强的一组结果。闪旱情景下，ERA5 与 GLEAM 给出了相反方向：

- `code1 SMrz Flash`：ERA5 `+0.88 d/dec`，GLEAM `-0.90 d/dec`
- `code2 SMs Flash`：ERA5 `+1.05 d/dec`，GLEAM `-0.31 d/dec`

这说明在 NEE 闪旱事件上，ERA5 对应的恢复时间逐渐延长，而 GLEAM 则表现为稳定甚至缩短。

缓旱情景下，两套资料都显示恢复时间延长，但 GLEAM 延长更快：

- `code3 SMrz Slow`：GLEAM `+1.81 d/dec`，ERA5 `+1.20 d/dec`
- `code4 SMs Slow`：GLEAM `+1.83 d/dec`，ERA5 `+1.31 d/dec`

均值上，ERA5 在 `code1` 和 `code2` 中恢复时间高于 GLEAM，但在 `code3` 和 `code4` 中低于 GLEAM。

## 6. RECO 对比结果

### 6.1 响应时间

RECO 的响应时间也总体呈增加趋势，但幅度明显小于 GPP 和 NEE。闪旱情景下 ERA5 明显更强：

- `code1 SMrz Flash`：ERA5 `+5.27 d/dec`，GLEAM `+1.20 d/dec`
- `code2 SMs Flash`：ERA5 `+3.34 d/dec`，GLEAM `+1.52 d/dec`

缓旱情景下则相反，GLEAM 变慢更快：

- `code3 SMrz Slow`：GLEAM `+4.12 d/dec`，ERA5 `+2.73 d/dec`
- `code4 SMs Slow`：GLEAM `+4.23 d/dec`，ERA5 `+2.83 d/dec`

均值上，ERA5 在闪旱情景中高于 GLEAM，而在缓旱情景中低于 GLEAM。

### 6.2 恢复时间

RECO 的恢复时间在四种情景下均表现为延长，但几乎所有情景中 GLEAM 都比 ERA5 增长更快：

- `code1 SMrz Flash`：GLEAM `+0.87 d/dec`，ERA5 `+0.25 d/dec`
- `code2 SMs Flash`：GLEAM `+0.87 d/dec`，ERA5 `+0.38 d/dec`
- `code3 SMrz Slow`：GLEAM `+2.13 d/dec`，ERA5 `+0.55 d/dec`
- `code4 SMs Slow`：GLEAM `+1.34 d/dec`，ERA5 `+0.48 d/dec`

其中 `code3` 的差异最大，说明 RECO 在根层缓旱情景下，GLEAM 更容易识别出长期恢复变慢的特征。

## 7. 综合归纳

综合 12 个情景，可以归纳出以下规律：

1. 在闪旱情景中，ERA5 往往给出更长的响应时间，且响应变慢趋势通常强于 GLEAM，尤其在 GPP、NEE、RECO 的 `code1/code2` 中都较一致。
2. 在恢复时间上，GPP 和 RECO 多数情景中均是 GLEAM 的延长趋势更强，表明 GLEAM 对恢复阶段的长期拖延更敏感。
3. NEE 是差异最大的变量，特别是闪旱情景中，ERA5 表现为恢复时间增加，而 GLEAM 则表现为减小或接近稳定，说明 NEE 恢复阶段对驱动数据源最敏感。
4. 缓旱情景下，GLEAM 常常给出更长的恢复时间和更强的恢复变慢趋势，而 ERA5 更倾向于给出较弱的恢复延长。
5. 因此，ERA5 与 GLEAM 的差异不仅体现在事件数量上，也显著体现在碳通量响应时间和恢复时间的长期演变上，尤其是“响应是否变慢”和“恢复是否持续拉长”这两个过程判断。

## 8. 建议的后续使用方式

如果后续需要写论文结果部分，建议按以下逻辑组织：

- 先写总体规律：ERA5 与 GLEAM 在响应时间上的差异普遍大于恢复时间
- 再分别讨论 GPP、NEE、RECO
- 对 NEE 闪旱恢复时间的相反趋势单独强调
- 对 GPP 和 RECO 中 GLEAM 恢复时间增长更强这一共同特征进行归纳
- 图件引用时以 `gpp_code1` 到 `reco_code4` 的 12 张图分别对应正文或补充材料

## 9. 相关文件

- 趋势表：`trend_summary_all_codes_era5_vs_gleam.csv`
- 年度均值表：`annual_response_recovery_comparison_all_codes_era5_vs_gleam.csv`
- 图件目录：当前目录下 `*_era5_vs_gleam_response_recovery.png`
