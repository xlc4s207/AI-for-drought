# -*- coding: utf-8 -*-
"""
骤旱检测算法模块
实现5日滑动平均、百分位计算、事件检测等核心功能
"""

import numpy as np
from config import (
    MOVING_WINDOW, PERCENTILE_HIGH, PERCENTILE_LOW, 
    PERCENTILE_RATE, MIN_DURATION, YEARS
)


def calculate_moving_average(data, window=MOVING_WINDOW):
    """
    计算滑动平均
    
    Parameters:
    -----------
    data : numpy.ndarray
        原始时序数据
    window : int
        滑动窗口大小
        
    Returns:
    --------
    ma : numpy.ndarray
        滑动平均值数组
    """
    # 使用有效值计算滑动平均，忽略NaN
    n = len(data)
    ma = np.full(n, np.nan)
    
    half_window = window // 2
    
    for i in range(n):
        start = max(0, i - half_window)
        end = min(n, i + half_window + 1)
        window_data = data[start:end]
        valid_data = window_data[~np.isnan(window_data)]
        if len(valid_data) >= window // 2:  # 至少一半有效值
            ma[i] = np.nanmean(window_data)
    
    return ma


def calculate_percentiles_by_doy(data, dates, percentiles=[PERCENTILE_LOW, PERCENTILE_HIGH, PERCENTILE_RATE]):
    """
    计算每个DOY的历年百分位值
    
    Parameters:
    -----------
    data : numpy.ndarray
        时序数据(45年拼接)
    dates : list
        日期列表 [(year, doy), ...]
    percentiles : list
        需要计算的百分位列表
        
    Returns:
    --------
    percentile_dict : dict
        {doy: {percentile: value, ...}, ...}
    """
    # 按DOY分组数据
    doy_data = {}
    for i, (year, doy) in enumerate(dates):
        if np.isnan(data[i]):
            continue
        if doy not in doy_data:
            doy_data[doy] = []
        doy_data[doy].append(data[i])
    
    # 计算每个DOY的百分位
    percentile_dict = {}
    for doy in range(1, 367):
        if doy in doy_data and len(doy_data[doy]) > 0:
            values = np.array(doy_data[doy])
            percentile_dict[doy] = {
                p: np.percentile(values, p) for p in percentiles
            }
        else:
            percentile_dict[doy] = {p: np.nan for p in percentiles}
    
    return percentile_dict


def calculate_decline_rate_percentiles(data, dates, window=MOVING_WINDOW):
    """
    计算每个DOY的历史下降速率百分位
    
    Returns:
    --------
    rate_percentiles : dict
        {doy: p5_rate, ...}
    """
    # 计算所有下降速率
    rates = np.full(len(data), np.nan)
    for i in range(window, len(data)):
        if not np.isnan(data[i]) and not np.isnan(data[i - window]):
            rates[i] = (data[i] - data[i - window]) / window
    
    # 按DOY分组
    doy_rates = {}
    for i, (year, doy) in enumerate(dates):
        if np.isnan(rates[i]):
            continue
        # 只统计负的下降速率(即真正的下降)
        if rates[i] < 0:
            if doy not in doy_rates:
                doy_rates[doy] = []
            doy_rates[doy].append(rates[i])
    
    # 计算P5 (第5百分位，即较快的下降速率)
    rate_percentiles = {}
    for doy in range(1, 367):
        if doy in doy_rates and len(doy_rates[doy]) > 0:
            rate_percentiles[doy] = np.percentile(doy_rates[doy], PERCENTILE_RATE)
        else:
            rate_percentiles[doy] = np.nan
    
    return rate_percentiles


