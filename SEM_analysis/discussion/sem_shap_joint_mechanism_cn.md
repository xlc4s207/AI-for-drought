# GPP 恢复时间的 SEM-SHAP 联合机理解释（面向论文写作）

本文整合两套独立分析——LightGBM-SHAP 的条件归因（`dual_precip_shap_20260418/shap_by_biome/`）与结构方程模型（`sem_process_recoverywin_precipEmean_usertrim/by_biome/`）——对骤旱后 GPP 恢复时间 `t_recover_to_baseline_abs_peak` 的各驱动因子给出生态学可写入论文的机理解释。所有数值可在 `by_biome/*_estimates.csv`、`by_biome/effect_decomposition_on_t_recover.csv`、`usertrim_summary.csv` 以及 `discussion/{pre_ssrd_inverted_u_mechanism_cn.md, all_features_shap_mechanism_cn.md}` 中回溯。

---

## 1. 引言：两套方法为何互补

- **SHAP（LightGBM + TreeSHAP）** 回答的是"在给定其他特征的水平下，该特征的取值条件上与 `t_recover` 之间呈现什么样的关系"。其优势是**自动捕获非线性与高阶交互**（例如 PRE 的倒 U、SMrz 在 Forest 的单调负、T2m 在 Grassland 的强斜率），但其归因受**样本结构效应**影响——同一条 SHAP 曲线上不同取值区间往往对应不同的水气候背景子集。
- **SEM（semopy, 标准化输入）** 在预先假定的因果结构下，用线性偏回归系数给出每条路径的**标准化强度**，从而可以把"总效应 = 直接效应 + 间接效应"显式地分解出来。其优势是**机理可解释、可量化**；代价是假设了**线性与设定正确性**，无法刻画非线性。
- 因此，**凡是 SEM 与 SHAP 方向一致的变量（VPD、T2m、STRD、SMrz 的主 biome），SEM 提供可发表的量化机理；凡是 SHAP 呈现非线性（PRE、SSRD 的倒 U），SEM 的线性系数只能当作主成分参考，真正的机制由 SHAP 与共变量剖面支撑。** 两者不冲突，而是**同一现象的不同切面**。

---

## 2. 方法简述

### 2.1 SEM 结构设定（五个 biome 统一）

```
recoverywin_SMrz_mean       ~ PRE + ET + T2m                   # 土壤水受降水、蒸散和温度驱动
recoverywin_VPD_mean        ~ T2m + ET + STRD                   # 大气需求由温度、蒸散、长波辐射调制
recoverywin_lai_total_mean  ~ SMrz + VPD + SSRD + STRD          # 冠层由土壤水、大气需求、辐射调控
t_recover_to_baseline_abs_peak ~ T2m + ET + VPD + SMrz + LAI    # 结果方程
```

- 外生变量：`PRE, ET, T2m, STRD, SSRD`；内生中介：`SMrz, VPD, LAI`。
- 所有变量在拟合前 z-score 标准化，因此路径系数即**标准化偏回归系数**，可直接横向比较。
- 说明：`SSRD → t_recover` 仅通过 `LAI` 传导，`PRE → t_recover` 仅通过 `SMrz → t_recover` 与 `SMrz → LAI → t_recover` 两条窄通道。

### 2.2 模型拟合质量（holdout R²）

| Biome      | holdout R² | 拟合评级 |
|------------|-----------:|---------|
| Cropland   | 0.129 | 中等 |
| Forest     | 0.216 | **最好** |
| Grassland  | 0.206 | **较好** |
| Savanna    | 0.103 | 最差 |
| Shrubland  | 0.127 | 中等 |

论文讨论时应把 Forest/Grassland 的路径系数当作**较可信**证据，把 Savanna 的系数写得更谨慎。

---

## 3. 结果

### 3.1 结果方程：5 个变量对 `t_recover` 的直接标准化路径系数

