# V9 全 biome 候选机制比较：landmark30_v21 版

## 版本定位

这一版与 V7、V8 的最大区别在于，它采用 `landmark30_v21` 的样本与特征口径，核心变量集中在 `postpeak30` 时间窗，明显更强调恢复窗早期 30 天内的关键生态状态。因此它更像是一个“短期关键窗口机制版”。

## 样本与变量特点

- 非湿地样本量相较前两版明显减少：
  - Forest `129,485`
  - Cropland `108,290`
  - Grassland `183,811`
  - Savanna `169,916`
  - Shrubland `64,807`
  - Wetland `2,419`
- 变量集合聚焦在：
  - `postpeak30_p_minus_et`
  - `postpeak30_total_evaporation_sum`
  - `postpeak30_temperature_2m_mean`
  - `postpeak30_SMrz_mean`
  - `postpeak30_SMs_mean`
  - `postpeak30_lai_total_mean`

## 主机制筛选结果

| Biome | 主机制模型 | 主要含义 |
|---|---|---|
| Cropland | `M2_canopy` | 短期恢复中冠层与能量通路已超过纯水分链 |
| Forest | `M2_canopy` | `total_evaporation + temperature + lai` 构成主轴 |
| Grassland | `M2_canopy` | 温度与蒸散在早期窗口内更重要 |
| Savanna | `M2_canopy` | 蒸散和温度共同塑造恢复时间 |
| Shrubland | `M2_canopy` | 冠层/能量结构优于纯水分链 |
| Wetland | `M2_dualwater` | 湿地仍然保留双水分结构 |

## 这版为何重要

1. V7、V8 都更偏向 `M1_water`，而 V9 在非湿地 5 个 biome 上一致转向 `M2_canopy`，这说明一旦只看恢复后 30 天的关键窗口，冠层与能量状态会变得更突出。
2. 这并不否定水分的重要性，而是提示水分效应可能先通过 `total_evaporation`、`temperature_2m` 和 `lai_total` 等更接近冠层过程的变量显现出来。
3. Wetland 仍然坚持 `M2_dualwater`，说明湿地生态系统的特殊性在不同口径下都较稳定。

## 主路径特征

- Forest：`postpeak30_total_evaporation_sum` 为最强正向直接路径，总效应也最强。
- Grassland：`postpeak30_temperature_2m_mean` 为最强负向路径，提示高温环境延缓恢复完成。
- Savanna：蒸散为正、`p_minus_et` 与温度为负，构成典型干热约束结构。
- Shrubland：温度与 `p_minus_et` 双负效应明显。
- Cropland：温度的总效应最强负向，蒸散为最强正向直接路径。
- Wetland：`postpeak30_SMs_mean` 和 `postpeak30_SMrz_mean` 仍是两条最核心的相反方向路径。

## 图件清单与说明

### `primary_model_paths/`

- 含义：landmark30_v21 版中各 biome 的主机制路径图。
- 用途：展示“恢复后 30 天关键窗口”下的最优机制结构。

### `candidate_model_summary.md`

- 含义：该版本 24 个候选模型的总比较表。
- 用途：核对各 biome 的样本量、变量数和拟合优度。

### `primary_mechanism_summary.md`

- 含义：该版本主机制模型的原始摘要。
- 用途：直接查看最强路径和总效应来源。

## 推荐定位

- 如果研究重点是“恢复后早期 30 天哪些过程最关键”，V9 很有价值。
- 如果研究重点是“恢复窗整体过程由什么控制”，V7/V8 更贴近全窗口解释。
- 因此，V9 非常适合作为一套对照分析，用来证明不同时间窗口会改变最优机制的生态解释。

## 为什么后续没有直接采用这一版

这一版没有作为最终主结果，最关键的原因是它使用了 `landmark30_v21` 的 30 天关键窗口口径，而后续正式主线采用的是更完整的 `process_recoverywin` 口径。也就是说，`V9` 回答的是“恢复早期 30 天内什么最重要”，而最终研究更关注“整个恢复窗口内什么控制恢复完成时间”。因此，这一版虽然揭示了冠层和能量变量在短窗口中的重要性，但因为样本量、时间窗口和特征体系都与正式主线不完全一致，最终更适合作为对照和补充分析，而不是定稿主结果。
