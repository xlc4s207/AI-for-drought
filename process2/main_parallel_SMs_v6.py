# -*- coding: utf-8 -*-
"""
骤旱检测主程序 v6 - 改进版 (SMs 表层土壤湿度)
==================================================
V6 核心改进 (解决事件碎片化问题):
1. 修复 confirm_count 连续性: NaN/阈值缺失时清零
2. Gap Merge 机制: 合并间隔 ≤5 天的相邻事件
3. 跨年连续滑动平均: 避免年边界切断事件
4. DOY 阈值平滑: ±15天窗口减少锯齿化
5. 修复 onset_start_idx==0 判断 bug

算法流程:
  Step-A: detect_all_drought_events()
    - 基于 sm_ma < P20 识别所有干旱事件段
    - 结束需连续 K 天 >= P20 确认 (连续性严格)
  
  Step-A2: merge_close_events()
    - 合并间隔 ≤ GAP_MERGE_DAYS 的事件

  Step-B: classify_event()
    - 向前回溯找 onset_start (sm_ma > P40)
    - 根据 onset_days 分类: flash / slow-onset / dry-to-drier

作者: AI Assistant
日期: 2026-01-25
"""

import os
import sys
import argparse
import time
import numpy as np
import netCDF4 as nc
from datetime import datetime
from multiprocessing import Pool, cpu_count
import warnings

# 过滤 All-NaN slice 警告
warnings.filterwarnings('ignore', message='All-NaN slice encountered')
warnings.filterwarnings('ignore', category=RuntimeWarning)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'process'))

from config import (
    YEARS, LAT_SIZE, LON_SIZE,
    TEST_LAT_RANGE, TEST_LON_RANGE, MOVING_WINDOW, MAX_EVENTS_PER_PIXEL,
    PERCENTILE_HIGH, PERCENTILE_LOW, MIN_DURATION
)

# 数据路径配置 - SMs 表层土壤湿度
BASE_DIR = "/home/xulc/flash_drought/gleam"
SM_FILE = "/data/GLEAM/SMs_45years.nc"
RESULT_DIR = os.path.join(BASE_DIR, "Flash_result", "SMs_result_v6_Global")

# 骤旱爆发期时间约束
MIN_ONSET_DAYS = 5
MAX_ONSET_DAYS = 20    # 4个候 = 20天

# V5 参数
LOOKBACK_MAX = 90
END_CONFIRM_DAYS = 10     # 配合 P30 滞回阈值使用

# V6 新增参数
GAP_MERGE_DAYS = 10       # 事件合并最大间隙 (天)
DOY_SMOOTH_WINDOW = 15   # DOY 阈值平滑窗口 (±15天)
PERCENTILE_RECOVERY = 30 # 滞回恢复阈值 (P30)

# 百分位基准期
REF_START_YEAR = 1981
REF_END_YEAR = 2010
REF_YEARS = set(range(REF_START_YEAR, REF_END_YEAR + 1))


def parse_args():
    parser = argparse.ArgumentParser(description='全球干旱检测程序 v6 - SMs (改进版)')
    parser.add_argument('--test-mode', action='store_true', help='测试模式')
    parser.add_argument('--lat-range', nargs=2, type=float, default=None)
    parser.add_argument('--lon-range', nargs=2, type=float, default=None)
    parser.add_argument('--workers', type=int, default=None)
    parser.add_argument('--resume', action='store_true', help='断点续传模式')
    return parser.parse_args()


def calculate_backward_moving_average_continuous(data_2d, window=MOVING_WINDOW):
    """
    V6 改进: 跨年连续的后向滑动平均
    不再在年边界重置，避免跨年事件被切断
    """
    min_valid = window // 2
    T, n_lon = data_2d.shape
    ma_2d = np.full_like(data_2d, np.nan, dtype=np.float64)
    
    valid_mask = ~np.isnan(data_2d)
    data_filled = np.where(valid_mask, data_2d, 0.0)
    
    cum_sum = np.cumsum(data_filled, axis=0)
    cum_count = np.cumsum(valid_mask.astype(np.int32), axis=0)
    
    cum_sum_shifted = np.zeros_like(cum_sum)
    cum_count_shifted = np.zeros_like(cum_count)
    
    if window < T:
        cum_sum_shifted[window:] = cum_sum[:-window]
        cum_count_shifted[window:] = cum_count[:-window]
    
    window_sum = cum_sum - cum_sum_shifted
    window_count = cum_count - cum_count_shifted
    
    valid_window = window_count >= min_valid
    ma_2d[valid_window] = window_sum[valid_window] / window_count[valid_window]
    
    return ma_2d