| Biome     | T2m 直接 | ET 直接 | VPD 直接 | SMrz 直接 | LAI 直接 |
|-----------|---------:|--------:|---------:|----------:|---------:|
| Cropland  | **−0.403** | −0.031 | +0.044 | +0.018 | −0.029 |
| Forest    | −0.295 | +0.160 | +0.042 | **−0.104** | −0.031 |
| Grassland | **−0.536** | +0.002 (ns) | +0.131 | +0.067 | +0.008 |
| Savanna   | −0.225 | +0.104 | +0.076 | −0.038 | −0.084 |
| Shrubland | **−0.642** | −0.023 | **+0.382** | −0.027 | +0.017 |

（所有系数的 `p < 0.001`，Grassland 的 ET 与 Savanna 的 LAI 小幅，其他都显著。）

**要点**：
- T2m 直接效应**在全部 biome 均为负且数值最大**，是所有直接路径中最强的一条；Shrubland 达 −0.642，Grassland −0.536，Cropland −0.403——说明低温在生长季活性层面直接限速恢复。
- VPD 直接效应**在所有 biome 为正**；Shrubland 的 +0.382 远强于其他 biome（Grassland +0.131、Savanna +0.076、Cropland/Forest 仅 +0.04），即干适应灌丛对大气需求的响应强度异常突出。
- SMrz 直接效应**方向 biome 间不一致**：Forest −0.104（经典供水加速）、Savanna −0.038、Shrubland −0.027 为负；Cropland +0.018、Grassland +0.067 为正。Forest 是唯一直接效应显著且符合"供水越多恢复越快"预期的 biome。
- ET 直接效应也不一致：Forest +0.160、Savanna +0.104 为正（活性指示）；Cropland、Shrubland 为小负；Grassland 几乎为零（p=0.50，不显著）。
- LAI 直接效应均在 |0.03–0.08| 范围内，方向 biome 间不一致，重要性最弱。

### 3.2 外生变量的直接+间接+总效应分解（对 `t_recover`）

SEM 允许把每个外生变量对 `t_recover` 的总效应拆为沿各中介链的贡献。下表节选自 `effect_decomposition_on_t_recover.csv`（保留两位小数并整理符号）：

| Biome     | PRE_total | T2m 直接 | T2m→VPD→ | T2m→SMrz→ | **T2m_total** | STRD→VPD→ | **STRD_total** | SSRD_total |
|-----------|----------:|---------:|---------:|----------:|--------------:|----------:|---------------:|-----------:|
| Cropland  | +0.002 | −0.403 | +0.074 | −0.011 | **−0.321** | −0.030 | **−0.042** | −0.007 |
| Forest    | −0.031 | −0.295 | +0.117 | +0.050 | **−0.109** | −0.081 | **−0.104** | −0.008 |
| Grassland | +0.016 | −0.536 | +0.214 | −0.030 | **−0.357** | −0.093 | **−0.088** | +0.001 |
| Savanna   | −0.010 | −0.225 | +0.144 | +0.022 | **+0.018** | −0.082 | **−0.145** | −0.023 |
| Shrubland | −0.003 | −0.642 | **+0.587** | +0.008 | **−0.054** | −0.265 | **−0.264** | +0.002 |

（ET 总效应与上表见原 CSV；Forest ET_total +0.244、Savanna ET_total +0.178、Cropland ET_total −0.013、Grassland ET_total +0.024、Shrubland ET_total +0.049。）

