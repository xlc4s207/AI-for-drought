# Lagged CCM 用于骤旱（Flash Drought）对 GPP 影响：可实现性分析与脚本规划

## 0. 目标
给定 1982–2022 日尺度：
- GPP(t)
- GLEAM Soil Moisture, SM(t)
- 从 SM(t) 识别的骤旱事件清单：每个事件包含爆发时间 t0、持续时间 D、烈度 S（以及其他指标）

完成两类分析：
1) 因果与滞后：检验 “SM/骤旱 → GPP” 是否存在因果证据，并估计响应滞后（天）
2) 事件响应特征：定量每次骤旱发生后 GPP 的响应时间与变化幅度（下降幅值、累计损失、恢复时间）

输出：
- 每个像元/站点/区域的：最可能滞后 lag*、显著性、事件响应统计
- 图：lag-skill 曲线、事件复合曲线、响应时间/幅度空间分布或分组箱线图


---

## 1. 方法总览（建议双轨：Lagged CCM + 事件对齐）
### 1.1 Lagged CCM（用于“方向性 + 最可能滞后”）
核心问题：若 SM 驱动 GPP，则用 GPP 的相空间重构可反推（cross-map）SM，并且映射技能随 library length 增加而收敛；扫描滞后 lag 可定位最强的因果时延。

主要输出：
- Cross-map skill ρ(L, lag) 的收敛曲线
- 固定足够大 L 下，ρ(lag) 的峰值位置 lag*（以及显著性）

### 1.2 事件对齐分析（用于“响应时间 + 幅度”）
以骤旱爆发日 t0 为 Day 0，提取事件窗口 [-B, +A] 天内的 GPP 异常曲线，计算：
- 响应起始时间：t_onset（首次显著偏离基线）
- 最强响应时间：t_min（最小异常发生日）
- 幅度：min(GPP_anom)、累计负异常面积、恢复时间等

将结果按烈度 S、持续时间 D、季节、植被类型等分组比较。


---

## 2. 数据准备与统一（脚本第一部分）
### 2.1 统一时间轴与单位
- 将所有数据对齐到同一日历（日尺度，UTC 或本地一致）
- 处理闰年（可选择保留 366 天并对气候态单独计算，或用 DOY 方式处理）

### 2.2 质量控制（QC）
对每个像元/站点：
- 缺测比例阈值（例如 >20% 缺测则剔除或仅做部分分析）
- 可选：对短缺测做插值（线性/样条），但 CCM 对插值敏感，建议尽量少插值；事件分析可以更灵活

### 2.3 去趋势与异常（强烈建议）
为减少长期趋势/CO2 施肥等影响：
- 计算 GPP 气候态：clim(doy) = mean(GPP on doy across years)
- 计算异常：GPP_anom(t) = GPP(t) - clim(doy(t))
- 可选标准化：GPP_z(t) = (GPP(t) - clim(doy))/sd(doy)

对 SM 也可做类似异常或标准化，以便不同区域可比。


---

## 3. Lagged CCM 设计（脚本第二部分）
### 3.1 分析对象的时间序列定义（两种选择）
选择 A（推荐，物理更连续）：
- X(t) = SM_anom(t) 或 SM_z(t)
- Y(t) = GPP_anom(t) 或 GPP_z(t)

选择 B（事件强度序列，适合“骤旱过程”但更离散）：
- 构造 FD_intensity(t)：若 t 在骤旱事件中，则取强度/烈度轨迹，否则为 0
- 用 X(t) = FD_intensity(t)，Y(t) = GPP_anom(t)
注意：离散/稀疏序列会降低 CCM 稳定性，优先用选择 A，再用事件分析量化幅度。

### 3.2 相空间重构参数
需要确定：
- E：嵌入维数（候选 2–10）
- τ：延迟（候选 1–30 天，或基于自相关/互信息）
建议策略：
1) 用简单准则选 τ（例如自相关首次过零/到 1/e，或平均互信息最小）
2) 对 E 做网格搜索：在一段训练数据上最大化简单 one-step 预测能力，或直接在 CCM 框架中选择使收敛最清晰的 E

### 3.3 Lag 扫描范围
根据生态响应常识与日尺度数据：
- lag 扫描：0–120 天（或 0–180 天）
- 步长：1 天（或 2–3 天以提速）
明确 lag 符号约定（必须统一）：
- 约定：检验 “SM leads GPP by lag days”
- 实现方式：比较 ρ( SM(t - lag) | M_GPP(t) ) 或等价定义
脚本中写清楚，并在输出图标题注明 “positive lag means SM earlier than GPP”。

### 3.4 Library length 与收敛检验
- 设置一组 library sizes：L = [500, 1000, 2000, ..., N_available]
- 对每个 L 重复抽样（bootstrap）K 次（例如 K=50–200）估计均值与置信区间
- 关键证据：ρ 随 L 增大上升并趋于稳定（converges）

### 3.5 显著性检验（必须做）
至少做一种 surrogate：
- 相位随机（phase randomization）或 AAFT surrogate：保持自相关结构但破坏耦合
- 或循环置换（circular shift）X 相对 Y 的相位
对每个 lag 比较：
- ρ_obs(lag) vs ρ_surr(lag) 分布，给出 p 值
并控制多重比较（lag 扫描很多）：可用 FDR。

### 3.6 结果提取
对每个像元/站点输出：
- lag*：在显著 lag 中使 ρ 最大的 lag
- ρ_max：对应技能
- p_min 或 q 值
- 方向对比：ρ_SM→GPP(lag*) vs ρ_GPP→SM(lag*)

