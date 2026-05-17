# -*- coding: utf-8 -*-
"""
骤旱检测主程序 v5.3 - 5天窗口百分位数优化版 (SMs 表层土壤湿度)
==================================================
核心改进:
1. 两步法: 先识别所有干旱事件，再分类 (flash vs non-flash)
2. 输出三类结果: Total drought / Flash drought / Non-flash drought
3. 保证 total = flash + non-flash (严格互斥)
4. V5.2: 深度内存优化
   - 分块处理: 每次处理 CHUNK_SIZE 行纬度
   - 增量写入: 处理完一块立即写入磁盘
   - 积极释放: 每块处理后立即 del + gc.collect()
5. **V5.3: 5天窗口百分位数计算**
   - 解决问题: 单个DOY在1981-2010只有30个值,数据较少
   - 新方法: 使用固定5天窗口(当天前后各2天)进行百分位数计算
   - 闰年处理: DOY=366的数据合并到DOY=365后,窗口统一基于365天
   - 数据量提升: 每个DOY从30个值增加到150个值(5天×30年)

算法流程:
  Step-A: detect_all_drought_events()
    - 基于 sm_ma < P20 识别所有干旱事件段
    - 结束需连续 K 天 >= P40 确认

  Step-B: classify_event()
    - 向前回溯找 onset_start (sm_ma > P40)
    - 根据 onset_days 分类: flash / slow-onset / dry-to-drier

分类规则:
  - Flash: 存在 onset_start 且 5 <= onset_days <= 20
  - Non-flash:
    - slow-onset: 存在 onset_start 但 onset_days > 20
    - dry-to-drier: 无 onset_start (持续偏干背景)

作者: AI Assistant
日期: 2026-01-30
"""

import os
import sys
import argparse
import time
import gc
import numpy as np
import netCDF4 as nc
import datetime as dt
from datetime import datetime
from multiprocessing import Pool, cpu_count
import warnings

# 过滤 All-NaN slice 警告（海洋等无数据区域的正常现象）
warnings.filterwarnings('ignore', message='All-NaN slice encountered')
warnings.filterwarnings('ignore', category=RuntimeWarning)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'process'))

from config import (
    YEARS, LAT_SIZE, LON_SIZE,
    TEST_LAT_RANGE, TEST_LON_RANGE, MOVING_WINDOW, MAX_EVENTS_PER_PIXEL,
    PERCENTILE_HIGH, PERCENTILE_LOW, MIN_DURATION
)

# 数据路径配置 - MERRA2 表层土壤含水量
BASE_DIR = "/home/xulc/flash_drought/gleam"
SM_FILE = "/home/xulc/flash_drought/gleam/result/SMs_MERRA2_1/SMs_MERRA2_1980_2024_daily.nc4"
RESULT_DIR = os.path.join(BASE_DIR, "result", "SMs_MERRA2_1")
SM_VAR = "SFMC"

# 骤旱爆发期时间约束
MIN_ONSET_DAYS = 5
MAX_ONSET_DAYS = 20

# V5 新增参数
LOOKBACK_MAX = 90          # 最大回溯窗口 (天)
END_CONFIRM_DAYS = 10      # 结束确认天数（改为10天，达到P40）
MIN_DROUGHT_DAYS_BELOW_P20 = 15  # 小于P20的天数必须≥15天

# 百分位基准期
REF_START_YEAR = 1981
REF_END_YEAR = 2010
REF_YEARS = set(range(REF_START_YEAR, REF_END_YEAR + 1))

# V5.2 分块参数
CHUNK_SIZE = 50  # 每次处理 50 行纬度

# V5.3 新增: 5天窗口参数
PERCENTILE_WINDOW = 5  # 百分位数计算窗口 (天)
WINDOW_HALF = PERCENTILE_WINDOW // 2  # 窗口半径 = 2


def parse_args():
    parser = argparse.ArgumentParser(description='全球干旱检测程序 v5.3 (5天窗口百分位数) - MERRA2 SFMC')
    parser.add_argument('--test-mode', action='store_true', help='测试模式')
    parser.add_argument('--lat-range', nargs=2, type=float, default=None)
    parser.add_argument('--lon-range', nargs=2, type=float, default=None)
    parser.add_argument('--workers', type=int, default=None)
    parser.add_argument('--chunk-size', type=int, default=CHUNK_SIZE, help='每次处理的行数')
    parser.add_argument('--sm-file', type=str, default=None,
                        help='MERRA2 合并后的日尺度土壤湿度文件路径（包含变量 SFMC）')
    return parser.parse_args()


def calculate_backward_moving_average_by_year(data_2d, dates, window=MOVING_WINDOW):
    """按年重置的后向滑动平均"""
    min_valid = window // 2
    T, n_lon = data_2d.shape
    ma_2d = np.full_like(data_2d, np.nan, dtype=np.float64)
    
    year_boundaries = []
    current_year = dates[0][0]
    start_idx = 0
    
    for i, (year, doy) in enumerate(dates):
        if year != current_year:
            year_boundaries.append((start_idx, i))
            start_idx = i
            current_year = year
    year_boundaries.append((start_idx, T))
    
    for year_start, year_end in year_boundaries:
        year_len = year_end - year_start
        year_data = data_2d[year_start:year_end, :]
        
        valid_mask = ~np.isnan(year_data)
        data_filled = np.where(valid_mask, year_data, 0.0)
        
        cum_sum = np.cumsum(data_filled, axis=0)
        cum_count = np.cumsum(valid_mask.astype(np.int32), axis=0)
        
        cum_sum_shifted = np.zeros_like(cum_sum)
        cum_count_shifted = np.zeros_like(cum_count)
        
        if window < year_len:
            cum_sum_shifted[window:] = cum_sum[:-window]
            cum_count_shifted[window:] = cum_count[:-window]
        
        window_sum = cum_sum - cum_sum_shifted
        window_count = cum_count - cum_count_shifted
        
        valid_window = window_count >= min_valid
        year_ma = np.full_like(year_data, np.nan, dtype=np.float64)
        year_ma[valid_window] = window_sum[valid_window] / window_count[valid_window]
        
        ma_2d[year_start:year_end, :] = year_ma
    
    return ma_2d