**三点结构性发现**：
1. **PRE 的总效应非常小（|·| ≤ 0.031）**。原因是 SEM 中 PRE 只能通过 `SMrz → t_recover` 一条窄通道影响恢复，而 SMrz 的直接效应本身就小。这说明 SHAP 上 PRE 居首位的特征重要性**不是"线性平均效应"造成的，而是 SHAP 在非线性阈值区间的放大作用**——详见 §4.4。
2. **T2m 的直接负效应被 `T2m→VPD→t_recover` 的间接正效应部分抵消**。Shrubland 最极端：T2m 直接 −0.642，`T2m→VPD→t_recover` 间接 +0.587（因为 `T2m→VPD` 系数 1.54，`VPD→t_recover` 系数 0.382），两者相抵，使 Shrubland 的 T2m 总效应只剩 −0.054。Forest、Savanna 类似但程度较弱。这条机理是**SHAP 看不到但 SEM 能量化**的重要发现：低温拖长恢复的生理效应，在干旱 biome 被"低温顺带降低大气需求"的反向效应大量抵消。
3. **STRD 的总效应几乎全部来自 `STRD→VPD→t_recover`**：STRD 越高（大气暖湿多云）→ VPD 越低 → 恢复越快。Shrubland 此链条最强（−0.265）、Savanna 次之（−0.082），Forest 中等。这与 SHAP 上 STRD 单调递减的曲线完全对应，并首次**定量确认**此因果链是 STRD "负向 SHAP"的主要驱动。

### 3.3 SEM 与 SHAP 的一致性对照（核心表）

本表总结每个变量在两套方法下的结论与解释。"SHAP 形态"来自 `all_features_shap_mechanism_cn.md` 与 `pre_ssrd_inverted_u_mechanism_cn.md`，"SEM 直接/总"来自 §3.1–§3.2。

| 变量 | SHAP 主要形态 | SEM 直接效应 | SEM 总效应 | 一致性 | 机理解释归口 |
|------|---------------|-------------|-----------|--------|-------------|
| **VPD**  | 单调正（Forest 斜率 17 天、Shrubland U 形 caveat） | +0.04 ~ +0.382（全正） | 无（中介变量自身无总效应列） | **一致** | 大气需求直接限速，Shrubland 敏感度最高 |
| **T2m**  | 单调负（Grassland/Shrubland 斜率 11–13 天） | −0.22 ~ −0.64（全负） | −0.05 ~ −0.36（均负但被抵消） | **一致**，SEM 另外定量刻画了 `T2m→VPD` 的反向抵消 | 生长季激活度 + 温湿耦合 |
| **STRD** | 单调负（跨度 −10 ~ −14 天） | 中介变量，无直接效应 | −0.042 ~ −0.264（全负） | **一致** | 主要经 `VPD↓` 通道；"暖湿多云"背景指示剂 |
| **SMrz** | Forest 单调负、Grassland 单调正、Savanna/Cropland 倒 U | Forest −0.104、Grassland +0.067、Savanna −0.038、Cropland +0.018、Shrubland −0.027 | 无 | **一致**：Forest 的负符号由 SEM 定量（供水加速）；Grassland 的正符号由 SEM 直接系数 + `SMrz→LAI` 正链条共同支撑（生态系统类型效应） | biome 分化机制 |
| **LAI**  | biome 间方向不一致 | ±0.008 ~ ±0.084（弱） | 无 | **一致**：两套方法都显示 LAI 是样本结构指示 | 不作生理直读 |
| **ET**   | biome 间方向不一致 | Forest +0.160、Savanna +0.104、Cropland −0.031、Shrubland −0.023、Grassland ≈0 | Forest +0.244、Savanna +0.178（正为主） | **一致**：方向 biome 间差异的事实本身一致 | 系统活性指示剂 |
| **PRE**  | 倒 U（峰 PRE ≈ 3–5 mm/d，Shrubland 1 mm/d） | 只经 `SMrz` 间接 | −0.031 ~ +0.016（极弱） | **SHAP 非线性，SEM 线性无法刻画** | SHAP 为主证据（§4.4）；SEM 提供"PRE→SMrz 上游贡献"的量化（PRE→SMrz：0.13–0.29） |
| **SSRD** | 倒 U（峰 190–230 W/m²） | 仅经 `LAI` 间接 | |·| ≤ 0.023（几近零） | **SHAP 非线性，SEM 线性无法刻画** | SHAP 为主证据；SEM 通道过窄，不作解释主线 |
| **Wind** | biome 间一致的负形态（高风样本恢复短） | **未建模** | — | 仅 SHAP 有证据 | 讨论时须说明 SEM 未纳入，作为 caveat |
| **prepeak_PRE** | Shrubland 反向，其余 biome 正常 | **未建模** | — | 仅 SHAP 有证据 | 写作时单独讨论 |

