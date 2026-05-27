# GPP、NEE 和 RECO 干旱响应趋势对比分析

## 1. 数据基础
- 来源目录：
  - `/home/xulc/flash_drought/process/result_analysis/GPP_trend`
  - `/home/xulc/flash_drought/process/result_analysis/NEE_trend`
  - `/home/xulc/flash_drought/process/result_analysis/RECO_trend`
- 本次对比主要使用的结果表：
  - `*_response_trend_summary_1980_2024.csv`
  - `*_pixel_trend_spatial_summary_1980_2024.csv`
  - `*_yearly_response_timeseries_1980_2024.csv`
- 三类变量的有效分析时间窗口均为 **1982-2022 年**，共 **41 个有效年份**。虽然文件中包含 1980-1981 年，但这两年没有有效事件，因此趋势拟合实际上基于 1982-2022 年。
- 碳循环关系说明：
  - **GPP** 表示总初级生产力，即生态系统总碳吸收；
  - **RECO** 表示生态系统总呼吸；
  - **NEE** 表示净生态系统交换，是吸收和呼吸共同作用后的净结果。
- 在很多研究中，可近似认为 `NEE ≈ RECO - GPP`，但本报告重点讨论的是干旱事件响应指标的趋势方向，而不是原始碳通量的严格闭合关系。

## 2. 核心结论
三类数据表现出一个比较清晰的一致信号：在 1982-2022 年期间，干旱响应总体上表现为 **响应比例下降、完全形成响应所需时间变长、但一旦进入影响阶段则变化更陡、更快恢复到最低点之后的恢复阶段**。

在三者之中，**NEE 在关键的响应比例和响应时序指标上与 GPP 更接近，而不是与 RECO 更接近**。这意味着，净碳交换响应的长期演变，更可能主要受光合作用侧变化驱动，而不是由呼吸侧的同步变化主导。

同时，GPP、NEE 和 RECO 并不完全一致。RECO 在响应比例类指标上的变化明显较弱，尤其是在两个 nonflash 情景中，`response_ratio` 和 `response_speed_proxy_mean` 的全球聚合趋势都接近于 0。这说明，净碳交换的长期变化不能仅靠呼吸过程解释。相反，GPP 和 NEE 的 `response_ratio` 同时显著下降，且 `t_response_mean` 同时上升，表明生态系统碳吸收与净碳交换都变得更难快速触发出明显响应。

## 3. 频次和响应比例类指标

### 3.1 事件数量和响应事件数量
- 在三类变量中，`events` 在两个 nonflash 情景下都显著增加，而两个 flash 情景下长期事件数趋势不明显。
- 对 GPP 而言，`response_count` 在 flash 情景下略有下降，在 nonflash 情景下显著增加。
- NEE 的 `response_count` 与 GPP 基本一致。
- RECO 的 `response_count` 在 flash 情景中基本平稳，但在 nonflash 情景下增幅最大。
- 这表明：nonflash 干旱事件池本身在扩大，但真正产生明显响应的事件比例并没有同步增加。

### 3.2 `response_ratio` 对比

| Scenario | GPP slope | GPP p | NEE slope | NEE p | RECO slope | RECO p |
| --- | --- | --- | --- | --- | --- | --- |
| Flash-SMrz | -0.006864 | 5.82e-22 | -0.006593 | 2.71e-18 | -0.002320 | 2.60e-06 |
| Flash-SMs | -0.006578 | 7.38e-20 | -0.006858 | 6.91e-20 | -0.002407 | 1.13e-06 |
| Nonflash-SMrz | -0.005976 | 1.14e-19 | -0.004834 | 2.14e-17 | 0.000133 | 0.5912 |
| Nonflash-SMs | -0.005157 | 8.16e-20 | -0.004433 | 9.77e-18 | -0.000117 | 0.6378 |

