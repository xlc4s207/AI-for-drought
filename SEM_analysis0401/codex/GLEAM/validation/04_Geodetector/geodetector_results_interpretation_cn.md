# Geodetector 结果解释：GPP 与 RECO 恢复时间的空间分层异质性验证

本文档解释 `process/SEM_analysis0401/codex/GLEAM/validation/04_Geodetector` 路径下的地理探测器验证结果。该分析以恢复时间 `t_recover_to_baseline_abs_peak` 为目标变量，分别在 GPP 和 RECO 的不同 biome 内检验 pre-peak 环境变量对恢复时间空间分层异质性的解释力。

## 1. 输出文件说明

`geodetector_factor_q.csv` 是因子探测器结果。它对每个 `metric-biome-feature` 组合计算一个 q 值，用来判断该 pre-peak 特征对恢复时间空间分层异质性的解释力。换句话说，它回答的是：如果按照某个变量，例如 TMP、SSRD、VPD，把样本划分成不同水平，那么这些分层能在多大程度上解释恢复时间的空间差异。

`geodetector_interactions.csv` 是交互探测器结果。它把 SHAP 中较重要的变量两两组合，计算组合分层后的 q 值，并判断两个因子共同作用时是双因子增强、非线性增强，还是削弱。它回答的是：单独看 TMP 或 SSRD 可能解释力有限，但 TMP+SSRD 是否能更好解释恢复时间的空间差异。

`results/GPP/.../*_risk_detector.csv` 和 `results/RECO/.../*_risk_detector.csv` 是风险探测器结果。每个文件对应一个 metric、biome 和 feature，里面给出该变量不同分箱内恢复时间的均值、中位数、标准差和样本数。它回答的是：某个变量从低到高变化时，不同分层中的平均恢复时间是否明显不同。

## 2. q 值的解释方式

q 值范围是 0 到 1。q 越高，说明该变量划分出来的分层越能解释恢复时间的空间差异。其核心计算逻辑可以理解为：

```text
q = 1 - 各分层内部方差加权和 / 总体方差
```

如果 q 接近 0，说明按这个变量分层后，各组内部仍然很分散，该变量对恢复时间空间异质性的解释力较弱。如果 q 较高，说明同一分层内部更相似，不同分层之间差异更明显，该变量对空间分异具有较强解释力。

需要注意的是，q 值不是 SHAP 值，不能直接解释为正效应或负效应。它只说明解释力强弱，不说明作用方向。另外，这里的变量被分成 6 个分位数层，因此 q 值表达的是分层解释力，而不是线性相关系数。

## 3. GPP 和 RECO 的总体主导因子

整体上，RECO 的恢复时间空间异质性比 GPP 更容易被环境因子解释，尤其是在 Savanna、Shrubland 和 Grassland 中。RECO 的最高 q 值出现在 Shrubland 的 SSRD，q=0.214；Savanna 的 TMP 和 STRD 也很高，分别为 0.193 和 0.188；Shrubland 的 TMP 和 VPD 也达到 0.180 和 0.166。这说明 RECO 恢复过程更强地受热量、辐射和大气干旱条件控制。

GPP 方面，主导因子也集中在热量和辐射相关变量，但整体 q 值略低。GPP Savanna 的 STRD、TMP、VPD 分别为 0.133、0.125、0.093；GPP Grassland 的 TMP、STRD、SSRD 分别为 0.112、0.104、0.075；GPP Shrubland 的 TMP、VPD、SMrz 分别为 0.109、0.105、0.093。也就是说，GPP 的恢复时间同样受到热量和辐射背景约束，但在干旱和半干旱 biome 中，水分状态和大气干旱也明显进入主导因子组。

## 4. 分 biome 的主要发现

### 4.1 Cropland