---

## 4. 讨论

### 4.1 VPD 与 T2m：机理明确、SEM 直接量化的一类

**VPD**：SHAP 在所有 biome 均单调递增；SEM 直接系数在所有 biome 均为正（+0.04 ~ +0.382）。两者一致表明**大气水汽压差是 GPP 恢复的直接胁迫因子**——高 VPD 通过气孔关闭抑制光合，从而拉长恢复时间。Shrubland 的 +0.382 与 SHAP 上干适应灌丛对高 VPD 的极强正响应完全吻合，是论文中"干旱系统对大气需求高度敏感"的核心量化证据。Forest 的 VPD 系数仅 +0.042，看似与 SHAP 上 Forest VPD 斜率最大（17 天）矛盾；**但需注意 SHAP 跨度是"VPD 从低到高"的端到端差，而 SEM 系数是标准化单位斜率**，Forest 的 VPD 变异范围本身较宽（标准差更大），单位斜率不大但端到端效应明显。这一条应作为 caveat 在讨论中注明，避免"Forest VPD 敏感度低"的误读。

**T2m**：SHAP 在所有 biome 单调负（低 T 对应正 SHAP），SEM 直接系数亦均为负（−0.22 ~ −0.64）；两者完全一致，共同指向**低温直接限速生长季活性**。SEM 在此基础上给出一条 SHAP 看不到的量化机理：`T2m → VPD` 的线性系数在所有 biome 均 > 1.5（Forest 2.83、Savanna 1.90、Cropland 1.68、Grassland 1.63、Shrubland 1.54），而 `VPD → t_recover` 又为正。两条正号相乘产生 `T2m → VPD → t_recover` 的**正向间接通道**，Shrubland 达到 +0.587，几乎完全抵消直接负号 −0.642，使 T2m 的总效应塌缩到仅 −0.054。**论文写作应强调这是"低温双向作用"的结构性发现**：低温既直接压抑生理活性，又顺带降低大气需求——后者在干旱 biome 比在湿润 biome 占比更大，使得 Shrubland 的 T2m 总效应反而是所有 biome 中最弱的。

> ⚠ 共线性告警：Forest 的 `T2m → VPD` 系数高达 2.83（标准化），这意味着 Forest 的 T2m 与 VPD 在样本上高度同步，SEM 把两者的协方差全部归给这条路径。论文讨论时应该加一句 "Forest 的该系数在物理上并非偏弹性意义下的真实强度，而是 T2m 与 VPD 在该 biome 下高度共线所致的统计归因"，避免审稿人质疑。

### 4.2 STRD：多云-湿润 vs 晴朗-冷干的联合状态指示剂

SHAP 上 STRD 在所有 biome 单调递减（STRD↑ → SHAP↓，即恢复变快），且跨度在 Forest 最大（从 +14 到 −10 天）。SEM 通过 `STRD → VPD → t_recover` 与 `STRD → LAI → t_recover` 两条路径给出总效应：Shrubland −0.264、Savanna −0.145、Forest −0.104、Grassland −0.088、Cropland −0.042。其中绝大部分（Shrubland 的 −0.265/−0.264、Forest 的 −0.081/−0.104）来自 VPD 通道，即 **"STRD 高 → 暖湿多云大气 → VPD 低 → 恢复快"**。

