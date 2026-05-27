# RECO 恢复时间的 `prepeak` 与 `recoverywin` 机制对比分析

本文针对 `RECO code1 flash SMrz` 的恢复时间解释结果，比较两套不同时间口径的 SHAP 与 SEM 结论。`prepeak` 使用事件开始到峰值前的特征，强调的是“在真正进入恢复期之前，峰值前信息是否已经预示了后续恢复难度”；`recoverywin` 使用恢复窗口内的环境均值特征，强调的是“进入恢复期之后，哪些近端环境过程直接控制恢复时间”。因此，这两套框架并不是互相替代，而是分别对应前置预测与近端过程解释两个层次。

本轮 RECO 对比图件已经生成在 `process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_compare_prepeak_vs_recoverywin_20260421`。该目录下包含 6 个 biome 的 dependence 对比图，即 `Forest_prepeak_vs_recoverywin_dependence.png`、`Grassland_prepeak_vs_recoverywin_dependence.png`、`Savanna_prepeak_vs_recoverywin_dependence.png`、`Cropland_prepeak_vs_recoverywin_dependence.png`、`Shrubland_prepeak_vs_recoverywin_dependence.png` 和 `Wetland_prepeak_vs_recoverywin_dependence.png`，还包括跨 biome 的总蜂巢图 `all_biomes_prepeak_vs_recoverywin_beeswarm.png` 与元数据表 `summary.csv`。底层 `prepeak` 结果来自 `process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome`，`recoverywin` 结果来自 `process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome`，对应 SEM 结果则分别来自 `prepeak_event_shap_sem_20260421/sem_by_biome` 与 `sem_process_recoverywin_mechanism/by_biome`。

为了保证比较严格可控，本文重点比较两套框架共同拥有的 9 个共享环境特征，即 `PRE`、`EVA`、`TMP`、`VPD`、`SMrz`、`LAI`、`SSRD`、`STRD` 和 `WIND`。其中 `prepeak` 结果虽然还包含 `ONS`、`DUR` 和 `INT` 三个事件特征，但在这份双口径比较中，这些事件变量仅用于解释 `prepeak` 的附加信息来源，不参与与 `recoverywin` 的共享特征对照。

---

## 1. 模型表现对比：谁更像预测器，谁更像机制框架？

首先从模型表现看，两套口径在 SHAP 与 SEM 上给出了非常不同的信号。SHAP 的 holdout R2 反映的是树模型对恢复时间的统计预测力，而 SEM 的 holdout R2 更接近线性路径结构能否稳定解释目标方程。结果表明，`recoverywin` 在 SHAP 上全面更强，但在 SEM 上并没有同样稳定地压过 `prepeak`。

| Biome | SHAP holdout R2 (`prepeak`) | SHAP holdout R2 (`recoverywin`) | 差值 (`recoverywin - prepeak`) | SEM holdout R2 (`prepeak`) | SEM holdout R2 (`recoverywin`) | 差值 (`recoverywin - prepeak`) |
|---|---:|---:|---:|---:|---:|---:|
| Forest | 0.407 | 0.634 | +0.227 | 0.051 | 0.025 | -0.026 |
| Grassland | 0.375 | 0.680 | +0.306 | 0.086 | 0.047 | -0.040 |
| Savanna | 0.438 | 0.684 | +0.246 | 0.041 | 0.020 | -0.020 |
| Cropland | 0.315 | 0.544 | +0.229 | 0.036 | 0.003 | -0.033 |
| Shrubland | 0.375 | 0.743 | +0.368 | 0.079 | 0.066 | -0.013 |
| Wetland | 0.544 | 0.707 | +0.163 | 0.039 | 0.129 | +0.090 |
| **平均值** | **0.409** | **0.665** | **+0.256** | **0.055** | **0.048** | **-0.007** |

表 1 清楚说明，`recoverywin` 在 6 个 biome 上的 SHAP holdout R2 全部高于 `prepeak`，平均值从 `0.409` 提升到 `0.665`。这意味着当模型直接读取恢复窗口内的环境状态时，确实能更有效地预测 `t_recover_to_baseline_abs_peak`，因为这些变量距离目标变量更近、更具即时性。换句话说，`recoverywin` 更像一个“恢复期近端诊断器”。

但 SEM 的结果并不支持“recoverywin 完全优于 prepeak”这一简单结论。除 Wetland 外，其余 5 个 biome 的 SEM holdout R2 都是 `prepeak` 更高，且总体平均值也是 `prepeak` 略优于 `recoverywin`。这说明，虽然 `prepeak` 离恢复期更远、统计预测力较弱，但它所保留的峰值前信息在大多数 biome 中能够形成更稳定的机制结构。也就是说，`prepeak` 更接近“恢复记忆的前置机制框架”，而 `recoverywin` 更接近“恢复发生时的近端控制框架”。

这个对比对论文写作很关键。若强调预测性能，应突出 `recoverywin`；若强调机制叙事和前置解释，则 `prepeak` 并不能被简单视为次优方案。更合理的写法是把二者放在同一个分层框架里：`prepeak` 回答“恢复为何会难”，`recoverywin` 回答“恢复此刻为何快或慢”。

