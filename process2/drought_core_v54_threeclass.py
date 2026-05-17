# -*- coding: utf-8 -*-
"""
干旱检测核心模块 v5.4 - 三分类版
=================================
在 v5.3/v5.4 共用优化框架上, 将事件按爆发时间拆分为:
1. rapid_1to4: 1-4 天超快起始事件
2. flash_5to20: 5-20 天骤旱事件
3. slow_gt20: >20 天慢发型事件
4. dry_to_drier: 无有效 onset_start 的持续偏干事件

保留:
- 两步法识别干旱事件
- 5天窗口百分位数计算
- 基准期 1981-2010
- Pool 全局复用与逐行写盘优化
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

warnings.filterwarnings('ignore', message='All-NaN slice encountered')
warnings.filterwarnings('ignore', category=RuntimeWarning)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'process'))

from config import (
    YEARS, LAT_SIZE, LON_SIZE,
    TEST_LAT_RANGE, TEST_LON_RANGE, MOVING_WINDOW, MAX_EVENTS_PER_PIXEL,
    PERCENTILE_HIGH, PERCENTILE_LOW, MIN_DURATION
)
from drought_event_v54_utils import (
    EVENT_TYPE_LABELS_CN,
    EVENT_TYPE_ORDER,
    MAIN_EVENT_TYPES,
    OUTPUT_EVENT_TYPES,
    classify_onset_days_v54,
)

# ==================== 骤旱检测参数 ====================
MIN_ONSET_DAYS = 5
MAX_ONSET_DAYS = 20
LOOKBACK_MAX = 90
END_CONFIRM_DAYS = 10
MIN_DROUGHT_DAYS_BELOW_P20 = 15

# 百分位基准期
REF_START_YEAR = 1981
REF_END_YEAR = 2010
REF_YEARS = set(range(REF_START_YEAR, REF_END_YEAR + 1))

# 分块参数
DEFAULT_CHUNK_SIZE = 50

# 百分位窗口参数
PERCENTILE_WINDOW = 5
WINDOW_HALF = PERCENTILE_WINDOW // 2


# ============================================================
# Section 1: 解析命令行参数
# ============================================================

def parse_args(sm_var_name, description):
    """通用命令行解析"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--test-mode', action='store_true', help='测试模式')
    parser.add_argument('--lat-range', nargs=2, type=float, default=None)
    parser.add_argument('--lon-range', nargs=2, type=float, default=None)
    parser.add_argument('--workers', type=int, default=None)
    parser.add_argument('--chunk-size', type=int, default=DEFAULT_CHUNK_SIZE, help='每次处理的行数')
    parser.add_argument('--sm-file', type=str, default=None,
                        help=f'MERRA2 合并后的日尺度土壤湿度文件路径（包含变量 {sm_var_name}）')
    return parser.parse_args()


# ============================================================
# Section 2: 时间/索引构建
# ============================================================

def build_daily_indices_from_time(time_var, valid_years, ref_years):
    """从文件 time 轴构建日尺度索引与 DOY 索引（自动按日期排序）"""
    tvals = time_var[:]
    units = getattr(time_var, 'units', None)
    calendar = getattr(time_var, 'calendar', 'standard')
    if units is None:
        raise ValueError("time 变量缺少 units 属性，无法解析日期")

    # V5.4: 过滤 masked/无效时间值 (C3S 数据可能存在)
    if hasattr(tvals, 'mask'):
        valid_mask = ~np.ma.getmaskarray(tvals)
        valid_indices = np.where(valid_mask)[0]
        tvals_valid = tvals[valid_mask].data
        n_masked = len(tvals) - len(valid_indices)
        if n_masked > 0:
            print(f"  [注意] 过滤了 {n_masked} 个 masked 时间值")
    else:
        valid_indices = np.arange(len(tvals))
        tvals_valid = np.asarray(tvals)

    datetimes = nc.num2date(tvals_valid, units=units, calendar=calendar)

    day_map = {}
    for i, t in enumerate(datetimes):
        idx = int(valid_indices[i])
        try:
            y = int(t.year)
        except (AttributeError, TypeError):
            continue
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

    # V5.4 新增: 检测时间索引是否连续, 连续则可用切片加速 I/O
    time_slice = None
    if is_daily and daily_time_indices is not None and len(daily_time_indices) > 0:
        t_start = int(daily_time_indices[0])
        t_end = int(daily_time_indices[-1]) + 1
        if t_end - t_start == len(daily_time_indices):
            time_slice = (t_start, t_end)

    return dates, doy_to_indices, doy_to_indices_for_ref, time_groups, is_daily, daily_time_indices, time_slice


def get_doy_window(doy, window_half=WINDOW_HALF):
    """获取DOY的窗口范围 (固定5天窗口, 循环边界处理)"""
    window_doys = []
    for offset in range(-window_half, window_half + 1):
        target_doy = doy + offset
        if target_doy < 1:
            target_doy += 365
        elif target_doy > 365:
            target_doy -= 365
        window_doys.append(target_doy)
    return window_doys


