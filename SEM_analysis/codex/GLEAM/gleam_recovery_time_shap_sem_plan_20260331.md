# GLEAM 恢复时间 SHAP+SEM 规划

## 1. 目标

本阶段的核心目标是：

1. 基于 `GLEAM` 版本的 `GPP / NEE / RECO` 三类碳通量结果文件，解释恢复时间 `t_recover_to_baseline_abs_peak` 的主控因子。
2. 使用 `GLEAM + ERA5` 联合驱动体系构建事件级解释变量。
3. 采用 `SHAP + SEM` 的联合框架，同时回答两个问题：
   - 哪些变量对恢复时间的贡献度最大。
   - 这些变量通过什么路径影响恢复时间。
4. 本阶段只分析 `GLEAM` 事件库，对应 `code1-code4` 的 `rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc` 文件。
5. `ERA5` 版本的干旱结果文件先不进入主体分析，但方法和目录结构要预留无缝扩展接口。

## 2. 分析范围

### 2.1 目标结果文件

本阶段只使用以下 12 个 `GLEAM` 目标文件：

- GPP
  - `/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`
  - `/home/xulc/flash_drought/process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`
  - `/home/xulc/flash_drought/process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`
  - `/home/xulc/flash_drought/process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`
- NEE
  - `/home/xulc/flash_drought/process/NEE-draught-analysis/code1SMrz/result/nee_response_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`
  - `/home/xulc/flash_drought/process/NEE-draught-analysis/code2SMs/result/nee_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`
  - `/home/xulc/flash_drought/process/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`
  - `/home/xulc/flash_drought/process/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`
- RECO
  - `/home/xulc/flash_drought/process/RECO-draught-analysis/code1/results/reco_response_SMrz_events_global_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`
  - `/home/xulc/flash_drought/process/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`
  - `/home/xulc/flash_drought/process/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`
  - `/home/xulc/flash_drought/process/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`

### 2.2 驱动因子文件

当前可用气象与陆面因子包括：

- 风场：`wind_u_10m_0p25deg_1980_2024.nc`、`wind_v_10m_0p25deg_1980_2024.nc`
- 水分收支：`total_precipitation_0p25deg_1980_2024.nc`、`total_evaporation_0p25deg_1980_2024.nc`
- 近地气象：`temperature_2m_0p25deg_1980_2024.nc`、`surface_pressure_0p25deg_1980_2024.nc`
- 辐射：`ssrd_0p25deg_1980_2024.nc`、`strd_0p25deg_1980_2024.nc`
- 土壤温度：`soil_temperature_level_1_0p25deg_1980_2024.nc` 到 `soil_temperature_level_4_0p25deg_1980_2024.nc`
- 植被冠层：`leaf_area_index_low_vegetation_0p25deg_1980_2024.nc`、`leaf_area_index_high_vegetation_0p25deg_1980_2024.nc`

针对 `GLEAM` 事件库，本阶段土壤湿度相关驱动必须使用 `GLEAM` 自身的 0.25° 年序列：

- `/data/GLEAM/0p25deg_yearly/SMs_45years_0p25deg.nc`
  - 变量名：`SMs`
- `/data/GLEAM/0p25deg_yearly/SMrz_45years_0p25deg.nc`
  - 变量名：`SMrz`

### 2.3 为什么不能用 ERA5 的土壤湿度解释 GLEAM 事件

这一点现在正式修正为：

1. 当前主体分析对象是 `GLEAM` 识别出的干旱事件。
2. 如果再用 `ERA5` 的土壤湿度去解释 `GLEAM` 事件，会引入“事件识别口径”和“解释变量口径”不一致的问题。
3. 因此第一阶段必须遵循：
   - `GLEAM` 事件 -> 使用 `GLEAM` 的 `SMs/SMrz`
   - `ERA5` 事件 -> 后续再使用 `ERA5` 的 `swvl1/root soil water`

## 3. 核心逻辑

本分析的逻辑链如下：