def build_daily_indices_from_time(time_var, valid_years, ref_years):
    """从文件 time 轴构建日尺度索引与 DOY 索引（自动按日期排序）"""
    tvals = time_var[:]
    units = getattr(time_var, 'units', None)
    calendar = getattr(time_var, 'calendar', 'standard')
    if units is None:
        raise ValueError("time 变量缺少 units 属性，无法解析日期")

    datetimes = nc.num2date(tvals, units=units, calendar=calendar)

    day_map = {}
    for idx, t in enumerate(datetimes):
        y = int(t.year)
        if y not in valid_years:
            continue
        key = (y, int(t.month), int(t.day))
        day_map.setdefault(key, []).append(idx)

    if not day_map:
        raise ValueError("输入文件在目标年份范围内无有效时间步")

    day_keys = sorted(day_map.keys())
    time_groups = [np.array(day_map[k], dtype=np.int32) for k in day_keys]

    dates = []
    doy_to_indices = {doy: [] for doy in range(1, 366)}
    doy_to_indices_for_ref = {doy: [] for doy in range(1, 366)}

    for daily_idx, (year, month, day) in enumerate(day_keys):
        doy = dt.date(year, month, day).timetuple().tm_yday
        doy_mapped = 365 if doy == 366 else doy
        dates.append((year, doy_mapped))
        doy_to_indices[doy_mapped].append(daily_idx)
        if year in ref_years:
            doy_to_indices_for_ref[doy_mapped].append(daily_idx)

    for doy in doy_to_indices:
        doy_to_indices[doy] = np.array(doy_to_indices[doy], dtype=np.int32)
        doy_to_indices_for_ref[doy] = np.array(doy_to_indices_for_ref[doy], dtype=np.int32)

    is_daily = all(len(g) == 1 for g in time_groups)
    daily_time_indices = np.array([g[0] for g in time_groups], dtype=np.int32) if is_daily else None

    return dates, doy_to_indices, doy_to_indices_for_ref, time_groups, is_daily, daily_time_indices


def get_doy_window(doy, window_half=WINDOW_HALF):
    """
    获取DOY的窗口范围 (固定5天窗口)
    
    参数:
        doy: 目标DOY (1-365)
        window_half: 窗口半径 (默认2)
    
    返回:
        window_doys: 窗口内的DOY列表 [doy-2, doy-1, doy, doy+1, doy+2]
    
    注意: 
        - 年初和年末采用循环处理 (365天)
        - 例如 doy=1: 窗口为 [364, 365, 1, 2, 3]
        - 例如 doy=365: 窗口为 [363, 364, 365, 1, 2]
    """
    window_doys = []
    for offset in range(-window_half, window_half + 1):
        target_doy = doy + offset
        # 循环处理边界
        if target_doy < 1:
            target_doy += 365
        elif target_doy > 365:
            target_doy -= 365
        window_doys.append(target_doy)
    
    return window_doys


def calculate_percentiles_batch(ma_2d, doy_to_indices_for_ref):
    """
    使用基准期 1981-2010 计算 P20/P40 (V5.3: 5天窗口优化)
    
    改进说明:
        - V5.2: 每个DOY单独计算, 只有30个值 (30年)
        - V5.3: 每个DOY使用5天窗口, 有150个值 (5天×30年)
        - 提升数据量5倍, 百分位数估计更稳定
    
    参数:
        ma_2d: 移动平均后的数据 (time, n_lon)
        doy_to_indices_for_ref: 基准期DOY索引映射
    
    返回:
        p20_2d: P20百分位数 (366, n_lon) [DOY 366留作占位,实际不使用]
        p40_2d: P40百分位数 (366, n_lon)
    """
    n_lon = ma_2d.shape[1]
    p20_2d = np.full((366, n_lon), np.nan, dtype=np.float64)
    p40_2d = np.full((366, n_lon), np.nan, dtype=np.float64)
    
    for doy in range(1, 366):  # 1-365
        # V5.3: 获取5天窗口
        window_doys = get_doy_window(doy, WINDOW_HALF)
        
        # 收集窗口内所有DOY的数据
        all_indices = []
        for window_doy in window_doys:
            indices = doy_to_indices_for_ref.get(window_doy)
            if indices is not None and len(indices) > 0:
                all_indices.extend(indices)
        
        if len(all_indices) == 0:
            continue
        
        # 提取窗口数据
        all_indices = np.array(all_indices, dtype=np.int32)
        window_data = ma_2d[all_indices, :]  # shape: (n_samples, n_lon)
        
        # 计算百分位数
        with np.errstate(all='ignore'):
            p20_2d[doy, :] = np.nanpercentile(window_data, PERCENTILE_LOW, axis=0)
            p40_2d[doy, :] = np.nanpercentile(window_data, PERCENTILE_HIGH, axis=0)
    
    return p20_2d, p40_2d


