# Data and Methods 公式 LaTeX 版

本文档整理自 `15_data_and_methods_cn.docx` 中 Data and Methods 部分涉及的主要公式。公式均改写为可直接用于 Markdown / LaTeX 的数学表达。

## 1. 骤旱识别与事件属性

土壤水分百分位降幅：

$$
\Delta S = S(p_{\mathrm{onset}}) - S(p_{20})
$$

骤旱发展速率：

$$
R_{\mathrm{onset}} = \frac{\Delta S}{D_{\mathrm{onset}}}
$$

其中：

$$
D_{\mathrm{onset}} = p_{20} - p_{\mathrm{onset}}
$$

事件强度，即 P20 以下土壤水分亏缺累积量：

$$
\mathrm{Intensity}
= \sum_{p=p_{20}}^{p_{\mathrm{end}}}
\max\left[0,\; P_{20}(p) - S(p)\right]
$$

骤旱判定条件可写为：

$$
S(p_{\mathrm{onset}}) > P_{40},\qquad
S(p_{20}) < P_{20},\qquad
D_{\mathrm{onset}} \leq 4\ \mathrm{pentads}
$$

土壤水分恢复条件可写为：

$$
S(p) \geq P_{20}
\quad \mathrm{for\ at\ least}\quad
2\ \mathrm{consecutive\ pentads}
$$

## 2. 碳通量异常与恢复时间

GPP 或 RECO 的标准化异常：

$$
Z_C(t) =
\frac{C(t)-\mu_{C,d}}{\sigma_{C,d}}
$$

灾前碳通量基线：

$$
B_C =
\operatorname{mean}\left[C_s(t)\right],
\qquad
t \in [t_{\mathrm{onset}}-30,\; t_{\mathrm{onset}}-1]
$$

恢复终点：

$$
t_{\mathrm{rec}} =
\min\left\{
t > t_{\mathrm{peak}}:
C_s(t+k) \geq 0.95 B_C,\;
k=0,1,2,3,4
\right\}
$$

恢复时间：

$$
T_{\mathrm{recovery}} =
N_{\mathrm{GS}}\left(t_{\mathrm{peak}}, t_{\mathrm{rec}}\right)
$$

其中，$C_s(t)$ 为 5 日平滑后的碳通量，$N_{\mathrm{GS}}$ 表示两个日期之间累计的生长季有效天数。

## 3. VPD 计算

饱和水汽压：

$$
e_s(T) =
0.6108 \exp\left(
\frac{17.27T}{T+237.3}
\right)
$$

水汽压亏缺：

$$
\mathrm{VPD} =
e_s(T_{\mathrm{air}}) - e_s(T_{\mathrm{dew}})
$$

其中，$T_{\mathrm{air}}$ 和 $T_{\mathrm{dew}}$ 以摄氏度表示，VPD 单位为 kPa。

## 4. SHAP 模型解释

单个事件恢复时间预测值的 SHAP 加性分解：

$$
f(\mathbf{x}_i) =
\phi_0 + \sum_{j=1}^{M} \phi_{ij}
$$

特征 $j$ 的 Shapley 值：

$$
\phi_j =
\sum_{S \subseteq F \setminus \{j\}}
\frac{|S|!(M-|S|-1)!}{M!}
\left[
f_{S \cup \{j\}}\left(\mathbf{x}_{S \cup \{j\}}\right)
- f_S\left(\mathbf{x}_S\right)
\right]
$$

特征 $j$ 的平均绝对 SHAP 重要性：

$$
I_j =
\frac{1}{n}
\sum_{i=1}^{n}
\left|\phi_{ij}\right|
$$

特征 $j$ 的相对贡献百分比：

$$
P_j =
\frac{I_j}{\sum_{k=1}^{M} I_k}
\times 100\%
$$

SHAP 值方向解释：

$$
\phi_{ij} > 0
\Rightarrow
\text{feature } j \text{ increases predicted recovery time}
$$

$$
\phi_{ij} < 0
\Rightarrow
\text{feature } j \text{ decreases predicted recovery time}
$$

## 5. 结构方程模型 SEM

一般结构方程：

$$
\boldsymbol{\eta}
=
\mathbf{B}\boldsymbol{\eta}
+ \boldsymbol{\Gamma}\boldsymbol{\xi}
+ \boldsymbol{\zeta}
$$

测量方程：

