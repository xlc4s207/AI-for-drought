# GPP 过程解释口径单独解释分析

本文件对应 `gpp_code1_flash_smrz_rechunk_py_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome` 与 `sem_process_recoverywin_precipEmean_usertrim` 的结果。该口径直接使用恢复窗口内的环境特征，因此其解释重点是恢复发生时的即时限速过程，而不是峰值前记忆。

| Biome | SHAP holdout R2 | SEM holdout R2 | SHAP 前 5 位特征 | dependence 最强响应 | SEM 目标方程主导路径 |
|---|---:|---:|---|---|---|
| Forest | 0.604 | 0.216 | EVA, STRD, PRE, SSRD, VPD | STRD `Δ=-22.53`；EVA `Δ=+21.92` | TMP `-0.295`；EVA `+0.160`；SMrz `-0.104` |
| Grassland | 0.653 | 0.206 | TMP, PRE, SSRD, STRD, SMrz | PRE `Δ=+22.34`；TMP `Δ=-22.30` | TMP `-0.536`；VPD `+0.131`；SMrz `+0.067` |
| Savanna | 0.643 | 0.103 | PRE, STRD, SSRD, EVA, WIND | PRE `Δ=+24.15`；EVA `Δ=+20.44` | TMP `-0.225`；EVA `+0.104`；LAI `-0.084` |
| Cropland | 0.483 | 0.129 | PRE, VPD, STRD, SSRD, SMrz | PRE `Δ=+23.45`；STRD `Δ=-15.27` | TMP `-0.403`；VPD `+0.044`；EVA `-0.031` |
| Shrubland | 0.713 | 0.127 | TMP, PRE, SSRD, STRD, VPD | PRE `Δ=+23.23`；TMP `Δ=-21.02` | TMP `-0.642`；VPD `+0.382`；SMrz `-0.027` |

与前置预测口径相比，GPP 过程解释口径的 SHAP holdout R2 全面更高，平均值达到 `0.619`。这说明恢复窗口内的即时环境状态对 GPP 恢复时间的解释力更强。与此同时，SEM 平均 holdout R2 降到 `0.156`，提示这些近端环境过程虽然更容易提高树模型预测精度，但未必更容易压缩为稳定的线性路径结构。

Forest 的过程解释型机制最具代表性。SHAP 排名前列为 `EVA-STRD-PRE-SSRD-VPD`，dependence 中 `STRD` 的分位差达到 `-22.53`，`PRE` 也达到 `+18.13`。这意味着在森林恢复期中，暖湿背景与持续补水显著缩短恢复，而高蒸散又对应更长恢复尾部。SEM 中 `TMP=-0.295`、`SMrz=-0.104` 与 `VPD=+0.042` 的方向表明，森林恢复快慢主要受热量条件、根区供水与大气需求共同限制，是最典型的恢复期近端控制情景。

Grassland 显示出最清晰的“补水-温度”双重限速。`PRE` 与 `TMP` 的 dependence 分位差分别达到 `+22.34` 和 `-22.30`，几乎对称，说明更多恢复期降水会明显改变恢复时间，而温度越高则越有利于恢复。SEM 中 `TMP=-0.536` 的绝对值最大，进一步说明草地恢复时间受物候季节性和生长季激活程度强烈制约。因此，Grassland 的恢复过程解释更接近“补水决定水分约束，温度决定是否进入有效生长季”的双控制结构。

Savanna 与 Cropland 都以 `PRE` 为最强 SHAP 特征。Savanna 的 `PRE` 分位差达到 `+24.15`，Cropland 为 `+23.45`，两者都说明恢复期降水补给是最稳定的控速变量。Savanna 同时保留了较强的 `EVA` 与 `STRD` 响应，表明恢复期水热条件仍在共同控制碳通量回升；而 Cropland 的第二位和第三位变量已经转为 `VPD` 与 `STRD`，说明农田恢复更容易受大气干旱与辐射背景直接约束。

Shrubland 是 GPP 过程解释型中最依赖即时环境的 biome，SHAP holdout R2 达到 `0.713`。其前列变量为 `TMP-PRE-SSRD-STRD-VPD`，且 `TMP` 与 `PRE` 的 dependence 响应分别达到 `-21.02` 和 `+23.23`。这说明在干旱灌丛区，恢复期是否有实质性补水以及是否回到较高温度背景，是决定 GPP 恢复的核心条件。SEM 中 `VPD=+0.382` 也表明大气需求在 Shrubland 中更像是持续性的限速因子，而不是次级修饰项。

总体来看，GPP 过程解释口径最稳定的物理图像是：恢复窗口内的补水、热量背景和大气需求直接决定光合恢复速率，因此 `PRE`、`TMP`、`STRD` 和 `VPD` 构成了最核心的即时控制框架。与前置预测口径相比，这一口径更强于解释“为什么此时恢复快或慢”，而不是“为什么该事件会留下较长恢复记忆”。