def read_row_from_merged(lat_idx, lon_start, lon_end, sm_ds, time_groups, is_daily, daily_time_indices):
    """读取单行并聚合为日尺度 (time_daily, n_lon)"""
    var = sm_ds.variables[SM_VAR]
    n_lon = lon_end - lon_start

    if is_daily:
        row_data = var[daily_time_indices, lat_idx, lon_start:lon_end]
        if hasattr(row_data, 'mask'):
            row_data = np.ma.filled(row_data, np.nan)
        return row_data.astype(np.float64)

    n_days = len(time_groups)
    out = np.full((n_days, n_lon), np.nan, dtype=np.float64)

    for d, idxs in enumerate(time_groups):
        day_data = var[idxs, lat_idx, lon_start:lon_end]
        if hasattr(day_data, 'mask'):
            day_data = np.ma.filled(day_data, np.nan)
        day_data = day_data.astype(np.float64)
        if day_data.ndim == 1:
            out[d, :] = day_data
        else:
            out[d, :] = np.nanmean(day_data, axis=0)

    return out


def detect_all_drought_events(sm_ma, p20_arr, p40_arr, dates):
    """
    Step-A: 识别所有干旱事件 (基于 sm_ma < P20)
    改进: 结束条件改为P40持续10天，小于P20天数必须≥15天
    
    返回: list of dict, 每个 dict 包含:
        - start_idx, end_idx, duration, days_below_p20
        - drought_start_year, drought_start_doy
        - drought_end_year, drought_end_doy
        - intensity
    """
    n = len(sm_ma)
    events = []
    
    i = 0
    while i < n:
        year, doy = dates[i]
        
        # 跳过 NaN
        if np.isnan(sm_ma[i]):
            i += 1
            continue
        
        p20 = p20_arr[doy]
        if np.isnan(p20):
            i += 1
            continue
        
        # 找到干旱开始 (sm_ma < P20)
        if sm_ma[i] < p20:
            drought_start_idx = i
            drought_start_year, drought_start_doy = dates[i]
            days_below_p20 = 1  # 统计<P20的天数
            
            # 继续向前直到干旱结束
            j = i + 1
            nan_count = 0
            confirmed_end_idx = None
            confirm_count = 0
            
            while j < n:
                if np.isnan(sm_ma[j]):
                    nan_count += 1
                    if nan_count >= 3:
                        # NaN 中断，截断事件
                        confirmed_end_idx = j - nan_count
                        break
                    j += 1
                    continue
                
                nan_count = 0
                _, doy_j = dates[j]
                p20_j = p20_arr[doy_j]
                p40_j = p40_arr[doy_j]
                
                if np.isnan(p20_j) or np.isnan(p40_j):
                    j += 1
                    continue
                
                # 统计<P20的天数
                if sm_ma[j] < p20_j:
                    days_below_p20 += 1
                
                # 结束条件：达到P40
                if sm_ma[j] >= p40_j:
                    # 可能结束，需确认
                    confirm_count += 1
                    if confirm_count >= END_CONFIRM_DAYS:
                        # 确认结束
                        confirmed_end_idx = j - END_CONFIRM_DAYS
                        break
                else:
                    # 仍在干旱中，重置计数
                    confirm_count = 0
                
                j += 1
            
            # 确定事件结束位置
            if confirmed_end_idx is None:
                drought_end_idx = j - 1 if j > drought_start_idx else drought_start_idx
            else:
                drought_end_idx = confirmed_end_idx
            
            # 确保结束不小于开始
            if drought_end_idx < drought_start_idx:
                drought_end_idx = drought_start_idx
            
            duration = drought_end_idx - drought_start_idx + 1
            
            # 检查：小于P20天数必须≥15天
            if duration >= MIN_DURATION and days_below_p20 >= MIN_DROUGHT_DAYS_BELOW_P20:
                # 计算强度
                intensity = 0.0
                for k in range(drought_start_idx, drought_end_idx + 1):
                    if not np.isnan(sm_ma[k]):
                        _, doy_k = dates[k]
                        p20_k = p20_arr[doy_k]
                        if not np.isnan(p20_k):
                            deficit = p20_k - sm_ma[k]
                            if deficit > 0:
                                intensity += deficit
                
                drought_end_year, drought_end_doy = dates[drought_end_idx]
                
                events.append({
                    'start_idx': drought_start_idx,
                    'end_idx': drought_end_idx,
                    'duration': duration,
                    'days_below_p20': days_below_p20,
                    'drought_start_year': drought_start_year,
                    'drought_start_doy': drought_start_doy,
                    'drought_end_year': drought_end_year,
                    'drought_end_doy': drought_end_doy,
                    'intensity': intensity
                })
            
            i = drought_end_idx + 1
        else:
            i += 1
    
    return events


def classify_event(event, sm_ma, p40_arr, dates):
    """
    Step-B: 对单个干旱事件进行分类 (flash vs non-flash)
    
    返回: 
        - event_type: 'flash', 'slow_onset', 'dry_to_drier'
        - onset_start_idx: 如果存在
        - onset_days: 如果存在
        - onset_drop, onset_rate
    """
    drought_start_idx = event['start_idx']
    
    # 向前回溯找 onset_start (sm_ma > P40)
    onset_start_idx = None
    lookback_start = max(0, drought_start_idx - LOOKBACK_MAX)
    
    for i in range(drought_start_idx - 1, lookback_start - 1, -1):
        if np.isnan(sm_ma[i]):
            continue
        _, doy_i = dates[i]
        p40_i = p40_arr[doy_i]
        if np.isnan(p40_i):
            continue
        
        if sm_ma[i] > p40_i:
            onset_start_idx = i
            break
    
    # 分类
    if onset_start_idx is not None:
        onset_days = drought_start_idx - onset_start_idx
        onset_drop = sm_ma[onset_start_idx] - sm_ma[drought_start_idx]
        onset_rate = onset_drop / onset_days if onset_days > 0 else np.nan
        onset_year, onset_doy = dates[onset_start_idx]
        
        if MIN_ONSET_DAYS <= onset_days <= MAX_ONSET_DAYS:
            event_type = 'flash'
        else:
            event_type = 'slow_onset'
    else:
        # 没有找到 > P40 的点
        event_type = 'dry_to_drier'
        onset_start_idx = None
        onset_days = -1
        onset_drop = np.nan
        onset_rate = np.nan
        onset_year = -1
        onset_doy = -1
    
    return {
        'event_type': event_type,
        'onset_start_idx': onset_start_idx,
        'onset_start_year': onset_year if onset_start_idx else -1,
        'onset_start_doy': onset_doy if onset_start_idx else -1,
        'onset_days': onset_days,
        'onset_drop': onset_drop,
        'onset_rate': onset_rate
    }