保存为表格（csv/parquet），并保存 lag-skill 曲线（可选 NetCDF 或 npy）。


---

## 4. 事件对齐响应分析（脚本第三部分：回答“响应时间 + 幅度”）
### 4.1 事件窗口提取
对每个骤旱事件 i：
- 爆发日 t0_i
- 窗口：[-B, +A]，例如 B=60 天，A=180 天
提取：
- g_i(k) = GPP_anom(t0_i + k)

若事件之间窗口重叠：
- 可保留，但在统计时对事件加权或做去相关处理
- 或仅保留不重叠事件（看研究设计）

### 4.2 基线定义（重要）
基线有两种常用方式（建议都实现，做敏感性分析）：
- 基线1：事件前 [-B, -1] 的均值/中位数
- 基线2：长期气候态异常（GPP_anom 已经相对 climatology）

### 4.3 响应时间指标
对每个事件 i 计算：
- t_onset：从 k=0 开始，首次满足 g_i(k) < -θ 的最小 k
  - θ 可取 0、-0.5σ、-1σ 或基于 surrogate 的显著阈值
- t_min：使 g_i(k) 最小的 k（k ∈ [0, A]）
- t_recover：首次满足 g_i(k) > -θ_recover 的 k（例如回到 0 或 -0.25σ）

### 4.4 幅度指标
对每个事件 i 计算：
- amp_min = min_{k∈[0,A]} g_i(k)
- amp_mean = mean_{k∈[0,A']} g_i(k)（A' 可取事件持续期或固定 30/60 天）
- impact_area = sum_{k=0..A} min(0, g_i(k))   （累计负异常面积）
- 可选：分段（爆发期/扩展期/恢复期）分别计算面积

### 4.5 分组与统计
按以下变量分组比较：
- 烈度 S：分位数分组（Q1–Q4）或阈值分组
- 持续时间 D：短/中/长
- 季节：t0 的月份/季节
- 植被类型、气候区（若有外部掩膜）
输出：
- 分组箱线图：t_onset、t_min、amp_min、impact_area
- 回归/模型：指标 ~ S + D + season + (random effects)

---

## 5. 将 Lagged CCM 与事件分析联动（建议的“主结论链”）
建议形成如下逻辑链（论文/报告结构清晰）：
1) Lagged CCM 显示 SM→GPP 的因果证据，并给出最可能滞后 lag*（空间/分组分布）
2) 事件对齐分析显示：在 Day 0 后约 lag* 天附近，GPP 异常达到最强下降（t_min 与 lag* 对齐）
3) 幅度指标随烈度 S 增强而增大（amp_min 更负、impact_area 更大），并讨论调制因子（季节/植被类型）

---

## 6. 脚本模块化设计（给 AI 生成代码的“接口说明”）
建议 Python（xarray/pandas/numpy/scipy）或 R（rEDM）实现。

### 6.1 输入约定
- gpp: DataArray(time, y, x) 或 (time, site)
- sm:  DataArray(time, y, x) 或 (time, site)
- events: DataFrame，至少包含：
  - id, y, x(or site), t0, duration, severity
  - 可选：t_end, intensity_series_id

### 6.2 函数清单（AI 写脚本时按这个实现）
1) `prepare_daily_timeseries(gpp, sm) -> aligned_gpp, aligned_sm`
2) `calc_climatology(ts, doy) -> clim_mean, clim_std`
3) `calc_anomaly(ts, clim_mean, clim_std=None) -> anom, z`
4) `select_embedding_params(ts) -> E, tau`  （可网格搜索）
5) `lagged_ccm(x, y, E, tau, lags, library_sizes, n_boot, surrogate='aaft') -> results`
   - 返回：rho_obs[L,lag], rho_surr[L,lag], pvals[lag], lag_star
6) `extract_event_windows(ts_anom, events, B, A) -> dict(event_id -> array[k])`
7) `compute_event_metrics(windows, theta, A) -> metrics_df`
8) `group_stats(metrics_df, by=['severity_bin','season']) -> summary_df`
9) `plot_lag_skill(results)` / `plot_composites(windows)` / `plot_maps(lag_star, amp_min)`（可选）

### 6.3 输出文件
- `ccm_results_{region_or_tile}.parquet`
- `event_metrics.parquet`
- `fig_lag_skill.png`, `fig_composite.png`, `fig_response_maps.png`

---

## 7. 注意事项与常见坑（必须在脚本里处理）
1) 强季节性：必须做 anomaly，否则 CCM 可能只是“共同季节循环”
2) 缺测与插值：CCM 对插值敏感，尽量减少；必要时只对短缺测插值并记录比例
3) 自相关与显著性：必须用 surrogate，否则容易把共同驱动/自相关当因果
4) 反馈：可能存在 SM→GPP 与 GPP→SM 双向，需同时做两方向比较
5) 多重比较：lag 扫描很多，p 值需要 FDR 控制
6) 计算量：全空间逐像元很重，建议：
   - 分区块并行（dask/joblib）
   - 先在代表性区域/站点调参，再批量跑


---

## 8. 最小可运行流程（MVP）
1) 选一个区域/站点：
   - 计算 GPP_anom、SM_anom
2) 选 E、τ
3) 跑 Lagged CCM：lags=0..120，library_sizes=递增，bootstrap=100，surrogate=AAFT
4) 用事件清单提窗口，算 t_min 与 amp_min
5) 检查：t_min 是否集中在 lag* 附近；烈度是否调制 amp_min

完成后再扩展到全区域批处理。