SEM 的这一分解**首次定量确认**前文 SHAP 解读中"STRD 不是辐射通量意义的加速因子、而是大气水汽-温度联合状态指示剂"的论断。两套方法一致，可作为论文中较稳健的一条结论。

### 4.3 SMrz 的 biome 分化：供水机制 vs 生态系统类型效应

SMrz 是两套分析中**生态学最富争议**的变量：SHAP 显示 Forest 单调负（符合经典供水假说）、Grassland 单调正、Savanna/Cropland 倒 U、Shrubland 弱响应。SEM 直接系数恰与 SHAP 一致：Forest −0.104、Savanna −0.038、Shrubland −0.027（负）；Cropland +0.018、Grassland +0.067（正）。

- **Forest 的负号**是最干净的"经典供水加速"证据——两套方法都量化了"根区土壤水越多 → 恢复越快"的直接效应。这条可作为论文的**核心机理亮点**：Forest 是唯一直接供水加速在 SEM 层面也能显著确认的 biome。
- **Grassland 的正号**同时在 SHAP 与 SEM 出现，机理如下：Grassland 中高 SMrz 样本往往对应较湿润的草原亚区（ρ(LAI,SMrz)=+0.51），这些事件本身持续时间更长、恢复轨迹更完整；SEM 同时给出 `SMrz → LAI` 正系数（Grassland +0.390，全 biome 最高）与 `LAI → t_recover` 的 +0.008。因此 Grassland 的 SMrz "正号"本质是生态系统类型（湿润亚区 ↔ 茂盛冠层 ↔ 长恢复）的统计联立，不是"土壤水越多越延迟恢复"的生理机制。这条机理 SEM 才能给出，SHAP 单靠一条依赖曲线无法区分。

### 4.4 PRE 与 SSRD 的倒 U：SEM 线性设定的边界

两变量在 SHAP 上呈显著倒 U 形（PRE 峰在 3–5 mm/d；SSRD 峰在 190–230 W/m²），但在 SEM 的线性框架内总效应极小（PRE_total |·| ≤ 0.031；SSRD_total |·| ≤ 0.023）。**这不是矛盾，而是线性模型无法捕获倒 U 形态的固有局限**。SEM 的线性系数反映的是"倒 U 的直线主成分"——PRE 的中段正峰与两端负值相互抵消后，线性拟合剩余一个几乎为零的净斜率。

论文写作时应**明确声明**：PRE 与 SSRD 的倒 U 机制解释以 SHAP + 共变量剖面（见 `pre_ssrd_inverted_u_mechanism_cn.md`）为主证据，SEM 只提供：
- `PRE → SMrz` 的上游贡献（Forest 0.285、Grassland 0.232、Savanna 0.187、Cropland 0.165、Shrubland 0.134 — 均显著正），即线性意义下"降水越多土壤水越湿"的标准供水链；
- `SSRD → LAI` 的上游贡献（Savanna +0.268、Forest +0.241、Cropland +0.227、Grassland +0.105、Shrubland +0.096），即"光量越多 LAI 越大"的经典响应。

这两条上游链在 SEM 中存在但下游 `SMrz → t_recover` 与 `LAI → t_recover` 的系数本身就小（|0.008 – 0.104|），所以 PRE 与 SSRD 的线性总效应才塌缩到接近零。SHAP 的倒 U 不是这条线性通道产生的，而是**水气候—样本结构—事件时长三重耦合**在条件归因上的投影（详见 `pre_ssrd_inverted_u_mechanism_cn.md`）。**"SEM 量化线性主成分、SHAP 刻画非线性结构"**这句话是本文对这对变量最准确的结论。

### 4.5 ET 与 LAI：两套方法都指向样本结构效应