def detect_flash_drought_events(sm_ma, dates, percentile_dict, rate_percentiles):
    """
    检测骤旱事件
    
    算法逻辑:
    1. 找到SM5从>P40下降至<P20的时段
    2. 检查下降速率是否达到阈值
    3. 标记事件起止时间
    4. 筛选持续>=15天的事件
    
    Parameters:
    -----------
    sm_ma : numpy.ndarray
        5日滑动平均土壤湿度
    dates : list
        日期列表
    percentile_dict : dict
        DOY百分位字典
    rate_percentiles : dict
        DOY下降速率百分位
        
    Returns:
    --------
    events : list
        事件列表 [{'start_idx': int, 'end_idx': int, 'year': int, 
                   'start_doy': int, 'duration': int, 'intensity': float}, ...]
    """
    events = []
    n = len(sm_ma)
    
    # 状态变量
    in_drought = False
    above_p40 = False
    event_start = None
    crossing_start = None  # 开始跨越P40-P20的位置
    
    for i in range(n):
        if np.isnan(sm_ma[i]):
            continue
        
        year, doy = dates[i]
        p40 = percentile_dict.get(doy, {}).get(PERCENTILE_HIGH, np.nan)
        p20 = percentile_dict.get(doy, {}).get(PERCENTILE_LOW, np.nan)
        
        if np.isnan(p40) or np.isnan(p20):
            continue
        
        # 检查当前状态
        if not in_drought:
            # 未在骤旱中
            if sm_ma[i] > p40:
                above_p40 = True
                crossing_start = i
            elif above_p40 and sm_ma[i] < p20:
                # 从P40上方下降到P20下方 - 潜在骤旱起始
                # 检查下降速率
                if crossing_start is not None:
                    window_size = i - crossing_start
                    if window_size > 0:
                        decline_rate = (sm_ma[i] - sm_ma[crossing_start]) / window_size
                        rate_threshold = rate_percentiles.get(doy, np.nan)
                        
                        # 速率条件：下降速率 <= P5 (更负的值表示更快下降)
                        if not np.isnan(rate_threshold) and decline_rate <= rate_threshold:
                            in_drought = True
                            event_start = i
                above_p40 = False
        else:
            # 已在骤旱中
            if sm_ma[i] > p20:
                # 骤旱结束
                event_end = i - 1
                duration = event_end - event_start + 1
                
                # 检查持续时间约束
                if duration >= MIN_DURATION:
                    # 计算烈度(累计亏缺)
                    intensity = 0.0
                    for j in range(event_start, event_end + 1):
                        _, doy_j = dates[j]
                        p20_j = percentile_dict.get(doy_j, {}).get(PERCENTILE_LOW, np.nan)
                        if not np.isnan(sm_ma[j]) and not np.isnan(p20_j):
                            deficit = p20_j - sm_ma[j]
                            if deficit > 0:
                                intensity += deficit
                    
                    start_year, start_doy = dates[event_start]
                    events.append({
                        'start_idx': event_start,
                        'end_idx': event_end,
                        'year': start_year,
                        'start_doy': start_doy,
                        'duration': duration,
                        'intensity': intensity
                    })
                
                in_drought = False
                event_start = None
    
    # 处理可能在时序末尾未结束的事件
    if in_drought and event_start is not None:
        event_end = n - 1
        duration = event_end - event_start + 1
        if duration >= MIN_DURATION:
            intensity = 0.0
            for j in range(event_start, event_end + 1):
                _, doy_j = dates[j]
                p20_j = percentile_dict.get(doy_j, {}).get(PERCENTILE_LOW, np.nan)
                if not np.isnan(sm_ma[j]) and not np.isnan(p20_j):
                    deficit = p20_j - sm_ma[j]
                    if deficit > 0:
                        intensity += deficit
            
            start_year, start_doy = dates[event_start]
            events.append({
                'start_idx': event_start,
                'end_idx': event_end,
                'year': start_year,
                'start_doy': start_doy,
                'duration': duration,
                'intensity': intensity
            })
    
    return events


def analyze_pixel(data, dates):
    """
    分析单个像元的骤旱事件
    
    Parameters:
    -----------
    data : numpy.ndarray
        像元时序数据(45年)
    dates : list
        日期列表
        
    Returns:
    --------
    events : list
        骤旱事件列表
    total_count : int
        总事件数
    yearly_counts : dict
        {year: count, ...}
    """
    # 检查有效数据比例
    valid_ratio = np.sum(~np.isnan(data)) / len(data)
    if valid_ratio < 0.5:
        return [], 0, {}
    
    # 1. 计算5日滑动平均
    sm_ma = calculate_moving_average(data)
    
    # 2. 计算历年同期百分位
    percentile_dict = calculate_percentiles_by_doy(sm_ma, dates)
    
    # 3. 计算下降速率百分位
    rate_percentiles = calculate_decline_rate_percentiles(sm_ma, dates)
    
    # 4. 检测骤旱事件
    events = detect_flash_drought_events(sm_ma, dates, percentile_dict, rate_percentiles)
    
    # 5. 统计
    total_count = len(events)
    yearly_counts = {year: 0 for year in YEARS}
    for event in events:
        yearly_counts[event['year']] += 1
    
    return events, total_count, yearly_counts