def build_doy_indices(years):
    """预计算 DOY 索引"""
    dates = []
    doy_to_indices = {doy: [] for doy in range(1, 366)}
    doy_to_indices_for_ref = {doy: [] for doy in range(1, 366)}
    
    idx = 0
    for year in years:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            n_days = 366
        else:
            n_days = 365
        
        for doy in range(1, n_days + 1):
            doy_mapped = 365 if doy == 366 else doy
            dates.append((year, doy_mapped))
            doy_to_indices[doy_mapped].append(idx)
            
            if year in REF_YEARS:
                doy_to_indices_for_ref[doy_mapped].append(idx)
            
            idx += 1
    
    for doy in doy_to_indices:
        doy_to_indices[doy] = np.array(doy_to_indices[doy], dtype=np.int32)
        doy_to_indices_for_ref[doy] = np.array(doy_to_indices_for_ref[doy], dtype=np.int32)
    
    return dates, doy_to_indices, doy_to_indices_for_ref


def read_row_from_merged(lat_idx, lon_start, lon_end, sm_ds):
    """从合并后的45年NC文件读取一行数据"""
    row_data = sm_ds.variables['SMs'][:, lat_idx, lon_start:lon_end]
    if hasattr(row_data, 'mask'):
        row_data = np.ma.filled(row_data, np.nan)
    return row_data.astype(np.float64)


def calculate_percentiles_smoothed(ma_2d, doy_to_indices_for_ref, doy_window=DOY_SMOOTH_WINDOW):
    """
    V6 优化版: 直接按 DOY 计算百分位阈值 (无 DOY 窗口平滑)
    包含 P20, P30, P40 三个阈值
    
    注意: 这是 V5 风格的快速版本，移除了 ±doy_window 的平滑处理。
    平滑功能可能导致 ~30-50x 性能下降，因此在全球尺度暂时关闭。
    """
    n_lon = ma_2d.shape[1]
    p20_2d = np.full((366, n_lon), np.nan, dtype=np.float64)
    p30_2d = np.full((366, n_lon), np.nan, dtype=np.float64)
    p40_2d = np.full((366, n_lon), np.nan, dtype=np.float64)
    
    for doy in range(1, 366):
        indices = doy_to_indices_for_ref.get(doy)
        if indices is None or len(indices) == 0:
            continue
        
        doy_data = ma_2d[indices, :]
        
        with np.errstate(all='ignore'):
            p20_2d[doy, :] = np.nanpercentile(doy_data, PERCENTILE_LOW, axis=0)
            p30_2d[doy, :] = np.nanpercentile(doy_data, PERCENTILE_RECOVERY, axis=0)
            p40_2d[doy, :] = np.nanpercentile(doy_data, PERCENTILE_HIGH, axis=0)
    
    return p20_2d, p30_2d, p40_2d