def build_prebuilt_window_indices(doy_to_indices_for_ref, window_half=WINDOW_HALF):
    """
    V5.4 新增: 预构建所有 DOY 的窗口索引
    避免在 calculate_percentiles_batch 中每次重复构建
    """
    prebuilt = {}
    for doy in range(1, 366):
        window_doys = get_doy_window(doy, window_half)
        all_indices = []
        for window_doy in window_doys:
            indices = doy_to_indices_for_ref.get(window_doy)
            if indices is not None and len(indices) > 0:
                all_indices.extend(indices.tolist())
        if len(all_indices) > 0:
            prebuilt[doy] = np.array(sorted(set(all_indices)), dtype=np.int32)
        else:
            prebuilt[doy] = np.array([], dtype=np.int32)
    return prebuilt


# ============================================================
# Section 3: 滑动平均计算
# ============================================================

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

        # V5.4: 减少中间数组, 直接计算窗口和
        window_sum = cum_sum.copy()
        window_count = cum_count.copy()
        if window < year_len:
            window_sum[window:] -= cum_sum[:-window]
            window_count[window:] -= cum_count[:-window]

        valid_window = window_count >= min_valid
        year_ma = np.full_like(year_data, np.nan, dtype=np.float64)
        year_ma[valid_window] = window_sum[valid_window] / window_count[valid_window]

        ma_2d[year_start:year_end, :] = year_ma

        # 释放年内中间数组
        del valid_mask, data_filled, cum_sum, cum_count
        del window_sum, window_count, valid_window, year_ma

    return ma_2d


# ============================================================
# Section 4: 百分位数计算 (优化版)
# ============================================================

def calculate_percentiles_batch(ma_2d, prebuilt_window_indices):
    """
    使用基准期 1981-2010 计算 P20/P40
    V5.4 优化:
      - 使用预构建的窗口索引 (避免重复构建)
      - 合并两个分位数为一次 np.nanpercentile 调用 (~1.5x 加速)
    """
    n_lon = ma_2d.shape[1]
    p20_2d = np.full((366, n_lon), np.nan, dtype=np.float64)
    p40_2d = np.full((366, n_lon), np.nan, dtype=np.float64)

    for doy in range(1, 366):
        indices = prebuilt_window_indices.get(doy)
        if indices is None or len(indices) == 0:
            continue

        window_data = ma_2d[indices, :]

        with np.errstate(all='ignore'):
            pcts = np.nanpercentile(window_data, [PERCENTILE_LOW, PERCENTILE_HIGH], axis=0)
            p20_2d[doy, :] = pcts[0]
            p40_2d[doy, :] = pcts[1]

        del window_data

    return p20_2d, p40_2d


# ============================================================
# Section 5: 干旱事件检测与分类
# ============================================================

def detect_all_drought_events(sm_ma, p20_arr, p40_arr, dates):
    """
    Step-A: 识别所有干旱事件 (基于 sm_ma < P20)
    结束条件: 连续 END_CONFIRM_DAYS 天 >= P40
    有效条件: 低于 P20 天数 >= MIN_DROUGHT_DAYS_BELOW_P20
    """
    n = len(sm_ma)
    events = []

    i = 0
    while i < n:
        year, doy = dates[i]

        if np.isnan(sm_ma[i]):
            i += 1
            continue

        p20 = p20_arr[doy]
        if np.isnan(p20):
            i += 1
            continue

        if sm_ma[i] < p20:
            drought_start_idx = i
            drought_start_year, drought_start_doy = dates[i]
            days_below_p20 = 1

            j = i + 1
            nan_count = 0
            confirmed_end_idx = None
            confirm_count = 0

            while j < n:
                if np.isnan(sm_ma[j]):
                    nan_count += 1
                    if nan_count >= 3:
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

                if sm_ma[j] < p20_j:
                    days_below_p20 += 1

                if sm_ma[j] >= p40_j:
                    confirm_count += 1
                    if confirm_count >= END_CONFIRM_DAYS:
                        confirmed_end_idx = j - END_CONFIRM_DAYS
                        break
                else:
                    confirm_count = 0

                j += 1

            if confirmed_end_idx is None:
                drought_end_idx = j - 1 if j > drought_start_idx else drought_start_idx
            else:
                drought_end_idx = confirmed_end_idx

            if drought_end_idx < drought_start_idx:
                drought_end_idx = drought_start_idx

            duration = drought_end_idx - drought_start_idx + 1

            if duration >= MIN_DURATION and days_below_p20 >= MIN_DROUGHT_DAYS_BELOW_P20:
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
    """Step-B: 对单个干旱事件进行 v5.4 三分类。"""
    drought_start_idx = event['start_idx']

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

    if onset_start_idx is not None:
        onset_days = drought_start_idx - onset_start_idx
        onset_drop = sm_ma[onset_start_idx] - sm_ma[drought_start_idx]
        onset_rate = onset_drop / onset_days if onset_days > 0 else np.nan
        onset_year, onset_doy = dates[onset_start_idx]
        event_type = classify_onset_days_v54(onset_days, has_onset_start=True)
    else:
        event_type = classify_onset_days_v54(-1, has_onset_start=False)
        onset_days = -1
        onset_drop = np.nan
        onset_rate = np.nan
        onset_year = -1
        onset_doy = -1

    return {
        'event_type': event_type,
        'onset_start_idx': onset_start_idx,
        'onset_start_year': onset_year if onset_start_idx is not None else -1,
        'onset_start_doy': onset_doy if onset_start_idx is not None else -1,
        'onset_days': onset_days,
        'onset_drop': onset_drop,
        'onset_rate': onset_rate
    }