def analyze_pixel_v5(sm_ma, p20_arr, p40_arr, dates):
    """
    V5 版本像元分析: 两步法
    
    返回:
        - total_events: 所有干旱事件
        - flash_events: 骤旱事件
        - nonflash_events: 非骤旱事件
        - is_valid
    """
    valid_ratio = np.sum(~np.isnan(sm_ma)) / len(sm_ma)
    if valid_ratio < 0.5:
        return None, None, None, False
    
    # Step-A: 检测所有干旱事件（改进：P40结束，≥15天<P20）
    all_events = detect_all_drought_events(sm_ma, p20_arr, p40_arr, dates)
    
    if len(all_events) == 0:
        return [], [], [], True
    
    # Step-B: 分类每个事件
    flash_events = []
    nonflash_events = []
    
    for event in all_events:
        classification = classify_event(event, sm_ma, p40_arr, dates)
        
        # 合并事件信息
        full_event = {
            **event,
            **classification
        }
        
        if classification['event_type'] == 'flash':
            flash_events.append(full_event)
        else:
            nonflash_events.append(full_event)
    
    return all_events, flash_events, nonflash_events, True


# 全局变量
_GLOBAL_DATES = None
_GLOBAL_DOY_INDICES = None
_GLOBAL_DOY_INDICES_REF = None
_GLOBAL_SM_DS = None
_GLOBAL_TIME_GROUPS = None
_GLOBAL_IS_DAILY = None
_GLOBAL_DAILY_TIME_INDICES = None


def init_worker(dates, doy_indices, doy_indices_ref, time_groups, is_daily, daily_time_indices):
    global _GLOBAL_DATES, _GLOBAL_DOY_INDICES, _GLOBAL_DOY_INDICES_REF, _GLOBAL_SM_DS
    global _GLOBAL_TIME_GROUPS, _GLOBAL_IS_DAILY, _GLOBAL_DAILY_TIME_INDICES
    _GLOBAL_DATES = dates
    _GLOBAL_DOY_INDICES = doy_indices
    _GLOBAL_DOY_INDICES_REF = doy_indices_ref
    _GLOBAL_TIME_GROUPS = time_groups
    _GLOBAL_IS_DAILY = is_daily
    _GLOBAL_DAILY_TIME_INDICES = daily_time_indices
    _GLOBAL_SM_DS = nc.Dataset(SM_FILE, 'r')