解释：
- `response_ratio` 在 **所有 GPP 情景** 和 **所有 NEE 情景** 下都显著下降，斜率大致在 `-0.0044` 到 `-0.0069 yr^-1` 之间。
- `RECO response_ratio` 的下降幅度明显更弱，只在两个 flash 情景下显著，在两个 nonflash 情景下基本接近于零。
- 这是整个对比中最清晰的信号之一：**GPP 和 NEE 同步减弱得很明显，而 RECO 只表现出轻微减弱甚至基本不变**。
- 因此，从长期看，生态系统净响应概率的下降，更符合“光合作用主导变化”的解释，而不是“呼吸主导变化”。

### 3.3 响应速度代理和幅度
- `response_speed_proxy_mean` 在 GPP 和 NEE 的四个情景中均为负值，说明响应形成速度总体变慢。
- 对 RECO 来说，这个指标仅在 flash 情景中为负，在 nonflash 情景中接近于 0。
- `amp_max_mean` 的方向则正好相反：
  - GPP 和 RECO 在所有情景中为正；
  - NEE 在所有情景中为负。
- 这一点说明，吸收和呼吸之间的相对平衡关系正在变化，而不是三者简单地同时增强或减弱。

## 4. 时间指标：响应更慢形成，但内部变化更陡峭

| Scenario | GPP t_response | NEE t_response | RECO t_response | GPP t_impact | NEE t_impact | RECO t_impact | GPP t_recover | NEE t_recover | RECO t_recover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Flash-SMrz | 0.155 | 0.139 | 0.089 | -0.298 | -0.464 | -0.296 | -0.214 | -0.183 | -0.142 |
| Flash-SMs | 0.154 | 0.148 | 0.089 | -0.314 | -0.429 | -0.279 | -0.200 | -0.187 | -0.093 |
| Nonflash-SMrz | 0.490 | 0.480 | -0.009 | -1.149 | -1.307 | -0.750 | -0.347 | -0.353 | -0.231 |
| Nonflash-SMs | 0.484 | 0.473 | 0.033 | -0.920 | -1.105 | -0.626 | -0.350 | -0.348 | -0.226 |

解释：
- `t_response_mean` 在 GPP 和 NEE 的四个情景中全部增加，最强的增加出现在两个 nonflash 情景中，尤其是 GPP 和 NEE。
- RECO 不同：
  - 在 flash 情景中仅弱增加；
  - 在 nonflash 情景中基本接近于 0。
- `t_impact_mean` 在三类变量的所有情景中均下降，且 NEE 的下降幅度最大。这说明一旦系统进入影响阶段，异常会更迅速地发展到更强水平。
- `t_recover_mean` 在所有变量和情景中也都为负，说明恢复阶段时长在缩短，但 GPP 和 NEE 的缩短更强，RECO 相对较弱。
- 综合 `t_response_mean` 和 `t_impact_mean` 可以概括为：
  - **形成完整响应需要更久；**
  - **但一旦进入冲击过程，内部恶化更快。**

## 5. 绝对碳通量指标

| Scenario | GPP drop_abs | NEE drop_abs | RECO drop_abs | GPP recovery_abs | NEE recovery_abs | RECO recovery_abs |
| --- | --- | --- | --- | --- | --- | --- |
| Flash-SMrz | 0.0090 | 0.0071 | 0.0025 | 0.0024 | 0.0007 | 0.0014 |
| Flash-SMs | 0.0088 | -0.0002 | 0.0041 | 0.0017 | 0.0005 | 0.0010 |
| Nonflash-SMrz | -0.0185 | 0.0270 | -0.0148 | 0.0022 | 0.0009 | 0.0012 |
| Nonflash-SMs | -0.0053 | 0.0213 | -0.0063 | 0.0022 | 0.0009 | 0.0012 |

解释：
- `*_recovery_rate_abs_mean` 在三类变量和四个情景中全部为正，这是最稳健的共同结果之一。
- 绝对恢复速率的增强强度表现为：
  - GPP 最大；
  - RECO 次之；
  - NEE 最小。