def analyze_pixel_v5(sm_ma, p20_arr, p40_arr, dates):
    """V5.4 像元分析: 检测全部事件后按四类互斥分类。"""
    valid_ratio = np.sum(~np.isnan(sm_ma)) / len(sm_ma)
    if valid_ratio < 0.5:
        return None, None, False

    all_events = detect_all_drought_events(sm_ma, p20_arr, p40_arr, dates)

    if len(all_events) == 0:
        return [], {event_type: [] for event_type in EVENT_TYPE_ORDER}, True

    classified_events = {event_type: [] for event_type in EVENT_TYPE_ORDER}

    for event in all_events:
        classification = classify_event(event, sm_ma, p40_arr, dates)
        full_event = {**event, **classification}
        classified_events[classification['event_type']].append(full_event)

    return all_events, classified_events, True


# ============================================================
# Section 6: Worker 初始化与处理
# ============================================================

_GLOBAL_DATES = None
_GLOBAL_PREBUILT_WINDOW = None
_GLOBAL_SM_DS = None
_GLOBAL_SM_VAR = None
_GLOBAL_TIME_GROUPS = None
_GLOBAL_IS_DAILY = None
_GLOBAL_DAILY_TIME_INDICES = None
_GLOBAL_TIME_SLICE = None
_GLOBAL_YEARS = None
_GLOBAL_N_YEARS = None
_GLOBAL_YEAR_TO_IDX = None


def init_worker(sm_file, sm_var, dates, prebuilt_window,
                time_groups, is_daily, daily_time_indices, time_slice, years):
    """Worker 初始化: 打开 NC 文件, 设置全局变量"""
    global _GLOBAL_DATES, _GLOBAL_PREBUILT_WINDOW
    global _GLOBAL_SM_DS, _GLOBAL_SM_VAR
    global _GLOBAL_TIME_GROUPS, _GLOBAL_IS_DAILY, _GLOBAL_DAILY_TIME_INDICES
    global _GLOBAL_TIME_SLICE, _GLOBAL_YEARS, _GLOBAL_N_YEARS, _GLOBAL_YEAR_TO_IDX

    _GLOBAL_DATES = dates
    _GLOBAL_PREBUILT_WINDOW = prebuilt_window
    _GLOBAL_TIME_GROUPS = time_groups
    _GLOBAL_IS_DAILY = is_daily
    _GLOBAL_DAILY_TIME_INDICES = daily_time_indices
    _GLOBAL_TIME_SLICE = time_slice
    _GLOBAL_SM_VAR = sm_var
    _GLOBAL_YEARS = years
    _GLOBAL_N_YEARS = len(years)
    _GLOBAL_YEAR_TO_IDX = {y: i for i, y in enumerate(years)}
    _GLOBAL_SM_DS = nc.Dataset(sm_file, 'r')


def read_row_from_merged(lat_idx, lon_start, lon_end):
    """读取单行并聚合为日尺度 - V5.4: 优先使用连续切片加速"""
    var = _GLOBAL_SM_DS.variables[_GLOBAL_SM_VAR]
    n_lon = lon_end - lon_start

    if _GLOBAL_IS_DAILY:
        # V5.4: 连续时间索引使用切片, 避免碎片化 I/O
        if _GLOBAL_TIME_SLICE is not None:
            t_start, t_end = _GLOBAL_TIME_SLICE
            row_data = var[t_start:t_end, lat_idx, lon_start:lon_end]
        else:
            row_data = var[_GLOBAL_DAILY_TIME_INDICES, lat_idx, lon_start:lon_end]
        if hasattr(row_data, 'mask'):
            row_data = np.ma.filled(row_data, np.nan)
        return row_data.astype(np.float64)

    n_days = len(_GLOBAL_TIME_GROUPS)
    out = np.full((n_days, n_lon), np.nan, dtype=np.float64)

    for d, idxs in enumerate(_GLOBAL_TIME_GROUPS):
        day_data = var[idxs, lat_idx, lon_start:lon_end]
        if hasattr(day_data, 'mask'):
            day_data = np.ma.filled(day_data, np.nan)
        day_data = day_data.astype(np.float64)
        if day_data.ndim == 1:
            out[d, :] = day_data
        else:
            out[d, :] = np.nanmean(day_data, axis=0)

    return out