$$
\mathbf{y}
=
\boldsymbol{\Lambda}_y\boldsymbol{\eta}
+ \boldsymbol{\varepsilon}_y,
\qquad
\mathbf{x}
=
\boldsymbol{\Lambda}_x\boldsymbol{\xi}
+ \boldsymbol{\varepsilon}_x
$$

恢复时间的标准化路径回归表达：

$$
T_{\mathrm{recovery}}
=
\beta_0
+ \beta_1 \mathrm{SSRD}
+ \beta_2 \mathrm{STRD}
+ \beta_3 \mathrm{TMP}
+ \beta_4 \mathrm{VPD}
+ \beta_5 \mathrm{SMrz}
+ \beta_6 \mathrm{EVA}
+ \beta_7 \mathrm{Pre}
+ \beta_8 \mathrm{Duration}
+ \beta_9 \mathrm{Intensity}
+ \varepsilon
$$

直接效应与间接效应合成的总效应：

$$
\mathrm{Effect}_{\mathrm{total}}(X)
=
c'
+ \sum_m a_m b_m
$$

其中，$a_m$ 表示 $X \rightarrow M_m$ 的路径系数，$b_m$ 表示 $M_m \rightarrow T_{\mathrm{recovery}}$ 的路径系数，$c'$ 表示 $X$ 对恢复时间的直接效应。

## 6. PDP、ICE 和 ALE

偏依赖函数 PDP：

$$
\mathrm{PDP}_j(z)
=
\frac{1}{n}
\sum_{i=1}^{n}
f\left(z, \mathbf{x}_{i,-j}\right)
$$

个体条件期望 ICE：

$$
\mathrm{ICE}_{ij}(z)
=
f\left(z, \mathbf{x}_{i,-j}\right)
$$

累积局部效应 ALE：

$$
\mathrm{ALE}_j(z)
=
\int_{z_0}^{z}
\mathbb{E}\left[
\frac{\partial f(\mathbf{X})}{\partial x_j}
\;\middle|\;
x_j=s
\right]
\,ds
- \mathrm{constant}
$$

## 7. 地理探测器

地理探测器 $q$ 统计量：

$$
q =
1 -
\frac{
\sum_{h=1}^{L}
N_h \sigma_h^2
}{
N\sigma^2
}
$$

其中，$h$ 表示分层类别，$N_h$ 和 $\sigma_h^2$ 分别表示第 $h$ 层样本量和恢复时间方差，$N$ 和 $\sigma^2$ 分别表示总体样本量和总体方差。

## 8. 符号说明

| 符号 | 含义 |
|---|---|
| $S(p)$ | 第 $p$ 个 pentad 的土壤水分百分位 |
| $P_{20}$ | 土壤水分第 20 百分位阈值 |
| $P_{40}$ | 土壤水分第 40 百分位阈值 |
| $p_{\mathrm{onset}}$ | 骤旱快速下降开始的 pentad |
| $p_{20}$ | 首次低于 $P_{20}$ 的 pentad |
| $p_{\mathrm{end}}$ | 事件恢复闭合的 pentad |
| $\Delta S$ | 土壤水分百分位降幅 |
| $R_{\mathrm{onset}}$ | 骤旱发展速率 |
| $C(t)$ | 日尺度 GPP 或 RECO |
| $C_s(t)$ | 5 日平滑后的 GPP 或 RECO |
| $B_C$ | 灾前碳通量基线 |
| $t_{\mathrm{peak}}$ | 碳通量损伤峰值日期 |
| $t_{\mathrm{rec}}$ | 碳通量恢复终点日期 |
| $T_{\mathrm{recovery}}$ | 碳通量恢复时间 |
| $N_{\mathrm{GS}}$ | 生长季有效天数计数函数 |
| $\phi_{ij}$ | 第 $i$ 个事件中特征 $j$ 的 SHAP 值 |
| $I_j$ | 特征 $j$ 的平均绝对 SHAP 重要性 |
| $P_j$ | 特征 $j$ 的相对贡献百分比 |
| $\boldsymbol{\eta}$ | SEM 内生变量向量 |
| $\boldsymbol{\xi}$ | SEM 外生变量向量 |
| $\mathbf{B}$ | 内生变量之间的路径系数矩阵 |
| $\boldsymbol{\Gamma}$ | 外生变量到内生变量的路径系数矩阵 |
| $q$ | 地理探测器空间分异解释力统计量 |
