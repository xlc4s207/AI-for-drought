# RECO 前置预测口径与过程解释口径对比分析

RECO 的双口径对比使用 `reco_code1_flash_smrz_compare_prepeak_vs_recoverywin_20260421` 目录中的 SHAP 对比图，同时分别结合 `prepeak_event_shap_sem_20260421`、`sem_prepeak_event_mechanism_20260421` 与 `shap_process_recoverywin_precipEmean_sample50k_by_biome`、`sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260415` 的结果。这里仍然要强调，RECO 的过程解释型 SEM 使用累计量版本，因此它比 compare 目录中的旧 SEM 更强，也更适合作为正式过程解释依据。

| 指标 | `prepeak` | `recoverywin` |
|---|---:|---:|
| SHAP 平均 holdout R2 | 0.409 | 0.665 |
| SEM 平均 holdout R2 | 0.055 | 0.593 |
| 最稳定 SHAP 主导变量 | SSRD, EVA, PRE | PRE, STRD/SSRD, VPD/WIND |
| 最适合承担的叙事 | 峰值前呼吸记忆 | 恢复期呼吸过程控制 |

与 GPP 相比，RECO 的双口径差异更大。`recoverywin` 不仅在 SHAP 上大幅强于 `prepeak`，在用户指定的 pruned SEM 上也明显更强。这说明 RECO 的恢复时间更接近一个由恢复期即时环境直接调控的过程问题，而峰值前信息虽然仍有预测价值，但更像一种统计上的背景记忆。

Forest 与 Grassland 已经体现出这种差异。Forest 的 `prepeak` 仍由 `SSRD-EVA-STRD` 主导，但 `recoverywin` 则转为 `STRD-PRE-VPD-SSRD`，同时 SEM 中 `EVA(sum)` 和 `TMP` 成为最强路径；Grassland 的 `prepeak` 更强调 `SSRD-PRE-TMP`，而 `recoverywin` 则直接转为 `PRE-SSRD-STRD-WIND`，再由 `EVA(sum)` 与 `TMP` 在 SEM 中完成整合。也就是说，RECO 的 SHAP 更容易首先识别补水与辐射，而 RECO 的 SEM 更倾向于用累计蒸散和温度来整合这些即时过程。

Savanna 与 Cropland 的差异更能说明“前置记忆”和“过程控制”的分工。Savanna 在 `prepeak` 里仍被 `SSRD-EVA-PRE` 主导，而进入 `recoverywin` 后，`PRE` 已稳居第一，`WIND` 也显著上升；Cropland 则从 `SSRD-EVA-PRE-SMrz` 转向 `PRE-VPD-STRD-SSRD-WIND`，并在 SEM 中出现极强的 `EVA(sum)` 正向路径。这意味着 RECO 的恢复期不是单纯地“等环境转好”，而是恢复窗口内的持续蒸散背景、温度和大气干旱共同决定系统何时回到原基线。

Shrubland 是 RECO 双口径对比中最极端的案例。`prepeak` 的 SHAP holdout R2 仅为 `0.375`，而 `recoverywin` 达到 `0.743`；对应的 SEM 也从 `0.079` 升到 `0.545`。这说明干旱区 RECO 恢复几乎无法只靠峰值前背景来解释，必须读取恢复期即时环境。与之相对，Wetland 在 SHAP 上也表现出对 `recoverywin` 的明显偏向，但因为用户指定的 pruned SEM 路径中未包含 Wetland，正式写作时应将其保留为 SHAP 层面的边界案例，而不要强行纳入同一套 SEM 比较框架。

总体而言，RECO 的双口径对比更加支持“过程解释优先”的写法。`prepeak` 可以保留为早期预警或前置预测框架，但如果需要构建更完整的物理机制叙事，应优先使用 `recoverywin`。其核心原因在于，RECO 恢复时间更强地受恢复期蒸散、温度和大气需求的即时组合控制，而不是仅由峰值前背景决定。