---

## 2. 特征排序对比：峰值前辐射记忆 vs 恢复期水分控制

SHAP beeswarm 与 `feature_importance.csv` 进一步揭示，两套框架虽然都在解释同一个恢复时间指标，但它们读取到的主导信息源并不相同。

| Biome | `prepeak` 前 5 位特征 | `recoverywin` 前 5 位特征 |
|---|---|---|
| Forest | SSRD, EVA, STRD, PRE, VPD | STRD, PRE, VPD, SSRD, EVA |
| Grassland | SSRD, PRE, TMP, VPD, WIND | PRE, SSRD, STRD, WIND, SMrz |
| Savanna | SSRD, EVA, PRE, STRD, DUR | PRE, SSRD, STRD, EVA, WIND |
| Cropland | SSRD, EVA, PRE, SMrz, STRD | PRE, VPD, STRD, SSRD, WIND |
| Shrubland | SSRD, PRE, WIND, STRD, TMP | STRD, PRE, SSRD, WIND, TMP |
| Wetland | SSRD, EVA, STRD, PRE, ONS | PRE, STRD, EVA, SSRD, WIND |

从表 2 可以看到，`prepeak` 在 6 个 biome 中几乎都把 `SSRD` 放在最前，只有少数 biome 的第 4 或第 5 位才出现明显的水分或事件特征。这说明在 RECO 的前置预测口径中，峰值前的辐射背景是最强的解释源，`EVA`、`STRD` 和 `PRE` 则共同补充了峰值形成阶段的水热背景。换句话说，`prepeak` 更像是在读取“事件如何被放大到峰值”的背景信息。

相反，`recoverywin` 的排序则明显转向了 `PRE`、`STRD`、`VPD` 与部分 `WIND`。其中 `PRE` 在 Grassland、Savanna、Cropland、Wetland 中位居第一，在 Forest 和 Shrubland 中也始终排在前二；`STRD` 则在 Forest 和 Shrubland 中排第一，并在其余 biome 中普遍进入前四。这个排序格局说明，进入恢复期之后，真正控制 RECO 恢复快慢的已经不再是峰值前辐射放大本身，而是恢复窗口内是否有持续补水、恢复期的大气热湿背景是否有利，以及是否仍处于强大气需求的状态。

因此，两套口径的特征排序差异并非噪声，而是反映了两个阶段完全不同的生态意义。`prepeak` 读取的是“峰值前背景如何决定系统留下怎样的恢复记忆”，`recoverywin` 读取的是“恢复期环境如何即时控制恢复速率”。这正是为什么它们在 SHAP 预测力和 SEM 机制稳定性上会出现分化。

---

## 3. biome 分区对比：不同生态系统到底由谁主导？

虽然两套框架的总体差异已经很清楚，但不同 biome 的机制重心并不完全一致。将表 1 的模型表现和表 2 的主导特征一起看，可以进一步整理出每个 biome 的主导叙事。

| Biome | `prepeak` 主导信号 | `recoverywin` 主导信号 | 解释重点 |
|---|---|---|---|
| Forest | 峰值前 `SSRD-EVA-STRD` 能量与蒸散背景 | 恢复期 `STRD-PRE-VPD` | 森林恢复同时受生长季热湿背景与大气需求控制 |
| Grassland | 峰值前 `SSRD-PRE-TMP` | 恢复期 `PRE-SSRD-STRD` | 草地既受前期辐射塑形，也受恢复窗补水强烈控制 |
| Savanna | 峰值前 `SSRD-EVA-PRE` | 恢复期 `PRE-SSRD-STRD` | 从辐射放大主导转向补水主导最明显 |
| Cropland | 峰值前 `SSRD-EVA-PRE-SMrz` | 恢复期 `PRE-VPD-STRD` | 农田在恢复期更受水分与大气干旱直接限制 |
| Shrubland | 峰值前 `SSRD-PRE-WIND` | 恢复期 `STRD-PRE-SSRD` | 干旱区对恢复窗即时环境依赖最强 |
| Wetland | 峰值前 `SSRD-EVA-STRD` | 恢复期 `PRE-STRD-EVA` | 湿地是唯一恢复期机制在 SEM 上也更强的 biome |

Forest 的一个突出特点是，`recoverywin` 与 `prepeak` 的主导变量虽然都包含辐射和水分信息，但侧重点发生了明显转移。峰值前最重要的是 `SSRD-EVA-STRD`，说明森林在到达峰值前，辐射和蒸散耦合背景已经决定了事件会留下怎样的恢复记忆；进入恢复期之后，最重要的则是 `STRD-PRE-VPD`，表明真正控制森林 RECO 恢复速度的是恢复阶段的热湿背景、补水与大气需求。这一结果与 Forest 在表 1 中表现出的特征一致：`recoverywin` 的 SHAP 提升明显，但 SEM 上 `prepeak` 仍更稳。

