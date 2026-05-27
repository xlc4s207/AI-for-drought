# CCM 分析脚本说明文档

## 概述

本脚本使用 **Lagged CCM (Convergent Cross Mapping)** 方法分析表层土壤湿度 (SMs) 骤旱事件对 GPP 的因果滞后效应。

## 核心原理

CCM 的核心思想：如果 X 驱动 Y，则 Y 的相空间重构可以"反推"(cross-map) X 的状态。通过扫描不同的时间滞后 (lag)，找到使这种反推能力最强的 lag*，即为因果响应时间。

## 输入数据

| 数据 | 路径 | 说明 |
|------|------|------|
| 骤旱事件 | `gleam/result/SMs_result/flash_drought_SMs_events_details_v2.nc` | 15.3M 事件 |
| GPP | `/data/BESS_V2/BESS_GPP_1982_2022.nc` | 1982-2022 日尺度 |
| SMs | `/data/GLEAM/SMs_45years.nc` | 1980-2024 日尺度 |

## CCM 参数

| 参数 | 值 | 说明 |
|------|-----|------|
| E | 3 | 嵌入维数 |
| τ | 7 | 时间延迟 (天) |
| Lag范围 | [-30, 90] | 扫描范围 (天) |
| Lag步长 | 5 | 减少计算量 |

## 输出

**文件**: `results/ccm_lag_results_global.nc`

| 变量 | 说明 |
|------|------|
| `lat`, `lon` | 像元坐标 |
| `lag_star` | **最优滞后时间** (天)，正值表示 SMs 领先 GPP |
| `rho_max` | 最大相关系数 |
| `rho_zero` | lag=0 时的相关系数 |
| `valid` | 数据是否有效 |

## 运行方式

```bash
cd /home/xulc/flash_drought/process/GPP-draught-analysis/CCM_code
nohup micromamba run -n Flash_dra python -u run_ccm_analysis_global.py > ccm_run.log 2>&1 &
```

## 内存优化策略

1. **分块并行**: 每次处理 20 行纬度数据
2. **增量写入**: 每个 chunk 立即保存为临时 `.npy` 文件
3. **Worker 独立文件句柄**: 避免多进程 I/O 冲突

## 注意事项

- 当前使用**简化版 CCM** (延迟嵌入相关)，比完整 CCM (manifold reconstruction) 快但精度略低
- 如需完整 CCM，可修改 `process_pixel_ccm()` 使用 `causal-ccm` 库
- 预计运行时间: 2-4 小时 (取决于 CPU)
