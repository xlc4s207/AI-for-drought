SMrz（根区土壤湿度）骤旱识别代码：需要修改的关键点（含可直接粘贴的代码片段）
目标：让 P20/P40 百分位阈值严格以 1981–2010 基准期计算；并减少因实现细节导致的系统性偏差（跨年滑动平均、闰日噪声、NORMAL 状态缺测穿越导致伪事件）。

1. 你当前代码“P40”的实际含义（对应代码逻辑）
在你的 analyze_pixel_v2() 中：

p40 = percentiles[doy][PERCENTILE_HIGH]：对同一 DOY（年内同一天）在历史样本上的 第40百分位阈值
p20 = percentiles[doy][PERCENTILE_LOW]：同一 DOY 上的 第20百分位阈值
事件触发方式是：

sm_ma > p40 时不断更新 wet_start_idx（“最近一次超过 P40 的那天”）
若之后某天 sm_ma < p20 且两者间隔 5–30 天 → 判定进入骤旱（DROUGHT）
因此 P40 在这里的角色不是“非常湿”，而是“非干旱/相对不偏干的起点门槛”，用于保证事件不是“本来就很干的持续干旱”。

2. 必改：用 1981–2010 作为百分位基准期（stationary baseline）
2.1 增加基准期配置（建议放在文件顶部）
# ========== 百分位基准期（气候常年值）==========
REF_START_YEAR = 1981
REF_END_YEAR   = 2010
REF_YEARS = set(range(REF_START_YEAR, REF_END_YEAR + 1))
建议：你现在统计期是 1980–2024。若要严格一致，可以把统计期也改为 1981–2024；如果仍保留 1980，需要在论文/报告说明“阈值基于 1981–2010”。

2.2 修改 percentile 样本采集（只用基准期年份）
在 analyze_pixel_v2() 中，找到这段：

doy_values = {}
for i, (year, doy) in enumerate(dates):
    if not np.isnan(sm_ma[i]):
        if doy not in doy_values:
            doy_values[doy] = []
        doy_values[doy].append(sm_ma[i])
替换为：

doy_values = {}
for i, (year, doy) in enumerate(dates):
    if year not in REF_YEARS:
        continue
    if np.isnan(sm_ma[i]):
        continue

    # （闰日处理见 3.1，这里可先不加）
    doy_values.setdefault(doy, []).append(sm_ma[i])
这样 P20/P40 就是 1981–2010 的 DOY 阈值。

3. 强烈建议：两个会显著影响空间格局的实现细节修正
3.1 闰日 DOY=366 处理（避免阈值噪声）
你现在按 for doy in range(1, 367) 计算 percentiles。
DOY=366 只在闰年出现（1981–2010 内只有少数闰年），导致阈值样本太少、噪声很大。

最小修改方案：把 366 合并到 365（简单且常用）：

在所有读取/使用 doy 的地方（构建阈值、事件检测、intensity 计算）统一加：

if doy == 366:
    doy = 365
具体位置建议：

构建 doy_values 处：year,doy = dates[i] 后立刻处理
事件检测循环：year, doy = dates[i] 后立刻处理
intensity 循环：_, doy_j = dates[j] 后立刻处理
示例（事件检测处）：

year, doy = dates[i]
if doy == 366:
    doy = 365
3.2 跨年后向滑动平均会“污染年界”（建议按年重置窗口）
你当前 calculate_backward_moving_average(sm_data) 是在拼接后的全序列上做后向窗口：
这会让每年 1 月初的滑动平均混入上一年 12 月数据，进而影响 DOY 阈值与事件触发。

推荐方案：在滑动平均计算时按年重置（窗口不跨年）

新增函数（可替代你原来的 calculate_backward_moving_average 或新增一个并在 analyze_pixel_v2 调用）：

def calculate_backward_moving_average_by_year(data, dates, window):
    n = len(data)
    ma = np.full(n, np.nan)

    year_start = 0
    while year_start < n:
        y = dates[year_start][0]
        year_end = year_start
        while year_end < n and dates[year_end][0] == y:
            year_end += 1

        # 对 [year_start, year_end) 这一年的片段做后向MA（不跨年）
        for i in range(year_start, year_end):
            start = max(year_start, i - window + 1)
            window_data = data[start:i+1]
            valid_data = window_data[~np.isnan(window_data)]
            if len(valid_data) >= window // 2:
                ma[i] = np.nanmean(window_data)

        year_start = year_end

    return ma
然后在 analyze_pixel_v2() 里把：

sm_ma = calculate_backward_moving_average(sm_data, MOVING_WINDOW)
改为：

sm_ma = calculate_backward_moving_average_by_year(sm_data, dates, MOVING_WINDOW)
4. 建议改：避免 NORMAL 状态下“缺测穿越”导致伪 onset
你现在只在 state == 'DROUGHT' 时对 NaN 做“连续3天中断事件”的处理；
但在 NORMAL 状态遇到 NaN，你只是 continue，不会重置 wet_start_idx。

这会导致一种伪事件：wet_start_idx 停留在一个很早的“>P40”日，期间可能有大量 NaN，之后某天 <P20 仍会被当作 onset。

最小改动：NORMAL 状态下若遇到 NaN，就重置 wet_start_idx（更保守）：

在事件检测循环最前面处理 NaN 的分支里，在 continue 之前补一行：

if np.isnan(sm_ma[i]):
    if state == 'NORMAL':
        wet_start_idx = None
    ...
    continue
5.（可选）为“异常快速强化”加一条速率/幅度约束（减少季节性转干误报）
你当前定义只要 5–30 天内跨 P40→P20 就算 onset，但这可能把某些地区“雨季→旱季”的季节性转干高频统计为骤旱。

你已经输出了 onset_rate 与 onset_drop，因此非常容易加一条筛选，例如：

onset_drop >= DROP_MIN
onset_rate >= RATE_MIN
示例（在满足 5–30 天后进入 DROUGHT 之前加）：

DROP_MIN = 0.02  # 示例阈值：体积含水量下降至少 0.02（需按数据量纲调整）
RATE_MIN = DROP_MIN / MAX_ONSET_DAYS

onset_drop = sm_ma[wet_start_idx] - sm_ma[i]
onset_rate = onset_drop / onset_days if onset_days > 0 else np.nan

if onset_drop >= DROP_MIN and onset_rate >= RATE_MIN:
    state = 'DROUGHT'
    drought_start_idx = i
else:
    wet_start_idx = None
阈值需要结合你的 SM 单位与区域分布做敏感性实验确定。

6. 推荐你做的“快速诊断”（验证是否解决华北/佛州等异常格局）
输出每像元 sm_ma > P40 的天数占比（按年/按季）
对比三套结果：
全时段阈值 vs 1981–2010 阈值
跨年 MA vs 按年重置 MA
加/不加 onset_rate（或 onset_drop）筛选
这样能快速判断：频率空间格局差异到底来自“物理层深差异”还是“算法结构/阈值基准”。

