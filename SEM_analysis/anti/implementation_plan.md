# GLEAM 碳通量恢复时间 SHAP+SEM 驱动机制分析 -- 实施规划

> 更新时间: 2026-03-31 (v2 -- 增加土地利用类型建模策略)  
> 工作路径: `/home/xulc/flash_drought/process/SEM_analysis/anti/`

---

## 1. 研究目标

利用 **SHAP + SEM** 联合框架, 定量回答:

1. **贡献度**: 哪些气象/土壤/植被/干旱特征因子对 GPP, NEE, RECO 的恢复时间贡献最大?
2. **驱动机制**: 这些因子通过什么路径 (直接 vs 中介) 影响恢复时间?
3. **差异比较**: GPP/NEE/RECO 主控因子是否一致? flash vs slow, SMrz vs SMs 的机制有何不同?
4. **生物群落差异**: 不同土地利用类型 (森林/草地/农田/灌丛/稀树草原) 的恢复驱动机制有何本质区别?

---

## 2. 数据盘点

### 2.1 目标变量 -- 12 个 GLEAM 事件文件

每个 NC 文件为事件维度 (event), 主目标字段: **`t_recover_to_baseline_abs_peak`**

| 通量 | 编号 | 干旱类型 | 土壤层 | 文件路径 (前缀 `.../process/`) |
|------|------|----------|--------|-------------------------------|
| GPP | code1 | flash | SMrz | `GPP-draught-analysis/code1/results/gpp_response_SMrz_...rec100.nc` |
| GPP | code2 | flash | SMs | `GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_...rec100.nc` |
| GPP | code3 | nonflash | SMrz | `GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_...rec100.nc` |
| GPP | code4 | nonflash | SMs | `GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_...rec100.nc` |
| NEE | code1 | flash | SMrz | `NEE-draught-analysis/code1SMrz/result/nee_response_SMrz_...rec100.nc` |
| NEE | code2 | flash | SMs | `NEE-draught-analysis/code2SMs/result/nee_response_SMs_...rec100.nc` |
| NEE | code3 | nonflash | SMrz | `NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_...rec100.nc` |
| NEE | code4 | nonflash | SMs | `NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_...rec100.nc` |
| RECO | code1 | flash | SMrz | `RECO-draught-analysis/code1/results/reco_response_SMrz_...rec100.nc` |
| RECO | code2 | flash | SMs | `RECO-draught-analysis/code2_SMs/results/reco_response_SMs_...rec100.nc` |
| RECO | code3 | nonflash | SMrz | `RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_...rec100.nc` |
| RECO | code4 | nonflash | SMs | `RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_...rec100.nc` |

> 文件名后缀统一: `*_v20260328_latfix_rel0_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc`

### 2.2 解释变量 -- ERA5 气象数据 (14 个变量)

路径: `/data/era5_for_GRN/yearly/`, 维度: `time(16437) x lat(720) x lon(1440)`

| 分组 | 变量 | NC 文件 |
|------|------|---------|
| **水分收支** | total_precipitation | `total_precipitation_0p25deg_1980_2024.nc` |
| | total_evaporation | `total_evaporation_0p25deg_1980_2024.nc` |
| **能量/热环境** | temperature_2m | `temperature_2m_0p25deg_1980_2024.nc` |
| | ssrd (短波辐射) | `ssrd_0p25deg_1980_2024.nc` |
| | strd (长波辐射) | `strd_0p25deg_1980_2024.nc` |
| | soil_temperature_level_1-4 | `soil_temperature_level_{1..4}_0p25deg_1980_2024.nc` |
| **动力/边界层** | wind_u_10m, wind_v_10m | `wind_{u,v}_10m_0p25deg_1980_2024.nc` |
| | surface_pressure | `surface_pressure_0p25deg_1980_2024.nc` |
| **植被结构** | LAI_high, LAI_low | `leaf_area_index_{high,low}_vegetation_0p25deg_1980_2024.nc` |

> **不使用** ERA5 土壤湿度 (`volumetric_soil_water_layer_1`, `volumetric_root_soil_water`), 因为干旱事件基于 GLEAM 识别, 必须使用同源的 GLEAM 土壤湿度。

