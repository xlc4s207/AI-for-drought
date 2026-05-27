
- 关键变量 dependence plot
- 变量交互图
- 不同 drought_class / metric 下的重要性对比

### 核心问题

1. 恢复时间主要受水分供给还是热环境控制？
2. GPP、NEE、RECO 三者主控因子是否一致？
3. SMrz vs SMs、flash vs slow 的控制机制是否不同？
4. 是否存在明显阈值（如 SMrz 低于某值后恢复显著变慢）？

---

## 8. SEM 分析规划

SEM 不替代 SHAP，而是将 SHAP 识别的关键变量组织成机制路径。

### 路径框架（初始）

```
水分供给（SMrz/SMs/TP）
    → 植被结构（LAI）        → 恢复时间
    → 直接效应              → 恢复时间

能量压力（T2m/ssrd）
    → 土壤热环境（Tsoil）   → 恢复时间
    → 直接效应              → 恢复时间

干旱烈度（intensity/onset_rate/change_to_peak）
    → 直接效应              → 恢复时间

水分供给 <-> 能量压力（协方差）
```

### 执行顺序

1. GPP code1 试跑（模板验证）
2. 根据 SHAP 结果删减变量，固化路径
3. 扩展到 NEE、RECO
4. 多组 SEM（按 flash/slow、SMrz/SMs）

---

## 9. 执行顺序

| 阶段 | 内容 |
|------|------|
| 阶段 0 | 文件核查：12 个目标文件字段一致性、事件数、缺测率 |
| 阶段 1 | 数据治理：读取 12 个文件，提取主键与恢复字段，建立事件索引 |
| 阶段 2 | 干旱事件配表：匹配 GLEAM 事件形态特征（onset_rate、intensity 等）|
| 阶段 3 | ERA5+GLEAM-SM 配表：按三类时间窗口提取特征，输出两套特征表 |
| 阶段 4 | 探索性统计：缺失率、分布、共线性检查 |
| 阶段 5 | SHAP：GPP code1 → 各通量 → 综合层 |
| 阶段 6 | SEM：GPP code1 试跑 → 固化路径 → 扩展 |

---

## 10. 文件存放规范

```
/home/xulc/flash_drought/process/SEM_analysis/claude_code/
    gleam/                          ← 本阶段所有代码与结果
        gleam_shap_sem_plan_v2_20260331.md   ← 本规划文档
        01_data_check.py            ← 阶段 0 核查脚本
        02_event_master_table.py    ← 阶段 1-2 数据治理
        03_feature_extraction.py    ← 阶段 3 ERA5+GLEAM 配表
        04_eda.py                   ← 阶段 4 探索性统计
        05_shap_model.py            ← 阶段 5 SHAP
        06_sem_model.py             ← 阶段 6 SEM
        results/
            event_tables/           ← 事件主表 (.parquet)
            feature_tables/         ← 特征表 (.parquet)
            shap/                   ← SHAP 图与结果
            sem/                    ← SEM 路径图与系数表
    era5/                           ← ERA5 版本（后续扩展）
```

---

## 11. 关键技术说明

### 为什么先 SHAP 后 SEM
候选因子多、共线性强，直接上 SEM 路径不稳定。先用 SHAP 做变量筛选与优先级排序，再构建 SEM。

### 为什么 W2 用均值不用总量
W2 窗口长度等于 `t_peak_abs`，事件间差异大。若用总量，长事件自然得到更大的累积值，会混淆"窗口长度"与"环境强度"两个信息。

### 为什么 W3 固定30天而非到恢复结束
若 W3 随恢复时间延伸（peak ~ recovery），则恢复越慢的事件 W3 窗口越长，窗口内均值会被目标变量反向影响，造成信息泄漏。固定30天切断这一循环。

### 土壤湿度选择原则
事件识别用 GLEAM-SM → 事件形态特征用 GLEAM 事件文件 → SM 驱动因子也用 GLEAM-SM，保持数据源一致性。ERA5 负责气象变量（降水、气温、辐射等）。
> Wetland（1,686 像素）样本量较少，建模时与全局模型合并，不单独做分类型模型。

### 12.4 两级建模策略

#### 第一级：全局模型（主 SHAP）

- 纳入全部有效植被格点（排除 0/13/15/16）
- `vegetation_func_class`（1-5）作为分类特征纳入 SHAP 模型
- 目的：评估植被类型本身的贡献度排名，作为是否需要分类型建模的依据
- 若 `vegetation_func_class` SHAP 重要性排名靠前，证实分类型建模必要性

#### 第二级：分功能类模型（机制 SEM）

对样本量充足的功能类单独建模（建议阈值 > 10,000 事件）：

| 功能类 | 预期事件量 | 是否单独建模 |
|--------|-----------|-------------|
| Savanna_Grassland | 最多 | 是 |
| Forest | 多 | 是 |
| Shrubland | 中 | 是 |
| Cropland | 中 | 是 |
| Wetland | 少 | 仅纳入全局模型 |

SEM 在每个功能类内部独立跑，路径系数跨类型对比是核心科学发现。

### 12.5 配表方法

将 `functional_class_025deg.tif` 的值按事件的 `lat/lon` 最近邻匹配到每个事件：

```python
# 0.25度网格索引
row = int((90 - lat) / 0.25)
col = int((lon + 180) / 0.25)
func_class = func_arr[row, col]
# func_class == 0 的事件排除出分析
```

---

---

## 执行记录

### 2026-03-31 阶段 0-2 完成

**01_data_check.py** ✅
- 12 个目标文件全部存在，关键字段齐全
- 主分析样本量：1,377,951（GPP code1）~ 3,421,335（NEE code2）

**02_event_master_table.py** ✅
- 合并 12 个 GLEAM 目标文件
- 匹配 GLEAM 干旱事件形态特征（onset_rate, intensity 等）
- 匹配功能类土地覆盖
- 输出：gleam_event_master_table.parquet（795 MB）

**最终统计：**
- 总事件数：24,399,181
- 已恢复事件：15,371,921
- 干旱形态匹配率：100%
- 功能类分布：Savanna_Grassland (53%), Forest (21%), Cropland (13%), Shrubland (12%), Wetland (0.7%)

**03_feature_extraction.py** 🔄 运行中
- 预计运行时间：数小时
