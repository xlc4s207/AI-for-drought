# 骤旱对 GPP 影响的因果分析方案

## 1. 研究目标

基于 1982-2022 年的日尺度数据，量化骤旱（Flash Drought）对植被总初级生产力（GPP）的影响：

### 1.1 核心输出指标

| 类别 | 指标 | 说明 |
|------|------|------|
| **响应** | 因果方向 | SM→GPP 因果关系强度 |
| | 响应时间 (t_min) | GPP最大下降出现的天数 |
| **抵抗力** | 变化速率 (decline_rate) | 从事件开始到最低点的下降速度 (σ/day) |
| | 变化幅度 (amp_max) | 最大下降幅度 (σ) |
| | 累计损失 (impact_area) | 累计负异常面积 |
| **恢复力** | 恢复时间 (t_recover) | 从最低点恢复到阈值的天数 |
| | 恢复速率 (recovery_rate) | 恢复过程的速度 (σ/day) |

### 1.2 数据输出格式

**每像元输出** (NetCDF格式，支持GIS可视化):
- `pixel_metrics.nc`: 每个有效像元的聚合指标
  - 维度: (lat, lon)
  - 变量: t_min_mean, amp_max_mean, t_recover_mean, decline_rate_mean, ...

**每事件输出** (Parquet格式，支持统计分析):
- `event_metrics.parquet`: 每个骤旱事件的详细指标
  - 字段: lat, lon, event_id, onset_year, t_min, amp_max, t_recover, ...

---

## 2. 数据源

| 数据集 | 路径 | 时间范围 | 空间分辨率 |
|--------|------|----------|------------|
| 骤旱事件 | `gleam/clip_result/SMrz/flash_drought_events_details_v2.nc` | 1980-2024 | 0.1° |
| 土壤湿度 | `gleam/SMrz_dd/` | 1980-2024 | 0.1° |
| GPP | `/data/BESS_V2/GPP_Daily/yearly0.1/` | 1982-2022 | 0.1° |
| 土地利用 | `land_use/MCD12C1_LC_Type1_2010_11km.tif` | 2010 | 0.1° |

**有效像元**: 1,169,891 个 (event_count > 0)

---

## 4. 脚本规划

### 4.1 脚本清单

| 脚本编号 | 脚本名称 | 功能 | 输入 | 输出 |
|----------|----------|------|------|------|
| **01** | `prepare_data.py` | 数据预处理与时间对齐 | 原始 NC 文件 | 统一格式的时序数据 |
| **02** | `calc_climatology.py` | 计算气候态和异常值 | 时序数据 | GPP_anom, SM_anom |
| **03** | `extract_valid_pixels.py` | 提取有效像元坐标 | 骤旱事件文件 | 有效像元列表 |
| **04** | `lagged_ccm_analysis.py` | Lagged CCM 因果分析 | anomaly 数据 | lag*, ρ_max, p值 |
| **05** | `event_extraction.py` | 事件窗口提取 | 事件列表 + GPP_anom | 事件响应曲线 |
| **06** | `event_metrics.py` | 事件响应指标计算 | 事件窗口 | t_onset, t_min, amp_min 等 |
| **07** | `aggregate_results.py` | 结果汇总与统计 | 各像元结果 | 全局统计表 |
| **08** | `visualization.py` | 可视化和图表生成 | 分析结果 | 图表文件 |

---

### 4.2 各脚本详细说明

#### 脚本 01: `prepare_data.py`
**功能**：
- 读取 GPP 和 SM 的年度 NC 文件
- 统一时间轴（处理闰年）
- 合并为连续时间序列
- 保存为优化格式（如 zarr 或分块 NC）

**关键参数**：
- `start_year = 1982`
- `end_year = 2022`

**输出**：
- `prepared_data/gpp_daily_1982_2022.nc` (time, lat, lon)
- `prepared_data/sm_daily_1982_2022.nc` (time, lat, lon)

---

#### 脚本 02: `calc_climatology.py`
**功能**：
- 计算每个 DOY 的气候态均值和标准差
- 计算异常值: `anom(t) = value(t) - clim(doy(t))`
- 可选：标准化异常 `z(t) = anom(t) / std(doy(t))`

**输出**：
- `climatology/gpp_clim_mean.nc` (doy, lat, lon)
- `climatology/gpp_clim_std.nc` (doy, lat, lon)
- `anomaly/gpp_anom_1982_2022.nc` (time, lat, lon)
- `anomaly/sm_anom_1982_2022.nc` (time, lat, lon)

---

#### 脚本 03: `extract_valid_pixels.py`
**功能**：
- 从骤旱事件文件提取 `event_count > 0` 的像元
- 生成有效像元坐标列表
- 可选：按区域/纬度带分组

**输出**：
- `valid_pixels.csv` (lat_idx, lon_idx, lat, lon, event_count)
- `valid_pixels_by_region.csv` (带区域标签)

---

#### 脚本 04: `lagged_ccm_analysis.py`
**功能**：
- 对每个有效像元执行 Lagged CCM 分析
- 扫描 lag 范围（0-120天）
- 使用 bootstrap 估计置信区间
- 使用 surrogate 检验显著性

**关键参数**：
```python
E = 3-5          # 嵌入维度（建议先调参确定）
tau = 1-7        # 延迟（使用自相关/互信息确定）
lags = range(0, 121, 2)  # lag 扫描范围和步长
n_boot = 100     # bootstrap 次数
n_surr = 100     # surrogate 次数
```