1. 干旱事件已经在 `GLEAM` 事件库中被识别。
2. 三类碳通量结果文件已经给出了每个事件的恢复时间等响应指标。
3. 现在不再重新识别事件，而是将每个事件视为一个分析样本。
4. 对每个样本，根据其经纬度和事件时间，从 `GLEAM + ERA5` 变量中抽取事件前后窗口特征。
5. 以恢复时间为目标变量，以气象陆面因子、土壤湿度因子和事件形态指标为解释变量，建立事件级样本表。
6. 先用 SHAP 定量识别主控因子和非线性阈值，再用 SEM 组织机制路径。

换句话说，本阶段不是“再算恢复时间”，而是“解释已经算好的恢复时间为什么长、为什么短”。

## 4. 目标变量定义

### 4.1 主目标变量

主目标变量定义为：

- `t_recover_to_baseline_abs_peak`

原因：

1. 该字段直接表示从“绝对值峰值”到“恢复到基准”的时间。
2. 它是当前 `rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100` 版本最稳定、最统一的恢复时间口径。
3. 在 GPP、NEE、RECO 三类通量之间都可直接比较。

### 4.2 辅助目标变量

建议保留一个敏感性分析目标：

- `t_recover_post_drought`

它用于区分：

1. “峰值后恢复”
2. “干旱结束后恢复”

### 4.3 事件筛选口径

主分析样本建议满足：

1. `response_detected == 1`
2. `t_recover_to_baseline_abs_peak` 为有限值且 `>= 0`
3. 经纬度、事件时间字段有效
4. 驱动窗口中主要变量缺测比例不超过阈值

这意味着：

- 主分析针对“已响应且已恢复”的事件
- 未恢复事件不进入主 SEM
- 未恢复事件可单独做补充分析，例如“恢复/未恢复二分类 SHAP”

## 5. 解释变量体系

### 5.1 一级变量组

建议将驱动因子划分为 6 个过程组：

1. 水分供给组
   - `total_precipitation`
   - `SMrz` 或 `SMs`
   - 可选派生项：事件前土壤湿度异常、事件后土壤湿度补给速度

2. 水分消耗与蒸散组
   - `total_evaporation`
   - 派生项：`P-ET`、累积水分亏缺

3. 能量与热环境组
   - `temperature_2m`
   - `ssrd`
   - `strd`
   - `soil_temperature_level_1~4`

4. 动力与边界层组
   - `wind_u_10m`
   - `wind_v_10m`
   - 派生项：风速 `sqrt(u^2+v^2)`
   - `surface_pressure`

5. 植被结构组
   - `leaf_area_index_low_vegetation`
   - `leaf_area_index_high_vegetation`
   - 派生项：总 LAI、低/高植被占优类型 proxy

6. 干旱事件形态组
   - `onset_drop`
   - `onset_rate`
   - `intensity`
   - `onset_days`
   - `duration`
   - `days_below_p20`

### 5.2 干旱事件特征来源

`GLEAM` 事件形态变量来自：

- `SMrz` 事件库：
  - `/home/xulc/flash_drought/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert`
- `SMs` 事件库：
  - `/home/xulc/flash_drought/gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert`

其中事件文件中已包含：

- `onset_drop`
- `onset_rate`
- `intensity`
- `onset_days`
- `duration`
- `days_below_p20`

后续 `ERA5` 事件形态变量来源于：

- `/home/xulc/flash_drought/era5/clip_result`

### 5.3 事件内部状态变量

仅用外部环境变量解释恢复时间是不够的，还需要加入事件内部状态变量：

1. `t_response_onset_start`
2. `t_response_drought_start`
3. `t_peak_abs`
4. `gpp/nee/reco_change_to_peak_abs`
5. `legacy_duration`
6. `onset_doy`
7. 干旱类型标签
   - `code1`: SMrz flash
   - `code2`: SMs flash
   - `code3`: SMrz slow
   - `code4`: SMs slow

这些变量对恢复时间具有强先验解释意义，后续在 SHAP 和 SEM 中都应保留。

### 5.4 土地利用分层策略

这一部分需要单独明确，因为恢复机制在不同地表类型之间差异很大。

#### 5.4.1 为什么不能只做一个全局模型

如果只做一个全球统一模型，会出现三个问题：

