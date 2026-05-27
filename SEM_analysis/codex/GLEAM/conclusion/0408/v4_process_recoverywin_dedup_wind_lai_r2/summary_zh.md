# V4 扩展稳健性版本：`dedup + wind_speed + lai_total`

## 版本定位

在 V3 已经完成去冗余的基础上，这一版本进一步讨论一个问题：当前特征是否过少，是否应补充风速与植被冠层信息。

因此，本版本在 V3 基础上新增：

- `recoverywin_wind_speed_mean`
- `recoverywin_lai_total_mean`

## 特征设置

非湿地 biome 使用 8 个特征：

- `temperature_2m_mean`
- `VPD_mean`
- `p_minus_et`
- `ssrd_mean`
- `strd_mean`
- `SMrz_mean`
- `wind_speed_mean`
- `lai_total_mean`

Wetland 最终仍保留 3 个特征，因为新增风速在湿地中没有稳定进入最终路径结构。

## SHAP 结果

- 全局样本行数：`1,322,953`
- SHAP 抽样：`20000`
- 全局特征数：`8`
- 全局 holdout `R2 = 0.8648`

各 biome SHAP holdout `R2`：

| Biome | SHAP holdout R2 |
|---|---:|
| Forest | 0.9018 |
| Shrubland | 0.8079 |
| Savanna | 0.8904 |
| Grassland | 0.8748 |
| Cropland | 0.8602 |
| Wetland | 0.3373 |

## SEM 结果

各 biome SEM holdout `R2`：

| Biome | 样本量 | 特征数 | SEM holdout R2 |
|---|---:|---:|---:|
| Forest | 318,380 | 8 | 0.6890 |
| Shrubland | 166,813 | 8 | 0.5088 |
| Savanna | 325,911 | 8 | 0.6743 |
| Grassland | 329,638 | 8 | 0.6400 |
| Cropland | 176,226 | 8 | 0.5918 |
| Wetland | 5,985 | 3 | 0.1240 |

## 与 V3 的比较

1. 全局 SHAP holdout `R2` 从 `0.8573` 提升到 `0.8648`。
2. 各 biome 的提升总体较小，但方向一致。
3. 重要变量排序没有发生根本变化，说明风速和 LAI 更像是补充型信息，而不是颠覆性信息。
4. 因此，这一版更适合作为稳健性补充，而不是主文主版本。

## 图件清单与说明

### `global_beeswarm.png`

- 含义：8 特征扩展版本的全局蜂巢图。
- 用途：观察新增 `wind_speed_mean` 与 `lai_total_mean` 的影响分布。

### `global_importance_topk.png`

- 含义：8 个特征的全局重要性条形图。
- 用途：直接判断新增变量是否进入头部解释层。

### `path_overview.png`

- 含义：6 个 biome 的直接效应路径图总览。
- 用途：对比新增风速和 LAI 后路径是否发生结构性改变。

### `GPP_code1_*_path_diagram.png`

- 含义：各 biome 单独路径图。
- 用途：检查不同 biome 是否真正接纳了新变量。

## 版本评价

V4 证明补充 `wind_speed` 和 `lai_total` 是合理的，但提升幅度有限。因此：

- 若强调简洁与可解释性，优先使用 V3。
- 若强调稳健性检验，可补充 V4。