### 2.3 解释变量 -- GLEAM 土壤湿度 (替代 ERA5 土壤湿度)

路径: `/data/GLEAM/0p25deg_yearly/`, 维度同 ERA5

| 变量 | NC 文件 | 说明 |
|------|---------|------|
| SMs (表层) | `SMs_45years_0p25deg.nc` | GLEAM 4.2a, m3/m3 |
| SMrz (根区) | `SMrz_45years_0p25deg.nc` | GLEAM 4.2a, m3/m3 |

### 2.4 解释变量 -- 干旱事件特征 (6 个字段)

干旱事件文件维度: `max_events x lat(720) x lon(1440)`

**GLEAM 干旱事件 (本阶段使用):**

| 土壤层 | 路径 |
|--------|------|
| SMrz | `.../gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/` |
| SMs | `.../gleam/clip_result/SMs_result_v5.4_0p25deg_no_ice_desert/` |

code1/code3 对应 `flash_lt20_drought_events_v5.4.nc` / `slow_gt20_drought_events_v5.4.nc` (SMrz)  
code2/code4 对应同名文件 (SMs)

**可提取字段:**

| 字段 | 含义 | 假设 |
|------|------|------|
| `onset_days` | 爆发天数 | 爆发越快 -> 恢复可能越慢 |
| `onset_rate` | 爆发速率 (SM下降速率) | 速率越大 -> 冲击越强 |
| `onset_drop` | 爆发期SM总降幅 | 降幅越大 -> 亏缺越重 |
| `intensity` | 干旱烈度 | 烈度越高 -> 恢复越慢 |
| `duration` | 干旱持续天数 | 持续越久 -> 损伤越深 |
| `days_below_p20` | 低于P20天数 | 极端缺水越多 -> 恢复越慢 |

**ERA5 干旱事件 (后续扩展):** `.../era5/clip_result/ERA5L_root_result_v5.4.../` 和 `ERA5L_swvl1_result_v5.4.../`

### 2.5 土地利用类型数据

数据文件: `/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_11km.tif`  
重采样版本: `MCD12C1_LC_Type1_2010_0.10deg.tif` (0.1 deg 分辨率)  
分类体系: IGBP 17 类

**IGBP 分类与生物群落聚合方案:**

| 生物群落 (Biome) | IGBP 编码 | 包含类型 |
|-----------------|----------|----------|
| **Forest** (森林) | 1,2,3,4,5 | 常绿针叶林, 常绿阔叶林, 落叶针叶林, 落叶阔叶林, 混交林 |
| **Shrubland** (灌丛) | 6,7 | 闭合灌丛, 开放灌丛 |
| **Savanna** (稀树草原) | 8,9 | 木本稀树草原, 稀树草原 |
| **Grassland** (草地) | 10 | 草地 |
| **Cropland** (农田) | 12,14 | 农田, 农田/自然镶嵌 |

> 排除: 0-Water, 13-Urban, 15-Snow/Ice, 16-Barren (已通过 `lu_event_valid` 过滤)  
> Permanent Wetland (11) 样本通常较少, 标记但不单独建模

**当前限制**: 事件 NC 中仅含 `lu_event_valid` (二值), 不含具体 IGBP 类别。  
**解决方案**: 在 `01_build_event_master_table.py` 中按事件 `(lat, lon)` 从 MCD12C1 TIF 查表赋值 `igbp_class` 和 `biome`。

### 2.6 不同生物群落的恢复机制差异 (建模依据)

| 特征维度 | 森林 | 草地 | 农田 | 灌丛/稀树草原 |
|----------|------|------|------|--------------|
| 根系深度 | 深 (数米) | 浅 (<1m) | 中等 | 中-浅 |
| LAI 水平 | 高 (3-8) | 低 (0.5-2) | 中 (2-5) | 低-中 |
| 水分获取策略 | 深层土壤水 | 表层降水依赖 | 灌溉+降水 | 干旱适应型 |
| 恢复驱动因子 | SM_root + 温度 | 降水 + 表层SM | 降水 + 管理 | 降水脉冲 |
| GPP 恢复模式 | 慢但稳 | 快但脆弱 | 取决于作物 | 极端依赖降水 |