1. 同一变量在不同群落中的作用方向可能相反。
   - 例如升温对森林可能意味着生长季延长，但对草地可能意味着蒸散加剧。
2. 全局模型会把不同群落的异质性平均掉。
   - 结果是 SHAP 贡献度被“冲淡”，SEM 路径也失去明确生态意义。
3. 恢复时间的控制因子具有明显群落依赖性。
   - 森林更偏向根区水分和热环境，草地和稀树草原更偏向降水脉冲与表层土壤湿度。

#### 5.4.2 为什么也不建议按原始 IGBP 17 类完全拆开

如果直接按原始地类逐类建模，又会出现另外几个问题：

1. 样本量会被切得过碎，部分地类不稳定。
2. 解释结果会变得过于零散，不利于跨通量对比。
3. SEM 在小样本类别下容易不收敛或路径不稳。

因此更合理的方案不是“单一全局”也不是“17 类全拆”，而是分层混合方案。

#### 5.4.3 推荐方案：全局 + 分组 + 多组 SEM

推荐采用三层结构：

1. 全局模型
   - 所有植被像元一起建模。
   - 显式加入土地利用变量。
   - 用于回答“整体上哪些因子最重要”“土地利用本身是否重要”。

2. 分组模型
   - 按大类生物群落单独建模。
   - 用于回答“森林、草地、农田等恢复机制是否不同”。
   - 这是主分析层。

3. 多组 SEM
   - 不做单一全局 SEM。
   - 优先在主要生物群落中分别建立路径模型并进行对比。

#### 5.4.4 土地利用数据与分组口径

土地利用文件使用：

- `/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_11km.tif`

建议采用 IGBP 大类聚合：

- `Forest`: 1-5
- `Shrubland`: 6-7
- `Savanna_Grassland`: 8-10
- `Cropland`: 12, 14
- `Wetland`: 11

建议剔除：

- `0 Water`
- `13 Urban`
- `15 Snow/Ice`
- `16 Barren/Sparse`

其中：

1. `Wetland` 是否单独建模，取决于样本量。
2. 如果 `Wetland` 样本不足，可以只保留在全局模型中，不进入分组 SEM。

#### 5.4.5 土地利用变量的表达方式

不建议只给每个 0.25° 像元赋一个单一类别。更稳妥的做法是同时构建：

1. 主类别变量
   - `dominant_class`
   - `biome_group`

2. 主类纯度变量
   - `dominant_fraction`

3. 各类覆盖比例变量
   - `forest_fraction`
   - `shrub_fraction`
   - `savanna_grass_fraction`
   - `cropland_fraction`
   - `wetland_fraction`

建议建模时分两层使用：

1. 全局 SHAP
   - 保留所有植被像元
   - 使用主类别 + 覆盖比例变量

2. 分组 SHAP / SEM
   - 仅保留 `dominant_fraction >= 0.6` 或 `0.7` 的纯像元
   - 提高解释清晰度

## 6. 时间窗口设计

这是整个解释逻辑最关键的部分。

### 6.0 干旱事件生命周期阶段

为避免后续特征提取口径混乱，建议固定使用五阶段划分：

- `P0 pre30`: `onset_start - 30d` 到 `onset_start - 1d`
- `P1 onset`: `onset_start` 到 `drought_start`
- `P2 shock`: `drought_start` 到 `peak`
- `P3 postpeak30`: `peak` 到 `peak + 30d`
- `P4 postpeak60`: `peak` 到 `peak + 60d`

含义如下：

1. `P0`
   - 干旱前背景状态
2. `P1`
   - 爆发阶段
3. `P2`
   - 从干旱开始到碳通量峰值的冲击累积阶段
4. `P3`
   - 峰值后的固定长度恢复早期
5. `P4`
   - 峰值后的更长恢复固定窗口

其中主 SHAP 只使用 `P0 + P1 + P2`，`P3/P4` 仅用于过程解释型分析。

### 6.1 必须避免的一个问题

如果直接用“恢复发生后的平均环境”去解释恢复时间，会有信息泄漏风险：

- 恢复时间越长，统计窗口越长
- 变量均值会被目标本身反向影响

因此必须区分两种分析口径。

