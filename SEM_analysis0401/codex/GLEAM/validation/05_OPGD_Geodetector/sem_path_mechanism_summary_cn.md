# SEM 路径机制总结：GPP 与 RECO 恢复时间的结构方程机制

本文根据 SEM 路径机制图整理 GPP 与 RECO 恢复时间的主要路径结构。图中每一行对应一个 biome，左列为 `GPP-RT`，右列为 `RECO-RT`。已将图中路径系数整理为结构化表：

`process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/sem_path_mechanism_from_image.csv`

图中 biome 顺序为：

1. Forest
2. Grassland
3. Savanna
4. Cropland
5. Shrubland

## 1. 图中路径的含义

该 SEM 图用于解释恢复时间 `RT` 的结构性机制。路径箭头表示变量之间的标准化路径系数，红色/橙色路径表示正向效应，蓝色路径表示负向效应。星号表示显著性水平，其中 `***` 表示最显著，`**` 次之，`*` 较弱。

如果路径直接指向 `GPP-RT` 或 `RECO-RT`，则表示该变量对恢复时间的直接效应。正系数表示变量升高会延长恢复时间，负系数表示变量升高会缩短恢复时间。

## 2. 总体机制结构

整体上，GPP 和 RECO 的恢复时间不是由单一变量直接控制，而是由热量、辐射、大气干旱、蒸散和土壤水分共同构成的路径网络控制。最核心的结构可以概括为两条链条：

```text
STRD -> TMP -> VPD -> EVA -> RT
```

以及：

```text
SSRD -> TMP -> RT
```

此外还有一条水分补给路径：

```text
PRE -> SMrz -> EVA -> RT
```

和一条风速-大气干旱路径：

```text
Wind -> VPD -> EVA -> RT
```

这说明恢复时间的变化并不是简单由降水或温度单独决定，而是由能量输入、大气干旱、土壤水分和蒸散状态共同调节。

## 3. 稳定的中介路径

在所有 biome 和两个通量指标中，以下路径最稳定：

```text
STRD -> TMP
TMP -> VPD
VPD -> EVA
SMrz -> EVA
PRE -> SMrz
```

其中 `STRD -> TMP` 和 `TMP -> VPD` 表明长波辐射和温度共同塑造热量与大气干旱背景。`VPD -> EVA` 表明大气水汽亏缺增强会推动蒸散过程变化。`PRE -> SMrz -> EVA` 则说明降水首先影响根区土壤水分，再通过土壤水分调节蒸散状态。

因此，`EVA` 在该 SEM 结构中不是一个简单的外生变量，而是连接水分状态、大气干旱和恢复时间的重要中介变量。

## 4. 直接控制恢复时间的关键路径

直接进入 `GPP-RT` 或 `RECO-RT` 的主要路径包括：

```text
TMP -> RT
SSRD -> RT
EVA -> RT
Duration -> RT
Intensity -> RT
```

其中最稳定、最值得解释的是 `SSRD -> RT` 和 `EVA -> RT`。

### 4.1 SSRD 对恢复时间的负向直接效应

`SSRD -> RT` 在所有 biome 和两个通量指标中均为负向，说明短波辐射增强通常对应更短的恢复时间。其路径系数范围为：

```text
GPP:  -0.337 到 -0.228
RECO: -0.454 到 -0.231
```

RECO 中该负向效应更强，尤其在 Savanna 和 Forest 中较突出。该结果说明短波辐射不仅是 SHAP 中的重要预测变量，也通过 SEM 表现为稳定的恢复时间直接调节因子。

### 4.2 EVA 对恢复时间的负向直接效应

`EVA -> RT` 也在所有 biome 中表现为负向：

```text
GPP:  -0.162 到 -0.073
RECO: -0.158 到 -0.054
```

这说明蒸散状态较高时，恢复时间整体趋于缩短。但由于 `EVA` 同时受到 `VPD` 和 `SMrz` 的正向驱动，因此它更适合被解释为综合水热状态的中介变量，而不是单独的因果源头。

### 4.3 TMP 对恢复时间的 biome 差异效应

`TMP -> RT` 在多数自然或半自然 biome 中表现为正向效应，但在 Cropland 中表现为负向效应。该结果说明温度背景对恢复时间的直接效应不是简单的统一方向，而是受到生态系统类型和管理背景调节。在 Forest、Grassland、Savanna 和 Shrubland 中，较高 TMP 通常会延长恢复时间，可能因为升温增强 `TMP -> VPD` 路径，提高大气水汽亏缺和蒸散需求，使干旱后恢复过程承受更强水分压力。Cropland 中路径转为负向，则更可能反映农田系统的灌溉、作物物候、播收制度和人为管理过程改变了温度与恢复时间之间的关系。

```text
GPP:
Forest     0.107
Grassland  0.285
Savanna    0.112
Cropland  -0.081
Shrubland  0.175

RECO:
Forest     0.150
Grassland  0.176
Savanna    0.139
Cropland  -0.092
Shrubland  0.241
```

Cropland 中 `TMP -> RT` 的方向与其他 biome 不同，GPP 为 `-0.081`，RECO 为 `-0.092`。因此 Cropland 不能写成“温度延长效应较弱但同向”，而应明确写为“温度直接路径为负向”。在解释上，这并不意味着温度没有通过 `TMP -> VPD -> EVA` 产生间接水分胁迫，而是说明在控制 SSRD、EVA、Duration、Intensity 以及中介链条后，TMP 对农田恢复时间的剩余直接效应表现为缩短恢复时间。

### 4.4 Duration 和 Intensity 对恢复时间的分 biome 事件效应

