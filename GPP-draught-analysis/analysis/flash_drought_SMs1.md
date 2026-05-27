SMs（表层土壤湿度）骤旱识别代码：是否存在相同问题？以及需要修改的地方（含可直接粘贴代码）
结论先说：你这份 SMs（表层）代码与 SMrz（根区）在“阈值计算与状态机逻辑”上几乎完全一致，因此 同样存在

百分位阈值未限定基准期（默认用了 1980–2024 全时段）
DOY=366 样本少、阈值噪声大
跨年滑动平均污染年界
NORMAL 状态 NaN 不重置 wet_start 导致缺测穿越伪 onset
“必须先 >P40 再 <P20” 的结构性偏差（对不同气候区影响不同）
但要注意：SSM 本身更“跳”（更易被降水脉冲打湿、被蒸发快速抽干），因此这些同样的算法结构会在表层上表现为更高的触发概率、更碎片化的事件序列——这也是你“表层在华北/中西部更多、华南更少”的常见原因之一（降水频繁会打断表层持续低于 P20 的段）。

1. SMs 代码与 SMrz 的关键相同点（决定它们会出现“同类偏差”）
在 SMs 代码中：

calculate_backward_moving_average：跨年连续后向滑动平均（与 SMrz 相同）
doy_values：使用所有 YEARS（1980–2024）构建 DOY 样本（与 SMrz 相同）
事件触发：wet_start_idx 为“最近一次 >P40”；5–30 天内首次 <P20 则进入 DROUGHT（与 SMrz 相同）
事件结束：回升到 >=P20 即结束；并要求持续期 >= MIN_DURATION（与 SMrz 相同）
NaN 中断：只在 DROUGHT 状态处理；NORMAL 状态 NaN 不重置（与 SMrz 相同）
因此，基准期/闰日/跨年MA/缺测穿越等问题在 SMs 上同样成立。

2. 必改：把百分位阈值改为 1981–2010 基准期
2.1 增加基准期配置（建议放在参数区）
# ========== 百分位基准期（气候常年值）==========
REF_START_YEAR = 1981
REF_END_YEAR   = 2010
REF_YEARS = set(range(REF_START_YEAR, REF_END_YEAR + 1))
2.2 修改 doy_values 的样本采集（只用基准期）
在 analyze_pixel_v2() 中，把：

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
    # 闰日处理见 3.1
    doy_values.setdefault(doy, []).append(sm_ma[i])
3. 强烈建议：两个实现细节修正（对表层同样重要）
3.1 闰日 DOY=366 合并（避免阈值噪声）
表层数据更“跳”，DOY=366 样本少会更不稳定。

统一处理：

if doy == 366:
    doy = 365
放在：

构建 doy_values 时
事件检测时
intensity 计算时
3.2 按年重置滑动平均窗口（避免年界污染）
新增按年重置 MA 的函数（与 SMrz 完全相同，可复制）：

def calculate_backward_moving_average_by_year(data, dates, window):
    n = len(data)
    ma = np.full(n, np.nan)

    year_start = 0
    while year_start < n:
        y = dates[year_start][0]
        year_end = year_start
        while year_end < n and dates[year_end][0] == y:
            year_end += 1

        for i in range(year_start, year_end):
            start = max(year_start, i - window + 1)
            window_data = data[start:i+1]
            valid_data = window_data[~np.isnan(window_data)]
            if len(valid_data) >= window // 2:
                ma[i] = np.nanmean(window_data)

        year_start = year_end

    return ma
把：

sm_ma = calculate_backward_moving_average(sm_data, MOVING_WINDOW)
改为：

sm_ma = calculate_backward_moving_average_by_year(sm_data, dates, MOVING_WINDOW)
4. 建议改：NORMAL 状态遇到 NaN 时重置 wet_start（防缺测穿越伪 onset）
在 NaN 分支里加：

if np.isnan(sm_ma[i]):
    if state == 'NORMAL':
        wet_start_idx = None
    ...
    continue
5. 表层是否“也会有 P40 触发导致的结构性偏差”？
会，但表现会不同：

对根区（RZSM）：半干旱区根区常年偏低 → 很难 >P40 → 更容易漏检
对表层（SSM）：降水脉冲很容易把表层瞬间打湿到 >P40 → 更容易触发 wet_start → 更容易形成“从 >P40 到 <P20 的快速跨越”
所以同一个定义在表层上通常会比根区“检测到更多、更频繁的事件”，尤其在降水间歇明显、蒸发需求强的地区（华北、美国中西部等）。

同时，湿润区（华南、东南沿海）表层又容易被频繁降水“打断低于 P20 的持续段”，因此表层事件可能反而偏少 —— 这与你的空间结果一致。

6.（可选）让表层与根区更可比的两个做法
把事件判断从“日尺度”改成“5日（pentad）尺度”再计算阈值与事件（很多骤旱研究喜欢用 pentad 来过滤日降水噪声）。
给 onset 加 onset_drop/onset_rate 的硬阈值，减少“雨季→旱季”的季节性转干被计为高频骤旱。
7. 你可以直接复制到两套代码里的“统一改动清单”（最小可跑版本）
增加 REF_YEARS（1981–2010）
doy_values 只收集 REF_YEARS
DOY=366 合并到 365
使用 calculate_backward_moving_average_by_year() 替代跨年 MA
NORMAL 状态遇到 NaN 重置 wet_start（可选但推荐）
做完这些，再对比“改前/改后”的华北、长江中下游、美国中西部、佛州四个区域，你会非常直观地看到哪些异常是算法引起、哪些更可能是层深物理差异。

