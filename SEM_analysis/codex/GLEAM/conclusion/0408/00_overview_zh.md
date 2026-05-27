# 2026-04-08 `process_recoverywin` 迭代结果总览

本目录用于集中归档 `process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean` 下与 `process_recoverywin` 主线直接相关的多轮迭代结果。归档目标不是简单复制原始输出，而是将每一轮版本的建模目的、特征变化、样本设置、关键结果、图件含义与结论统一整理为中文说明，方便后续写论文、做图注和回顾版本演进。

本次归档现已整理 9 个版本，其中前 5 个是 `process_recoverywin` 主线迭代版本，后 4 个是候选机制模型分支版本：

| 版本 | 文件夹 | 核心目的 | SHAP 特征口径 | SEM 口径 | 推荐定位 |
|---|---|---|---|---|---|
| V1 | `v1_process_recoverywin_original` | 原始 recoverywin 全特征解释 | 17 个 recoverywin 特征，SHAP 抽样 5000 | 单方程直接效应 | 最初始基线 |
| V2 | `v2_process_recoverywin_sample_compare` | 比较 5000 / 10000 / 20000 抽样稳定性 | 17 个 recoverywin 特征，多档抽样 | SEM 不变，沿用 V1 口径 | 说明 5000 是否足够 |
| V3 | `v3_process_recoverywin_dedup_r2` | 去除冗余变量，并加入显式 R2 | 非湿地 6 特征，湿地 3 特征 | 单方程直接效应 | 主文本候选版本 |
| V4 | `v4_process_recoverywin_dedup_wind_lai_r2` | 在 V3 基础上加入 wind_speed 与 lai_total | 非湿地 8 特征，湿地 3 特征 | 单方程直接效应 | 扩展稳健性版本 |
| V5 | `v5_process_recoverywin_mechanism_sem` | 构建多方程机制型 SEM，体现间接效应 | SHAP 参考 V4 的 8 特征 | 多方程机制路径 | 机制解释版本 |
| V6 | `v6_sem_candidate_models_forest_process` | 仅 Forest 的候选机制比较 | 不单独重跑 SHAP，承接 Forest 过程特征筛选 | Forest 候选 SEM | Forest 机制筛选补充版 |
| V7 | `v7_sem_candidate_models_all_biomes_process` | 全 biome 宽松过程型候选机制比较 | 过程特征候选集 | 全 biome 候选 SEM | 机制筛选初稿 |
| V8 | `v8_sem_candidate_models_all_biomes_strict_process` | 全 biome 严格过程型候选机制比较 | 更严格的过程特征口径 | 全 biome 候选 SEM | 简洁稳健机制版 |
| V9 | `v9_sem_candidate_models_all_biomes_landmark30_v21` | 30 天关键窗口候选机制比较 | `postpeak30` 为主的 landmark30 口径 | 全 biome 候选 SEM | 短期关键窗口机制版 |

## 版本演进主线

1. V1 先回答“恢复窗内哪些变量最重要”。
2. V2 检验“SHAP 抽样 5000 是否足够稳定”。
3. V3 解决“变量冗余过强，解释不够干净”的问题。
4. V4 进一步检验“加入风速和 LAI 后是否显著提升模型解释力”。
5. V5 解决“路径图只有直接效应、没有间接效应”的问题，转向机制型 SEM。
6. V6 单独比较 Forest biome 内部不同机制假设的适配性。
7. V7 将候选机制扩展到全部 biome，形成宽松过程型比较。
8. V8 进一步压缩结构，检验最简洁水分机制是否仍然稳健。
9. V9 切换到 `landmark30_v21` 口径，比较“恢复后 30 天关键窗口”下的最优机制。

## 当前建议

如果目标是做结果主文，推荐：

- 主结果解释与稳健性：优先参考 `V3`。
- 扩展变量稳健性：补充 `V4`。
- 机制路径图与间接效应：使用 `V5`。
- 候选机制比较与补充材料：补充 `V6`、`V7`、`V8`、`V9`。

如果目标是说明整个分析流程如何逐步迭代而来，则建议先呈现主线 `V1 -> V2 -> V3 -> V4 -> V5`，再补充候选机制分支 `V6 -> V7 -> V8 -> V9`。

## 为什么 V6 到 V9 后来没有作为最终主结果

`V6` 到 `V9` 都是非常有价值的前期探索版本，但后续没有直接作为最终主结果采用，主要有以下原因：

1. 这四版的主要任务是“候选机制筛选”，而不是形成最终统一结果。它们回答的是“哪类路径结构更可能成立”，后续主线回答的则是“在统一 recoverywin 口径下，哪些变量最重要、模型解释力如何、机制路径如何表达”。
2. 这四版与最终主线在变量体系上并不完全一致。后续正式版本又继续做了变量去冗余、加入 `wind_speed` 和 `lai_total`、补充 `R2`、再升级到机制型 SEM，因此前期候选版所用的变量集合仍属于探索阶段。
3. `V6-V8` 使用的是候选模型竞争思路，机制假设较强；而后续最终主线采用的是“先 SHAP 筛选、再 SEM 解释”的数据驱动流程，与整条研究线更一致，也更容易向外说明变量进入模型的依据。
4. `V9` 采用 `landmark30_v21` 的 30 天关键窗口口径，样本量与时间窗口都和后续正式使用的 recoverywin 主线不同，因此更适合作为对照分析，而不是最终总结果。
5. 从论文写作角度看，`V6-V9` 更适合放在补充材料，说明前期如何比较不同机制假设；真正用于主结果的则是 `V3-V5` 这条已经完成统一变量口径、可信度评估和路径解释的正式主线。