**输出**：
- `ccm_results/ccm_pixel_results.parquet`
  - 字段: lat_idx, lon_idx, lag_star, rho_max, p_value, direction_ratio
- `ccm_results/lag_skill_curves.nc` (可选，用于诊断)

---

#### 脚本 05: `event_extraction.py`
**功能**：
- 从骤旱事件文件解析每个事件的 t0（onset_start_year + onset_start_doy）
- 提取每个事件的 GPP_anom 时间窗口 [-B, +A]

**关键参数**：
```python
B = 60   # 事件前天数
A = 180  # 事件后天数
min_event_gap = 30  # 最小事件间隔（可选，用于去除重叠）
```

**输出**：
- `event_windows/event_{lat}_{lon}.npz` (per pixel)
  - 包含：event_id, t0, window_data[-B:A]

---

#### 脚本 06: `event_metrics.py`
**功能**：
- 计算每个事件的响应指标：
  - `t_onset`: 首次显著下降时间
  - `t_min`: 最大下降时间
  - `t_recover`: 恢复时间
  - `amp_min`: 最大下降幅度
  - `amp_mean`: 平均下降幅度
  - `impact_area`: 累计负异常面积

**关键参数**：
```python
theta_onset = -0.5  # 下降阈值（σ单位）
theta_recover = -0.25  # 恢复阈值
```

**输出**：
- `event_metrics/event_metrics_all.parquet`
  - 字段: lat_idx, lon_idx, event_id, t0_year, t0_doy, duration, severity, t_onset, t_min, t_recover, amp_min, amp_mean, impact_area

---

#### 脚本 07: `aggregate_results.py`
**功能**：
- 汇总 CCM 结果和事件指标
- 按区域/纬度带/植被类型分组统计
- 生成汇总表格

**输出**：
- `summary/ccm_summary_by_region.csv`
- `summary/event_metrics_summary.csv`
- `summary/lag_distribution.csv`

---

#### 脚本 08: `visualization.py`
**功能**：
- 生成分析图表

**输出图表**：
1. `fig_lag_star_map.png` - lag* 空间分布图
2. `fig_rho_max_map.png` - CCM 技能分布图
3. `fig_lag_skill_curve.png` - 代表像元的 lag-skill 曲线
4. `fig_event_composite.png` - 事件复合响应曲线
5. `fig_response_by_severity.png` - 按烈度分组的响应箱线图
6. `fig_t_min_vs_lag_star.png` - t_min 与 lag* 对比图
7. `fig_impact_by_season.png` - 按季节分组的影响分析

---

## 5. 执行策略

### 5.1 分阶段执行

| 阶段 | 脚本 | 预计耗时 | 并行策略 |
|------|------|----------|----------|
| **Phase 1: 数据准备** | 01, 02, 03 | 2-4 小时 | 年份并行 |
| **Phase 2: CCM 分析** | 04 | 12-48 小时 | 像元分块并行（50核） |
| **Phase 3: 事件分析** | 05, 06 | 4-8 小时 | 像元分块并行（50核） |
| **Phase 4: 汇总可视化** | 07, 08 | 1-2 小时 | 单进程 |

### 5.2 计算资源建议

- **内存**：建议 64GB+（可分块处理降低需求）
- **CPU**：使用 50 核并行
- **存储**：预计中间结果约 50-100GB

### 5.3 调试策略

1. **先小区域测试**：选择一个 10°×10° 区域（如美国西部）
2. **验证方法**：在测试区域验证 CCM 收敛性和事件提取正确性
3. **再全域执行**：确认无误后扩展到全球

---

## 6. 预期输出

### 6.1 数据产品

| 文件 | 描述 | 格式 |
|------|------|------|
| `ccm_pixel_results.parquet` | 每像元 CCM 结果 | Parquet |
| `event_metrics_all.parquet` | 所有事件响应指标 | Parquet |
| `lag_star_map.nc` | lag* 空间分布 | NetCDF |
| `impact_severity_relation.csv` | 烈度-影响关系 | CSV |

### 6.2 图表产品

| 图表 | 用途 | 格式 |
|------|------|------|
| lag* 空间分布图 | 展示响应滞后的空间异质性 | PNG/PDF |
| 事件复合曲线 | 展示平均响应形态 | PNG/PDF |
| 烈度-响应关系图 | 展示骤旱强度与 GPP 损失的关系 | PNG/PDF |
| 季节调制图 | 展示响应的季节差异 | PNG/PDF |

---

## 7. 后续分析建议

1. **区域差异分析**：按气候区/植被类型分层分析
2. **极端事件案例**：选取典型极端骤旱事件进行详细分析
3. **长期趋势**：分析 lag* 和响应幅度的年际变化趋势
4. **与其他因子交互**：结合 VPD、温度等因子分析调制效应

---

## 8. 注意事项

> [!IMPORTANT]
> 1. **必须使用异常值**：直接使用原始 GPP/SM 会导致假的因果关系（季节同步）
> 2. **显著性检验**：CCM 必须配合 surrogate 检验，否则结果不可靠
> 3. **多重比较校正**：lag 扫描产生多个假设检验，需 FDR 控制

> [!WARNING]
> - CCM 对插值敏感，尽量不插值或仅对短缺失插值
> - 注意 GPP 数据在冬季高纬度可能有大量缺失

> [!TIP]
> - 先在代表性区域（如 Amazon、Sahel、US Great Plains）调参
> - 使用 `dask` 或 `joblib` 进行大规模并行计算