> **核心矛盾**: 同一变量 (如 temperature_2m) 在不同群落中可能作用方向相反 -- 对森林可能 "适度升温促进恢复", 对草地却是 "高温加剧蒸散阻碍恢复"。全局模型会平均掉这些反向效应, 低估真实贡献度。

---

## 3. 各因子的时间阶段归属 -- 详细说明

### 3.1 干旱事件生命周期五阶段

```
                    P0           P1            P2              P3          P4
              +----------++----------++--------------++----------++----------+
              |  干旱前  || 爆发阶段 ||  干旱持续期  ||恢复早期  ||恢复全期  |
              +----------++----------++--------------++----------++----------+
         onset-30d    onset_start   drought_start    peak    peak+30d   peak+60d
```

| 阶段 | 名称 | 时间范围 | 代号 | 能否用于SHAP主模型 |
|------|------|---------|------|-------------------|
| P0 | 干旱前期 | onset_start - 30d -> onset_start - 1d | `pre30` | YES (无泄漏) |
| P1 | 爆发阶段 | onset_start -> drought_start | `onset` | YES (无泄漏) |
| P2 | 干旱持续期 | drought_start -> peak | `drought` | YES (无泄漏) |
| P3 | 恢复早期 | peak -> peak+30d (固定窗口) | `rec30` | 辅助模型 |
| P4 | 恢复全期 | peak -> peak+60d (固定窗口) | `rec60` | 仅SEM用 |

> **核心原则**: SHAP 主模型只用 P0+P1+P2 (恢复前已知信息), P3/P4 用固定窗口避免泄漏, 仅供辅助 SHAP 和 SEM。

### 3.2 变量 x 阶段 完整归属表

#### A. ERA5 气象变量 (时间序列型, 需按阶段窗口提取聚合统计量)

| 变量 | P0 干旱前 | P1 爆发 | P2 持续期 | P3 恢复30d | P4 恢复60d |
|------|:---------:|:-------:|:---------:|:----------:|:----------:|
| temperature_2m | mean, max | mean | mean, max | mean | mean |
| total_precipitation | sum, mean | sum | sum | sum | sum |
| total_evaporation | sum | sum | sum | sum | sum |
| ssrd | mean | mean | mean | mean | -- |
| strd | mean | -- | mean | mean | -- |
| soil_temp_L1 | mean | -- | mean | mean | -- |
| soil_temp_L2 | -- | -- | mean | -- | -- |
| soil_temp_L3 | -- | -- | mean | -- | -- |
| soil_temp_L4 | -- | -- | mean | -- | -- |
| wind_u/v -> wind_speed | mean | -- | mean | mean | -- |
| surface_pressure | mean | -- | -- | -- | -- |
| LAI_high | mean | -- | mean | mean | -- |
| LAI_low | mean | -- | mean | mean | -- |

#### B. GLEAM 土壤湿度 (时间序列型, 按阶段提取)

| 变量 | P0 干旱前 | P1 爆发 | P2 持续期 | P3 恢复30d |
|------|:---------:|:-------:|:---------:|:----------:|
| SMrz | mean, min | min, delta | min, mean | mean, delta |
| SMs | mean, min | min, delta | min, mean | mean, delta |

> code1/code3(SMrz事件)主提取SMrz; code2/code4(SMs事件)主提取SMs; 两者均提取做对照。

#### C. 干旱事件特征 (静态属性, 从事件文件一次性提取)

| 变量 | 归属阶段 | 说明 |
|------|---------|------|
| `onset_days` | 描述 P1 的时长 | 直接从事件文件读取 |
| `onset_rate` | 描述 P1 的速率 | 同上 |
| `onset_drop` | 描述 P1 的总降幅 | 同上 |
| `intensity` | 描述 P2 的严重程度 | 同上 |
| `duration` | 描述 P1+P2 的总时长 | 同上 |
| `days_below_p20` | 描述 P2 中极端天数 | 同上 |

#### D. 碳通量事件形态变量 (从响应文件直接读取)

