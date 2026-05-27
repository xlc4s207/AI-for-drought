# RECO 过程解释口径单独解释分析

本文件对应 `reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome` 与用户指定的 `sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260415`。需要特别说明的是，该 SEM 版本使用的是 `PRE(sum)` 与 `EVA(sum)` 等累计量，而 SHAP 使用的是 `PRE(mean)` 与 `EVA(mean)` 等均值变量，因此二者在变量定义上不是完全一一对应，但都指向恢复期即时环境的过程解释。

| Biome | SHAP holdout R2 | SEM holdout R2 | SHAP 前 5 位特征 | dependence 最强响应 | SEM 目标方程主导路径 |
|---|---:|---:|---|---|---|
| Forest | 0.634 | 0.569 | STRD, PRE, VPD, SSRD, EVA | SSRD `Δ=+25.53`；PRE `Δ=+22.29` | EVA(sum) `+0.811`；TMP `-0.578`；SMrz `-0.060` |
| Grassland | 0.680 | 0.581 | PRE, SSRD, STRD, WIND, SMrz | PRE `Δ=+28.27`；STRD `Δ=-16.90` | EVA(sum) `+0.802`；TMP `-0.593`；VPD `+0.174` |
| Savanna | 0.684 | 0.598 | PRE, SSRD, STRD, EVA, WIND | PRE `Δ=+24.71`；WIND `Δ=-16.03` | EVA(sum) `+0.858`；TMP `-0.585`；SMrz `-0.107` |
| Cropland | 0.544 | 0.670 | PRE, VPD, STRD, SSRD, WIND | PRE `Δ=+32.50`；SSRD `Δ=+24.53` | EVA(sum) `+0.897`；TMP `-0.485`；VPD `+0.135` |
| Shrubland | 0.743 | 0.545 | STRD, PRE, SSRD, WIND, TMP | STRD `Δ=-33.10`；PRE `Δ=+23.46` | TMP `-0.687`；EVA(sum) `+0.670`；VPD `+0.331` |

这一版本的 RECO 过程解释型结果有两个非常鲜明的特征。第一，SHAP 平均 holdout R2 达到 `0.657` 左右，说明恢复期即时环境对 RECO 恢复时间具有很高的预测力。第二，SEM 平均 holdout R2 也达到 `0.593`，远高于前置预测口径，表明在这套 pruned 混合模型中，恢复期环境过程不仅能提高预测力，也确实能够形成稳定的机制路径结构。这一点与前面使用的其他 RECO SEM 版本不同，因此在后续写作中应当明确指明本文件使用的是 `20260415 pruned hybrid` 版本。

Forest 的过程解释结果表明，RECO 恢复时间主要由恢复期蒸散总量、温度和部分土壤水控制。虽然 SHAP 排名前列是 `STRD-PRE-VPD-SSRD-EVA`，但 SEM 目标路径中绝对值最大的是 `EVA(sum)=+0.811` 与 `TMP=-0.578`。这说明在森林中，恢复期更高的累计蒸散更可能对应更长的 RECO 恢复尾部，而较高温度则有利于缩短恢复时间。换句话说，Forest 的 RECO 恢复更像是在“热量条件有利时由蒸散背景调节恢复尾部长度”。

Grassland 与 Savanna 呈现出非常一致的结构。SHAP 上二者都由 `PRE` 主导，Grassland 的分位差达到 `+28.27`，Savanna 达到 `+24.71`；SEM 上二者又都由 `EVA(sum)` 与 `TMP` 主导。这说明草地和稀树草原的 RECO 恢复虽然在树模型层面最容易被恢复期补水所识别，但真正进入路径模型后，更核心的仍是恢复期累计蒸散与热量条件的组合。也就是说，`PRE` 更像是 SHAP 捕获到的直接环境信号，而 `EVA(sum)` 与 `TMP` 更像是整合后的过程变量。

Cropland 是这套结果里最强的案例之一。SHAP 上 `PRE` 的分位差高达 `+32.50`，`SSRD` 也达到 `+24.53`；SEM 上 `EVA(sum)=+0.897` 是所有 biome 中最大的正向路径。这表明农田 RECO 恢复非常依赖恢复期水热条件是否把系统维持在高呼吸活动状态。一旦恢复期蒸散累计较高，就意味着系统在较长一段时间内仍保持较强能量和水分交换，因此回到原基线所需时间也更长。

Shrubland 则由 `STRD` 与 `PRE` 共同主导，SHAP 分位差分别达到 `-33.10` 和 `+23.46`。同时，SEM 中 `TMP=-0.687` 和 `VPD=+0.331` 的绝对值都很高，说明干旱区 RECO 恢复更直接地受恢复期热量和大气干旱条件约束。与 GPP 相比，Shrubland 的 RECO 恢复更像是一个典型的“大气需求调节过程”，而不是单纯的补水阈值问题。

总体上，这一版本的 RECO 过程解释结果支持一个更清晰的过程框架：恢复期补水是最容易被 SHAP 直接识别的近端信号，而累计蒸散、温度与大气需求则是更适合进入 SEM 路径模型的过程变量。对于 RECO 来说，这一口径比前置预测口径更接近真正的恢复控制结构，因此更适合作为过程解释主线。