def process_single_row(args):
    """
    处理单行 - V5.4 优化版
    优化:
      - 海洋行轻量返回 (仅标记, 不创建填充数组)
      - 年度数据用 3 个紧凑数组替代 135 个独立数组
      - 使用预构建窗口索引加速百分位数计算
    """
    row_idx, lat_idx_global, lon_start, lon_end, n_lon = args

    dates = _GLOBAL_DATES
    years = _GLOBAL_YEARS
    n_years = _GLOBAL_N_YEARS
    year_to_idx = _GLOBAL_YEAR_TO_IDX

    try:
        row_data = read_row_from_merged(lat_idx_global, lon_start, lon_end)

        # V5.4: 海洋行轻量返回, 不创建任何填充数组
        if np.all(np.isnan(row_data)):
            del row_data
            return {'row_idx': row_idx, 'is_ocean': True}

        ma_2d = calculate_backward_moving_average_by_year(row_data, dates, MOVING_WINDOW)
        del row_data

        # V5.4: 使用预构建窗口索引
        p20_2d, p40_2d = calculate_percentiles_batch(ma_2d, _GLOBAL_PREBUILT_WINDOW)

        row_freq = {event_type: np.full(n_lon, np.nan, dtype=np.float32) for event_type in OUTPUT_EVENT_TYPES}
        yearly_freq = {
            event_type: np.full((n_years, n_lon), np.nan, dtype=np.float32) for event_type in OUTPUT_EVENT_TYPES
        }
        row_events = {event_type: [] for event_type in OUTPUT_EVENT_TYPES}

        valid_count = 0
        event_counts = {event_type: 0 for event_type in OUTPUT_EVENT_TYPES}

        for j in range(n_lon):
            pixel_ma = ma_2d[:, j]

            if np.all(np.isnan(pixel_ma)):
                continue

            p20_pixel = p20_2d[:, j]
            p40_pixel = p40_2d[:, j]

            all_evts, classified_evts, is_valid = analyze_pixel_v5(
                pixel_ma, p20_pixel, p40_pixel, dates
            )

            if not is_valid:
                del all_evts, classified_evts
                continue

            row_freq['total'][j] = len(all_evts)
            for event_type in EVENT_TYPE_ORDER:
                row_freq[event_type][j] = len(classified_evts[event_type])

            for e in all_evts:
                yi = year_to_idx.get(e['drought_start_year'])
                if yi is not None:
                    yearly_freq['total'][yi, j] = (
                        yearly_freq['total'][yi, j] + 1
                    ) if not np.isnan(yearly_freq['total'][yi, j]) else 1

            for event_type in EVENT_TYPE_ORDER:
                for e in classified_evts[event_type]:
                    yi = year_to_idx.get(e['drought_start_year'])
                    if yi is not None:
                        yearly_freq[event_type][yi, j] = (
                            yearly_freq[event_type][yi, j] + 1
                        ) if not np.isnan(yearly_freq[event_type][yi, j]) else 1

            for yi_init in range(n_years):
                for event_type in OUTPUT_EVENT_TYPES:
                    if np.isnan(yearly_freq[event_type][yi_init, j]):
                        yearly_freq[event_type][yi_init, j] = 0

            row_events['total'].append((j, all_evts[:MAX_EVENTS_PER_PIXEL]))
            for event_type in EVENT_TYPE_ORDER:
                row_events[event_type].append((j, classified_evts[event_type][:MAX_EVENTS_PER_PIXEL]))

            del all_evts, classified_evts

            valid_count += 1
            for event_type in OUTPUT_EVENT_TYPES:
                event_counts[event_type] += int(row_freq[event_type][j])

        del ma_2d, p20_2d, p40_2d

        result = {
            'row_idx': row_idx,
            'is_ocean': False,
            'valid_count': valid_count,
        }
        for event_type in OUTPUT_EVENT_TYPES:
            result[event_type] = row_freq[event_type]
            result[f'yearly_{event_type}'] = yearly_freq[event_type]
            result[f'{event_type}_events'] = row_events[event_type]
            result[f'{event_type}_event_count'] = event_counts[event_type]
        return result
    except Exception as e:
        print(f"\n[错误] 行 {row_idx}: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================
# Section 7: 输出文件初始化
# ============================================================

def init_netcdf_files(result_dir, n_lat, n_lon, lat_sub, lon_sub, sm_var, source_label):
    """初始化 NetCDF 文件结构 - V5.4: 优化 chunksizes 以适配逐行写入"""
    filepaths = {}

    for event_type in OUTPUT_EVENT_TYPES:
        filepath = os.path.join(result_dir, f"{event_type}_drought_events_v5.4.nc")
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

            ds.createVariable('event_count', 'i2', ('lat', 'lon'),
                              fill_value=-1, zlib=True,
                              chunksizes=(1, n_lon))

            # V5.4: chunksizes 优化为 (max_events, 1, n_lon) 适配逐行写入
            event_chunk = (MAX_EVENTS_PER_PIXEL, 1, n_lon)

            for key in ['onset_start_year', 'onset_start_doy', 'drought_start_year', 'drought_start_doy',
                        'drought_end_year', 'drought_end_doy', 'onset_days', 'duration', 'days_below_p20']:
                ds.createVariable(key, 'i2', ('max_events', 'lat', 'lon'),
                                  fill_value=-1, zlib=True, chunksizes=event_chunk)

            for key in ['onset_drop', 'onset_rate', 'intensity']:
                ds.createVariable(key, 'f4', ('max_events', 'lat', 'lon'),
                                  fill_value=-9999, zlib=True, chunksizes=event_chunk)

            ds.title = f'{event_type} Drought Events Details v5.4'
            ds.source = f'{source_label} ({YEARS[0]}-{YEARS[-1]})'
            ds.algorithm = 'Two-step Method v5.4 (Three-class, 5-day Window Percentile)'
            ds.percentile_baseline = f'{REF_START_YEAR}-{REF_END_YEAR}'
            ds.percentile_window = f'{PERCENTILE_WINDOW} days (±{WINDOW_HALF})'

    return filepaths


def init_tiff_files(result_dir, n_lat, n_lon, lat_sub, lon_sub):
    """初始化 TIFF 文件结构 - V5.4: 修正坐标系方向"""
    from osgeo import gdal, osr

    n_lat, n_lon = int(n_lat), int(n_lon)
    filepaths = {}

    lon_res = abs(lon_sub[1] - lon_sub[0]) if len(lon_sub) > 1 else 0.1
    lat_res = abs(lat_sub[1] - lat_sub[0]) if len(lat_sub) > 1 else 0.1

    # GeoTransform 原点应在左上角 (西经, 北纬)
    # TIFF 标准: 行从北向南排列, 所以 Y 分辨率为负
    lat_max = float(max(lat_sub[0], lat_sub[-1]))
    lon_min = float(min(lon_sub[0], lon_sub[-1]))
    geotransform = (lon_min - lon_res/2, lon_res, 0,
                    lat_max + lat_res/2, 0, -lat_res)

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    projection = srs.ExportToWkt()

    driver = gdal.GetDriverByName('GTiff')

    for event_type in OUTPUT_EVENT_TYPES:
        filepath = os.path.join(result_dir, f"{event_type}_drought_frequency_{YEARS[0]}_{YEARS[-1]}_v5.4.tif")
        filepaths[f'{event_type}_freq'] = filepath

        out_ds = driver.Create(filepath, n_lon, n_lat, 1, gdal.GDT_Float32)
        out_ds.SetGeoTransform(geotransform)
        out_ds.SetProjection(projection)
        band = out_ds.GetRasterBand(1)
        band.SetNoDataValue(-9999)
        band.Fill(-9999)
        band.FlushCache()
        out_ds = None

    for year in YEARS:
        for event_type in OUTPUT_EVENT_TYPES:
            filepath = os.path.join(result_dir, f"{event_type}_drought_{year}_v5.4.tif")
            filepaths[f'{event_type}_{year}'] = filepath

            out_ds = driver.Create(filepath, n_lon, n_lat, 1, gdal.GDT_Float32)
            out_ds.SetGeoTransform(geotransform)
            out_ds.SetProjection(projection)
            band = out_ds.GetRasterBand(1)
            band.SetNoDataValue(-9999)
            band.Fill(-9999)
            band.FlushCache()
            out_ds = None

    return filepaths


# ============================================================
# Section 8: 输出写入函数
# ============================================================

def write_row_events_to_nc(nc_handles, result, global_row, n_lon):
    """
    V5.4 新增: 逐行写入事件到 NC 文件
    替代 v5.3 的 chunk_events 缓冲区方式, 峰值内存从 ~720MB 降到 ~15MB
    """
    for event_type in OUTPUT_EVENT_TYPES:
        ds = nc_handles[event_type]
        events_list = result[f'{event_type}_events']

        # 构建当前行的事件数组
        event_count_row = np.full(n_lon, -1, dtype=np.int16)
        osy = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -1, dtype=np.int16)
        osd = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -1, dtype=np.int16)
        dsy = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -1, dtype=np.int16)
        dsd = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -1, dtype=np.int16)
        dey = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -1, dtype=np.int16)
        ded = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -1, dtype=np.int16)
        ond = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -1, dtype=np.int16)
        dur = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -1, dtype=np.int16)
        dbp = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -1, dtype=np.int16)
        odr = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -9999, dtype=np.float32)
        ort = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -9999, dtype=np.float32)
        ity = np.full((MAX_EVENTS_PER_PIXEL, n_lon), -9999, dtype=np.float32)

        for j, evts in events_list:
            event_count_row[j] = len(evts)
            for k, e in enumerate(evts):
                osy[k, j] = e.get('onset_start_year', -1)
                osd[k, j] = e.get('onset_start_doy', -1)
                dsy[k, j] = e['drought_start_year']
                dsd[k, j] = e['drought_start_doy']
                dey[k, j] = e['drought_end_year']
                ded[k, j] = e['drought_end_doy']
                ond[k, j] = e.get('onset_days', -1)
                dur[k, j] = e['duration']
                dbp[k, j] = e.get('days_below_p20', -1)
                odr[k, j] = e.get('onset_drop', -9999)
                ort[k, j] = e.get('onset_rate', -9999)
                ity[k, j] = e['intensity']

        # 批量写入 (一次写入一行的所有事件变量)
        ds.variables['event_count'][global_row, :] = event_count_row
        ds.variables['onset_start_year'][:, global_row, :] = osy
        ds.variables['onset_start_doy'][:, global_row, :] = osd
        ds.variables['drought_start_year'][:, global_row, :] = dsy
        ds.variables['drought_start_doy'][:, global_row, :] = dsd
        ds.variables['drought_end_year'][:, global_row, :] = dey
        ds.variables['drought_end_doy'][:, global_row, :] = ded
        ds.variables['onset_days'][:, global_row, :] = ond
        ds.variables['duration'][:, global_row, :] = dur
        ds.variables['days_below_p20'][:, global_row, :] = dbp
        ds.variables['onset_drop'][:, global_row, :] = odr
        ds.variables['onset_rate'][:, global_row, :] = ort
        ds.variables['intensity'][:, global_row, :] = ity

        del event_count_row, osy, osd, dsy, dsd, dey, ded, ond, dur, dbp, odr, ort, ity