| 变量 | 归属阶段 | 说明 |
|------|---------|------|
| `t_response_onset_start` | P1->P2 过渡 | 碳通量响应延迟天数 |
| `t_peak_abs` | P2 | 到碳通量最低点的天数 |
| `change_to_peak_abs` | P2 | 碳通量峰值降幅 (绝对值) |
| `legacy_duration` | P3/P4 | 遗留效应持续时间 |
| `onset_doy` | 静态 | 季节标识 (生长季/非生长季) |

#### E. 派生变量

| 派生变量 | 公式 | 提取阶段 |
|----------|------|---------|
| wind_speed | sqrt(u^2 + v^2) | P0, P2, P3 |
| P_minus_ET | TP - ET (水分盈亏) | P0, P2, P3 |
| LAI_total | LAI_high + LAI_low | P0, P2, P3 |
| LAI_change | LAI(P2_mean) - LAI(P0_mean) | 跨阶段 |
| SM_recovery | SM(P3_end) - SM(P2_min) | 跨阶段 |
| soil_temp_gradient | ST_L1 - ST_L4 | P2 |

### 3.3 SHAP 与 SEM 各自使用的变量汇总

| 模型 | 使用的阶段 | 核心原则 |
|------|-----------|---------|
| **SHAP 主模型** | P0 + P1 + P2 + 静态干旱特征 + 碳通量形态 + biome | 仅含恢复前信息 (口径A) |
| **SHAP 辅助模型** | P0 + P1 + P2 + P3(固定30d) | 探索恢复初期条件的作用 |
| **SEM** | SHAP筛选后关键变量, 可含 P3 | 固定窗口防泄漏, 分群落建模 |

---

## 4. 土地利用类型建模策略 -- 三层混合框架

### 4.1 为什么不能只建全局模型

- 不同群落的恢复机制是**本质不同**, 不仅是程度差异
- 全局模型中关键变量的 SHAP 值会因正/负效应互抵而失真
- SEM 假设线性关系, 全局 SEM 的路径系数缺乏明确生态学意义

### 4.2 三层混合建模策略

```
第1层: 全局模型 (biome 作为类别特征)
  -> 回答: 整体上哪些因子最重要? biome本身对恢复时间的贡献度?
  -> SHAP interaction 揭示 biome x variable 交互效应

第2层: 分生物群落模型 (5 大类各独立建模)
  -> 回答: 各群落主控因子排序是否不同? 驱动机制差异?
  -> 最核心的分析层

第3层: 跨群落对比
  -> 回答: 哪些因子是 "群落通用"? 哪些是 "群落特异"?
  -> SHAP 排序对比 + SEM 路径系数对比
```

### 4.3 SHAP 建模层次

| 层次 | 维度 | 模型数量 | 用途 |
|------|------|---------|------|
| 1. 全局+biome | 通量 x (code1-4合并) | 3 个 | 全局概览 + biome交互 |
| 2. 分群落 | 通量 x 群落 | 3 x 5 = 15 个 | **核心分析** |
| 3. 全综合 | 全部合并 | 1 个 | 总体对比 |

> 推荐优先级: **层次2 > 层次1 > 层次3**  
> 先从 GPP code1 x Forest 调试 -> 扩展到 GPP x 5群落 -> 扩展到全通量

### 4.4 SEM 建模策略

- SEM **只做分群落版本**, 不做全局 SEM
- 每个群落的 SEM 路径结构可能不同
- 先在样本量最大的 1-2 个群落上调试路径框架

### 4.5 SEM 假设路径框架

```
干旱特征 -------> 冲击强度 --> 恢复时间
(onset_rate,      (delta_peak,      ^
 intensity,        t_peak)          |
 duration)                          |
                                    |
水分供给 -------> 植被状态 ---------+
(TP, SM)          (LAI变化)         ^
     |                              |
     v                              |
能量压力 -------> 水分消耗 ---------+
(T2m, SSRD)       (ET, P-ET)
```

> 此框架为初始假设, 各群落的实际路径需根据 SHAP 结果调整

---

## 5. 文件组织结构

