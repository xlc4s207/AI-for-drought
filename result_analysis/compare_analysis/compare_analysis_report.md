# 12个 v11_with_abs 文件对比分析报告

## 1. 数据范围
- 文件数量：12
- 组合结构：GPP / NEE / RECO × flash / nonflash × SMrz / SMs
- 最大事件数：GPP_nonflash_SMs = 34,224,593
- 最小事件数：NEE_flash_SMs = 16,195,963
- 数值字段统计默认采用事件维前 200,000 个等步长样本或全量数组。

## 2. 字段结构
- 全部 12 文件共同字段数：10
- 全体共同字段：amp_max, event_id, lat, lon, recovery_rate, response_detected, t_impact, t_min, t_recover, t_response
- flash 共同字段：amp_max, event_id, lat, lon, recovery_rate, response_detected, t_impact, t_min, t_recover, t_response, onset_doy, onset_year
- nonflash 共同字段：amp_max, event_id, lat, lon, recovery_rate, response_detected, t_impact, t_min, t_recover, t_response, actual_window_after, drought_duration, drought_end_doy, drought_end_year, drought_start_doy, drought_start_year
- GPP 的 with_abs 字段：gpp_baseline_abs, gpp_change_to_peak_abs, gpp_drop_abs, gpp_max_abs, gpp_mean_abs, gpp_min_abs, gpp_recovery_rate_abs, gpp_rise_abs, gpp_trend_abs
- NEE 的 with_abs 字段：nee_baseline_abs, nee_change_to_peak_abs, nee_drop_abs, nee_max_abs, nee_mean_abs, nee_min_abs, nee_recovery_rate_abs, nee_rise_abs, nee_trend_abs
- RECO 的 with_abs 字段：reco_baseline_abs, reco_change_to_peak_abs, reco_drop_abs, reco_max_abs, reco_mean_abs, reco_min_abs, reco_recovery_rate_abs, reco_rise_abs, reco_trend_abs

## 3. 核心对比
### 3.1 响应检测率
- GPP (SMrz): flash=0.632, nonflash=0.804, delta=+0.172
- GPP (SMs): flash=0.630, nonflash=0.822, delta=+0.192
- NEE (SMrz): flash=0.660, nonflash=0.837, delta=+0.177
- NEE (SMs): flash=0.660, nonflash=0.841, delta=+0.181
- RECO (SMrz): flash=0.686, nonflash=0.902, delta=+0.215
- RECO (SMs): flash=0.700, nonflash=0.903, delta=+0.203

### 3.2 核心指标差异较大的组合
- flash_vs_nonflash | GPP | baseline_abs (gpp_baseline_abs vs gpp_baseline_abs) | GPP_flash_SMrz=281.355, GPP_nonflash_SMrz=170.032, delta=-111.323
- flash_vs_nonflash | GPP | drop_abs (gpp_drop_abs vs gpp_drop_abs) | GPP_flash_SMrz=238.652, GPP_nonflash_SMrz=157.348, delta=-81.304
- flash_vs_nonflash | GPP | baseline_abs (gpp_baseline_abs vs gpp_baseline_abs) | GPP_flash_SMs=248.913, GPP_nonflash_SMs=173.973, delta=-74.940
- flash_vs_nonflash | RECO | baseline_abs (reco_baseline_abs vs reco_baseline_abs) | RECO_flash_SMrz=270.807, RECO_nonflash_SMrz=199.078, delta=-71.729
- flash_vs_nonflash | GPP | change_to_peak_abs (gpp_change_to_peak_abs vs gpp_change_to_peak_abs) | GPP_flash_SMrz=-93.980, GPP_nonflash_SMrz=-32.320, delta=+61.660
- flash_vs_nonflash | GPP | drop_abs (gpp_drop_abs vs gpp_drop_abs) | GPP_flash_SMs=217.545, GPP_nonflash_SMs=161.522, delta=-56.024
- flash_vs_nonflash | GPP | change_to_peak_abs (gpp_change_to_peak_abs vs gpp_change_to_peak_abs) | GPP_flash_SMs=-92.293, GPP_nonflash_SMs=-37.748, delta=+54.544
- flash_vs_nonflash | NEE | drop_abs (nee_drop_abs vs nee_drop_abs) | NEE_flash_SMs=172.730, NEE_nonflash_SMs=219.546, delta=+46.816
- flash_vs_nonflash | RECO | baseline_abs (reco_baseline_abs vs reco_baseline_abs) | RECO_flash_SMs=245.145, RECO_nonflash_SMs=198.624, delta=-46.522
- flash_vs_nonflash | RECO | drop_abs (reco_drop_abs vs reco_drop_abs) | RECO_flash_SMrz=174.712, RECO_nonflash_SMrz=128.359, delta=-46.353
- flash_vs_nonflash | RECO | change_to_peak_abs (reco_change_to_peak_abs vs reco_change_to_peak_abs) | RECO_flash_SMrz=-72.404, RECO_nonflash_SMrz=-32.548, delta=+39.856
- flash_vs_nonflash | RECO | change_to_peak_abs (reco_change_to_peak_abs vs reco_change_to_peak_abs) | RECO_flash_SMs=-69.395, RECO_nonflash_SMs=-36.382, delta=+33.012

## 4. 文献结合解释
- 深度研究报告_骤旱与非骤旱对碳通量影响差异.md (2026 note): GPP 对骤旱通常比对非骤旱更快、更敏感，且其变化经常主导后续 NEE 的变化。 用于解释 flash 与 nonflash 间的 value_drop_abs、t_response、recovery 相关差异。
- Jiao et al. 2022 (2022): 滞后干旱影响比同步影响更显著地影响生态系统碳吸收，生态系统生产对干旱时间尺度更敏感，呼吸相对较弱。 用于解释 value_change_to_peak_abs、t_recover_to_baseline 与 legacy_duration 的重要性。
- Zhang et al. 2021 (2021): 森林和半干旱/半湿润生态系统恢复时间更长，存在长期不完全恢复风险。 用于解释 t_recover、t_recover_to_baseline 与 recovery_rate_to_baseline 的空间平均差异。
- Higher sensitivity of gross primary production than ecosystem respiration... (2023): GPP 对干旱与增温的敏感性高于 RECO，NEE 变化通常更多由 GPP 侧驱动。 用于解释三类碳通量中 GPP/NEE/RECO 对绝对值指标的对比格局。
- Zhao et al. 2025 (2025): 显著的 GPP 损失会发生在干旱结束后，恢复阶段是总干旱损失的重要组成部分。 用于解释 value_change_to_peak_abs、legacy_integral 和恢复相关指标的意义。
- 补充分析_NEE响应机制与碳汇源动态.md (2026 note): NEE 在强干旱下可从碳汇转为碳源，且短期水分变化对其影响往往强于长期缓变胁迫。 用于解释 NEE 的 cross_zero_after_onset、source_days 和 source_integral。

## 5. 产出文件
- `file_inventory.csv`：文件级清单
- `field_presence_matrix.csv`：字段存在矩阵
- `variable_summary.csv`：字段级统计摘要
- `core_metric_comparison.csv`：核心指标摘要
- `paired_metric_deltas.csv`：flash/nonflash 与 SMrz/SMs 的均值差
- `literature_evidence_table.csv`：文献证据表
- `figures/*.png`：事件数、响应率、字段覆盖与核心指标热图

## 6. 解释边界
- 本报告的字段统计重点是跨文件可比性与数量级差异，不替代逐区域、逐生物群系的精细空间分析。
- 连续型变量采用样本统计以控制运行成本；事件数和字段结构来自文件全量元数据。