def detect_all_drought_events(sm_ma, p20_arr, p30_arr, dates):
    """
    Step-A: 识别所有干旱事件 (V6 改进版 + 滞回机制)
    
    改进: 
    - NaN 时清零 confirm_count (保证连续性)
    - 阈值缺失时也清零 confirm_count
    - 滞回机制: 开始用 P20，恢复用 P30
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
        
        # 找到干旱开始 (sm_ma < P20)
        if sm_ma[i] < p20:
            drought_start_idx = i
            drought_start_year, drought_start_doy = dates[i]
            
            j = i + 1
            nan_count = 0
            confirmed_end_idx = None
            confirm_count = 0
            
            while j < n:
                if np.isnan(sm_ma[j]):
                    nan_count += 1
                    confirm_count = 0  # V6 修复: 连续恢复被打断
                    if nan_count >= 3:
                        confirmed_end_idx = j - nan_count
                        break
                    j += 1
                    continue
                
                nan_count = 0
                _, doy_j = dates[j]
                p30_j = p30_arr[doy_j]  # 使用 P30 判断恢复 (滞回机制)
                
                if np.isnan(p30_j):
                    confirm_count = 0  # V6 修复: 阈值缺失也打断连续性
                    j += 1
                    continue
                
                # 恢复条件: SM >= P30 (滞回阈值)
                if sm_ma[j] >= p30_j:
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
            
            if duration >= MIN_DURATION:
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


def merge_close_events(events, sm_ma, p20_arr, dates, max_gap=GAP_MERGE_DAYS):
    """
    V6 新增: 合并间隔小于 max_gap 的相邻事件
    
    这可以避免阈值附近抖动导致的事件碎片化
    """
    if len(events) <= 1:
        return events
    
    # 按开始索引排序
    sorted_events = sorted(events, key=lambda e: e['start_idx'])
    merged = [sorted_events[0].copy()]
    
    for event in sorted_events[1:]:
        last = merged[-1]
        gap = event['start_idx'] - last['end_idx'] - 1
        
        if gap <= max_gap:
            # 合并事件: 扩展结束位置
            last['end_idx'] = event['end_idx']
            last['duration'] = last['end_idx'] - last['start_idx'] + 1
            last['intensity'] += event['intensity']
            last['drought_end_year'] = event['drought_end_year']
            last['drought_end_doy'] = event['drought_end_doy']
        else:
            merged.append(event.copy())
    
    # 重新验证最小持续时间
    final_events = [e for e in merged if e['duration'] >= MIN_DURATION]
    
    return final_events


def classify_event(event, sm_ma, p40_arr, dates):
    """
    Step-B: 对单个干旱事件进行分类 (V6 修复版)
    
    修复: onset_start_idx == 0 时的判断 bug
    """
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
        
        if MIN_ONSET_DAYS <= onset_days <= MAX_ONSET_DAYS:
            event_type = 'flash'
        else:
            event_type = 'slow_onset'
    else:
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
        'onset_start_year': onset_year if onset_start_idx is not None else -1,  # V6 修复
        'onset_start_doy': onset_doy if onset_start_idx is not None else -1,    # V6 修复
        'onset_days': onset_days,
        'onset_drop': onset_drop,
        'onset_rate': onset_rate
    }


def analyze_pixel_v6(sm_ma, p20_arr, p30_arr, p40_arr, dates):
    """V6 版本像元分析: 两步法 + Gap Merge + 滞回机制"""
    valid_ratio = np.sum(~np.isnan(sm_ma)) / len(sm_ma)
    if valid_ratio < 0.5:
        return None, None, None, False
    
    # Step-A: 检测所有干旱事件 (使用 P30 滞回恢复)
    all_events = detect_all_drought_events(sm_ma, p20_arr, p30_arr, dates)
    
    if len(all_events) == 0:
        return [], [], [], True
    
    # Step-A2: Gap Merge 合并相邻事件
    all_events = merge_close_events(all_events, sm_ma, p20_arr, dates)
    
    if len(all_events) == 0:
        return [], [], [], True
    
    # Step-B: 分类每个事件
    flash_events = []
    nonflash_events = []
    
    for event in all_events:
        classification = classify_event(event, sm_ma, p40_arr, dates)
        full_event = {**event, **classification}
        
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


def init_worker(dates, doy_indices, doy_indices_ref):
    global _GLOBAL_DATES, _GLOBAL_DOY_INDICES, _GLOBAL_DOY_INDICES_REF, _GLOBAL_SM_DS
    _GLOBAL_DATES = dates
    _GLOBAL_DOY_INDICES = doy_indices
    _GLOBAL_DOY_INDICES_REF = doy_indices_ref
    _GLOBAL_SM_DS = nc.Dataset(SM_FILE, 'r')


def process_single_row(args):
    """处理单行 - V6 版本"""
    row_idx, lat_idx_global, lon_start, lon_end, n_lon = args
    
    global _GLOBAL_DATES, _GLOBAL_DOY_INDICES, _GLOBAL_DOY_INDICES_REF, _GLOBAL_SM_DS
    dates = _GLOBAL_DATES
    doy_to_indices_ref = _GLOBAL_DOY_INDICES_REF
    
    try:
        row_data = read_row_from_merged(lat_idx_global, lon_start, lon_end, _GLOBAL_SM_DS)
        
        # V6: 使用跨年连续滑动平均
        ma_2d = calculate_backward_moving_average_continuous(row_data, MOVING_WINDOW)
        
        # V6: 使用 DOY 平滑阈值 (含 P30 滞回阈值)
        p20_2d, p30_2d, p40_2d = calculate_percentiles_smoothed(ma_2d, doy_to_indices_ref)
        
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
            p30_pixel = p30_2d[:, j]  # P30 滞回阈值
            p40_pixel = p40_2d[:, j]
            
            all_evts, flash_evts, nonflash_evts, is_valid = analyze_pixel_v6(
                pixel_ma, p20_pixel, p30_pixel, p40_pixel, dates
            )
            
            if not is_valid:
                continue
            
            row_total[j] = len(all_evts)
            row_flash[j] = len(flash_evts)
            row_nonflash[j] = len(nonflash_evts)
            
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
            
            row_total_events.append((j, all_evts[:MAX_EVENTS_PER_PIXEL]))
            row_flash_events.append((j, flash_evts[:MAX_EVENTS_PER_PIXEL]))
            row_nonflash_events.append((j, nonflash_evts[:MAX_EVENTS_PER_PIXEL]))
            
            valid_count += 1
            total_event_count += len(all_evts)
            flash_event_count += len(flash_evts)
            nonflash_event_count += len(nonflash_evts)
        
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


def init_netcdf_files(lat_sub, lon_sub, n_lat, n_lon, resume=False):
    """初始化输出 NetCDF 文件，返回文件句柄字典"""
    os.makedirs(RESULT_DIR, exist_ok=True)
    
    files = {}
    types = ['total', 'flash', 'nonflash']
    names = ['Total Drought', 'Flash Drought', 'Non-flash Drought']
    
    # 检查是否所有文件都存在且结构完整 (续传的前提)
    all_exist = True
    if resume:
        for t_name in types:
            fname = f"{t_name}_drought_SMs_events_v6.nc"
            fpath = os.path.join(RESULT_DIR, fname)
            if not os.path.exists(fpath):
                all_exist = False
                break
            
            # 完整性检查: 尝试打开并读取关键变量
            try:
                with nc.Dataset(fpath, 'r') as ds_check:
                    if 'event_count' not in ds_check.variables:
                        print(f"[警告] 文件 {fname} 损坏 (缺少 event_count)，将重新创建。")
                        all_exist = False
                        break
            except Exception as e:
                print(f"[警告] 文件 {fname} 无法读取 ({e})，将重新创建。")
                all_exist = False
                break
    
    # 如果断点续传失败 (文件缺失或损坏)，强制切换回 'w' 模式
    # 并清除进度记录，避免逻辑错乱
    if resume and not all_exist:
        print("[提示] 续传条件不满足 (文件不完整)，切换为重写模式。")
        mode = 'w'
        progress_file = get_progress_file()
        if os.path.exists(progress_file):
            os.remove(progress_file)
    else:
        mode = 'r+' if (resume and all_exist) else 'w'
    
    print(f"[初始化] NetCDF 模式: {mode} (Resume={resume}, Valid={all_exist})")
    
    for t_idx, t_name in enumerate(types):
        fname = f"{t_name}_drought_SMs_events_v6.nc"
        fpath = os.path.join(RESULT_DIR, fname)
        
        if mode == 'w':
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except OSError:
                    pass # 忽略无法删除的错误
            
            ds = nc.Dataset(fpath, 'w', format='NETCDF4')
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
            
            ds.title = f'{names[t_idx]} Events Details v6'
            ds.source = f'GLEAM SMs data ({YEARS[0]}-{YEARS[-1]})'
            ds.algorithm = 'Two-step Method v6 with Gap Merge'
            ds.percentile_baseline = f'{REF_START_YEAR}-{REF_END_YEAR}'
            
        else:
            ds = nc.Dataset(fpath, 'r+')
        
        files[t_name] = ds
        
    return files


def get_progress_file():
    return os.path.join(RESULT_DIR, "completed_rows.txt")

def get_completed_rows():
    """读取已完成的行号"""
    fpath = get_progress_file()
    if not os.path.exists(fpath):
        return set()
    with open(fpath, 'r') as f:
        rows = set()
        for line in f:
            try:
                rows.add(int(line.strip()))
            except ValueError:
                pass
    return rows

def mark_row_completed(row_idx):
    """标记行已完成"""
    with open(get_progress_file(), 'a') as f:
        f.write(f"{row_idx}\n")


def write_row_to_netcdf(row_idx, col_len, events_list, ds):
    """
    向量化写入 NetCDF (终极优化版)
    构建整行的全量数组，一次性写入，最大限度减少 IO 次数
    """
    if not events_list:
        return

    # 1. Event Count
    # 初始化全行数组 (Fill Value = -1)
    full_count = np.full(col_len, -1, dtype=np.int16)
    
    # 填充有效像元的值
    for col_idx, evts in events_list:
        full_count[col_idx] = len(evts)
        
    # 一次性写入整行
    ds.variables['event_count'][row_idx, :] = full_count
    
    # 2. 其他变量 (3D 变量)
    # Shape: (max_events, n_lon)
    # 我们只处理有事件的像元，减少循环次数
    
    # 提取有事件的像元 (count > 0)
    active_pixels = [(col, evts) for col, evts in events_list if len(evts) > 0]
    
    if not active_pixels:
        return

    # 定义变量及其 Fill Value
    vars_int = ['onset_start_year', 'onset_start_doy', 'drought_start_year', 'drought_start_doy',
                'drought_end_year', 'drought_end_doy', 'onset_days', 'duration']
    vars_float = ['onset_drop', 'onset_rate', 'intensity']
    
    # 预分配全行内存 (MAX_EVENTS, n_lon)
    # 约 50 * 3600 * 4 bytes = 720KB，非常小
    full_int_arrays = {v: np.full((MAX_EVENTS_PER_PIXEL, col_len), -1, dtype=np.int16) for v in vars_int}
    full_float_arrays = {v: np.full((MAX_EVENTS_PER_PIXEL, col_len), -9999.0, dtype=np.float32) for v in vars_float}
    
    # 填充数据 (纯内存操作，极快)
    for col_idx, evts in active_pixels:
        n = min(len(evts), MAX_EVENTS_PER_PIXEL)
        for k in range(n):
            e = evts[k]
            # Int vars
            full_int_arrays['onset_start_year'][k, col_idx] = e.get('onset_start_year', -1)
            full_int_arrays['onset_start_doy'][k, col_idx] = e.get('onset_start_doy', -1)
            full_int_arrays['drought_start_year'][k, col_idx] = e['drought_start_year']
            full_int_arrays['drought_start_doy'][k, col_idx] = e['drought_start_doy']
            full_int_arrays['drought_end_year'][k, col_idx] = e['drought_end_year']
            full_int_arrays['drought_end_doy'][k, col_idx] = e['drought_end_doy']
            full_int_arrays['onset_days'][k, col_idx] = e.get('onset_days', -1)
            full_int_arrays['duration'][k, col_idx] = e['duration']
            
            # Float vars
            full_float_arrays['onset_drop'][k, col_idx] = e.get('onset_drop', -9999)
            full_float_arrays['onset_rate'][k, col_idx] = e.get('onset_rate', -9999)
            full_float_arrays['intensity'][k, col_idx] = e['intensity']
            
    # 一次性写入 (IO 操作)
    # 格式: [:, row_idx, :]
    for v in vars_int:
        ds.variables[v][:, row_idx, :] = full_int_arrays[v]
        
    for v in vars_float:
        ds.variables[v][:, row_idx, :] = full_float_arrays[v]


def main():
    args = parse_args()
    n_workers = args.workers if args.workers else max(1, cpu_count() - 1)
    
    print("="*70)
    print("   全球干旱检测 v6 - SMs (向量化写入 + 断点续传)")
    print("="*70)
    # ... (header prints unchanged) ...
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"并行进程数: {n_workers}")
    print(f"数据年份: {YEARS[0]} - {YEARS[-1]}")
    print(f"结果目录: {RESULT_DIR}")
    print(f"断点续传: {'开启' if args.resume else '关闭'}")
    
    # ... (omitted algorithm params prints) ...
    print()
    print("[算法参数]")
    print(f"  滑动窗口: {MOVING_WINDOW} 天")
    print(f"  干旱阈值: P{PERCENTILE_LOW}, 恢复阈值: P{PERCENTILE_RECOVERY} (滞回), 湿润阈值: P{PERCENTILE_HIGH}")
    print(f"  骤旱 onset: {MIN_ONSET_DAYS}-{MAX_ONSET_DAYS} 天")
    print(f"  最小持续: {MIN_DURATION} 天")
    print(f"  回溯窗口: {LOOKBACK_MAX} 天")
    print(f"  结束确认: {END_CONFIRM_DAYS} 天")
    
    print("\n[预处理] 构建 DOY 索引...")
    dates, doy_to_indices, doy_to_indices_ref = build_doy_indices(YEARS)
    print(f"  时间序列长度: {len(dates)} 天")
    
    with nc.Dataset(SM_FILE, 'r') as ds:
        lat_array = ds.variables['lat'][:]
        lon_array = ds.variables['lon'][:]
    
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
        lat_idx_min, lat_idx_max = 0, LAT_SIZE - 1
        lon_idx_min, lon_idx_max = 0, LON_SIZE - 1
    
    n_lat = lat_idx_max - lat_idx_min + 1
    n_lon = lon_idx_max - lon_idx_min + 1
    print(f"\n[处理范围] {n_lat} 行 x {n_lon} 列")
    
    # 内存优化: 移除巨大的 in-memory 字典
    # 仅保留频率统计
    freq_total = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    freq_flash = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    freq_nonflash = np.full((n_lat, n_lon), np.nan, dtype=np.float32)
    
    # 年度频率保留在内存，最后统一写 (比较小, 45 * 1800 * 3600 * 4 bytes ≈ 1GB，可接受)
    yearly_total = {year: np.full((n_lat, n_lon), np.nan, dtype=np.float32) for year in YEARS}
    yearly_flash = {year: np.full((n_lat, n_lon), np.nan, dtype=np.float32) for year in YEARS}
    yearly_nonflash = {year: np.full((n_lat, n_lon), np.nan, dtype=np.float32) for year in YEARS}
    
    lat_sub = lat_array[lat_idx_min:lat_idx_max+1]
    lon_sub = lon_array[lon_idx_min:lon_idx_max+1]
    
    # 初始化 NetCDF 文件
    print("\n[初始化] 准备 NetCDF 文件...")
    # 注意：如果 Resume，这里会以 r+ 打开
    nc_files = init_netcdf_files(lat_sub, lon_sub, n_lat, n_lon, resume=args.resume)
    
    # 检查已完成的行
    completed_rows = set()
    if args.resume:
        completed_rows = get_completed_rows()
        print(f"已完成行数: {len(completed_rows)}")
    else:
        # 非 resume 模式，清空记录
        if os.path.exists(get_progress_file()):
            os.remove(get_progress_file())
    
    all_rows = [(i, lat_idx_min + i, lon_idx_min, lon_idx_max + 1, n_lon) for i in range(n_lat)]
    
    # 过滤掉已完成的 (注意：i 是 0~n_lat-1 的相对索引)
    tasks = [t for t in all_rows if t[0] not in completed_rows]
    
    print(f"待处理行数: {len(tasks)} (总共 {len(all_rows)})")
    
    if len(tasks) == 0:
        print("所有任务已完成！")
        for ds in nc_files.values():
            ds.close()
        return

    print(f"\n[处理开始] 使用 {n_workers} 个进程...")
    print("-"*70)
    
    start_time = time.time()
    stats = {'valid': 0, 'total': 0, 'flash': 0, 'nonflash': 0}
    completed_in_session = 0
    total_to_process = len(tasks)
    
    # 减小 chunksize 以让 workers 更快启动
    with Pool(processes=n_workers, initializer=init_worker,
              initargs=(dates, doy_to_indices, doy_to_indices_ref)) as pool:
        
        for result in pool.imap_unordered(process_single_row, tasks, chunksize=1):
            if result is None:
                completed_in_session += 1
                continue
            
            row_idx = result['row_idx']
            
            freq_total[row_idx] = result['total']
            freq_flash[row_idx] = result['flash']
            freq_nonflash[row_idx] = result['nonflash']
            
            for year in YEARS:
                yearly_total[year][row_idx] = result['yearly_total'][year]
                yearly_flash[year][row_idx] = result['yearly_flash'][year]
                yearly_nonflash[year][row_idx] = result['yearly_nonflash'][year]
            
            # 关键修复: 传入 n_lon 作为 col_len
            write_row_to_netcdf(row_idx, n_lon, result['total_events'], nc_files['total'])
            write_row_to_netcdf(row_idx, n_lon, result['flash_events'], nc_files['flash'])
            write_row_to_netcdf(row_idx, n_lon, result['nonflash_events'], nc_files['nonflash'])
            
            # 标记完成
            mark_row_completed(row_idx)
            
            stats['valid'] += result['valid_count']
            stats['total'] += result['total_event_count']
            stats['flash'] += result['flash_event_count']
            stats['nonflash'] += result['nonflash_event_count']
            completed_in_session += 1
            
            if completed_in_session % 10 == 0 or completed_in_session == total_to_process:
                elapsed = time.time() - start_time
                speed = completed_in_session / elapsed if elapsed > 0 else 0
                eta = (total_to_process - completed_in_session) / speed if speed > 0 else 0
                print(f"\r[{completed_in_session}/{total_to_process}] Speed:{speed:.1f}行/s | "
                      f"ETA:{eta/60:.1f}m | Valid:{stats['valid']}", 
                      end='', flush=True)
    
    print("\n\n" + "="*70)
    print("[关闭文件 & 保存 TIFF]")
    print("="*70)
    
    # 关闭 NetCDF 文件
    for ds in nc_files.values():
        ds.close()
    
    # 注意：如果使用了 Resume，这里的 TIFF 只有最后一部分数据。
    if args.resume:
        print("\n[提示] 您使用了断点续传模式。")
        print("当前生成的 TIFF 仅包含本次运行处理的行。")
    
    from osgeo import gdal, osr
    
    def save_tiff(data, filename, lat_sub, lon_sub):
        filepath = os.path.join(RESULT_DIR, filename)
        rows, cols = data.shape
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(filepath, cols, rows, 1, gdal.GDT_Float32)
        
        lon_res = abs(lon_sub[1] - lon_sub[0]) if len(lon_sub) > 1 else 0.1
        lat_res = abs(lat_sub[1] - lat_sub[0]) if len(lat_sub) > 1 else 0.1
        geotransform = (float(lon_sub[0]) - lon_res/2, lon_res, 0,
                        float(lat_sub[0]) + lat_res/2, 0, -lat_res)
        out_ds.SetGeoTransform(geotransform)
        
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        out_ds.SetProjection(srs.ExportToWkt())
        
        band = out_ds.GetRasterBand(1)
        band.SetNoDataValue(-9999)
        band.WriteArray(np.where(np.isnan(data), -9999, data))
        band.FlushCache()
        out_ds = None
    
    print("  保存频率 TIFF...")
    save_tiff(freq_total, f"total_drought_SMs_frequency_{YEARS[0]}_{YEARS[-1]}.tif", lat_sub, lon_sub)
    save_tiff(freq_flash, f"flash_drought_SMs_frequency_{YEARS[0]}_{YEARS[-1]}.tif", lat_sub, lon_sub)
    save_tiff(freq_nonflash, f"nonflash_drought_SMs_frequency_{YEARS[0]}_{YEARS[-1]}.tif", lat_sub, lon_sub)
    
    print("  保存年度频率...")
    for year in YEARS:
        save_tiff(yearly_total[year], f"total_drought_SMs_{year}.tif", lat_sub, lon_sub)
        save_tiff(yearly_flash[year], f"flash_drought_SMs_{year}.tif", lat_sub, lon_sub)
        save_tiff(yearly_nonflash[year], f"nonflash_drought_SMs_{year}.tif", lat_sub, lon_sub)
    
    elapsed = time.time() - start_time
    print("\n" + "="*70)
    print("                    处理完成")
    print("="*70)
    print(f"总耗时: {elapsed/60:.1f}分钟")
    print(f"总事件数: {stats['total']}")


if __name__ == '__main__':
    main()
