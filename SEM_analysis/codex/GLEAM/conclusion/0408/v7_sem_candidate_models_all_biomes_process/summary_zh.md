# V7 全 biome 候选机制比较：宽松过程版

## 版本定位

这一版将候选机制模型扩展到全部 6 个 biome，并采用相对宽松的过程型候选集。它的核心目标不是只给出一个最终 SEM，而是比较不同 biome 在“直接效应”“水分机制”“冠层机制”“基线综合机制”之间更偏向哪一类解释框架。

## 版本内容

- 结果目录共包含 `24` 个模型，即 `6` 个 biome × `4` 套候选机制。
- 候选模型包括：
  - 非湿地：`M0_direct`、`M1_water`、`M2_canopy`、`M3_baseline`
  - 湿地：`M0_direct`、`M1_water`、`M2_dualwater`、`M3_baselinewater`
- 选择规则：
  - 先排除纯基线 `M0_direct`
  - 再在每个 biome 中选 `fit_rank_score` 最优的过程机制模型作为 primary model

## 主机制筛选结果

| Biome | 主机制模型 | 主要含义 |
|---|---|---|
| Cropland | `M1_water` | 恢复主要受恢复窗内水分收支和根区土壤水控制 |
| Forest | `M1_water` | `p_minus_et` 与 `SMrz` 是核心过程链 |
| Grassland | `M1_water` | 30 天与 60 天根区土壤水共同决定恢复 |
| Savanna | `M1_water` | 水分链条为主，事件属性仍保留直接和间接贡献 |
| Shrubland | `M1_water` | 水分机制主导，但效应强度相对较弱 |
| Wetland | `M2_dualwater` | 表层与根区双水分通道共同作用 |

## 这版最重要的认识

1. 在宽松过程候选框架下，非湿地 5 个 biome 的最优机制都集中到 `M1_water`，说明“恢复窗水分过程”在不同植被类型中具有高度一致性。
2. Wetland 没有落在 `M1_water`，而是更适合 `M2_dualwater`，表明湿地系统里表层土壤水和根区土壤水需要同时进入机制图，不能简单套用非湿地结构。
3. 虽然 `M0_direct` 在很多 biome 中拟合排序更靠前，但它不提供机制链，因此这一版更强调“可解释的过程模型”而不是“最省参数的回归方程”。

## 直接路径与总效应特征

- Cropland：`postpeak30_SMrz_mean` 为最强直接负路径，`event_duration` 是最强总效应驱动。
- Forest：`postpeak30_p_minus_et` 是最强直接负路径，`event_duration` 的总效应在间接路径修正后转为微弱正向。
- Grassland：`postpeak60_SMrz_mean` 为最强正向路径，表明更长时间尺度的水分恢复对恢复完成时间更重要。
- Savanna：`event_intensity` 和 `event_duration` 同时保留较明显间接效应。
- Shrubland：效应结构与 Savanna 相似，但路径强度更弱。
- Wetland：`postpeak30_SMs_mean` 为强负向路径，`postpeak30_SMrz_mean` 为强正向路径，体现双水分库的相反作用。

## 图件清单与说明

### `primary_model_paths/`

- 含义：每个 biome 主机制模型的路径图。
- 用途：直接展示“该 biome 最终被选中的机制路径结构”。

### `candidate_model_summary.md`

- 含义：24 个候选模型的综合比较表。
- 用途：查看每个 biome 四套模型的样本量、方程数、路径数和拟合指标。

### `primary_mechanism_summary.md`

- 含义：主机制模型的英文原始摘要。
- 用途：核对 primary model 的选择依据、直接路径和总效应。

## 推荐定位

- 这版非常适合作为“全 biome 机制筛选初稿”归档。
- 如果要在论文或答辩中说明“为什么后面会转向更严格版或 landmark30 版”，这版是最早的统一比较基线。

## 为什么后续没有直接采用这一版

这一版虽然首次把候选机制比较扩展到全部 biome，但它的结构仍然偏宽松，候选路径较多，更适合用来探索“可能的生态机制”，不够适合作为最终定稿结果。后续分析发现，需要进一步压缩变量和结构、降低冗余，并把 SHAP 特征筛选、模型 `R2` 与 SEM 解释整合到同一条主线中，因此 `V7` 后来没有作为正式主结果，而是保留为前期机制筛选初稿。