def process_single_row(args):
    """处理单行 - V5.3 版本 (5天窗口百分位数)"""
    row_idx, lat_idx_global, lon_start, lon_end, n_lon = args
    
    global _GLOBAL_DATES, _GLOBAL_DOY_INDICES, _GLOBAL_DOY_INDICES_REF, _GLOBAL_SM_DS
    global _GLOBAL_TIME_GROUPS, _GLOBAL_IS_DAILY, _GLOBAL_DAILY_TIME_INDICES
    dates = _GLOBAL_DATES
    doy_to_indices_ref = _GLOBAL_DOY_INDICES_REF
    
    try:
        row_data = read_row_from_merged(
            lat_idx_global, lon_start, lon_end,
            _GLOBAL_SM_DS, _GLOBAL_TIME_GROUPS, _GLOBAL_IS_DAILY, _GLOBAL_DAILY_TIME_INDICES
        )
        
        # 快速跳过全NaN行（海洋/无效区域）
        if np.all(np.isnan(row_data)):
            return {
                'row_idx': row_idx,
                'total': np.full(n_lon, np.nan, dtype=np.float32),
                'flash': np.full(n_lon, np.nan, dtype=np.float32),
                'nonflash': np.full(n_lon, np.nan, dtype=np.float32),
                'yearly_total': {year: np.full(n_lon, np.nan, dtype=np.float32) for year in YEARS},
                'yearly_flash': {year: np.full(n_lon, np.nan, dtype=np.float32) for year in YEARS},
                'yearly_nonflash': {year: np.full(n_lon, np.nan, dtype=np.float32) for year in YEARS},
                'total_events': [],
                'flash_events': [],
                'nonflash_events': [],
                'valid_count': 0,
                'total_event_count': 0,
                'flash_event_count': 0,
                'nonflash_event_count': 0
            }
        
        ma_2d = calculate_backward_moving_average_by_year(row_data, dates, MOVING_WINDOW)
        # 立即释放row_data内存
        del row_data
        
        # V5.3: 使用5天窗口计算百分位数
        p20_2d, p40_2d = calculate_percentiles_batch(ma_2d, doy_to_indices_ref)
        
        # 三类结果
        row_total = np.full(n_lon, np.nan, dtype=np.float32)
        row_flash = np.full(n_lon, np.nan, dtype=np.float32)
        row_nonflash = np.full(n_lon, np.nan, dtype=np.float32)
        
        row_yearly_total = {year: np.full(n_lon, np.nan, dtype=np.float32) for year in YEARS}
        row_yearly_flash = {year: np.full(n_lon, np.nan, dtype=np.float32) for year in YEARS}
        row_yearly_nonflash = {year: np.full(n_lon, np.nan, dtype=np.float32) for year in YEARS}
        
        row_total_events = []
        row_flash_events = []
        row_nonflash_events = []
        
        valid_count = 0
        total_event_count = 0
        flash_event_count = 0
        nonflash_event_count = 0
        
        for j in range(n_lon):
            pixel_ma = ma_2d[:, j]
            
            if np.all(np.isnan(pixel_ma)):
                continue
            
            p20_pixel = p20_2d[:, j]
            p40_pixel = p40_2d[:, j]
            
            all_evts, flash_evts, nonflash_evts, is_valid = analyze_pixel_v5(
                pixel_ma, p20_pixel, p40_pixel, dates
            )
            
            if not is_valid:
                del all_evts, flash_evts, nonflash_evts
                continue
            
            row_total[j] = len(all_evts)
            row_flash[j] = len(flash_evts)
            row_nonflash[j] = len(nonflash_evts)
            
            # 年度统计
            yearly_total = {year: 0 for year in YEARS}
            yearly_flash = {year: 0 for year in YEARS}
            yearly_nonflash = {year: 0 for year in YEARS}
            
            for e in all_evts:
                yearly_total[e['drought_start_year']] += 1
            for e in flash_evts:
                yearly_flash[e['drought_start_year']] += 1
            for e in nonflash_evts:
                yearly_nonflash[e['drought_start_year']] += 1
            
            for year in YEARS:
                row_yearly_total[year][j] = yearly_total[year]
                row_yearly_flash[year][j] = yearly_flash[year]
                row_yearly_nonflash[year][j] = yearly_nonflash[year]
            
            del yearly_total, yearly_flash, yearly_nonflash
            
            # 保存事件详情 (限制数量)
            row_total_events.append((j, all_evts[:MAX_EVENTS_PER_PIXEL]))
            row_flash_events.append((j, flash_evts[:MAX_EVENTS_PER_PIXEL]))
            row_nonflash_events.append((j, nonflash_evts[:MAX_EVENTS_PER_PIXEL]))
            
            del all_evts, flash_evts, nonflash_evts
            
            valid_count += 1
            total_event_count += len(row_total_events[-1][1])
            flash_event_count += len(row_flash_events[-1][1])
            nonflash_event_count += len(row_nonflash_events[-1][1])
        
        # 处理完所有像素后，释放大数组
        del ma_2d, p20_2d, p40_2d
        
        return {
            'row_idx': row_idx,
            'total': row_total,
            'flash': row_flash,
            'nonflash': row_nonflash,
            'yearly_total': row_yearly_total,
            'yearly_flash': row_yearly_flash,
            'yearly_nonflash': row_yearly_nonflash,
            'total_events': row_total_events,
            'flash_events': row_flash_events,
            'nonflash_events': row_nonflash_events,
            'valid_count': valid_count,
            'total_event_count': total_event_count,
            'flash_event_count': flash_event_count,
            'nonflash_event_count': nonflash_event_count
        }
    except Exception as e:
        print(f"\n[错误] 行 {row_idx}: {e}")
        import traceback
        traceback.print_exc()
        return None


def init_netcdf_files(result_dir, n_lat, n_lon, lat_sub, lon_sub):
    """初始化 NetCDF 文件结构（仅创建维度和变量，不写数据）"""
    filepaths = {}
    
    for event_type in ['total', 'flash', 'nonflash']:
        filepath = os.path.join(result_dir, f"{event_type}_drought_events_v5.nc")
        filepaths[event_type] = filepath
        
        with nc.Dataset(filepath, 'w', format='NETCDF4') as ds:
            ds.createDimension('lat', n_lat)
            ds.createDimension('lon', n_lon)
            ds.createDimension('max_events', MAX_EVENTS_PER_PIXEL)
            
            lat_var = ds.createVariable('lat', 'f4', ('lat',))
            lat_var[:] = lat_sub
            lat_var.units = 'degrees_north'
            
            lon_var = ds.createVariable('lon', 'f4', ('lon',))
            lon_var[:] = lon_sub
            lon_var.units = 'degrees_east'
            
            ds.createVariable('event_count', 'i2', ('lat', 'lon'), fill_value=-1, zlib=True)
            
            for key in ['onset_start_year', 'onset_start_doy', 'drought_start_year', 'drought_start_doy',
                        'drought_end_year', 'drought_end_doy', 'onset_days', 'duration']:
                ds.createVariable(key, 'i2', ('max_events', 'lat', 'lon'), fill_value=-1, zlib=True)
            
            for key in ['onset_drop', 'onset_rate', 'intensity']:
                ds.createVariable(key, 'f4', ('max_events', 'lat', 'lon'), fill_value=-9999, zlib=True)
            
            ds.title = f'{event_type.capitalize()} Drought Events Details v5.3'
            ds.source = f'MERRA2 SFMC data ({YEARS[0]}-{YEARS[-1]})'
            ds.algorithm = 'Two-step Method v5.3 (5-day Window Percentile)'
            ds.percentile_baseline = f'{REF_START_YEAR}-{REF_END_YEAR}'
            ds.percentile_window = f'{PERCENTILE_WINDOW} days (±{WINDOW_HALF})'
    
    return filepaths