- `*_min_abs_mean` 在全球聚合趋势中，对 GPP、NEE、RECO 的所有情景都为负，说明最小绝对异常整体在加深，且通常在 nonflash 情景中更强。
- `drop_abs_mean` 更复杂：
  - GPP 在 flash 情景中为正，但在两个 nonflash 情景下全球聚合趋势为负；
  - NEE 在四个情景中的三个为正，且在 nonflash 下最强；
  - RECO 在 flash 下为正，在 nonflash 下为负。
- 这里 NEE 的结果尤其重要：
  - `nee_drop_abs_mean` 在两个 nonflash 情景下的斜率最大；
  - 说明净碳交换异常在 nonflash 干旱条件下有明显增强，即使 GPP 和 RECO 的全球聚合趋势并不一致。

## 6. 像元尺度空间趋势

### 6.1 `response_ratio` 的像元平均趋势和显著面积比例
每个单元格格式为：`像元平均斜率 / p < 0.005 的像元比例`

| Scenario | GPP mean_slope / sig_frac | NEE mean_slope / sig_frac | RECO mean_slope / sig_frac |
| --- | --- | --- | --- |
| Flash-SMrz | -0.006654 / 0.204 | -0.006914 / 0.308 | -0.001689 / 0.297 |
| Flash-SMs | -0.006534 / 0.189 | -0.007820 / 0.287 | -0.001338 / 0.272 |
| Nonflash-SMrz | -0.003437 / 0.117 | -0.003449 / 0.168 | -0.000794 / 0.161 |
| Nonflash-SMs | -0.003836 / 0.155 | -0.003813 / 0.207 | -0.000886 / 0.197 |

解释：
- 像元尺度上，`response_ratio` 在 **所有变量、所有情景** 中都是负值。
- 即使 RECO 在 nonflash 情景的全球聚合趋势接近于 0，其像元平均趋势仍然为负。
- NEE 的 `response_ratio` 显著面积比例通常最大，尤其在 flash 情景下最明显。
- 这说明响应比例减弱是一个空间上相当广泛的现象，即便在事件加权的全球聚合结果中看起来不那么强。

### 6.2 `drop_abs_mean` 的像元平均趋势和显著面积比例
每个单元格格式为：`像元平均斜率 / p < 0.005 的像元比例`

| Scenario | GPP mean_slope / sig_frac | NEE mean_slope / sig_frac | RECO mean_slope / sig_frac |
| --- | --- | --- | --- |
| Flash-SMrz | 0.010094 / 0.120 | 0.004770 / 0.151 | 0.007888 / 0.112 |
| Flash-SMs | 0.015682 / 0.110 | 0.004574 / 0.132 | 0.012279 / 0.101 |
| Nonflash-SMrz | 0.000730 / 0.166 | 0.011997 / 0.214 | 0.002025 / 0.187 |
| Nonflash-SMs | 0.004100 / 0.160 | 0.011312 / 0.250 | 0.003288 / 0.184 |

解释：
- 在像元尺度上，`drop_abs_mean` 对 GPP、NEE、RECO 的四个情景全部为正。
- NEE 在两个 nonflash 情景下具有最大的正斜率和最大的显著面积比例。
- 这说明，从空间分布看，净碳交换绝对响应增强是一个更广泛、更一致的特征，即使全球均值聚合后可能被抵消掉。

## 7. 全球聚合趋势与像元平均趋势的差异
以下指标在“事件加权全球趋势”和“像元平均趋势”之间出现了方向不一致：