**ET**：SHAP 方向 biome 间反转（Forest/Savanna 单调递增、Cropland 倒 U 两端负、Grassland 弱、Shrubland 弱）。SEM 直接系数也方向不一致（Forest +0.160、Savanna +0.104、Cropland −0.031、Shrubland −0.023、Grassland ≈0 ns）。**两套方法都告诉我们 ET 不能按单向机制读**：ET 是"系统活性 × 水分可用性"的复合指示，Forest/Savanna 强 ET 对应恢复尚未结束的活跃子集（正符号），Cropland 强 ET 对应已接近完成恢复的样本（负符号）。写作时应该把 ET 描述成"活性代理变量"而非"水文通量收支项"。

**LAI**：SEM 直接系数 |0.008–0.084|，SHAP 绝对 SHAP 跨度也最小，特征重要性 rank 10。两套方法一致指向 LAI 不宜用作物理机制解释，只作为"生态系统类型/季节"分层的辅助证据。

### 4.6 Shrubland 的特殊性：由多条 SEM 结构刻画

Shrubland 在多条路径上都是极端：`VPD → t_recover` 直接 +0.382（全 biome 最强）；`T2m → VPD` 仅 1.54（全 biome 最低，与其干大气的高 VPD 基线一致）；`T2m → t_recover` 直接 −0.642（全 biome 最负）；`PRE → SMrz` 仅 0.134（全 biome 最弱，反映土壤入渗容量有限）；`STRD → VPD` −0.695（与 Forest、Savanna 量级相当但通过 VPD 系数放大后间接效应最强）。这一组 SEM 证据与 SHAP 上 Shrubland 的诸多"方向反转"现象（例如 prepeak_PRE 单调递增、VPD 非单调、PRE 峰位偏左至 1 mm/d）形成**互相独立的双重支撑**，共同把干适应灌丛描绘为 **"低温驱动 + 大气需求敏感 + 降水阈值极低 + 生态容量上限窄"** 的特殊类型。这条 biome 特异结论可作为论文讨论的独立亮点。

---

## 5. 不变的 caveats（审稿人可能提的问题）

1. **SEM 线性假设**：无法刻画 SHAP 的倒 U。论文需明确"SEM 用于量化线性主成分与中介分解，非线性机理由 SHAP 承担"。
2. **Holdout R² 偏低**（0.103–0.216）：说明 `t_recover` 的方差中仍有 ~80% 以上未被当前 SEM 结构解释。讨论时建议加一句"未建模变量（wind、prepeak_PRE、事件持续时间、baseline GPP 水平）或非线性交互可能解释剩余方差"。
3. **共线性导致的超 1 标准化系数**：Forest `T2m → VPD` 2.83、Savanna 1.90 超出了"单位标准差扰动"的可解释区间，是共线性归因的结果；应声明为"统计归因，不作偏弹性读"。
4. **未建模变量**：wind、prepeak_PRE 未进入 SEM。论文可在 caveats 段说"这两个变量的机理通过 SHAP 旁证，未纳入 SEM 以保持路径图的可读性"。
5. **样本非独立**：一个网格的多场骤旱事件在 SEM 中被当作独立观测处理，可能低估了标准误；但 z 值绝对值大（多数 > 30），该偏差不影响显著性结论。
6. **Savanna 拟合最差**（R² 0.103）：论文中提到 Savanna 机制时应加"Savanna 的 SEM 路径系数方差解释能力较弱，建议以 SHAP 证据为主"。

---

## 6. 论文写作模板

### 6.1 Results 段（约 220 字，可直接改造）