Cropland 中，GPP 的单因子解释力以 STRD 最高，q=0.061，其次是 TMP、PRE 和 VPD；RECO 中则是 TMP、STRD 和 VPD 居前，q 分别为 0.092、0.089 和 0.070。Cropland 的一个重要特征不是单个变量 q 特别高，而是交互增强明显。GPP 中 `|EVA| + STRD` 的 q_interaction=0.084，`SSRD + STRD` 的 q_interaction=0.082，均高于对应单因子；RECO 中 `STRD + VPD`、`|EVA| + STRD`、`SSRD + STRD` 也表现出增强。

这说明农田恢复时间并不是由单一光照或水分变量决定，而更像是辐射背景、蒸散状态和大气干旱共同调节。LAI 在当前 Geodetector 单因子结果中 q 值较低，但它仍可在 SHAP/SEM 中作为冠层结构变量参与机制解释；也就是说，LAI 更适合被理解为过程调节因子，而不是当前空间分层中最强的单因子。

### 4.2 Forest

Forest 中，GPP 和 RECO 都显示 `|EVA|` 的单因子 q 最高，分别为 0.071 和 0.090，TMP 和 STRD 次之。交互上，`|EVA| + TMP`、`|EVA| + STRD`、`SSRD + STRD` 都有明显增强。虽然 WIND 和 VPD 的单因子 q 不算最高，但在森林系统中它们可以作为大气交换和水汽亏缺背景解释变量，尤其要结合 SHAP dependence、ALE 和 ICE 判断其局部方向。

森林的结果说明，恢复时间更依赖蒸散需求、热量条件和辐射条件的复合背景，而不是单一水分变量。

### 4.3 Grassland

Grassland 中，GPP 和 RECO 都由 TMP、STRD、SSRD 主导。GPP 的 TMP q=0.112，STRD q=0.104，SSRD q=0.075；RECO 的 TMP q=0.129，SSRD q=0.118，STRD q=0.116。RECO 的热量和辐射解释力整体高于 GPP，说明草地生态系统中呼吸恢复对温度和能量条件更敏感。

交互结果也支持这一点：RECO 的 `SSRD + TMP` q_interaction=0.218，是 Grassland 中非常强的组合；GPP 的 `SSRD + TMP` 也达到 0.175。

### 4.4 Savanna

Savanna 中，TMP、STRD、SSRD 和 VPD 共同构成主导组。GPP 中 STRD q=0.133、TMP q=0.125、VPD q=0.093、|EVA| q=0.093；RECO 中 TMP q=0.193、STRD q=0.188、VPD q=0.146、|EVA| q=0.123。这个结果很符合 Savanna 作为热干边缘生态系统的性质：恢复时间同时受能量输入、热量累积、水汽亏缺和蒸散条件控制。

交互上，RECO 的 `TMP + |EVA|` q_interaction=0.250，`SSRD + STRD` q_interaction=0.233，说明热量-蒸散和短波-长波辐射组合对恢复时间分异尤其重要。

### 4.5 Shrubland

Shrubland 中，RECO 的解释力最强。RECO 的 SSRD q=0.214，TMP q=0.180，VPD q=0.166，SMrz q=0.125；GPP 中 TMP q=0.109，VPD q=0.105，SMrz q=0.093，PRE q=0.091。这里不仅热量和辐射强，水分变量也明显增强。

GPP 的结果说明灌丛区生产力恢复更受温度、大气干旱和土壤水分共同约束；RECO 的结果则显示呼吸恢复对辐射和热量背景更敏感。交互中，RECO 的 `SSRD + PRE` q_interaction=0.275，`SSRD + TMP` q_interaction=0.273，说明 Shrubland 的恢复时间具有很强的能量-水分耦合特征。

## 5. interaction 结果的重要性

interaction 结果很关键，因为它说明恢复时间的空间差异并不是简单由单个变量决定。当前 100 个交互组合中，没有出现削弱型关系；GPP 中 26 个是 `bi_factor_enhance`、24 个是 `nonlinear_enhance`，RECO 中 31 个是 `bi_factor_enhance`、19 个是 `nonlinear_enhance`。这说明大多数变量组合后的解释力都高于单因子。