- GPP Nonflash-SMrz `gpp_drop_abs_mean`：全球斜率为负，像元平均斜率为正
- GPP Nonflash-SMs `gpp_drop_abs_mean`：全球斜率为负，像元平均斜率为正
- NEE Flash-SMs `nee_drop_abs_mean`：全球斜率接近 0 且略为负，但像元平均斜率为正
- NEE Nonflash-SMrz `nee_min_abs_mean`：全球斜率为负，但像元平均斜率略为正
- NEE Nonflash-SMs `nee_min_abs_mean`：全球斜率为负，但像元平均斜率略为正
- RECO Nonflash-SMrz `reco_drop_abs_mean`：全球斜率为负，但像元平均斜率为正
- RECO Nonflash-SMs `reco_drop_abs_mean`：全球斜率为负，但像元平均斜率为正
- RECO Nonflash-SMrz `response_ratio`：全球斜率约为 0，但像元平均斜率为负
- RECO Nonflash-SMrz `response_speed_proxy_mean`：全球斜率约为 0，但像元平均斜率略为负
- RECO Nonflash-SMrz `t_response_mean`：全球斜率约为 0 且略为负，但像元平均斜率为正

解释：
- 最重要的差异出现在 `gpp_drop_abs_mean` 和 `reco_drop_abs_mean` 的两个 nonflash 情景中：
  - **全球聚合趋势为负；**
  - **但像元平均趋势为正。**
- 这并不表示数据矛盾，而是两种统计方式的空间权重不同：
  - `*_response_trend_summary` 反映的是按年份聚合后的事件平均趋势；
  - `*_pixel_trend_spatial_summary` 反映的是逐像元斜率的平均。
- 因此，少数高权重区域可能把全球聚合结果拉成负值，但从大多数像元来看仍然呈现弱正趋势。
- NEE 在 `drop_abs_mean` 上的方向矛盾最小：
  - 非 flash 情景下，无论全球聚合还是像元平均，趋势都为正。
- 这进一步说明，净碳交换异常增强在空间上具有更强的一致性。

## 8. 综合碳循环解释

1. **NEE 在响应发生概率上更接近 GPP，而不是 RECO**
- `response_ratio` 和 `response_speed_proxy_mean` 中，NEE 与 GPP 的变化幅度和方向都更接近。
- 这说明，干旱响应发生概率的长期变化，主要受碳吸收侧控制，而非呼吸侧主导。

2. **Nonflash 干旱产生了更强的结构性变化**
- nonflash 情景下，`events` 增幅最大；
- `t_response_mean` 增幅最大；
- `t_impact_mean` 和 `t_recover_mean` 的下降也最强；
- 同时 `nee_drop_abs_mean` 也在 nonflash 下表现出最大增强。
- 说明 nonflash 干旱更可能驱动长期碳循环响应结构重组。

3. **呼吸过程相对更“缓冲”**
- RECO 在 `response_ratio` 上变化较弱；
- 在 nonflash 情景下 `t_response_mean` 也几乎没有明显聚合趋势。
- 这说明呼吸响应虽然也在变化，但不如吸收和净交换那样稳定、强烈。

4. **净效应指向更不稳定的碳循环响应**
- GPP 响应概率下降，NEE 响应概率也下降；
- 同时 NEE 的绝对跌落幅度在多种情景下增强；
- 再叠加更短的 `t_impact` 和 `t_recover`，意味着净碳异常在长期上变得更陡、更突然，但未必更容易被触发。

## 9. 总结
从 1982 到 2022 年，最明确的总体结论是：**GPP 和 NEE 的变化比 RECO 更一致、也更强**。光合作用对干旱的响应，在长期上表现为响应比例下降、完整形成响应更慢，而净生态系统交换基本同步反映了这种变化。呼吸过程也有变化，但变化幅度更弱、情景依赖性更强，尤其在 nonflash 干旱情景下更明显。

空间分析进一步说明，一些在全球聚合结果中看似弱化甚至为负的趋势，实际上掩盖了大范围区域中的局地增强，尤其是在 `drop_abs_mean` 上表现得很明显。

因此，更准确的理解不是“干旱碳循环响应整体单向增强或减弱”，而是：
- **空间异质性增强；**
- **内部演化更陡峭；**
- **最终净效应越来越受吸收侧变化主导。**
