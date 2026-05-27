# V1 原始版本：`process_recoverywin` 全特征 SHAP + 直接效应 SEM

## 版本定位

这是 `process_recoverywin` 主线的原始基线版本。其核心目标是先不人为压缩变量，而是直接用 recoverywin 阶段可得到的主要环境特征去解释 `t_recover_to_baseline_abs_peak`，从而回答“恢复完成时间主要受哪些恢复窗环境因素控制”。

## 方法设置

- 数据行数：`1,322,953`
- SHAP 建模行数：`1,322,953`
- SHAP 解释抽样：`5000`
- 模型：`LightGBM + TreeSHAP`
- 特征范围：`process_recoverywin`
- 特征数：全局 `17`

本版本的特点是保留了较多 recoverywin 特征，因此可以较完整地观察变量竞争关系，但也会引入一定冗余，例如：

- `dewpoint_temperature` 与 `VPD`、`temperature_2m` 之间存在物理相关性
- `total_precipitation`、`total_evaporation` 与 `p_minus_et` 之间存在信息重叠

## SEM 样本量与路径

本版本的 SEM 采用单方程直接效应结构，即所有特征直接连到 `t_recover_to_baseline_abs_peak`，尚未引入显式中介通路。

各 biome 样本量如下：

| Biome | 样本量 | 特征数 |
|---|---:|---:|
| Forest | 318,380 | 8 |
| Shrubland | 166,813 | 7 |
| Savanna | 325,911 | 8 |
| Grassland | 329,638 | 8 |
| Cropland | 176,226 | 8 |
| Wetland | 5,985 | 3 |

这一版最重要的意义在于：它先给出了“恢复窗内哪些变量会进入路径模型”的原始事实基础。

## 主要结论

1. 恢复窗阶段的水热条件、辐射条件与根区土壤湿度共同控制恢复完成时间。
2. Forest、Savanna、Grassland、Cropland 中会出现较多并列的水热变量进入目标方程，说明原始版本偏向“全变量并列解释”。
3. Wetland 的特征明显更少，表明其恢复过程更接近由少数水分相关指标控制。
4. 由于原始版本特征较多，虽然可解释面较广，但后续去冗余是必要的。

## 图件清单与说明

### `global_beeswarm_5000.png`

- 含义：展示在 `5000` 抽样下，全局 SHAP 值在样本中的分布。
- 说明：原始版本最初没有单独导出蜂巢图，因此此处使用同口径 `5000` 样本比较版补齐。
- 用途：适合观察某个特征在不同样本上是正向推动还是负向推动恢复时间。

### `global_importance_topk_5000.png`

- 含义：展示全局平均绝对 SHAP 值最高的一组特征。
- 说明：这是原始版本最直接的“变量重要性排序图”。
- 用途：适合在结果部分说明哪些变量最值得进入后续 SEM。

### `path_overview.png`

- 含义：6 个 biome 的原始 SEM 路径图总览。
- 说明：这一版全部是“直接效应图”，即变量直接连到目标值，没有显式中介。
- 用途：适合作为后续机制型路径图的对照。

### `GPP_code1_*_path_diagram.png`

- 含义：各 biome 的单独路径图。
- 说明：不同 biome 的路径数不同，Wetland 最少。
- 用途：适合逐 biome 检查变量进入路径模型的差异。

## 本版本的局限

1. 变量冗余较强，解释不够干净。
2. SHAP 抽样只有 `5000`，适合看大体排序，但对细微排序稳定性仍需进一步检验。
3. 路径图只有直接效应，尚不足以支撑机制解释。