def init_tiff_files(result_dir, n_lat, n_lon, lat_sub, lon_sub):
    """初始化 TIFF 文件结构"""
    from osgeo import gdal, osr
    
    filepaths = {}
    
    lon_res = abs(lon_sub[1] - lon_sub[0]) if len(lon_sub) > 1 else 0.1
    lat_res = abs(lat_sub[1] - lat_sub[0]) if len(lat_sub) > 1 else 0.1
    geotransform = (float(lon_sub[0]) - lon_res/2, lon_res, 0,
                    float(lat_sub[0]) + lat_res/2, 0, -lat_res)
    
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    projection = srs.ExportToWkt()
    
    driver = gdal.GetDriverByName('GTiff')
    
    # 总频率文件
    for event_type in ['total', 'flash', 'nonflash']:
        filepath = os.path.join(result_dir, f"{event_type}_drought_frequency_{YEARS[0]}_{YEARS[-1]}.tif")
        filepaths[f'{event_type}_freq'] = filepath
        
        out_ds = driver.Create(filepath, int(n_lon), int(n_lat), 1, gdal.GDT_Float32)
        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(projection)
        band = out_ds.GetRasterBand(1)
        band.SetNoDataValue(-9999)
        band.Fill(-9999)
        band.FlushCache()
        out_ds = None
    
    # 年度频率文件
    for year in YEARS:
        for event_type in ['total', 'flash', 'nonflash']:
            filepath = os.path.join(result_dir, f"{event_type}_drought_{year}.tif")
            filepaths[f'{event_type}_{year}'] = filepath
            
            out_ds = driver.Create(filepath, int(n_lon), int(n_lat), 1, gdal.GDT_Float32)
            out_ds.SetGeoTransform(geotransform)
            out_ds.SetProjection(projection)
            band = out_ds.GetRasterBand(1)
            band.SetNoDataValue(-9999)
            band.Fill(-9999)
            band.FlushCache()
            out_ds = None
    
    return filepaths


def write_chunk_to_netcdf(nc_filepaths, chunk_events_data, chunk_start, chunk_size):
    """将块数据写入 NetCDF 文件"""
    for event_type, filepath in nc_filepaths.items():
        events_data = chunk_events_data[event_type]
        
        with nc.Dataset(filepath, 'r+') as ds:
            ds.variables['event_count'][chunk_start:chunk_start+chunk_size, :] = events_data['event_count']
            
            for key in ['onset_start_year', 'onset_start_doy', 'drought_start_year', 'drought_start_doy',
                        'drought_end_year', 'drought_end_doy', 'onset_days', 'duration',
                        'onset_drop', 'onset_rate', 'intensity']:
                if key in events_data:
                    ds.variables[key][:, chunk_start:chunk_start+chunk_size, :] = events_data[key]


def write_chunk_to_tiff(tiff_filepaths, chunk_freq_data, chunk_yearly_data, chunk_start):
    """将块数据写入 TIFF 文件"""
    from osgeo import gdal
    
    for event_type in ['total', 'flash', 'nonflash']:
        # 写入总频率
        filepath = tiff_filepaths[f'{event_type}_freq']
        ds = gdal.Open(filepath, gdal.GA_Update)
        band = ds.GetRasterBand(1)
        data = np.where(np.isnan(chunk_freq_data[event_type]), -9999, chunk_freq_data[event_type])
        band.WriteArray(data, xoff=0, yoff=chunk_start)
        band.FlushCache()
        ds = None
        
        # 写入年度频率
        for year in YEARS:
            filepath = tiff_filepaths[f'{event_type}_{year}']
            ds = gdal.Open(filepath, gdal.GA_Update)
            band = ds.GetRasterBand(1)
            data = np.where(np.isnan(chunk_yearly_data[event_type][year]), -9999, chunk_yearly_data[event_type][year])
            band.WriteArray(data, xoff=0, yoff=chunk_start)
            band.FlushCache()
            ds = None