### 6.2 口径 A：前置预测型

目标：解释“哪些条件使一个事件更容易恢复得慢”

只允许使用恢复发生前就已知的信息：

1. 干旱前窗口：`-30 ~ -1 d`
2. 爆发窗口：`onset_start ~ drought_start`
3. 冲击累积窗口：`drought_start ~ peak`

这一口径中不同类型变量的使用方式为：

1. 干旱前窗口
   - `temperature_2m`, `ssrd`, `strd`, `surface_pressure`, `wind`, `ET`, `P`
   - `GLEAM SMs/SMrz`
   - `LAI high/low`
   - `soil_temperature_level_1~4`

2. 爆发窗口
   - `onset_start ~ drought_start` 的均值、累积量、极值、变化率
   - 重点描述爆发期环境背景

3. 冲击累积窗口
   - `drought_start ~ peak`
   - 重点描述从干旱开始到碳通量最受损阶段的环境压力累积

4. 干旱事件形态变量
   - `onset_rate`, `intensity`, `duration`, `days_below_p20` 等直接作为输入
   - 这些变量天然属于“事件发生后、恢复前已知”信息，可进入主模型

这个口径适合：

- 主 SHAP 模型
- 做“预测型贡献度”解释
- 避免明显信息泄漏

### 6.3 口径 B：过程解释型

目标：解释“恢复阶段的环境条件如何决定最终恢复速度”

可使用恢复过程中、但仍然具有过程意义的变量：

1. `peak ~ peak+30d`
2. `peak ~ recovery`
3. `drought_end ~ recovery`

这一口径中：

1. `peak ~ peak+30d`
   - 用于描述恢复初期环境是否有利
   - 例如恢复初期降水、土壤补水、温度回落、辐射下降

2. `peak ~ recovery`
   - 用于描述完整恢复阶段的平均环境
   - 仅作为机制解释，不作为主预测变量

3. `drought_end ~ recovery`
   - 用于分析“干旱结束之后的恢复环境”作用
   - 更适合和 `t_recover_post_drought` 联动分析

这个口径适合：

- 辅助 SHAP
- SEM 机制路径
- 分析为什么有些事件在恢复期恢复更快

### 6.4 现在的输入因子到底属于哪一阶段

这里明确说明：

1. 主 SHAP 输入：
   - 以“干旱前 + 爆发期 + 峰值前”为主
   - 不把完整恢复期均值直接作为主预测输入

2. 辅助 SHAP / SEM 输入：
   - 可以加入恢复期窗口变量
   - 但必须单独标注为“过程解释型变量”

3. 干旱事件形态变量：
   - 属于“事件属性”
   - 不归入单一时段，而是事件本身的综合描述

以后所有特征字段都必须显式区分来源：

- `pre_`：干旱前
- `onset_`：爆发期
- `shock_`：干旱开始到峰值
- `postpeak_`：峰值后短期恢复阶段
- `recovery_`：恢复期
- `event_`：事件属性

### 6.4.1 变量与阶段归属表

为避免后续代码实现时再反复讨论，建议直接采用下面的提取框架。

#### ERA5 气象与陆面变量

1. `temperature_2m`
   - `pre_`: mean, max
   - `onset_`: mean
   - `shock_`: mean, max
   - `postpeak_`: mean

2. `total_precipitation`
   - `pre_`: sum, mean
   - `onset_`: sum
   - `shock_`: sum
   - `postpeak_`: sum

3. `total_evaporation`
   - `pre_`: sum
   - `onset_`: sum
   - `shock_`: sum
   - `postpeak_`: sum

4. `ssrd`
   - `pre_`: mean
   - `onset_`: mean
   - `shock_`: mean
   - `postpeak_`: mean

5. `strd`
   - `pre_`: mean
   - `shock_`: mean
   - `postpeak_`: mean

6. `soil_temperature_level_1-4`
   - `pre_`: mean
   - `shock_`: mean
   - `postpeak_`: mean

7. `wind_u_10m`, `wind_v_10m`
   - `pre_`: mean
   - `shock_`: mean
   - `postpeak_`: mean

8. `surface_pressure`
   - `pre_`: mean

