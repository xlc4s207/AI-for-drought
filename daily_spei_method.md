# 日尺度 SPEI（daily SPEI）计算方法（已知 P 与 PET）

> 参考文献：Wan et al., 2023（Science of the Total Environment）提出/使用了**日尺度 SPEI** 来刻画短时旱情，并说明 SPEI 的核心是 **P 与 PET 的差值**，以及其在本文中采用 **GEV（Generalized Extreme Value）分布**来标准化得到 daily SPEI。fileciteturn1file7L5-L18

---

## 1. 你现在的数据与目标

### 1.1 输入（你已有）
- 日降水：`P(t)`（单位通常为 mm/day）
- 日潜在蒸散：`PET(t)`（单位通常为 mm/day）

> 文献中 PET 是用 Hargreaves 模型估算的（需要温度与辐射），但**如果你已拥有 PET**，可以直接进入 SPEI 计算流程；关键是保证 P 与 PET **单位一致、时间尺度一致（都为日）**。fileciteturn1file7L5-L16

### 1.2 输出（你要算）
- 日尺度 SPEI：`SPEI_k(t)`  
  其中 `k` 是累积时间尺度（例如 30 天、90 天等）。文献示例中 daily SPEI **采用 30 天尺度**。fileciteturn1file4L18-L23

---

## 2. 计算思想概览（从水分盈亏到标准化指数）

SPEI 的基本流程可以概括为：

1) **水分盈亏序列**：  
\$\$D(t) = P(t) - PET(t)\$\$

2) **k 天尺度累积（或滑动和）**：  
\$\$X_k(t)=\sum_{i=0}^{k-1} D(t-i)\$$  
- 若 `k=30`，则 `X_30(t)` 表示“截至 t 日、前 30 天累计水分盈亏”。
- 文献中在分析干旱期气候因子时也采用“当前日 + 前 29 天”的 30 天聚合思路来与 30 天 SPEI 尺度对齐。fileciteturn1file4L18-L27

3) **对 \(X_k(t)\) 做概率分布拟合，并把概率映射到标准正态**：  
- 文献说明 daily SPEI 最终基于 **GEV 分布**得到。fileciteturn1file7L16-L18  
- 标准化思想：先得到 \(p = F_{GEV}(x)\)，再计算  
\$\$\mathrm{SPEI}=\Phi^{-1}(p)\$$  
其中 \(\Phi^{-1}\) 是标准正态分布的反函数（ppf）。

---

## 3. 关键细节：日尺度的“季节性分布拟合”怎么做？

月尺度 SPEI 通常会按月分别拟合分布（1 月一套参数，2 月一套参数……），以处理季节性。  
日尺度 SPEI 通常也需要类似处理：**同一年中的不同日（DOY）分布不同**，如果把全年混在一起拟合，会把季节性当成“异常”。

工程上常见的 daily SPEI 做法（也与“日尺度、多时间尺度”思路一致）是：

### 3.1 以“年内日序 DOY”为分组单位拟合
- 令 `d = doy(t)` 为 t 的年内日序（1…365/366）
- 收集所有年份中同一 DOY 的 \(X_k(t)\) 样本（可选：再加一个 DOY 邻域窗口来增大样本量，例如 ±15 天）
- 对每个 DOY 分组的样本拟合 **GEV 分布参数**（形状 ξ、尺度 σ、位置 μ）
- 用拟合好的 \(F_{GEV,d}(\cdot)\) 去算当天的累计盈亏 \(x=X_k(t)\) 的概率 \(p\)

> 文献指出 daily SPEI 的拟合与计算细节可参考 Wang et al. (2021a)。本 md 文档给出的是可复现的“日尺度+季节分组拟合”的通用实现路线。fileciteturn1file7L16-L18

### 3.2 概率到标准正态的转换（得到 SPEI）
- 计算：\(p = F_{GEV,d}(x)\)
- 为避免 \(p=0\) 或 \(p=1\) 导致无穷大，可做截断：  
  \(p \leftarrow \min(\max(p, \epsilon), 1-\epsilon)\)（例如 \(\epsilon=10^{-6}\)）
- 得到：\(\mathrm{SPEI}(t)=\Phi^{-1}(p)\)

---

## 4. 计算步骤（给你一套可直接落地的流程）

### Step 0｜预处理与检查
- P 与 PET 的单位必须一致（常用 mm/day）
- 时间序列必须连续：缺测会影响滑动累积与分布拟合
- 若有闰年：DOY=366 的处理可采用
  - 将 2 月 29 日并入 DOY=59/60 的邻域窗口，或
  - 单独拟合 DOY=366（样本会少）

