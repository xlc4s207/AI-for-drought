# 基于 SHAP 规划的 GPP 与 RECO 恢复时间 SEM 结果包

本目录按照 `process/SEM_analysis0401/codex/writing3/05_SHAP_SEM_path_analysis_design_cn.docx` 中的设计逻辑，整理 pre-peak 阶段 GPP 与 RECO 恢复时间的 SEM 结果。

## 模型角色

SHAP 用于筛选变量、识别阈值和提出机制假设；SEM 用于把这些变量组织成直接路径和中介路径。GPP 与 RECO 作为两个独立响应系统分别建模，不设置 GPP 指向 RECO 或 RECO 指向 GPP 的路径。

## 文件说明

- `tables/sem_prepeak_r2_gpp_reco.csv`：不同 metric 和 biome 的训练集与 holdout R2。
- `tables/sem_prepeak_all_structural_paths.csv`：所有标准化结构路径系数。
- `tables/sem_prepeak_target_direct_paths.csv`：直接指向恢复时间的路径系数。
- `tables/sem_prepeak_total_effects.csv`：由有向 SEM 路径计算的直接效应、间接效应和总效应。
- `tables/sem_prepeak_design_alignment.csv`：05 文档规划与当前 half-unified 实现之间的对应关系。
- `figures/sem_prepeak_holdout_r2_gpp_reco.png`：GPP 与 RECO 的解释力对比。
- `figures/sem_prepeak_target_direct_coefficients_heatmap.png`：恢复时间直接路径系数热图。
- `figures/sem_prepeak_total_effects_heatmap.png`：包含中介路径后的总效应热图。

## 与 05 文档设计的对应关系

| mechanism | planned_path | implementation_note |
| --- | --- | --- |
| Water supply | PRE -> SMrz | 主模型建议路径；当前用 PRE -> \|EVA\| 与 PRE -> SMrz 表达水分补给。 |
| Energy-thermal | STRD -> TMP | 扩展热量背景路径；当前作为半统一骨架的上游路径。 |
| Atmospheric dryness | TMP + WIND -> VPD | 当前用 TMP 和 WIND 解释 VPD，符合大气干旱调节设计。 |
| Evaporation coupling | PRE + VPD -> \|EVA\| | 当前将蒸散作为水分和大气干旱共同作用的中介。 |
| Root-zone mediation | PRE + \|EVA\| -> SMrz | 当前将 SMrz 作为根区水分中介，符合 05 文档主干。 |
| GPP target | TMP + VPD + \|EVA\| + SMrz -> recovery | GPP 保留 \|EVA\| 直接路径，用于表示蒸散-光合恢复耦合。 |
| RECO target | TMP + VPD + SMrz -> recovery | RECO 不保留 \|EVA\| 直接终点路径，更强调温度和水分对呼吸恢复的控制。 |
| LAI | Sensitivity only | 05 文档建议弱化 LAI；当前主模型未加入 LAI。 |
| Duration | Event memory | 05 文档建议加入；当前 half-unified 版本未加入，后续可做 event-aware 扩展模型。 |
| SSRD | Shortwave radiation | 05 文档建议作为主变量；当前为控制共线性未直接入主模型，使用 STRD/TMP 表达热量背景。 |

## Holdout R2

| metric | biome | rows | holdout_r2 | train_r2 | predictor_count |
| --- | --- | --- | --- | --- | --- |
| GPP | Cropland | 190590 | 0.044 | 0.045 | 4 |
| GPP | Forest | 356455 | 0.063 | 0.067 | 4 |
| GPP | Grassland | 393445 | 0.063 | 0.066 | 4 |
| GPP | Savanna | 436636 | 0.105 | 0.107 | 4 |
| GPP | Shrubland | 243279 | 0.109 | 0.109 | 4 |
| RECO | Cropland | 217386 | 0.048 | 0.048 | 3 |
| RECO | Forest | 394850 | 0.030 | 0.029 | 3 |
| RECO | Grassland | 439163 | 0.079 | 0.079 | 3 |
| RECO | Savanna | 486666 | 0.104 | 0.103 | 3 |
| RECO | Shrubland | 293653 | 0.154 | 0.152 | 3 |

## 指向恢复时间的最强直接路径

| metric | biome | from_label | estimate | p_value | significance |
| --- | --- | --- | --- | --- | --- |
| GPP | Cropland | TMP | 0.296 | 0.000 | *** |
| GPP | Cropland | \|EVA\| | 0.287 | 0.000 | *** |
| GPP | Forest | TMP | 0.538 | 0.000 | *** |
| GPP | Forest | \|EVA\| | 0.496 | 0.000 | *** |
| GPP | Grassland | TMP | 0.527 | 0.000 | *** |
| GPP | Grassland | VPD | -0.274 | 0.000 | *** |
| GPP | Savanna | TMP | 0.638 | 0.000 | *** |
| GPP | Savanna | \|EVA\| | 0.394 | 0.000 | *** |
| GPP | Shrubland | TMP | 0.349 | 0.000 | *** |
| GPP | Shrubland | VPD | -0.262 | 0.000 | *** |
| RECO | Cropland | TMP | 0.175 | 0.000 | *** |
| RECO | Cropland | VPD | 0.060 | 0.000 | *** |
| RECO | Forest | TMP | 0.174 | 0.000 | *** |
| RECO | Forest | SMrz | -0.044 | 0.000 | *** |
| RECO | Grassland | TMP | 0.391 | 0.000 | *** |
| RECO | Grassland | VPD | -0.144 | 0.000 | *** |
| RECO | Savanna | TMP | 0.310 | 0.000 | *** |
| RECO | Savanna | SMrz | -0.040 | 0.000 | *** |
| RECO | Shrubland | VPD | -0.438 | 0.000 | *** |
| RECO | Shrubland | SMrz | -0.377 | 0.000 | *** |

## 结果解释

当前实现采用较保守的 half-unified 骨架：STRD 作为 TMP 的上游热量/长波辐射背景；TMP 和 WIND 共同解释 VPD；PRE 和 VPD 调节 |EVA|；PRE 和 |EVA| 进一步调节 SMrz；最后由温度、大气干旱、蒸散和根区水分变量解释恢复时间。这样既保持 GPP 与 RECO 模型之间的可比性，也控制了 SHAP-to-SEM 规划文档中反复提到的共线性风险。

GPP 模型保留 |EVA| 到恢复时间的直接路径，符合 05 文档中“实际蒸散可代表水分-能量耦合并影响光合恢复”的设计。RECO 模型不保留 |EVA| 的终点直接路径，而更强调 TMP、VPD 和 SMrz，这与生态系统呼吸恢复受温度激活、水分可用性和大气干旱共同控制的机制更一致。LAI 按照 05 文档建议未进入主模型，仅适合作为后续敏感性分析变量。

写作时需要明确两点与 05 文档完整设计的差异：第一，Duration 尚未进入当前 half-unified 主模型，后续应作为 event-aware 扩展模型中的事件记忆路径处理；第二，SSRD 在当前主模型中没有直接进入，而是为了降低共线性风险，暂时使用 STRD/TMP 表达热量背景。若后续共线性诊断允许，可把 SSRD 作为 STRD/TMP 热量路径的替代或扩展版本单独检验。
