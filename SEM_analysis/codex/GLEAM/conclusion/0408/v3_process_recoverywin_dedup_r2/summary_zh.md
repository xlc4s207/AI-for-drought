# V3 去冗余版本：`dedup_r2`

## 版本定位

这一版本的核心目标是解决原始版本变量冗余过强的问题，并且在 SHAP 和 SEM 中引入显式 `R2` 指标，以提高解释结果的可信度。

## 特征策略

非湿地 biome 保留 6 个特征：

- `recoverywin_temperature_2m_mean`
- `recoverywin_VPD_mean`
- `recoverywin_p_minus_et`
- `recoverywin_ssrd_mean`
- `recoverywin_strd_mean`
- `recoverywin_SMrz_mean`

Wetland 保留 3 个特征：

- `recoverywin_SMrz_mean`
- `recoverywin_SMrz_delta`
- `recoverywin_ssrd_mean`

去冗余逻辑是：

- 不再同时使用 `dewpoint_temperature`、`temperature_2m` 和 `VPD`
- 不再同时使用 `total_precipitation`、`total_evaporation` 与 `p_minus_et`

## SHAP 结果

- 全局样本行数：`1,322,953`
- SHAP 抽样：`20000`
- 全局特征数：`6`
- 全局 holdout `R2 = 0.8573`

各 biome SHAP holdout `R2`：

| Biome | SHAP holdout R2 |
|---|---:|
| Forest | 0.8959 |
| Shrubland | 0.7914 |
| Savanna | 0.8843 |
| Grassland | 0.8644 |
| Cropland | 0.8533 |
| Wetland | 0.3373 |

## SEM 结果

各 biome 的单方程直接效应 SEM holdout `R2`：

| Biome | 样本量 | 特征数 | SEM holdout R2 |
|---|---:|---:|---:|
| Forest | 318,380 | 6 | 0.6872 |
| Shrubland | 166,813 | 6 | 0.5072 |
| Savanna | 325,911 | 6 | 0.6705 |
| Grassland | 329,638 | 6 | 0.6386 |
| Cropland | 176,226 | 6 | 0.5867 |
| Wetland | 5,985 | 3 | 0.1240 |

## 主要结论

1. 去冗余后，模型解释力仍然很高，说明核心恢复控制因子并没有因为删掉冗余变量而丢失。
2. Forest、Savanna、Grassland 的解释力依旧较强，说明这些生态系统的恢复时间主要受恢复窗内水分与能量环境共同调控。
3. Wetland 的 `R2` 明显偏低，提示其恢复机制可能需要额外的湿地水文或土壤变量。
4. 这一版相较原始版更适合作为主文本分析，因为变量集合更紧凑、逻辑更清晰。

## 图件清单与说明

### `global_beeswarm.png`

- 含义：`20000` 抽样下、6 特征版本的全局蜂巢图。
- 用途：说明去冗余后各核心变量的正负影响方向与分布。

### `global_importance_topk.png`

- 含义：6 个保留变量的全局重要性排序图。
- 用途：适合在主文中展示“精简后最重要的恢复窗变量”。

### `path_overview.png`

- 含义：去冗余版本在 6 个 biome 上的 SEM 直接效应路径图总览。
- 用途：展示删减变量后路径结构如何简化。

### `GPP_code1_*_path_diagram.png`

- 含义：各 biome 单独路径图。
- 用途：对比不同 biome 在同一精简特征框架下的路径差异。

## 版本评价

V3 是当前最平衡的一版：变量少、解释力高、便于写作。后续 V4 主要是作为扩展稳健性版本，而不是替代 V3。