`Duration -> RT` 和 `Intensity -> RT` 并非所有 biome 方向一致。Forest、Grassland 和 Cropland 中二者为负向，Savanna 和 Shrubland 中二者为正向。该结果说明事件属性的直接效应具有生态系统背景依赖性：在 Savanna 和 Shrubland 等干旱或半干旱系统中，事件持续更久、强度更高通常会延长恢复；而在 Forest、Grassland 和 Cropland 中，事件属性在控制水热背景和蒸散状态后表现为负向直接效应，可能反映更强事件通常伴随更明确的恢复判定边界、事件后水热条件补偿或农田管理干预等过程。因此事件变量不宜写成统一方向的机制变量，应分 biome 解释。

## 5. GPP 与 RECO 的差异

总体上，RECO 的路径结构比 GPP 更强，尤其体现在 `SSRD -> RT`、`TMP -> RT` 和部分事件变量路径上。

RECO 中 `SSRD -> RT` 的负向效应更强：

```text
RECO Forest:    -0.396
RECO Grassland: -0.362
RECO Savanna:   -0.454
RECO Cropland:  -0.231
RECO Shrubland: -0.387
```

这说明 RECO 恢复时间对辐射与能量背景更敏感。相比之下，GPP 的恢复时间虽然也受 SSRD 控制，但直接效应整体弱于 RECO。

RECO 在 Shrubland 中的 `TMP -> RT` 也较强，达到 `0.241`，说明干旱或半干旱生态系统中呼吸恢复过程对热量背景尤其敏感。

## 6. 分 biome 机制解释

### 6.1 Forest

Forest 中，GPP 和 RECO 都表现出清晰的能量-蒸散控制路径。`SSRD -> RT` 为负向，`EVA -> RT` 也为负向，说明辐射和蒸散状态提高有助于缩短恢复时间。RECO 中 `SSRD -> RECO-RT = -0.396`，强于 GPP 的 `-0.267`，说明森林呼吸恢复对短波辐射背景更敏感。

### 6.2 Grassland

Grassland 中，TMP 对 GPP 和 RECO 的直接正效应都较明显，分别为 `0.285` 和 `0.176`。同时，`SSRD -> RT` 显著为负，说明草地恢复时间受到热量延长效应与辐射缩短效应的共同控制。该结果与 SHAP/OPGD 中 TMP 和 SSRD 的重要性相互支持。

### 6.3 Savanna

Savanna 中，RECO 的 `SSRD -> RECO-RT = -0.454` 是所有 RECO 直接路径中最强的负向效应之一，说明稀树草原呼吸恢复对短波辐射特别敏感。与此同时，`VPD -> EVA` 和 `TMP -> VPD` 也较强，表明 Savanna 的恢复机制具有明显的热干耦合特征。

### 6.4 Cropland

Cropland 中，`TMP -> RT` 在 GPP 和 RECO 中均为负向，分别为 `-0.081` 和 `-0.092`，这是与其他 biome 最主要的差异。与此同时，`SSRD -> RT`、`EVA -> RT`、`Duration -> RT` 和 `Intensity -> RT` 也均为负向，说明农田恢复时间在控制中介过程后呈现较强的负向直接路径组合。该结果更适合解释为农田系统受到灌溉、作物物候、播收制度和人为管理过程调节，使温度和事件属性对恢复时间的直接效应不同于自然生态系统。

### 6.5 Shrubland

Shrubland 中，RECO 的 `TMP -> RECO-RT = 0.241`，`SSRD -> RECO-RT = -0.387`，同时 `PRE -> SMrz = 0.364`。这说明灌丛区恢复过程同时受到热量、大气干旱、辐射和土壤水分补给控制。该结果与 OPGD 中 Shrubland 的 SSRD、TMP、VPD 高解释力一致。

## 7. 与 SHAP 和 OPGD 的关系

这张 SEM 图适合解释路径方向和中介机制，而 SHAP 和 OPGD 分别回答不同问题：

- SHAP：哪些变量对模型预测恢复时间贡献最大。
- OPGD：哪些变量能够解释恢复时间的空间分层异质性。
- SEM：这些变量通过什么路径直接或间接影响恢复时间。

因此，三者可以形成一条完整证据链：

```text
SHAP 识别关键预测变量
-> OPGD 验证其空间分层解释力
-> SEM 解释其直接路径和中介路径方向
```

例如，`SSRD` 在 SHAP 和 OPGD 中均表现为重要变量，而 SEM 中 `SSRD -> RT` 在所有 biome 中均为负向，说明它不仅具有预测贡献和空间分层解释力，还具有稳定的直接路径方向。

`TMP` 在 SHAP 和 OPGD 中也较重要，但 SEM 显示其直接路径方向具有 biome 差异：Forest、Grassland、Savanna 和 Shrubland 中为正向，Cropland 中为负向。因此 TMP 不应被写成统一方向的热量背景因子，而应写成“受生态系统类型和管理背景调节的热量路径变量”。对自然或半自然生态系统，TMP 更偏延长恢复；对 Cropland，TMP 的剩余直接效应表现为缩短恢复。

## 8. 可用于论文的总结表述

综合 SEM、SHAP 与 OPGD 结果可以认为，GPP 和 RECO 恢复时间主要受热量-辐射-大气干旱-蒸散-土壤水分耦合路径调节。`SSRD` 和 `EVA` 对恢复时间表现出稳定负向直接效应，说明更强的辐射能量供给和更活跃的蒸散水热交换状态通常对应更短恢复时间；`TMP`、`Duration` 和 `Intensity` 则具有明显 biome 依赖性，其中 Cropland 的 `TMP -> RT` 为负向，是区别于其他 biome 的关键路径。RECO 的路径强度整体高于 GPP，尤其在 Savanna 和 Shrubland 中，说明生态系统呼吸恢复对能量和水分背景更敏感。