9. `leaf_area_index_high_vegetation`, `leaf_area_index_low_vegetation`
   - `pre_`: mean
   - `shock_`: mean
   - `postpeak_`: mean

#### GLEAM 土壤湿度变量

1. `SMrz`
   - `pre_`: mean, min
   - `onset_`: min, delta
   - `shock_`: min, mean
   - `postpeak_`: mean, delta

2. `SMs`
   - `pre_`: mean, min
   - `onset_`: min, delta
   - `shock_`: min, mean
   - `postpeak_`: mean, delta

具体使用原则：

1. `code1/code3` 以 `SMrz` 为主解释变量，`SMs` 作为对照。
2. `code2/code4` 以 `SMs` 为主解释变量，`SMrz` 作为对照。

#### 事件属性与通量形态变量

1. 干旱事件属性
   - `event_onset_days`
   - `event_onset_rate`
   - `event_onset_drop`
   - `event_intensity`
   - `event_duration`
   - `event_days_below_p20`

2. 通量事件形态
   - `t_response_onset_start`
   - `t_response_drought_start`
   - `t_peak_abs`
   - `change_to_peak_abs`
   - `legacy_duration`
   - `onset_doy`

#### 派生变量

建议统一派生：

1. `wind_speed = sqrt(u^2 + v^2)`
2. `p_minus_et = precipitation - evaporation`
3. `lai_total = lai_high + lai_low`
4. `lai_change = shock_lai_mean - pre_lai_mean`
5. `soil_temp_gradient = st_l1 - st_l4`
6. `sm_recovery_proxy = postpeak_sm_mean - shock_sm_min`

### 6.5 建议

建议最终构建两套特征表：

1. `pre_recovery_feature_table`
   - 用于主 SHAP

2. `recovery_phase_feature_table`
   - 用于过程 SEM 与机制补充解释

补充说明：

1. `pre_recovery_feature_table`
   - 只允许包含 `P0 + P1 + P2 + event_ + 通量形态` 字段
   - 这是主 SHAP 使用的标准表

2. `recovery_phase_feature_table`
   - 可以增加固定窗口 `P3/P4` 变量
   - 这是过程 SHAP 与 SEM 的补充表

## 7. 事件级样本表设计

建议最终输出三层表：

### 7.1 原始事件表

每一行一个事件，保留：

- 坐标：`lat`, `lon`
- 时间：`onset_year`, `onset_doy`, `drought_start_year`, `drought_start_doy`
- 类型：`metric`, `code_id`, `drought_class`
- 响应与恢复字段
- 峰值和变化量字段
- 事件形态字段

### 7.2 特征汇总表

每一行一个事件，列为聚合后的驱动变量，例如：

- `pre30_tp_mean`
- `pre30_smrz_mean` 或 `pre30_sms_mean`
- `pre30_lai_total_mean`
- `onset_to_start_t2m_mean`
- `start_to_peak_ssrd_mean`
- `peak_to_30d_tp_sum`
- `peak_to_30d_et_sum`
- `peak_to_30d_wind_mean`
- `event_onset_rate`
- `event_intensity`
- `event_duration`
- `event_days_below_p20`

### 7.3 SEM 输入表

在特征汇总表基础上进一步压缩：

- 水分供给复合因子
- 能量负荷复合因子
- 土壤热环境复合因子
- 冠层状态复合因子
- 冲击强度复合因子

这个表用于 SEM。

## 8. SHAP 分析规划

### 8.1 建模策略

建议优先使用树模型：

- `LightGBM` 或 `XGBoost`
- 目标变量：`t_recover_to_baseline_abs_peak`

### 8.2 建模层次

建议采用分层混合建模，而不是只有单一全局模型。

推荐层次如下：

1. 文件级模型
   - 每个结果文件单独建模
   - 共 12 个基础模型
   - 用于检查不同通量和不同干旱类型下的可解释性稳定性

2. 通量级全局模型
   - GPP 四组合并
   - NEE 四组合并
   - RECO 四组合并
   - 显式加入 `code_id` 与土地利用变量

