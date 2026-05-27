# V5 机制型 SEM 版本：显式中介路径与间接效应

## 版本定位

V1 到 V4 的共同特点是：路径图里所有变量都直接连到目标值，因此只能解释“直接效应”，无法表达间接机制。V5 的目标就是把 `process_recoverywin` 这条线从“直接效应回归”升级为“多方程机制型 SEM”。

## 机制框架

非湿地 biome 使用如下机制框架：

1. `SMrz_mean ~ p_minus_et + ssrd_mean + temperature_2m_mean`
2. `VPD_mean ~ temperature_2m_mean + strd_mean + wind_speed_mean`
3. `lai_total_mean ~ SMrz_mean + VPD_mean + ssrd_mean`
4. `t_recover_to_baseline_abs_peak ~ p_minus_et + SMrz_mean + VPD_mean + lai_total_mean`

Forest 使用相同的总体思路，但单独保存为独立 spec。Wetland 使用更简化的水分动态结构：

1. `SMrz_delta ~ SMrz_mean + ssrd_mean`
2. `t_recover_to_baseline_abs_peak ~ SMrz_mean + SMrz_delta + ssrd_mean`

## 为什么这版重要

这一版首次使路径图中出现中介变量，因此可以表达：

- `temperature_2m_mean -> VPD_mean -> t_recover_to_baseline_abs_peak`
- `p_minus_et -> SMrz_mean -> t_recover_to_baseline_abs_peak`
- `SMrz_mean -> lai_total_mean -> t_recover_to_baseline_abs_peak`

这些都是典型的间接效应通路。

## SHAP 与特征来源

这一版机制 SEM 仍然建立在 V4 的变量筛选基础上，因此：

- 蜂巢图与重要性图参考 V4 的 SHAP 结果
- SEM 模型本身改为多方程机制结构

## 机制型 SEM 结果

各 biome 目标方程 holdout `R2`：

| Biome | 样本量 | 目标方程预测变量数 | Mechanism SEM holdout R2 |
|---|---:|---:|---:|
| Forest | 318,380 | 4 | 0.5858 |
| Shrubland | 166,813 | 4 | 0.3181 |
| Savanna | 325,911 | 4 | 0.5587 |
| Grassland | 329,638 | 4 | 0.4610 |
| Cropland | 176,226 | 4 | 0.4148 |
| Wetland | 5,985 | 3 | 0.1240 |

相较于 V4 的直接效应模型，这一版 `R2` 普遍更低，但这是预期结果，因为：

- 目标方程不再吸收所有解释力
- 一部分解释被分流到中介路径中
- 因此它更强调机制清晰度，而不是单一回归方程的极致拟合

## 图件清单与说明

### `global_beeswarm_reference.png`

- 含义：来自 V4 的全局蜂巢图。
- 用途：说明机制型 SEM 所基于的变量筛选背景。

### `global_importance_topk_reference.png`

- 含义：来自 V4 的全局重要性图。
- 用途：说明哪些变量先通过 SHAP 被保留下来，再进入机制建模。

### `path_overview.png`

- 含义：6 个 biome 的机制型路径图总览。
- 说明：图中已将 `recoverywin_` 前缀去掉，以减少节点挤压。
- 用途：适合论文中展示间接效应结构。

### `GPP_code1_*_path_diagram.png`

- 含义：各 biome 单独机制路径图。
- 用途：逐 biome 检查水分、VPD、冠层与恢复时间之间的中介链。

## 如何解读路径图中的数字

图中两个变量之间箭头旁边的数字是该路径的标准化路径系数，即 SEM 输出中的 `Estimate`。由于变量建模前做过 z-score 标准化，因此数字可理解为：上游变量增加 `1` 个标准差时，下游变量平均变化多少个标准差。正号表示正向作用，负号表示负向作用，绝对值越大表示路径越强。数字后面的星号表示显著性水平，`*`、`**`、`***` 分别对应更严格的显著性阈值。

## 版本评价

如果目标是：

- 追求最高解释力与最简洁主文，优先 V3。
- 说明加入风速和 LAI 的稳健性，参考 V4。
- 强调生态机制、间接效应和路径链条，必须使用 V5。

因此，V5 最适合作为“机制解释图”版本。