def write_chunk_to_tiff(tiff_filepaths, chunk_freq_data, chunk_yearly_data, chunk_start, chunk_size, n_lat, years, lat_flipped):
    """
    将块数据写入 TIFF 文件
    V5.4: 支持 lat 方向翻转, 确保 TIFF 行序为 N→S
    """
    from osgeo import gdal

    for event_type in OUTPUT_EVENT_TYPES:
        filepath = tiff_filepaths[f'{event_type}_freq']
        ds = gdal.Open(filepath, gdal.GA_Update)
        band = ds.GetRasterBand(1)
        data = np.where(np.isnan(chunk_freq_data[event_type]), -9999, chunk_freq_data[event_type])
        if lat_flipped:
            # NC 数据按 S→N 排列, TIFF 需要 N→S
            # chunk_start 是 NC 中的起始行 (从南端开始), 对应 TIFF 中的行要翻转
            tiff_yoff = n_lat - chunk_start - data.shape[0]
            data = data[::-1]
        else:
            tiff_yoff = chunk_start
        band.WriteArray(data, xoff=0, yoff=tiff_yoff)
        band.FlushCache()
        ds = None

        for yi, year in enumerate(years):
            filepath = tiff_filepaths[f'{event_type}_{year}']
            ds = gdal.Open(filepath, gdal.GA_Update)
            band = ds.GetRasterBand(1)
            data = np.where(np.isnan(chunk_yearly_data[event_type][yi]),
                            -9999, chunk_yearly_data[event_type][yi])
            if lat_flipped:
                tiff_yoff = n_lat - chunk_start - data.shape[0]
                data = data[::-1]
            else:
                tiff_yoff = chunk_start
            band.WriteArray(data, xoff=0, yoff=tiff_yoff)
            band.FlushCache()
            ds = None