### Step 1｜计算日水分盈亏 \(D(t)\)
\$\$D(t)=P(t)-PET(t)\$$

### Step 2｜计算 k 天尺度累计序列 \(X_k(t)\)
\$\$X_k(t)=\sum_{i=0}^{k-1}D(t-i)\$$
- 你要做“30 天日尺度 SPEI”，就取 `k=30`（与文献一致）。fileciteturn1file4L18-L23
- `t<k` 的前 k-1 天无法得到完整累计，可设为 NA 或用较短窗口（建议 NA，保持定义一致）。

### Step 3｜按 DOY（可带邻域窗口）拟合 GEV
对每个 DOY = d：
1. 取样本集合  
   \(\mathcal{S}_d = \{X_k(t): doy(t)\in[d-w, d+w]\}\)（环形处理年内边界）
2. 用最大似然等方法拟合 GEV 参数
3. 得到分布函数 \(F_{GEV,d}(\cdot)\)

推荐经验值：
- 年限 ≥ 30 年：可用 `w=0`（每个 DOY ~30 个样本）
- 年限较短：建议 `w=7~15` 增大样本量（牺牲一点季节分辨率换稳定性）

### Step 4｜逐日计算概率并标准化得到 SPEI
对每个 t：
1. d = doy(t)，x = X_k(t)
2. p = \(F_{GEV,d}(x)\)
3. SPEI(t) = \(\Phi^{-1}(p)\)

### Step 5｜（可选）干旱事件识别：Runs theory
文献在识别干旱事件时采用 runs theory：
- **阈值**：SPEI < -0.5 视为进入干旱状态；fileciteturn1file7L23-L27
- **最小持续**：若连续低于阈值少于 3 天，剔除；连续 ≥3 天才算一次干旱事件。fileciteturn1file7L28-L33

在此基础上可计算：
- 年干旱持续天数（ADD）：一年内所有干旱日数之和 fileciteturn1file7L34-L38
- 年干旱强度（ADS）：一年内干旱期间 |SPEI| 的累加 fileciteturn1file7L38-L40

---

## 5. 你“只有 P 和 PET”的情况下，最容易踩的坑

1) **P 与 PET 时间戳不对齐**：例如 P 是 00–24 时累计，PET 是 08–08 时日值。必须统一“日”的定义。  
2) **单位或尺度混用**：P(mm/day) vs PET(mm/month) 会直接毁掉结果。  
3) **分布拟合没做季节分组**：把全年 X_k 混在一起拟合，会把季节差异误判为干湿异常。  
4) **样本量不足导致 GEV 不稳定**：年份少时请用 DOY 邻域窗口（w>0）或改用更稳健的分布/经验分布。  
5) **极端概率导致无穷大**：务必对 p 做 epsilon 截断再做正态反函数。

---

## 6. 最小伪代码（语言无关）

```text
input: P[t], PET[t], dates[t], scale k, doy_window w
D[t] = P[t] - PET[t]

Xk[t] = rolling_sum(D, window=k)   # 过去 k 天累计；前 k-1 天为 NA

for doy d in 1..365(366):
    Sd = { Xk[t] where doy(dates[t]) in [d-w, d+w] (cyclic) and Xk[t] not NA }
    fit GEV(d) on Sd  -> params[d]

for each t with Xk[t] not NA:
    d = doy(dates[t])
    p = CDF_GEV(Xk[t] | params[d])
    p = clip(p, eps, 1-eps)
    SPEI[t] = inv_norm_cdf(p)
output: SPEI[t]
```

---

## 7. 与本文（Wan et al., 2023）的一致性说明

- SPEI 的核心：用降水与潜在蒸散之差来表征干湿（P - PET）。fileciteturn1file7L5-L6  
- 文献示例采用 30 天尺度 daily SPEI（便于刻画短时干旱并确定年内干旱期）。fileciteturn1file4L18-L23  
- 文献明确 daily SPEI 的标准化基于 **GEV 分布**；更细的拟合细节指向 Wang et al. (2021a)。fileciteturn1file7L16-L18  
- 干旱事件识别使用 runs theory：阈值 -0.5、持续 ≥3 天。fileciteturn1file7L23-L33  

---

## 8. 你接下来可以怎么用我这套流程

如果你愿意把你的数据格式（例如 CSV 的列名、是否有缺测、是否闰年、想要 k=30 还是多尺度）告诉我，我可以基于这份方法把“数据清洗—计算—输出结果（含 SPEI 与干旱事件表）”的脚本也整理出来。
