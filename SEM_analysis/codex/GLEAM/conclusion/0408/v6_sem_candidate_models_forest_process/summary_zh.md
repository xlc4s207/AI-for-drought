# V6 Forest 单 biome 候选机制模型比较

## 版本定位

这一版不是对全部 biome 同时建模，而是专门针对 `Forest` 做机制候选模型比较。它的意义在于回答一个更聚焦的问题：对于森林生态系统，恢复时间的驱动路径到底更接近“纯直接效应”“水分机制”“冠层机制”，还是“包含基线状态的综合机制”。

## 模型集合

本版本共比较 4 个 Forest 候选模型，样本量均为 `318,380`：

| 模型 | 机制含义 | 方程数 | 路径数 | 特征数 |
|---|---|---:|---:|---:|
| `M0_direct` | 所有关键变量直接指向恢复时间 | 1 | 6 | 13 |
| `M1_water` | 事件强度/持续时间通过 `p_minus_et` 与 `SMrz` 影响恢复时间 | 3 | 9 | 11 |
| `M2_canopy` | 在水分链基础上加入 `lai_total` 冠层通路 | 4 | 11 | 12 |
| `M3_baseline` | 再加入 `pre30_SMrz`、`pre30_lai_total` 基线状态 | 4 | 17 | 14 |

## 四套路径结构

### `M0_direct`

- 目标：用最直接的单方程结构解释森林恢复时间。
- 目标方程：
  `t_recover_to_baseline_abs_peak ~ event_intensity + event_duration + pre30_SMrz_mean + pre30_lai_total_mean + postpeak30_p_minus_et + postpeak30_SMrz_mean`

### `M1_water`

- 目标：强调水分收支与根区土壤水的中介链。
- 结构：
  1. `postpeak30_p_minus_et ~ event_intensity + event_duration`
  2. `postpeak30_SMrz_mean ~ event_intensity + event_duration + postpeak30_p_minus_et`
  3. `t_recover_to_baseline_abs_peak ~ event_intensity + event_duration + postpeak30_p_minus_et + postpeak30_SMrz_mean`

### `M2_canopy`

- 目标：在水分链之外，进一步测试冠层状态是否构成关键中介。
- 结构：
  1. `postpeak30_p_minus_et ~ event_intensity + event_duration`
  2. `postpeak30_SMrz_mean ~ event_intensity + event_duration + postpeak30_p_minus_et`
  3. `postpeak30_lai_total_mean ~ postpeak30_SMrz_mean + postpeak30_p_minus_et`
  4. `t_recover_to_baseline_abs_peak ~ event_intensity + event_duration + postpeak30_SMrz_mean + postpeak30_lai_total_mean`

### `M3_baseline`

- 目标：检验干旱前基线水分与冠层状态是否会改变恢复路径。
- 结构：
  1. `postpeak30_p_minus_et ~ event_intensity + event_duration + pre30_SMrz_mean + pre30_lai_total_mean`
  2. `postpeak30_SMrz_mean ~ event_intensity + event_duration + postpeak30_p_minus_et + pre30_SMrz_mean`
  3. `postpeak30_lai_total_mean ~ postpeak30_SMrz_mean + postpeak30_p_minus_et + pre30_lai_total_mean`
  4. `t_recover_to_baseline_abs_peak ~ event_intensity + event_duration + pre30_SMrz_mean + pre30_lai_total_mean + postpeak30_SMrz_mean + postpeak30_lai_total_mean`

## 关键结论

1. 森林 biome 的候选机制比较显示，`M0_direct` 的拟合排名最高，`M1_water` 次之，`M3_baseline` 与 `M2_canopy` 更复杂但没有取得更优的整体拟合排序。
2. 这说明在 Forest 中，`postpeak30_p_minus_et` 与 `postpeak30_SMrz_mean` 已经能抓住恢复时间的重要控制信息，额外引入更长的冠层链或基线链，并不一定换来更好的简洁拟合。
3. 但从生态解释角度看，`M2_canopy` 和 `M3_baseline` 仍然很重要，因为它们给出了“土壤水分如何通过冠层状态传导到恢复时间”的备选机制框架。

## 图件清单与说明

### `forest_M0_direct_path_diagram.png`

- 含义：Forest 的直接效应模型。
- 用途：对比机制模型时的基线参照图。

### `forest_M1_water_path_diagram.png`

- 含义：Forest 的水分机制模型。
- 用途：展示 `event -> p_minus_et -> SMrz -> recovery time` 的链条。

### `forest_M2_canopy_path_diagram.png`

- 含义：Forest 的冠层机制模型。
- 用途：展示水分变量如何进一步通过 `lai_total` 影响恢复时间。

### `forest_M3_baseline_path_diagram.png`

- 含义：Forest 的基线状态综合模型。
- 用途：展示前期状态、事件属性和恢复窗变量共同作用的更完整结构。

## 推荐定位

- 如果要说明 Forest biome 的机制比较过程，这一版非常关键。
- 如果要写“为什么最终没有直接采用更复杂的 Forest 机制模型”，这一版就是最直接的证据。
- 如果要在正文中保持简洁，这一版更适合放在补充材料，用来说明候选路径的筛选过程。

## 为什么后续没有直接采用这一版

这一版最终没有作为正式主结果，主要是因为它只覆盖 `Forest` 单一 biome，更像局部机制试验，而不是全 biome 的统一结论。同时，这一版的任务是比较四类机制假设谁更适合森林，而不是给出最终的 recoverywin 主线结果。后续分析转向了统一的 `process_recoverywin` 框架，并在全部 biome 上进行了去冗余、`R2` 评估和机制型 SEM，因此 `V6` 最终保留为前期探索性补充版本。
