# GPP 前置预测口径与过程解释口径对比分析

GPP 的 `prepeak` 与 `recoverywin` 对比，本质上是在比较“峰值前恢复记忆”与“恢复期即时环境控制”两种解释框架。前者对应 `prepeak_event_shap_sem_20260420` 与 `sem_prepeak_event_mechanism_20260420`，后者对应 `shap_process_recoverywin_precipEmean_sample50k_by_biome` 与 `sem_process_recoverywin_precipEmean_usertrim`，而双口径图件则集中存放在 `gpp_code1_flash_smrz_compare_prepeak_vs_recoverywin_20260420`。

| 指标 | `prepeak` | `recoverywin` |
|---|---:|---:|
| SHAP 平均 holdout R2 | 0.423 | 0.619 |
| SEM 平均 holdout R2 | 0.220 | 0.156 |
| 最稳定 SHAP 主导变量 | SSRD, EVA, STRD | PRE, TMP/STRD, VPD |
| 最适合承担的叙事 | 前置预测与恢复记忆 | 恢复期近端控速 |

这一对比表明，GPP 的 `recoverywin` 在树模型层面更强，因为恢复期环境更接近目标变量；但 `prepeak` 在 SEM 上反而更稳，说明峰值前水热背景更容易形成清晰的机制结构。因此，GPP 的双口径结果不应写成“谁替代谁”，而应写成“一个提供更早的机制记忆，一个提供更强的近端解释”。

Forest 的变化最典型。`prepeak` 主要由 `EVA-SSRD-STRD-VPD` 主导，而 `recoverywin` 转向 `EVA-STRD-PRE-SSRD-VPD`，同时 SHAP holdout R2 从 `0.434` 升至 `0.604`。这说明森林在峰值前已积累了明显的能量与蒸散记忆，但真正进入恢复期之后，持续补水和热湿背景对 GPP 恢复时间的即时控制更强。Grassland 与 Savanna 的转向则更突出：前者从 `SSRD-TMP-PRE` 转向 `TMP-PRE-SSRD`，后者从 `SSRD-EVA-STRD-PRE` 转向 `PRE-STRD-SSRD-EVA`，都说明恢复期补水开始压过峰值前辐射背景。

Cropland 与 Shrubland 的差异说明 biome 背景仍然重要。Cropland 的 `prepeak` 与 `recoverywin` 在 SHAP 上都保留了强烈的水热混合结构，但过程解释型中 `PRE` 与 `VPD` 的权重明显上升，说明农田恢复更强地受恢复窗内的补水和大气需求限制。Shrubland 则在两套口径下都表现出较强的 `PRE` 效应，但在 `recoverywin` 中 `TMP` 与 `VPD` 的地位更高，说明干旱区一旦进入恢复窗，即时热量与大气干旱会比峰值前背景更直接地影响恢复速度。

综合来看，GPP 的双口径对比支持一个明确分层框架：`prepeak` 适合写成“恢复难度已经在峰值前被部分写入”，`recoverywin` 适合写成“恢复速度最终由恢复期补水、温度和热湿背景直接控制”。从写作策略上，前者更适合 Results 里突出“可预报性”，后者更适合 Discussion 里突出“恢复期近端限制”。
