# SEM路径图重绘规划报告

## 1. 数据来源

本次重绘基于以下文件：

- `prepeak_path_effect_strengths.csv`
- `recoverywin_path_effect_strengths.csv`
- `unified11_r2_summary.csv`
- `sem_prepeak/sem_prepeak_sem_path_diagrams_overview.png`
- `sem_recoverywin/sem_recoverywin_sem_path_diagrams_overview.png`

当前目录中每个 biome 还包含 `*_estimates.csv`、`*_model_spec.txt` 和原始 `*_path_diagram.png`，说明已经具备完整的路径系数与现图对照信息，适合在不改动模型结果的前提下，只对“视觉表达层”进行重绘。

## 2. 现有图像的主要问题

从现有 `prepeak` 和 `recoverywin` 总图看，主要问题不是结果本身，而是连线组织方式不够克制：

1. 外生变量过多，且大量直接连到 `t_recover`，造成右侧拥堵。
2. 指向 `SMrz`、`VPD`、`LAI` 的边与直接指向 `t_recover` 的边交织，产生多层交叉。
3. 一些效应很弱但仍被完整绘出，视觉权重和核心路径过于接近。
4. 节点布局随图自动调整，缺少稳定结构，不利于跨 biome 横向比较。
5. 标签较长，尤其 `dewpoint_temperature_mean`，进一步挤压了布线空间。

## 3. 重绘目标

本次重绘不改变统计结果，只优化图形表达，目标如下：

1. 让图首先读出“水分链”和“干旱/大气需求链”。
2. 减少弱边干扰，但保留必要的过程骨架。
3. 让不同 biome 使用同一套节点布局，便于比较。
4. 参考你提供的示意图风格，采用更规整的分层结构和更少的交叉。
5. 满足你的硬要求：**中间变量到 `t_recover` 之间必须保留连线。**
6. 在同一 scope 内，**所有 biome 使用完全相同的可视化特征框架**，不再出现某些 biome 缺节点、某些 biome 多节点的情况。

## 4. 结构布局方案

采用固定分层布局，而不是每个子图单独自动排布：

- 左侧：外生气候变量
  - `PRE`
  - `TMP`
  - `EVA`
  - `SSRD`
  - `STRD`
  - `WIND`
  - `DPT`（由 `dewpoint_temperature_mean` 缩写）
- 上中：`P-ET`
- 中部：`SMrz`
- 下中：`VPD`
- 中右：`LAI`
- 最右：`t_recover`

其中节点集合在同一 scope 内保持固定：

- `prepeak` 统一显示 11 个共同特征：
  - `PRE`
  - `TMP`
  - `EVA`
  - `SSRD`
  - `STRD`
  - `WIND`
  - `DPT`
  - `P-ET`
  - `SMrz`
  - `VPD`
  - `LAI`
- `recoverywin` 统一显示同样结构的 11 个对应特征

`prepeak` 中个别 biome 额外出现的 `event_onset_days / event_duration / event_intensity` 不纳入本轮 clean 图的统一展示框架，否则不同 biome 无法进行严格的横向对照。

这套布局的逻辑是：

- `PRE` / `EVA` 先塑造 `P-ET`
- `P-ET`、`PRE`、`TMP` 主要进入 `SMrz`
- `TMP`、`DPT`、`STRD` 主要进入 `VPD`
- `SMrz`、`VPD`、`SSRD` 等再影响 `LAI`
- 所有必须保留的中间变量统一向 `t_recover` 收束

## 5. 保留与裁剪规则

### 5.1 一定保留的边

以下边无论强弱都保留：

- `P-ET -> t_recover`
- `SMrz -> t_recover`
- `VPD -> t_recover`
- `LAI -> t_recover`

如果某条边统计显著性弱，则保留但使用更细、更浅或虚线表示，和强边区分开。

### 5.2 指向中间变量的边

对于指向 `P-ET`、`SMrz`、`VPD`、`LAI` 的边：

- 保留显著边；
- 优先保留每个中间变量的前 2 条最强入边；
- 其余入边只有在 `abs(estimate)` 达到中等以上强度时才保留；
- 明显很弱、且只增加拥堵的边直接删除。

具体上可理解为：

- `P-ET`：保留 `PRE` 和 `EVA` 两条主链；
- `SMrz`：优先保留 `P-ET`、`PRE`、`TMP`；
- `VPD`：优先保留 `TMP`、`DPT`、`STRD`；
- `LAI`：优先保留 `SMrz`、`VPD`，必要时保留 `SSRD`。

### 5.3 外生变量直接指向 `t_recover`

这部分是当前图里最乱的来源，因此采用更严格筛选：

- 只保留强直接效应；
- 或保留该 biome 中指向 `t_recover` 的前几条主导直接路径；
- 很弱、且与机制主线重复的信息删除。

换句话说，`t_recover` 右侧保留的是“真正主导恢复时间的直接控制”，不是把所有显著但很小的系数都堆上去。

## 6. 线型与视觉编码

- 正效应：橙红色
- 负效应：蓝色
- 线宽：随 `abs(estimate)` 增加
- 弱但被强制保留的边：细线或虚线
- 标签：保留系数值，保留显著性星号

这样可以做到：

- 强主路径一眼能看见
- 弱保留路径仍然存在，但不会抢主线

## 7. 预期的机制表达效果

### prepeak

`prepeak` 图更适合突出“峰值前记忆”：

- `PRE/EVA -> P-ET -> SMrz`
- `TMP/DPT/STRD -> VPD`
- `SMrz/VPD/LAI -> t_recover`
- 再辅以少量强直接路径到 `t_recover`

### recoverywin

`recoverywin` 图更适合突出“恢复窗内即时控制”：

- `TMP/DPT/STRD -> VPD`
- `PRE/EVA -> P-ET`
- `PRE/TMP -> SMrz`
- `P-ET` 和 `TMP` 往往是 `t_recover` 的强直接控制量

## 8. 输出计划

本次将生成一套新的“clean”版本，而不覆盖原图：

- `sem_prepeak/sem_prepeak_sem_path_diagrams_overview_clean.png`
- `sem_prepeak/sem_prepeak_sem_path_diagrams_overview_clean.pdf`
- `sem_recoverywin/sem_recoverywin_sem_path_diagrams_overview_clean.png`
- `sem_recoverywin/sem_recoverywin_sem_path_diagrams_overview_clean.pdf`
- `redraw_sem_overview.py`

如果后续需要“严格统计意义上的同特征 SEM”，则下一步应以 `prepeak` 的 11 个交集特征重新拟合全部 biome 的模型，再导出一套新的 estimates 和 path diagram。当前这一步先解决的是图形表达一致性，而不是重新估计 SEM 参数。

如需后续继续细化，还可以在同一脚本基础上再输出：

- 每个 biome 的单独 clean 图
- 中文注释版图
- 只保留核心主路径的“极简论文主图版”

## 9. 本次重绘的判断原则

本次不是“尽可能完整画出所有边”，而是“在不歪曲结果的前提下，提高结构可读性”。因此我会优先保证三点：

1. 机制骨架不丢；
2. 中间变量到 `t_recover` 的线一定在；
3. 图一眼能看出主要水分链、能量链和大气需求链。