# ============================================================
# Section 9: 主处理函数
# ============================================================

def run_main(sm_file, sm_var, result_dir, label_long):
    """
    骤旱检测主入口 v5.4

    参数:
        sm_file: NC 输入文件路径
        sm_var: 变量名 (SFMC / RZMC)
        result_dir: 结果输出目录
        label_long: 显示标签 (如 'MERRA2 SFMC 表层')
    """
    args = parse_args(sm_var, f'全球干旱检测程序 v5.4 (性能优化版) - {label_long}')

    if args.sm_file:
        sm_file = args.sm_file

    n_workers = args.workers if args.workers else max(1, cpu_count() - 1)
    chunk_size = args.chunk_size

    print("=" * 70)
    print(f"   全球干旱检测 v5.4 - 性能与内存深度优化版 ({label_long}, 日尺度)")
    print("=" * 70)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"并行进程数: {n_workers}")
    print(f"数据年份: {YEARS[0]} - {YEARS[-1]}")
    print(f"输入文件: {sm_file}")
    print(f"结果目录: {result_dir}")
    print()
    print("[算法参数]")
    print(f"  滑动窗口: {MOVING_WINDOW} 天")
    print(f"  干旱阈值: P{PERCENTILE_LOW}, 湿润阈值: P{PERCENTILE_HIGH}")
    print(f"  骤旱 onset: {MIN_ONSET_DAYS}-{MAX_ONSET_DAYS} 天")
    print(f"  最小持续: {MIN_DURATION} 天")
    print(f"  回溯窗口: {LOOKBACK_MAX} 天")
    print(f"  结束确认: {END_CONFIRM_DAYS} 天")
    print()
    print("[V5.4 核心优化]")
    print(f"  ✓ Pool 全局复用: 避免每 chunk 重建进程池")
    print(f"  ✓ NC I/O: 连续时间索引使用切片加速")
    print(f"  ✓ 内存优化: 消除 chunk_events 缓冲区 (~720MB → ~15MB/行)")
    print(f"  ✓ 海洋行轻量返回: 减少 ~70% 无效传输")
    print(f"  ✓ 百分位数: 预构建窗口索引 + 合并分位数调用")
    print(f"  ✓ 年度数据: 紧凑数组 (3个替代135个)")
    print(f"  ✓ NC chunksizes 优化: 适配逐行写入模式")
    print()
    print("[V5.3 继承特性]")
    print(f"  ✓ 百分位数窗口: {PERCENTILE_WINDOW} 天 (当天 ±{WINDOW_HALF} 天)")
    print("  ✓ 两步法: 先检测全部干旱，再分类")
    print("  ✓ 五类输出: Total / 1-4天 / 5-20天 / >20天 / 持续偏干")
    print("  ✓ 主分析三类: 1-4天 / 5-20天 / >20天")
    print(f"  ✓ 分块处理: 每次处理 {chunk_size} 行纬度")
    print("  ✓ 增量写入: 处理完一块立即写入磁盘")

    print("\n[预处理] 从 time 轴构建日尺度索引与 DOY 索引...")
    with nc.Dataset(sm_file, 'r') as ds:
        if sm_var not in ds.variables:
            raise ValueError(f"输入文件不包含变量 {sm_var}: {sm_file}")
        lat_array = ds.variables['lat'][:]
        lon_array = ds.variables['lon'][:]
        dates, doy_to_indices, doy_to_indices_ref, time_groups, is_daily, daily_time_indices, time_slice = \
            build_daily_indices_from_time(ds.variables['time'], set(YEARS), REF_YEARS)

    print(f"  日尺度时间步: {len(dates)}")
    if dates:
        print(f"  日尺度起止: {dates[0][0]}(DOY={dates[0][1]}) -> {dates[-1][0]}(DOY={dates[-1][1]})")
    print(f"  输入文件是否已是日尺度: {'是' if is_daily else '否（已在脚本内聚合到日尺度）'}")
    if time_slice:
        print(f"  ✓ 时间索引连续, 使用切片加速 I/O: [{time_slice[0]}:{time_slice[1]}]")
    else:
        print(f"  ✗ 时间索引不连续, 使用整数索引读取")

    # V5.4: 预构建窗口索引
    print("\n[预处理] 预构建百分位数窗口索引...")
    prebuilt_window = build_prebuilt_window_indices(doy_to_indices_ref, WINDOW_HALF)
    valid_doys = sum(1 for v in prebuilt_window.values() if len(v) > 0)
    print(f"  有效 DOY: {valid_doys}/365")

    print(f"\n[窗口验证] 测试关键DOY的5天窗口:")
    for test_doy in [1, 2, 183, 364, 365]:
        window = get_doy_window(test_doy, WINDOW_HALF)
        n_samples = len(prebuilt_window.get(test_doy, []))
        print(f"  DOY {test_doy:3d}: 窗口 = {window}, 样本数 = {n_samples}")

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

    # V5.4: 检测 lat 是否 S→N 排列 (需要翻转 TIFF 数据)
    lat_flipped = len(lat_sub) > 1 and lat_sub[1] > lat_sub[0]
    if lat_flipped:
        print(f"  ✓ 纬度方向: S→N, TIFF 输出将自动翻转为 N→S")
    else:
        print(f"  ✓ 纬度方向: N→S, 无需翻转")

    os.makedirs(result_dir, exist_ok=True)

    # 初始化输出文件
    print("\n[初始化] 创建输出文件...")
    nc_filepaths = init_netcdf_files(result_dir, n_lat, n_lon, lat_sub, lon_sub, sm_var, label_long)
    tiff_filepaths = init_tiff_files(result_dir, n_lat, n_lon, lat_sub, lon_sub)
    print(f"  已创建 {len(nc_filepaths)} 个 NetCDF 文件")
    print(f"  已创建 {len(tiff_filepaths)} 个 TIFF 文件")

    print(f"\n[处理开始] 使用 {n_workers} 个进程, 分块大小 {chunk_size}...")
    print("-" * 70)

    start_time = time.time()
    stats = {'valid': 0, **{event_type: 0 for event_type in OUTPUT_EVENT_TYPES}}
    completed_rows = 0
    n_chunks = (n_lat + chunk_size - 1) // chunk_size
    n_years = len(YEARS)

    # V5.4: 预先打开 NC 输出文件, 全程保持打开
    nc_handles = {}
    for event_type, filepath in nc_filepaths.items():
        nc_handles[event_type] = nc.Dataset(filepath, 'r+')

    try:
        # V5.4: Pool 全局复用, 整个处理过程只创建一次
        with Pool(processes=n_workers, initializer=init_worker,
                  initargs=(sm_file, sm_var, dates, prebuilt_window,
                            time_groups, is_daily, daily_time_indices,
                            time_slice, YEARS)) as pool:

            for chunk_idx in range(n_chunks):
                chunk_start = chunk_idx * chunk_size
                chunk_end = min(chunk_start + chunk_size, n_lat)
                actual_chunk_size = chunk_end - chunk_start

                print(f"\n[块 {chunk_idx+1}/{n_chunks}] 处理行 {chunk_start}-{chunk_end-1} (共 {actual_chunk_size} 行)")

                tasks = [(i, lat_idx_min + chunk_start + i, lon_idx_min, lon_idx_max + 1, n_lon)
                         for i in range(actual_chunk_size)]

                # V5.4: 只保留小的 freq/yearly 缓冲区, 不再有 chunk_events
                chunk_freq = {
                    event_type: np.full((actual_chunk_size, n_lon), np.nan, dtype=np.float32)
                    for event_type in OUTPUT_EVENT_TYPES
                }

                chunk_yearly = {
                    event_type: np.full((n_years, actual_chunk_size, n_lon), np.nan, dtype=np.float32)
                    for event_type in OUTPUT_EVENT_TYPES
                }

                chunk_completed = 0

                for result in pool.imap_unordered(process_single_row, tasks, chunksize=4):
                    if result is None:
                        chunk_completed += 1
                        continue

                    row_idx = result['row_idx']

                    # V5.4: 海洋行跳过, 不需要写任何数据 (输出文件已初始化为 fill_value)
                    if result.get('is_ocean'):
                        chunk_completed += 1
                        continue

                    # 更新频率缓冲区
                    for event_type in OUTPUT_EVENT_TYPES:
                        chunk_freq[event_type][row_idx] = result[event_type]
                        chunk_yearly[event_type][:, row_idx, :] = result[f'yearly_{event_type}']

                    # V5.4: 事件直接逐行写入 NC (不缓冲整个 chunk)
                    global_row = chunk_start + row_idx
                    write_row_events_to_nc(nc_handles, result, global_row, n_lon)

                    # 立即释放事件数据
                    for event_type in OUTPUT_EVENT_TYPES:
                        del result[f'{event_type}_events']
                        del result[f'yearly_{event_type}']

                    stats['valid'] += result['valid_count']
                    for event_type in OUTPUT_EVENT_TYPES:
                        stats[event_type] += result[f'{event_type}_event_count']
                    chunk_completed += 1

                    elapsed = time.time() - start_time
                    progress = (completed_rows + chunk_completed) / n_lat * 100
                    speed = (completed_rows + chunk_completed) / elapsed if elapsed > 0 else 0
                    eta = (n_lat - completed_rows - chunk_completed) / speed if speed > 0 else 0
                    print(
                        f"\r  [{progress:.1f}%] Total:{stats['total']} "
                        f"1-4d:{stats['rapid_1to4']} 5-20d:{stats['flash_5to20']} "
                        f">20d:{stats['slow_gt20']} Dry:{stats['dry_to_drier']} "
                        f"| {speed:.1f}行/s | ETA:{eta/60:.1f}m",
                        end='',
                        flush=True,
                    )

                # 写入频率和年度数据到 TIFF
                print(f"\n  写入块 {chunk_idx+1} TIFF 数据到磁盘...")
                write_chunk_to_tiff(tiff_filepaths, chunk_freq, chunk_yearly, chunk_start, actual_chunk_size, n_lat, YEARS, lat_flipped)

                # 刷新 NC 文件
                for ds_handle in nc_handles.values():
                    ds_handle.sync()

                completed_rows += actual_chunk_size

                # 释放块缓冲区
                del chunk_freq, chunk_yearly, tasks
                gc.collect()
                print(f"  块 {chunk_idx+1} 完成, 内存已释放")

    finally:
        # 确保 NC 文件始终被正确关闭
        for ds_handle in nc_handles.values():
            try:
                ds_handle.close()
            except Exception:
                pass

    elapsed = time.time() - start_time
    print("\n\n" + "=" * 70)
    print("                    处理完成")
    print("=" * 70)
    print(f"总耗时: {elapsed/60:.1f}分钟")
    print(f"有效像元: {stats['valid']}")
    print(f"\n[事件统计]")
    if stats['total'] > 0:
        print(f"  Total drought:     {stats['total']}")
        for event_type in EVENT_TYPE_ORDER:
            print(
                f"  {EVENT_TYPE_LABELS_CN[event_type]}: {stats[event_type]} "
                f"({stats[event_type]/stats['total']*100:.1f}%)"
            )
        print(
            f"  验证 (四类和 = total): "
            f"{sum(stats[event_type] for event_type in EVENT_TYPE_ORDER)} = {stats['total']}"
        )
    else:
        print("  未检测到任何干旱事件")

    print(f"\n[V5.4 优化效果预期]")
    print(f"  主进程峰值内存: ~50MB (v5.3: ~770MB, 降低 93%)")
    print(f"  进程池创建次数: 1 (v5.3: {n_chunks})")
    print(f"  时间索引方式: {'连续切片' if time_slice else '整数索引'}")
    print(f"  百分位数窗口索引: 预构建 (v5.3: 每行重复构建)")
