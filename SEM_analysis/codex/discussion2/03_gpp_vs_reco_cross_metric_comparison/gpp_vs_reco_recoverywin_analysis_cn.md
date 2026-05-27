# GPP 与 RECO 在过程解释口径下的对比分析

在 `recoverywin` 口径下，GPP 与 RECO 都表现出比 `prepeak` 更高的 SHAP 预测力，但二者的 SEM 结果差异很大。GPP 的 SHAP 平均 holdout R2 为 `0.619`，RECO 为 `0.665`；GPP 的 SEM 平均 holdout R2 为 `0.156`，而 RECO 在用户指定的 pruned hybrid 版本中达到 `0.593`。这意味着恢复期即时环境对两种通量都重要，但对 RECO 来说，这些过程变量更容易形成稳定的路径机制。

| 指标 | GPP `recoverywin` | RECO `recoverywin` |
|---|---:|---:|
| SHAP 平均 holdout R2 | 0.619 | 0.665 |
| SEM 平均 holdout R2 | 0.156 | 0.593 |
| 最常见 SHAP 主导变量 | PRE, TMP, STRD, VPD | PRE, STRD/SSRD, VPD/WIND |
| 最常见 SEM 主导路径 | TMP, VPD, SMrz | EVA(sum), TMP, VPD |

这组差异具有非常明确的物理含义。对 GPP 而言，恢复期环境首先表现为“是否具备重新启动光合的条件”，因此 `PRE`、`TMP`、`STRD` 和 `VPD` 最容易在 SHAP 中成为主导变量；其 SEM 目标路径也多由 `TMP`、`VPD`、`SMrz` 构成，说明光合恢复更依赖热量、生长季激活程度和水分供给。对 RECO 而言，虽然 SHAP 同样首先识别 `PRE` 和辐射特征，但一旦进入路径模型，最强的变量会转为 `EVA(sum)`、`TMP` 和 `VPD`，这表明呼吸恢复更接近一个由累计蒸散背景和即时热量条件共同调控的过程。

Forest 和 Grassland 最能体现这一点。GPP 的 Forest 过程解释型更强调 `STRD-PRE-VPD`，而 RECO 的 Forest 则在 SEM 中由 `EVA(sum)=+0.811` 与 `TMP=-0.578` 主导。Grassland 也是类似：GPP 端的核心是 `TMP=-0.536` 与 `PRE` 的强 SHAP 响应，而 RECO 端除了 `PRE` 之外，还要通过 `EVA(sum)=+0.802` 与 `VPD=+0.174` 才能完整解释恢复时间。这说明对森林和草地而言，GPP 更像一个“重新恢复光合活动”的问题，而 RECO 更像一个“何时从增强呼吸状态回归”的问题。

Savanna、Cropland 和 Shrubland 则进一步放大了这种差异。GPP 在这三个 biome 中仍然以 `PRE` 和 `TMP`/`STRD` 为主，强调补水和热量背景如何促使光合恢复；RECO 则显著强化 `EVA(sum)` 和 `VPD` 的作用，尤其 Cropland 与 Shrubland 的 `EVA(sum)` 分别达到 `+0.897` 和 `+0.670`，说明恢复期持续的蒸散背景会明显延长 RECO 回到原基线的时间。换句话说，GPP 的过程解释更像“资源重新到位以后多快恢复”，而 RECO 的过程解释更像“高呼吸状态会持续多久”。

因此，在过程解释口径下，GPP 与 RECO 的共同点是都高度依赖恢复期即时环境；但它们的差异同样非常明确：GPP 更依赖恢复期资源条件是否足以重新启动生产过程，RECO 更依赖恢复期水热条件是否维持了高呼吸背景。从论文写作角度，这一差异非常适合作为两个通量机制分化的主线结论。