Grassland 与 Savanna 共同体现出“从辐射背景转向恢复期补水”的切换。Grassland 的 `prepeak` 前列包含 `SSRD-PRE-TMP`，表明辐射与温度背景对草地峰值前状态塑形明显；但到了 `recoverywin`，最重要的已经是 `PRE-SSRD-STRD`，说明草地恢复期是否有持续补水成为更关键的决定因素。Savanna 的转折更明显，`prepeak` 仍由 `SSRD-EVA-PRE` 主导，而 `recoverywin` 已经稳定转为 `PRE-SSRD-STRD`，这说明热带和亚热带稀树草原的恢复控制更依赖恢复阶段本身的补水和辐射背景，而不是峰值前能量状态本身。

Cropland 体现出非常典型的“双层机制”。在 `prepeak` 中，农田仍由 `SSRD-EVA-PRE-SMrz` 主导，说明峰值前辐射和蒸散条件决定了事件将留下怎样的水分亏缺记忆；但在 `recoverywin` 中，变量迅速切换为 `PRE-VPD-STRD`，显示农田 RECO 恢复期更直接地受降水补给和大气干旱控制。这一结果与 Cropland 在表 1 中的数值对比高度一致：SHAP 从 `0.315` 升到 `0.544`，但 SEM 从 `0.036` 降到仅 `0.003`，提示农田恢复期虽然容易被近端环境准确预测，但这些近端过程并不容易压缩成稳定的线性路径结构。

Shrubland 是恢复期依赖最强的 biome。其 `recoverywin` SHAP holdout R2 达到 `0.743`，在所有 biome 中最高，说明干旱区 RECO 恢复时间非常依赖恢复窗口内的即时环境状态。即便如此，Shrubland 的 `prepeak` SEM 仍略高于 `recoverywin`，说明峰值前信息并没有失去解释价值，而是保留了部分可线性表达的恢复记忆。这类“SHAP 更偏 recoverywin、SEM 仍偏 prepeak”的组合，是支持双框架并存而非相互替代的最好证据。

Wetland 则是边界情形最鲜明的 biome。它不仅在 SHAP 上是 `recoverywin` 明显更强，在 SEM 上也是唯一一个 `recoverywin` 超过 `prepeak` 的 biome，分别达到 `0.129` 与 `0.039`。这意味着湿地 RECO 恢复更依赖恢复期的即时环境状态，而峰值前信息对后续恢复的外推能力相对较弱。因此，在论文中可以将 Wetland 作为一个例外来写：对于高湿、强水文耦合系统，恢复期近端环境比峰值前背景更接近真正的恢复限制过程。

---

## 4. 机制综合：如何把两套口径写成一个统一故事？

如果只看 SHAP holdout R2，很容易得出“recoverywin 更好”的结论；但如果把 SEM 和特征结构一起考虑，这样的结论其实过于简单。`recoverywin` 确实更能预测恢复时间，因为它使用的是恢复期本身的环境状态；但是 `prepeak` 之所以在多数 biome 的 SEM 上仍不弱，恰恰说明恢复时间并不是在恢复期才被决定，而是在峰值形成阶段就已经部分写入系统状态。

因此，更合理的总结不是“选 prepeak 还是 recoverywin”，而是明确它们分别回答了两个不同问题。`prepeak` 更适合承担前置预测的叙事：峰值前的辐射放大、蒸散背景、前期水分与部分事件特征共同塑造了系统的恢复记忆，因此在真正进入恢复窗之前，就已经可以对后续恢复难度做出一定程度判断。`recoverywin` 则更适合承担恢复过程解释的叙事：进入恢复期之后，降水补给、长波辐射背景、VPD 与风速等近端环境共同决定恢复是被加速还是被拖慢。

用论文语言来说，`prepeak` 可以被定义为“恢复难度的早期指示器框架”，`recoverywin` 可以被定义为“恢复速度的近端调控框架”。前者的价值在于提供更早的可预报性与机制记忆，后者的价值在于提供更高的即时解释力与统计预测力。对于 RECO 而言，这两套框架不是二选一，而应当被组织成一个分层机制故事：峰值前信息决定恢复记忆，恢复期环境决定恢复速率。

---

## 5. 可直接写入论文的结论段

综合 SHAP、dependence plot、beeswarm 和 SEM 结果，RECO 的恢复时间机制可以概括为以下三点。第一，`recoverywin` 在统计预测上显著优于 `prepeak`，其平均 SHAP holdout R2 从 `0.409` 提升到 `0.665`，表明恢复期即时环境是更强的近端预测器。第二，`prepeak` 在机制结构上并未失效，反而在 6 个 biome 中有 5 个的 SEM holdout R2 高于 `recoverywin`，说明峰值前水热背景确实携带了稳定的恢复记忆。第三，两套框架的主导变量存在清晰分工：`prepeak` 主要由 `SSRD`、`EVA`、`STRD` 等峰值前能量与蒸散背景主导，而 `recoverywin` 主要由 `PRE`、`STRD`、`VPD` 等恢复期补水与热湿背景主导。因此，RECO 的恢复时间并不是单一阶段决定的，而是同时受到峰值前记忆写入和恢复期近端调控的双重控制。