def main():
    args = parse_args()
    global SM_FILE
    if args.sm_file:
        SM_FILE = args.sm_file

    n_workers = args.workers if args.workers else max(1, cpu_count() - 1)
    chunk_size = args.chunk_size
    
    print("="*70)
    print("   全球干旱检测 v5.3 - 5天窗口百分位数优化版 (MERRA2 SFMC 表层, 日尺度)")
    print("="*70)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"并行进程数: {n_workers}")
    print(f"数据年份: {YEARS[0]} - {YEARS[-1]}")
    print(f"输入文件: {SM_FILE}")
    print(f"结果目录: {RESULT_DIR}")
    print()
    print("[算法参数]")
    print(f"  滑动窗口: {MOVING_WINDOW} 天")
    print(f"  干旱阈值: P{PERCENTILE_LOW}, 湿润阈值: P{PERCENTILE_HIGH}")
    print(f"  骤旱 onset: {MIN_ONSET_DAYS}-{MAX_ONSET_DAYS} 天")
    print(f"  最小持续: {MIN_DURATION} 天")
    print(f"  回溯窗口: {LOOKBACK_MAX} 天")
    print(f"  结束确认: {END_CONFIRM_DAYS} 天")
    print()
    print("[V5.3 核心改进]")
    print(f"  ✓ 百分位数窗口: {PERCENTILE_WINDOW} 天 (当天 ±{WINDOW_HALF} 天)")
    print(f"  ✓ 数据量提升: 30个值/DOY → 150个值/DOY (5倍)")
    print(f"  ✓ 基准期: {REF_START_YEAR}-{REF_END_YEAR} (30年)")
    print(f"  ✓ 闰年处理: DOY=366合并至365, 窗口统一基于365天")
    print()
    print("[V5.2 继承特性]")
    print("  ✓ 两步法: 先检测全部干旱，再分类")
    print("  ✓ 三类输出: Total / Flash / Non-flash")
    print("  ✓ 保证 Total = Flash + Non-flash")
    print(f"  ✓ 分块处理: 每次处理 {chunk_size} 行纬度")
    print("  ✓ 增量写入: 处理完一块立即写入磁盘")
    print("  ✓ 积极释放: 每块处理后 del + gc.collect()")
    
    print("\n[预处理] 从 time 轴构建日尺度索引与 DOY 索引...")
    with nc.Dataset(SM_FILE, 'r') as ds:
        if SM_VAR not in ds.variables:
            raise ValueError(f"输入文件不包含变量 {SM_VAR}: {SM_FILE}")
        lat_array = ds.variables['lat'][:]
        lon_array = ds.variables['lon'][:]
        dates, doy_to_indices, doy_to_indices_ref, time_groups, is_daily, daily_time_indices = \
            build_daily_indices_from_time(ds.variables['time'], set(YEARS), REF_YEARS)

    print(f"  日尺度时间步: {len(dates)}")
    if dates:
        print(f"  日尺度起止: {dates[0][0]}(DOY={dates[0][1]}) -> {dates[-1][0]}(DOY={dates[-1][1]})")
    print(f"  输入文件是否已是日尺度: {'是' if is_daily else '否（已在脚本内聚合到日尺度）'}")

    print(f"\n[窗口验证] 测试关键DOY的5天窗口:")
    for test_doy in [1, 2, 183, 364, 365]:
        window = get_doy_window(test_doy, WINDOW_HALF)
        print(f"  DOY {test_doy:3d}: 窗口 = {window}")
    
    if args.test_mode:
        lat_range = args.lat_range if args.lat_range else TEST_LAT_RANGE
        lon_range = args.lon_range if args.lon_range else TEST_LON_RANGE
        print(f"\n[测试模式] 纬度: {lat_range}, 经度: {lon_range}")
        
        lat_idx_min = np.argmin(np.abs(lat_array - lat_range[1]))
        lat_idx_max = np.argmin(np.abs(lat_array - lat_range[0]))
        lon_idx_min = np.argmin(np.abs(lon_array - lon_range[0]))
        lon_idx_max = np.argmin(np.abs(lon_array - lon_range[1]))
        
        if lat_idx_min > lat_idx_max:
            lat_idx_min, lat_idx_max = lat_idx_max, lat_idx_min
    else:
        lat_idx_min, lat_idx_max = 0, len(lat_array) - 1
        lon_idx_min, lon_idx_max = 0, len(lon_array) - 1
    
    n_lat = lat_idx_max - lat_idx_min + 1
    n_lon = lon_idx_max - lon_idx_min + 1
    print(f"\n[处理范围] {n_lat} 行 x {n_lon} 列")
    
    lat_sub = lat_array[lat_idx_min:lat_idx_max+1]
    lon_sub = lon_array[lon_idx_min:lon_idx_max+1]
    
    os.makedirs(RESULT_DIR, exist_ok=True)
    
    # 初始化输出文件
    print("\n[初始化] 创建输出文件...")
    nc_filepaths = init_netcdf_files(RESULT_DIR, n_lat, n_lon, lat_sub, lon_sub)
    tiff_filepaths = init_tiff_files(RESULT_DIR, n_lat, n_lon, lat_sub, lon_sub)
    print(f"  已创建 {len(nc_filepaths)} 个 NetCDF 文件")
    print(f"  已创建 {len(tiff_filepaths)} 个 TIFF 文件")
    
    print(f"\n[处理开始] 使用 {n_workers} 个进程, 分块大小 {chunk_size}...")
    print("-"*70)
    
    start_time = time.time()
    stats = {'valid': 0, 'total': 0, 'flash': 0, 'nonflash': 0}
    completed_rows = 0
    n_chunks = (n_lat + chunk_size - 1) // chunk_size
    
    for chunk_idx in range(n_chunks):
        chunk_start = chunk_idx * chunk_size
        chunk_end = min(chunk_start + chunk_size, n_lat)
        actual_chunk_size = chunk_end - chunk_start
        
        print(f"\n[块 {chunk_idx+1}/{n_chunks}] 处理行 {chunk_start}-{chunk_end-1} (共 {actual_chunk_size} 行)")
        
        # 生成当前块的任务
        tasks = [(i, lat_idx_min + chunk_start + i, lon_idx_min, lon_idx_max + 1, n_lon) 
                 for i in range(actual_chunk_size)]
        
        # 初始化块缓冲区
        chunk_freq = {
            'total': np.full((actual_chunk_size, n_lon), np.nan, dtype=np.float32),
            'flash': np.full((actual_chunk_size, n_lon), np.nan, dtype=np.float32),
            'nonflash': np.full((actual_chunk_size, n_lon), np.nan, dtype=np.float32)
        }
        
        chunk_yearly = {
            'total': {year: np.full((actual_chunk_size, n_lon), np.nan, dtype=np.float32) for year in YEARS},
            'flash': {year: np.full((actual_chunk_size, n_lon), np.nan, dtype=np.float32) for year in YEARS},
            'nonflash': {year: np.full((actual_chunk_size, n_lon), np.nan, dtype=np.float32) for year in YEARS}
        }
        
        def init_chunk_events_data(size):
            return {
                'event_count': np.full((size, n_lon), -1, dtype=np.int16),
                'onset_start_year': np.full((MAX_EVENTS_PER_PIXEL, size, n_lon), -1, dtype=np.int16),
                'onset_start_doy': np.full((MAX_EVENTS_PER_PIXEL, size, n_lon), -1, dtype=np.int16),
                'drought_start_year': np.full((MAX_EVENTS_PER_PIXEL, size, n_lon), -1, dtype=np.int16),
                'drought_start_doy': np.full((MAX_EVENTS_PER_PIXEL, size, n_lon), -1, dtype=np.int16),
                'drought_end_year': np.full((MAX_EVENTS_PER_PIXEL, size, n_lon), -1, dtype=np.int16),
                'drought_end_doy': np.full((MAX_EVENTS_PER_PIXEL, size, n_lon), -1, dtype=np.int16),
                'onset_days': np.full((MAX_EVENTS_PER_PIXEL, size, n_lon), -1, dtype=np.int16),
                'duration': np.full((MAX_EVENTS_PER_PIXEL, size, n_lon), -1, dtype=np.int16),
                'onset_drop': np.full((MAX_EVENTS_PER_PIXEL, size, n_lon), -9999, dtype=np.float32),
                'onset_rate': np.full((MAX_EVENTS_PER_PIXEL, size, n_lon), -9999, dtype=np.float32),
                'intensity': np.full((MAX_EVENTS_PER_PIXEL, size, n_lon), -9999, dtype=np.float32),
            }
        
        chunk_events = {
            'total': init_chunk_events_data(actual_chunk_size),
            'flash': init_chunk_events_data(actual_chunk_size),
            'nonflash': init_chunk_events_data(actual_chunk_size)
        }
        
        chunk_completed = 0
        
        with Pool(processes=n_workers, initializer=init_worker,
                  initargs=(dates, doy_to_indices, doy_to_indices_ref, time_groups, is_daily, daily_time_indices)) as pool:
            for result in pool.imap_unordered(process_single_row, tasks, chunksize=4):
                if result is None:
                    chunk_completed += 1
                    continue
                
                row_idx = result['row_idx']
                chunk_freq['total'][row_idx] = result['total']
                chunk_freq['flash'][row_idx] = result['flash']
                chunk_freq['nonflash'][row_idx] = result['nonflash']
                
                for year in YEARS:
                    chunk_yearly['total'][year][row_idx] = result['yearly_total'][year]
                    chunk_yearly['flash'][year][row_idx] = result['yearly_flash'][year]
                    chunk_yearly['nonflash'][year][row_idx] = result['yearly_nonflash'][year]
                
                # 保存事件详情
                def save_row_events(events_list, events_data, row):
                    for j, evts in events_list:
                        events_data['event_count'][row, j] = len(evts)
                        for k, e in enumerate(evts):
                            events_data['onset_start_year'][k, row, j] = e.get('onset_start_year', -1)
                            events_data['onset_start_doy'][k, row, j] = e.get('onset_start_doy', -1)
                            events_data['drought_start_year'][k, row, j] = e['drought_start_year']
                            events_data['drought_start_doy'][k, row, j] = e['drought_start_doy']
                            events_data['drought_end_year'][k, row, j] = e['drought_end_year']
                            events_data['drought_end_doy'][k, row, j] = e['drought_end_doy']
                            events_data['onset_days'][k, row, j] = e.get('onset_days', -1)
                            events_data['duration'][k, row, j] = e['duration']
                            events_data['onset_drop'][k, row, j] = e.get('onset_drop', -9999)
                            events_data['onset_rate'][k, row, j] = e.get('onset_rate', -9999)
                            events_data['intensity'][k, row, j] = e['intensity']
                
                save_row_events(result['total_events'], chunk_events['total'], row_idx)
                save_row_events(result['flash_events'], chunk_events['flash'], row_idx)
                save_row_events(result['nonflash_events'], chunk_events['nonflash'], row_idx)
                
                # 清理 result 中的大数据
                del result['total_events'], result['flash_events'], result['nonflash_events']
                del result['yearly_total'], result['yearly_flash'], result['yearly_nonflash']
                
                stats['valid'] += result['valid_count']
                stats['total'] += result['total_event_count']
                stats['flash'] += result['flash_event_count']
                stats['nonflash'] += result['nonflash_event_count']
                chunk_completed += 1
                
                elapsed = time.time() - start_time
                progress = (completed_rows + chunk_completed) / n_lat * 100
                speed = (completed_rows + chunk_completed) / elapsed if elapsed > 0 else 0
                eta = (n_lat - completed_rows - chunk_completed) / speed if speed > 0 else 0
                print(f"\r  [{progress:.1f}%] Total:{stats['total']} Flash:{stats['flash']} "
                      f"NonFlash:{stats['nonflash']} | {speed:.1f}行/s | ETA:{eta/60:.1f}m", 
                      end='', flush=True)
        
        # 写入块数据到磁盘
        print(f"\n  写入块 {chunk_idx+1} 数据到磁盘...")
        write_chunk_to_netcdf(nc_filepaths, chunk_events, chunk_start, actual_chunk_size)
        write_chunk_to_tiff(tiff_filepaths, chunk_freq, chunk_yearly, chunk_start)
        
        completed_rows += actual_chunk_size
        
        # 释放块缓冲区
        del chunk_freq, chunk_yearly, chunk_events, tasks
        gc.collect()
        print(f"  块 {chunk_idx+1} 完成, 内存已释放")
    
    elapsed = time.time() - start_time
    print("\n\n" + "="*70)
    print("                    处理完成")
    print("="*70)
    print(f"总耗时: {elapsed/60:.1f}分钟")
    print(f"有效像元: {stats['valid']}")
    print(f"\n[事件统计]")
    if stats['total'] > 0:
        print(f"  Total drought:     {stats['total']}")
        print(f"  Flash drought:     {stats['flash']} ({stats['flash']/stats['total']*100:.1f}%)")
        print(f"  Non-flash drought: {stats['nonflash']} ({stats['nonflash']/stats['total']*100:.1f}%)")
        print(f"  验证 (flash + nonflash = total): {stats['flash'] + stats['nonflash']} = {stats['total']}")
    else:
        print("  未检测到任何干旱事件")
    
    print(f"\n[V5.3 改进说明]")
    print(f"  百分位数计算采用{PERCENTILE_WINDOW}天窗口, 大幅提升统计稳定性")
    print(f"  每个DOY样本量从30个增加到约150个 (提升5倍)")


if __name__ == '__main__':
    main()