3. 生物群落分组模型
   - `Forest`
   - `Shrubland`
   - `Savanna_Grassland`
   - `Cropland`
   - `Wetland`（样本足够时）
   - 这是主分析层

4. 综合层
   - 12 个文件整体合并
   - 增加 `metric`、`code_id`、土地利用变量

优先级建议为：

1. 生物群落分组模型
2. 通量级全局模型
3. 文件级模型
4. 全综合模型

### 8.3 SHAP 输出内容

至少输出：

1. 全局重要性条形图
2. SHAP beeswarm 图
3. 关键变量 dependence plot
4. 变量交互图
5. 不同 drought type / metric 下的重要性差异
6. 不同 biome 下的重要性排序差异
7. biome 与关键变量的交互效应图

## 9. SEM 分析规划

### 9.1 SEM 角色

SEM 不负责替代 SHAP，而是负责把 SHAP 已经识别出来的关键变量组织成机制路径。

### 9.2 建议路径框架

建议先从以下 5 个潜在过程构建：

1. 水分供给
   - precipitation
   - GLEAM soil moisture

2. 大气/能量压力
   - temperature
   - ssrd
   - strd
   - wind speed

3. 土壤热环境
   - soil temperature level 1~4

4. 植被结构状态
   - LAI low
   - LAI high
   - total LAI

5. 事件冲击强度
   - change_to_peak_abs
   - t_peak_abs
   - t_response_onset_start
   - onset_rate
   - intensity

对应关系建议为：

- 水分供给 -> 植被结构状态 -> 恢复时间
- 大气/能量压力 -> 水分消耗/土壤热环境 -> 恢复时间
- 事件冲击强度 -> 恢复时间
- 水分供给 <-> 大气/能量压力

### 9.3 SEM 的分组原则

SEM 不建议做单一全球版本，而建议做：

1. 分 biome 的独立 SEM
2. 或多组 SEM（multi-group SEM）

原因是：

1. 路径系数具有明确生态意义时才值得解释。
2. 全局 SEM 很容易把不同生态系统的相反路径平均掉。
3. 多组比较更适合回答“森林和草地的恢复驱动机制是否不同”。

建议实施顺序：

1. 先在样本量最大的 1-2 个 biome 上调试
2. 再扩展到全部主要 biome
3. 最后做跨 biome 路径系数对比

## 10. 推荐的执行顺序

### 阶段 1：数据治理

1. 统一读取 12 个 GLEAM 目标文件
2. 统一提取事件主键与恢复字段
3. 统一建立事件索引体系
4. 按 `(lat, lon)` 从土地利用栅格匹配 `igbp_class / biome_group / dominant_fraction`
5. 只保留主分析样本

### 阶段 2：驱动与事件形态配表

1. 按事件经纬度匹配 `GLEAM` 土壤湿度网格
2. 按事件经纬度匹配 `ERA5` 气象网格
3. 按事件主键回取事件库中的 `onset_rate / intensity / duration` 等形态特征
4. 按事件时间截取窗口
5. 计算窗口均值、累积量、极值、异常量
6. 输出事件级特征表

### 阶段 3：探索性统计

1. 检查变量缺失率
2. 检查变量分布
3. 检查不同 metric / code 的恢复时间分布
4. 检查不同 biome / code 的样本量分布
5. 检查共线性

### 阶段 4：SHAP

1. 先做 GPP `code1`
2. 先在 `GPP code1 x Forest` 上调通流程
3. 再做 GPP 四组
4. 再扩展到 NEE、RECO
5. 最后做综合模型

### 阶段 5：SEM

1. 基于 GPP `code1` 试跑路径模型
2. 先在样本量最大的 biome 上试跑
3. 根据 SHAP 结果删减变量
4. 固化路径框架
5. 扩展到其他通量和事件类型

## 11. 关键技术判断

### 11.1 为什么先 SHAP 后 SEM

因为当前候选驱动因子较多，直接上 SEM 会遇到：

- 变量过多
- 共线性强
- 路径结构不稳定

先用 SHAP 做变量筛选与优先级排序，更容易建立稳健的 SEM。

### 11.2 为什么主目标先用 `t_recover_to_baseline_abs_peak`