```
/home/xulc/flash_drought/process/SEM_analysis/anti/
|-- implementation_plan.md
|-- GLEAM/                              <-- GLEAM 版本分析 (本阶段)
|   |-- code/
|   |   |-- 01_build_event_master_table.py   <-- 含土地利用查表赋值
|   |   |-- 02_extract_era5_features.py
|   |   |-- 03_extract_gleam_sm_features.py
|   |   |-- 04_extract_drought_characteristics.py
|   |   |-- 05_eda_and_quality_check.py      <-- 含分群落 EDA
|   |   |-- 06_shap_analysis.py              <-- 全局+分群落 SHAP
|   |   |-- 07_sem_analysis.py               <-- 分群落 SEM
|   |   +-- 08_cross_biome_comparison.py     <-- 跨群落对比
|   |-- data/
|   |   |-- event_master_table.parquet       <-- 含 igbp_class, biome 列
|   |   |-- feature_table_pre_recovery.parquet
|   |   +-- feature_table_recovery_phase.parquet
|   |-- results/
|   |   |-- shap/
|   |   |   |-- global/
|   |   |   |-- by_biome/
|   |   |   +-- comparison/
|   |   +-- sem/
|   |       +-- by_biome/
|   +-- plots/
|       |-- eda/
|       |-- shap/
|       +-- sem/
+-- ERA5/                               <-- ERA5 版本分析 (后续扩展, 结构同上)
```

---

## 6. 执行阶段

### 阶段 1: 事件主表构建
- [ ] `01_build_event_master_table.py`
  - 读 12 个 GLEAM 事件 NC
  - **按 (lat, lon) 从 MCD12C1 TIF 查表赋值 `igbp_class` 和 `biome`**
  - 统计各 biome x code 的有效事件数量 (样本量检查, 阈值 >= 1000)
  - 输出 parquet

### 阶段 2: 特征提取 (3 个脚本可并行)
- [ ] `02_extract_era5_features.py` -- ERA5 气象变量按 P0-P4 窗口提取
- [ ] `03_extract_gleam_sm_features.py` -- GLEAM SMs/SMrz 按窗口提取
- [ ] `04_extract_drought_characteristics.py` -- 从干旱事件文件匹配 onset_rate/intensity 等

### 阶段 3: EDA
- [ ] `05_eda_and_quality_check.py`
  - 全局 + **分群落** 的缺失率, 分布, 共线性检查
  - **各群落恢复时间分布对比**
  - 各群落 x code 的样本量汇总表

### 阶段 4: SHAP
- [ ] `06_shap_analysis.py`
  - 4a: GPP code1 x Forest 调试流程
  - 4b: GPP 全局模型 (biome 作 feature) -> SHAP interaction
  - 4c: GPP x 5 群落各独立模型 -> 分群落 SHAP
  - 4d: 扩展到 NEE, RECO

### 阶段 5: SEM (分群落)
- [ ] `07_sem_analysis.py`
  - 仅做分群落版本
  - 先在样本量最大的 1-2 个群落上调试
  - SHAP 筛选变量 -> 构建群落专属路径

### 阶段 6: 跨群落对比
- [ ] `08_cross_biome_comparison.py`
  - SHAP 重要性排序对比 (5 群落 x 3 通量)
  - SEM 路径系数对比
  - 识别 "群落通用因子" vs "群落特异因子"
  - 输出综合对比报告

---

## 7. 关键约束

1. **本阶段仅 GLEAM**, ERA5 版本后续扩展到 `anti/ERA5/`
2. **土壤湿度用 GLEAM** (SMs/SMrz), 不用 ERA5 的 swvl1/root_sm
3. **干旱特征必须纳入** (onset_rate, intensity 等), 是恢复时间的强先验解释变量
4. **恢复期变量用固定窗口** (30d/60d), 防止信息泄漏
5. **先 SHAP 后 SEM**, SHAP 筛选后再组织 SEM 路径
6. **分群落建模为核心**, 全局模型用于概览和交互效应检测, SEM 只做分群落版本
7. **土地利用类型** 从 MCD12C1 (2010) 查表赋值, 聚合为 5 大生物群落