这对机制解释很重要：如果只看单因子 q，某些变量如 SSRD、|EVA|、SMrz 或 LAI 在部分 biome 中可能不算很强；但当它们与 TMP、STRD、VPD 或 PRE 组合后，解释力明显增强。这支持一个更合理的生态解释：GPP/RECO 的恢复过程不是单一气候因子控制，而是由热量、辐射、水分和植被状态共同塑造。

## 6. risk detector 的使用方式和解释边界

risk detector 适合用来辅助判断不同变量水平下恢复时间的变化形态。例如某个 feature 被分成 6 个分位数层后，可以查看每一层的 `target_mean` 和 `target_median`，判断恢复时间是否在高温层、强辐射层或高 VPD 层中明显变长或变短。

但这里不要过度解读为因果关系。risk detector 只是分层均值比较，不能控制其他变量，也不能说明某个变量单独导致恢复时间变化。它更适合用作三个用途：第一，检查 q 值较高的变量是否确实表现出不同分层均值差异；第二，辅助判断 SHAP/ALE 中看到的阈值是否有数据分层支持；第三，发现非单调关系，例如中等温度层恢复时间最长，而不是简单的越高越长。

另外，当前 risk detector 的 `strata` 是区间字符串，查看时最好按区间数值顺序重新排序，避免字符串排序造成视觉误判。

## 7. 与 SHAP、ALE、ICE、PDP 的关系

Geodetector 和 SHAP/ALE/ICE/PDP 的角色不同。SHAP 主要回答模型认为哪些变量重要，以及变量对预测的局部贡献方向是什么；ALE 用来验证 SHAP dependence 中看到的方向和阈值，减少特征相关性带来的偏差；ICE 用来检查同一 biome 内部是否存在强烈个体异质性；PDP 用于展示平均响应趋势；Geodetector 则验证这些 SHAP 重要变量是否真的具有空间分层解释力。

因此，比较稳妥的解释链条是：先用 SHAP 找出重要变量和可能的非线性关系，再用 ALE/PDP 检查平均趋势和阈值，用 ICE 判断 biome 内部是否存在异质性，最后用 Geodetector 验证这些变量是否能解释恢复时间的空间分异。如果某个变量 SHAP 重要、ALE 方向清楚、Geodetector q 也高，那么它就是比较可靠的机制变量；如果 SHAP 重要但 q 低，说明它可能影响个体预测，但不一定主导空间格局；如果 q 高但 SHAP 方向复杂，则说明它具有空间分层解释力，但作用方向需要通过 ALE/ICE/risk detector 进一步拆解。

## 8. Geodetector 与 SHAP 结果对比表

下表将每个 `metric-biome` 组合中 Geodetector q 值最高的 Top 3 特征与 SHAP mean absolute importance 排名前三的特征进行对比。需要注意的是，两者衡量的问题不同：SHAP 反映模型预测中各变量的平均贡献强度，而 Geodetector q 值反映变量对恢复时间空间分层异质性的解释力。因此，二者一致时说明该变量既是模型中的关键预测因子，也是空间格局的重要解释因子；二者不完全一致时，通常说明该变量更偏向局部预测贡献或空间分层解释中的某一侧。

<!-- SHAP_GEODETECTOR_COMPARISON_TABLE -->

## 9. 可写入论文或报告的结论段

地理探测器结果表明，GPP 和 RECO 恢复时间的空间分异主要受热量、辐射和大气干旱条件共同控制，其中 RECO 对 TMP、SSRD、STRD 和 VPD 的空间分层响应整体强于 GPP，尤其在 Grassland、Savanna 和 Shrubland 中表现突出。交互探测进一步显示，多数变量组合呈现双因子增强或非线性增强，说明干旱后碳通量恢复并非由单一气候因子线性驱动，而是由能量供给、水分胁迫、蒸散需求和植被状态共同调节。该结果为空间层面验证 SHAP dependence、ALE、ICE 和 PDP 所揭示的非线性响应及阈值特征提供了独立证据。
