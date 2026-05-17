"""
表层土壤湿度 (SMs) 骤旱对GPP影响分析 - v7 全球版
==========================================
基于 SMrz v7 全球版修改

关键特性：
  1. 记录所有事件，不论GPP是否明显下降
  2. response_detected 标志区分有/无明显响应
  3. 按行处理减少内存占用
"""
import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool
import warnings
from datetime import datetime
from numba import jit
warnings.filterwarnings('ignore')

# ============================================
# 配置 - SMs 全球版
# ============================================
BASE_DIR = "/home/xulc/flash_drought"
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMs/flash_drought_SMs_events_details_v2.nc")
MERGED_GPP_FILE = os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_result/BESS_GPP_1982_2022.nc")
OUTPUT_DIR = os.path.join(BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

START_YEAR, END_YEAR = 1982, 2022
WINDOW_BEFORE = 60
WINDOW_AFTER = 120
RESPONSE_SEARCH_WINDOW = 60
THRESHOLD_RESPONSE = -0.5
THRESHOLD_RECOVER = -0.25
CONSECUTIVE_DAYS_RESPONSE = 3
CONSECUTIVE_DAYS_RECOVER = 3
N_WORKERS = 16

# ============================================
# 全局变量
# ============================================
_gpp_ds = None
_event_ds = None
_gpp_var = None
_ec_var = None
_oy_var = None
_od_var = None
_lon_arr = None
_year_offsets = None
_doy_index = None

def build_year_offsets():
    offsets = {}
    cumsum = 0
    for year in range(START_YEAR, END_YEAR + 1):
        offsets[year] = cumsum
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        cumsum += 366 if is_leap else 365
    return offsets

def build_doy_index():
    idx_arr = []
    for year in range(START_YEAR, END_YEAR + 1):
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        for d in range(366 if is_leap else 365):
            doy_idx = d if is_leap else (d if d < 59 else d + 1)
            idx_arr.append(doy_idx)
    return np.array(idx_arr, dtype=np.int16)

def worker_init():
    global _gpp_ds, _event_ds, _gpp_var, _ec_var, _oy_var, _od_var
    global _lon_arr, _year_offsets, _doy_index
    
    _gpp_ds = nc.Dataset(MERGED_GPP_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')
    
    _gpp_var = _gpp_ds.variables['GPP']
    _ec_var = _event_ds.variables['event_count']
    _oy_var = _event_ds.variables['onset_start_year']
    _od_var = _event_ds.variables['onset_start_doy']
    
    _lon_arr = _gpp_ds.variables['lon'][:]
    
    _year_offsets = build_year_offsets()
    _doy_index = build_doy_index()

def calc_climatology_and_zscore_matrix(gpp_matrix, doy_idx):
    n_time, n_pixels = gpp_matrix.shape
    clim_mean = np.full((366, n_pixels), np.nan, dtype=np.float32)
    clim_std = np.full((366, n_pixels), np.nan, dtype=np.float32)
    
    for d in range(366):
        time_mask = (doy_idx == d)
        if not np.any(time_mask):
            continue
        data_chunk = gpp_matrix[time_mask, :]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            clim_mean[d, :] = np.nanmean(data_chunk, axis=0)
            clim_std[d, :] = np.nanstd(data_chunk, axis=0, ddof=0)
    
    clim_std[clim_std < 0.01] = np.nan
    full_mean = clim_mean[doy_idx, :]
    full_std = clim_std[doy_idx, :]
    
    with np.errstate(divide='ignore', invalid='ignore'):
        z_matrix = (gpp_matrix - full_mean) / full_std
    return z_matrix

@jit(nopython=True)
def smooth_causal_numba(x, window=7):
    n = len(x)
    result = np.full(n, np.nan)
    for i in range(n):
        start = max(0, i - window + 1)
        vals = []
        for j in range(start, i + 1):
            if not np.isnan(x[j]):
                vals.append(x[j])
        if len(vals) >= 3:
            result[i] = np.mean(np.array(vals))
    return result

@jit(nopython=True)
def find_threshold_crossing_numba(x, threshold, n_consecutive, max_search):
    n = min(len(x), max_search)
    for i in range(n - n_consecutive + 1):
        all_below = True
        valid_count = 0
        for j in range(i, i + n_consecutive):
            if np.isnan(x[j]) or x[j] > threshold:
                all_below = False
                break
            valid_count += 1
        if all_below and valid_count == n_consecutive:
            return i
    return -1

@jit(nopython=True)
def find_recovery_numba(x, start_idx, threshold, n_consecutive):
    n = len(x)
    for i in range(start_idx, n - n_consecutive + 1):
        all_above = True
        valid_count = 0
        for j in range(i, i + n_consecutive):
            if np.isnan(x[j]) or x[j] <= threshold:
                all_above = False
                break
            valid_count += 1
        if all_above and valid_count == n_consecutive:
            return i
    return -1

@jit(nopython=True)
def calc_linear_trend_numba(y):
    valid_x = []
    valid_y = []
    for i in range(len(y)):
        if not np.isnan(y[i]):
            valid_x.append(float(i))
            valid_y.append(y[i])
    if len(valid_x) < 10:
        return np.nan
    x_arr = np.array(valid_x)
    y_arr = np.array(valid_y)
    x_mean = np.mean(x_arr)
    y_mean = np.mean(y_arr)
    numerator = 0.0
    denominator = 0.0
    for i in range(len(x_arr)):
        numerator += (x_arr[i] - x_mean) * (y_arr[i] - y_mean)
        denominator += (x_arr[i] - x_mean) ** 2
    if denominator == 0:
        return np.nan
    return numerator / denominator

@jit(nopython=True)
def calc_all_metrics_v7_numba(post, threshold_resp, threshold_recov, 
                               n_consec_resp, n_consec_recov, max_search):
    n = len(post)
    pre_vals = []
    for i in range(min(60, n)):
        if not np.isnan(post[i]):
            pre_vals.append(post[i])
    
    if len(pre_vals) < 5:
        return 0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan
    
    post_part = post[60:]
    n_post = len(post_part)
    
    if n_post < 10:
        return 0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan
    
    gpp_min, t_min_all = 1e9, -1
    valid_vals = []
    for i in range(n_post):
        if not np.isnan(post_part[i]):
            valid_vals.append(post_part[i])
            if post_part[i] < gpp_min:
                gpp_min = post_part[i]
                t_min_all = i
    
    gpp_mean = np.mean(np.array(valid_vals)) if valid_vals else np.nan
    gpp_trend = calc_linear_trend_numba(post_part)
    
    t_response = find_threshold_crossing_numba(post_part, threshold_resp, n_consec_resp, max_search)
    
    if t_response == -1:
        return 0, gpp_min, gpp_mean, gpp_trend, t_min_all, -1, -1, np.nan, np.nan, np.nan
    
    t_min_local, min_val = -1, 1e9
    for i in range(t_response, n_post):
        if not np.isnan(post_part[i]) and post_part[i] < min_val:
            min_val = post_part[i]
            t_min_local = i
    
    if t_min_local == -1:
        return 1, gpp_min, gpp_mean, gpp_trend, t_min_all, t_response, -1, np.nan, np.nan, np.nan
    
    t_impact = t_min_local - t_response
    t_recover_idx = find_recovery_numba(post_part, t_min_local + 1, threshold_recov, n_consec_recov)
    
    if t_recover_idx == -1:
        t_recover, recovery_rate = np.nan, np.nan
    else:
        t_recover = t_recover_idx - t_min_local
        recovery_rate = (threshold_recov - min_val) / t_recover if t_recover > 0 else np.nan
    
    return 1, gpp_min, gpp_mean, gpp_trend, t_min_all, t_response, t_impact, min_val, t_recover, recovery_rate

def calc_metrics_v7(gpp_z_segment):
    if np.sum(~np.isnan(gpp_z_segment)) < 30:
        return None
    smoothed = smooth_causal_numba(gpp_z_segment, window=7)
    result = calc_all_metrics_v7_numba(smoothed, THRESHOLD_RESPONSE, THRESHOLD_RECOVER,
                                        CONSECUTIVE_DAYS_RESPONSE, CONSECUTIVE_DAYS_RECOVER,
                                        RESPONSE_SEARCH_WINDOW)
    return {
        'response_detected': int(result[0]),
        'gpp_min': float(result[1]),
        'gpp_mean': float(result[2]),
        'gpp_trend': float(result[3]),
        't_min': int(result[4]) if result[4] >= 0 else -1,
        't_response': int(result[5]) if result[5] >= 0 else -1,
        't_impact': int(result[6]) if result[6] >= 0 else -1,
        'amp_max': float(result[7]) if result[0] else float(result[1]),
        't_recover': float(result[8]),
        'recovery_rate': float(result[9])
    }

def process_row(lat_info):
    all_results = []
    try:
        lat_idx = lat_info['lat_idx']
        lat_val = lat_info['lat_val']
        lon_indices = lat_info['lon_indices']
        
        if not lon_indices:
            return [], 0
        
        gpp_row = _gpp_var[:, lat_idx, :]
        if hasattr(gpp_row, 'filled'):
            gpp_row = gpp_row.filled(np.nan).astype(np.float32)
        else:
            gpp_row = gpp_row.astype(np.float32)
        
        ec_row = _ec_var[lat_idx, :]
        max_ec = int(np.max([ec_row[j] for j in lon_indices]))
        if max_ec <= 0:
            return [], 0
        
        oy_row = _oy_var[:max_ec, lat_idx, :]
        od_row = _od_var[:max_ec, lat_idx, :]
        
        gpp_matrix = gpp_row[:, lon_indices]
        valid_count = np.sum(~np.isnan(gpp_matrix), axis=0)
        good_mask = valid_count >= 100
        
        if not np.any(good_mask):
            return [], 0
        
        good_indices = [lon_indices[i] for i, g in enumerate(good_mask) if g]
        gpp_matrix = gpp_row[:, good_indices]
        z_matrix = calc_climatology_and_zscore_matrix(gpp_matrix, _doy_index)
        
        for idx, lon_idx in enumerate(good_indices):
            ec = int(ec_row[lon_idx])
            gpp_z = z_matrix[:, idx]
            
            for i in range(ec):
                oy = int(oy_row[i, lon_idx])
                od = int(od_row[i, lon_idx])
                
                if oy < START_YEAR or oy > END_YEAR or od <= 0 or od > 366:
                    continue
                
                onset = _year_offsets[oy] + od - 1
                ws, we = onset - WINDOW_BEFORE, onset + WINDOW_AFTER
                
                if ws < 0 or we >= len(gpp_z):
                    continue
                
                m = calc_metrics_v7(gpp_z[ws:we+1])
                if m:
                    all_results.append({
                        'lat': lat_val,
                        'lon': float(_lon_arr[lon_idx]),
                        'event_id': i,
                        'onset_year': oy,
                        'onset_doy': od,
                        **m
                    })
    except:
        return [], 1
    return all_results, 0

def main():
    print("="*70)
    print("表层土壤湿度 (SMs) 骤旱对GPP影响分析 - v7 全球版")
    print("="*70)
    
    if not os.path.exists(MERGED_GPP_FILE) or not os.path.exists(DROUGHT_EVENTS_FILE):
        print("Error: 数据文件不存在")
        return
    
    print("="*70)
    print("Step 1: 确定全球范围")
    print("="*70)
    start_time = datetime.now()
    
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
        ec = ds.variables['event_count'][:]
        
        print(f"纬度范围: {lat.min():.1f} ~ {lat.max():.1f} ({len(lat)}行)")
        print(f"经度范围: {lon.min():.1f} ~ {lon.max():.1f} ({len(lon)}列)")
        
        tasks = []
        n_pixels = 0
        total_events = 0
        
        for i in range(len(lat)):
            lon_indices = [j for j in range(len(lon)) if ec[i, j] > 0]
            if lon_indices:
                tasks.append({'lat_idx': i, 'lat_val': float(lat[i]), 'lon_indices': lon_indices})
                n_pixels += len(lon_indices)
                for j in lon_indices:
                    total_events += int(ec[i, j])
    
    print(f"有效行数: {len(tasks)}, 有效像元: {n_pixels}, 总事件数: {total_events}")
    
    print("\n" + "="*70)
    print(f"Step 2: 并行分析 ({N_WORKERS}核)")
    print("="*70)
    
    all_results = []
    total_errors = 0
    
    with Pool(N_WORKERS, initializer=worker_init) as pool:
        for r, err in tqdm(pool.imap_unordered(process_row, tasks), total=len(tasks), desc="处理"):
            all_results.extend(r)
            total_errors += err
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n总耗时: {elapsed/60:.1f}分钟")
    print(f"事件结果数: {len(all_results)}")
    if total_events > 0:
        print(f"事件保留率: {len(all_results)/total_events*100:.1f}%")
    
    n_with_response = sum(1 for r in all_results if r['response_detected'] == 1)
    print(f"明显响应事件: {n_with_response} ({n_with_response/len(all_results)*100:.1f}%)")
    
    print("\n" + "="*70)
    print("Step 3: 保存结果")
    print("="*70)
    
    out_file = os.path.join(OUTPUT_DIR, "gpp_response_SMs_events_global_v7.nc")
    
    with nc.Dataset(out_file, 'w') as ds:
        ds.createDimension('event', len(all_results))
        
        for v, units in [('lat', 'degrees_north'), ('lon', 'degrees_east')]:
            var = ds.createVariable(v, 'f4', ('event',))
            var[:] = [r[v] for r in all_results]
            var.units = units
        
        for v in ['event_id', 'onset_year', 'onset_doy']:
            var = ds.createVariable(v, 'i2', ('event',))
            var[:] = [r[v] for r in all_results]
        
        var = ds.createVariable('response_detected', 'i1', ('event',))
        var[:] = [r['response_detected'] for r in all_results]
        var.long_name = '是否检测到明显GPP下降响应'
        
        for v, (ln, u) in {'gpp_min': ('GPP最低值', 'sigma'), 'gpp_mean': ('GPP平均值', 'sigma'),
                          'gpp_trend': ('GPP趋势', 'sigma/day'), 't_min': ('最低点位置', 'days')}.items():
            var = ds.createVariable(v, 'f4', ('event',), fill_value=np.nan)
            var[:] = [r[v] for r in all_results]
            var.long_name = ln; var.units = u
        
        for v, (ln, u) in {'t_response': ('响应时间', 'days'), 't_impact': ('影响期', 'days'),
                          'amp_max': ('最大下降', 'sigma'), 't_recover': ('恢复期', 'days'),
                          'recovery_rate': ('恢复速率', 'sigma/day')}.items():
            var = ds.createVariable(v, 'f4', ('event',), fill_value=np.nan)
            var[:] = [r[v] if r['response_detected'] else np.nan for r in all_results]
            var.long_name = ln; var.units = u
        
        ds.title = 'GPP Response to SMs Flash Drought - Global (v7)'
        ds.comment = 'v7: All events recorded. response_detected=1 for clear decline.'
    
    print(f"输出: {out_file}")
    print(f"文件大小: {os.path.getsize(out_file)/1024/1024:.1f} MB")
    
    print("\n" + "="*70)
    print("✅ SMs 全球分析完成！")
    print("="*70)

if __name__ == "__main__":
    main()