因为它在当前所有 `rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100` 文件中最统一、最可比、最贴近“受损后恢复”的定义。

### 11.3 为什么第一阶段只做 GLEAM 目标

因为：

1. 用户当前明确要求先用 GLEAM 版本
2. GLEAM 与 ERA5 事件库在事件数量和时间分布上明显不同
3. 若一开始混合两套目标文件，会让 SHAP 与 SEM 的目标定义不稳定

### 11.4 为什么恢复期变量必须使用固定窗口

如果直接使用“峰值到恢复”的整段均值，会出现目标泄漏：

1. 恢复时间越长，统计窗口越长。
2. 解释变量的均值会被目标变量本身反向塑造。
3. 最终模型学到的是“长恢复时间对应长窗口统计特征”，而不是恢复机制本身。

因此过程变量只能在固定窗口下提取，例如：

- `peak ~ peak+30d`
- `peak ~ peak+60d`

## 12. 目录与脚本组织建议

建议在 `/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM` 下按下面结构推进：

- `code/`
  - `01_build_event_master_table.py`
  - `02_extract_era5_features.py`
  - `03_extract_gleam_sm_features.py`
  - `04_extract_drought_characteristics.py`
  - `05_eda_and_quality_check.py`
  - `06_shap_analysis.py`
  - `07_sem_analysis.py`
  - `08_cross_biome_comparison.py`
- `data/`
  - `event_master_table.parquet`
  - `feature_table_pre_recovery.parquet`
  - `feature_table_recovery_phase.parquet`
- `results/`
  - `shap/global/`
  - `shap/by_biome/`
  - `shap/comparison/`
  - `sem/by_biome/`
- `plots/`
  - `eda/`
  - `shap/`
  - `sem/`

## 13. 预期输出物

建议在 `/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM` 下逐步形成：

1. 规划文档
2. 事件基础表
3. 驱动特征表
4. SHAP 结果
5. SEM 结果
6. 对比报告

## 14. 关键约束

1. 本阶段仅分析 `GLEAM` 事件结果。
2. `GLEAM` 事件必须配套 `GLEAM SMs/SMrz`，不能混用 `ERA5` 土壤湿度。
3. 干旱事件形态变量必须纳入模型。
4. 主 SHAP 必须避免恢复期信息泄漏。
5. 恢复期变量只允许固定窗口提取。
6. SHAP 先于 SEM。
7. 分群落建模是主体，全局模型仅用于概览与交互。

## 15. 下一步建议

下一步最合理的实施顺序是：

1. 先从 `GPP code1` 开始，构建单文件事件表与驱动配表流程
2. 先跑一版 `pre_recovery_feature_table`
3. 先在 `GPP code1` 上验证：
   - 变量缺失
   - 时间窗口是否正确
   - 恢复时间分布是否合理
   - `GLEAM` 土壤湿度与 `GLEAM` 事件库是否完全对齐
   - 事件形态变量是否成功拼接
4. 再复制到其余 11 个 GLEAM 文件
5. 在全部 GLEAM 跑通后，最后再扩展到 ERA5 版本目标文件

## 16. 本规划的最终方法口径

本阶段正式方法口径定为：

- 目标文件：`GLEAM` 版本 `GPP/NEE/RECO × code1-code4`
- 主目标字段：`t_recover_to_baseline_abs_peak`
- 主分析框架：`事件级 SHAP + 分组 SEM`
- 主解释变量：`GLEAM 土壤湿度 + ERA5 气象陆面因子 + 干旱事件形态变量 + 事件内部状态变量`
- 主时间口径：`前置预测型` 为主，`恢复过程型` 为辅
- 扩展顺序：先 GLEAM，后 ERA5

## 17. 路径与目录约定

从现在开始，`SHAP + SEM` 相关文件统一放到：

- `/home/xulc/flash_drought/process/SEM_analysis/codex`

并明确分为：

- `GLEAM`
  - `/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM`
- `ERA5`
  - `/home/xulc/flash_drought/process/SEM_analysis/codex/ERA5`

建议未来输出按以下结构组织：

- `raw_tables/`
- `feature_tables/`
- `shap/`
- `sem/`
- `figures/`
- `reports/`