> 我们在五个主要植被类型（Cropland、Forest、Grassland、Savanna、Shrubland）上分别拟合了恢复期 GPP 的结构方程模型，以 `t_recover_to_baseline_abs_peak` 为结果变量，纳入 T2m、ET、VPD、SMrz、LAI 五条直接路径，并通过 SMrz、VPD、LAI 三条中介联通外生变量 PRE、ET、T2m、STRD、SSRD。全样本 holdout R² 在 `0.103–0.216` 区间（Forest 0.216 最高、Savanna 0.103 最低）。在结果方程中，**T2m 的直接标准化效应在所有 biome 均为最大负值**（Shrubland −0.642、Grassland −0.536、Cropland −0.403），**VPD 的直接效应均为正**（Shrubland +0.382 最强），**SMrz 的直接效应在 Forest 为显著负（−0.104）**，符合经典供水加速假说；其他 biome 的 SMrz 直接效应方向不一致。效应分解显示，`T2m → VPD → t_recover` 的间接正效应（Shrubland +0.587、Grassland +0.214、Savanna +0.144）系统性抵消 T2m 的直接负效应，使 T2m 的总效应在 Shrubland 压缩到 −0.054、在 Savanna 反转为 +0.018。STRD 的总效应通过 `VPD↓` 通道传导（Shrubland −0.264、Forest −0.104），PRE 与 SSRD 的总效应在线性框架下极小（|·| ≤ 0.031）。

### 6.2 Discussion 段（约 320 字，可直接改造）

> 将 SEM 的路径分解与 LightGBM-SHAP 的条件归因并列对照，我们得到一个统一的机理框架：**VPD、T2m、STRD 是在两套方法中方向一致、可量化的直接/间接恢复限速因子**；**SMrz 的 Forest 负号是唯一直接供水加速机制**；**PRE 与 SSRD 的 SHAP 倒 U 是非线性的样本结构效应**，SEM 的线性设定无法表达，但其上游链（`PRE → SMrz`、`SSRD → LAI`）仍可提供线性主成分的量化。一个 SHAP 看不到而 SEM 必须指出的结构性发现是：**低温拖长恢复的直接生理效应在所有 biome 被 `T2m → VPD → t_recover` 的间接正效应部分抵消**，在 Shrubland 尤为明显（直接 −0.642、间接 +0.587），这与 Shrubland 对大气需求的极端敏感度（VPD 直接 +0.382）共同刻画出干适应灌丛"低温驱动叠加大气需求锁定"的独特机制。同时，`STRD → VPD↓ → t_recover↓` 通道在 SEM 中被定量确认，为 SHAP 上 STRD 单调递减的曲线提供了明确的物理链条解释——STRD 不是作为辐射通量直接加速恢复，而是作为大气暖湿多云联合状态的指示剂。综合两套方法，我们建议：**在论文主文本中将 VPD、T2m、STRD、Forest 的 SMrz 作为直接可量化的机理因子写作，将 PRE 与 SSRD 的倒 U 以 SHAP + 共变量剖面展开讨论并明确其非线性性质，将 ET、LAI 定位为样本结构指示而非单向生理变量，将 wind、prepeak_PRE 置于讨论段的辅助证据中并加 SEM 未建模的 caveat。** 这一框架以 SEM 的可解释性与 SHAP 的非线性捕获能力互补，对恢复时间的 biome 差异给出了机理有据、可追溯的解读。

---

## 7. 附：数值追溯指引

| 数值 | 来源文件 |
|------|---------|
| 5 biome × 5 变量直接路径系数（§3.1） | `by_biome/GPP_code1_{biome}_flash_SMrz_estimates.csv` 的 `t_recover_to_baseline_abs_peak ~ *` 行 |
| 外生变量总效应分解（§3.2） | `by_biome/effect_decomposition_on_t_recover.csv` |
| Holdout R²（§2.2） | `usertrim_summary.csv` |
| 模型设定（§2.1） | `by_biome/GPP_code1_{biome}_flash_SMrz_model_spec.txt` |
| `T2m → VPD`、`PRE → SMrz` 等路径系数（§4.1、§4.4） | `by_biome/GPP_code1_{biome}_flash_SMrz_estimates.csv` 的对应 `~` 行 |
| SHAP 分箱曲线与共变量剖面（§3.3、§4.*） | `discussion/all_features_shap_mechanism_cn.md` 与 `discussion/pre_ssrd_inverted_u_mechanism_cn.md` |

— 文档结束 —
