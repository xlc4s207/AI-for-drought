# GPP 与 RECO 在前置预测口径下的对比分析

在 `prepeak` 口径下，GPP 与 RECO 的 SHAP 平均 holdout R2 分别为 `0.423` 与 `0.409`，两者非常接近；但 SEM 平均 holdout R2 则分别为 `0.220` 与 `0.055`，差异明显。这说明峰值前信息对两种通量都具有前置预测价值，但对 GPP 更容易形成稳定的机制结构，对 RECO 则更像分散的背景记忆。

| 指标 | GPP `prepeak` | RECO `prepeak` |
|---|---:|---:|
| SHAP 平均 holdout R2 | 0.423 | 0.409 |
| SEM 平均 holdout R2 | 0.220 | 0.055 |
| 最常见 SHAP 主导变量 | EVA, SSRD, STRD, VPD | SSRD, EVA, PRE, VPD |
| 最常见 SEM 主导路径 | SSRD, STRD, EVA | EVA, TMP, VPD |

这组结果表明，GPP 的前置预测更接近“光合恢复记忆”的概念，而 RECO 的前置预测更接近“呼吸水热背景记忆”。具体来说，GPP 的 `prepeak` 在 Forest、Grassland、Savanna 和 Cropland 中都保持较强的 `SSRD`、`STRD` 与 `EVA` 主导，这意味着峰值前能量环境和蒸散背景能够较稳定地预示后续光合恢复难度。RECO 虽然也受到 `SSRD` 和 `EVA` 强烈影响，但其 SEM 端更偏 `TMP` 与 `VPD`，说明峰值前大气需求和热量状态对呼吸过程的背景塑形更强。

Forest 是这种差异最典型的 biome。GPP 的前置机制以 `SSRD=-0.313`、`EVA=+0.177` 和 `STRD=-0.102` 为核心，而 RECO 则转为 `EVA=+0.442`、`TMP=+0.336` 与 `VPD=-0.111`。这说明在森林中，GPP 更容易保留峰值前辐射和水分消耗的结构性记忆，而 RECO 更敏感于峰值前温度和蒸散背景本身。Grassland 与 Savanna 也有类似趋势：GPP 端的 `SSRD` 和 `STRD` 作用更稳定，而 RECO 端的 `TMP`、`VPD` 或 `EVA` 更容易进入核心路径。

Cropland 与 Shrubland 则说明两种通量对前期湿润背景的响应并不一样。GPP 的 Cropland 仍主要由 `SSRD-STRD-EVA-VPD` 主导，而 RECO 的 Cropland 则更明显地引入了 `PRE` 和 `SMrz`；Shrubland 中 GPP 与 RECO 都表现出较强的 `PRE` 响应，但 GPP 更容易被解释为“相对湿润异常改变光合恢复基线”，RECO 则更像“峰值前湿润背景放大呼吸偏离幅度”。因此，即便两种通量在 SHAP 排序上共享部分变量，它们的生态意义也不完全相同。

总体上，前置预测口径下的 GPP 与 RECO 共有一个共同事实：峰值前辐射和蒸散背景都很重要。但更深一层的差异是，GPP 的这些信号更容易转化为稳定的机制结构，而 RECO 的这些信号更分散、更依赖温度和大气需求。写作时可以将这一点概括为：GPP 的前置预测更偏“结构化恢复记忆”，RECO 的前置预测更偏“统计型背景记忆”。
