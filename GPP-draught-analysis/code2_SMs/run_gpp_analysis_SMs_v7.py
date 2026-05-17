"""
表层土壤湿度 (SMs) 骤旱对GPP影响分析 - v7 (完整记录版)
==========================================
基于 SMrz v7 修改，使用 SMs 骤旱事件

v7 核心改进：不丢弃任何事件！
  1. 记录所有事件，不论GPP是否有明显下降
  2. 添加 response_detected 标志
  3. 对所有事件计算基础指标：gpp_min, gpp_mean, gpp_trend
  4. 仅对有响应的事件计算详细指标
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
# 配置 - SMs版本
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
BATCH_SIZE = 5

TEST_REGION = {'name': 'US_West', 'lat_min': 30, 'lat_max': 45, 'lon_min': -125, 'lon_max': -100}

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
_lon_start = None
_lon_end = None

# ============================================
# 预计算
# ============================================
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

def worker_init(lon_start, lon_end):
    global _gpp_ds, _event_ds, _gpp_var, _ec_var, _oy_var, _od_var
    global _lon_arr, _year_offsets, _doy_index, _lon_start, _lon_end
    
    _gpp_ds = nc.Dataset(MERGED_GPP_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')
    
    _gpp_var = _gpp_ds.variables['GPP']
    _ec_var = _event_ds.variables['event_count']
    _oy_var = _event_ds.variables['onset_start_year']
    _od_var = _event_ds.variables['onset_start_doy']
    
    _lon_arr = _gpp_ds.variables['lon'][:]
    
    _lon_start = lon_start
    _lon_end = lon_end
    
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
            if np.isnan(x[j]):
                all_below = False
                break
            if x[j] > threshold:
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
            if np.isnan(x[j]):
                all_above = False
                break
            if x[j] <= threshold:
                all_above = False
                break
            valid_count += 1
        if all_above and valid_count == n_consecutive:
            return i
    return -1

@jit(nopython=True)
def calc_linear_trend_numba(y):
    n = len(y)
    valid_x = []
    valid_y = []
    for i in range(n):
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
    
    baseline = np.mean(np.array(pre_vals))
    
    post_part = post[60:]
    n_post = len(post_part)
    
    if n_post < 10:
        return 0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan
    
    # 基础指标
    gpp_min = 1e9
    t_min_all = -1
    for i in range(n_post):
        if not np.isnan(post_part[i]) and post_part[i] < gpp_min:
            gpp_min = post_part[i]
            t_min_all = i
    
    if t_min_all == -1:
        gpp_min = np.nan
    
    valid_vals = []
    for i in range(n_post):
        if not np.isnan(post_part[i]):
            valid_vals.append(post_part[i])
    
    if len(valid_vals) > 0:
        gpp_mean = np.mean(np.array(valid_vals))
    else:
        gpp_mean = np.nan
    
    gpp_trend = calc_linear_trend_numba(post_part)
    
    # 响应检测
    t_response = find_threshold_crossing_numba(
        post_part, threshold_resp, n_consec_resp, max_search
    )
    
    if t_response == -1:
        return 0, gpp_min, gpp_mean, gpp_trend, t_min_all, -1, -1, np.nan, np.nan, np.nan
    
    t_min_local = -1
    min_val = 1e9
    for i in range(t_response, n_post):
        if not np.isnan(post_part[i]) and post_part[i] < min_val:
            min_val = post_part[i]
            t_min_local = i
    
    if t_min_local == -1:
        return 1, gpp_min, gpp_mean, gpp_trend, t_min_all, t_response, -1, np.nan, np.nan, np.nan
    
    t_impact = t_min_local - t_response
    
    if t_impact > 0:
        val_resp = post_part[t_response]
        if not np.isnan(val_resp):
            decline_rate = (min_val - val_resp) / t_impact
        else:
            decline_rate = (min_val - baseline) / t_impact
    else:
        decline_rate = np.nan
    
    t_recover_idx = find_recovery_numba(post_part, t_min_local + 1, threshold_recov, n_consec_recov)
    
    if t_recover_idx == -1:
        t_recover = np.nan
        recovery_rate = np.nan
    else:
        t_recover = t_recover_idx - t_min_local
        if t_recover > 0:
            recovery_rate = (threshold_recov - min_val) / t_recover
        else:
            recovery_rate = np.nan
    
    return 1, gpp_min, gpp_mean, gpp_trend, t_min_all, t_response, t_impact, min_val, t_recover, recovery_rate

def calc_metrics_v7(gpp_z_segment):
    if np.sum(~np.isnan(gpp_z_segment)) < 30:
        return None
    
    smoothed = smooth_causal_numba(gpp_z_segment, window=7)
    
    (response_detected, gpp_min, gpp_mean, gpp_trend, t_min_all,
     t_response, t_impact, amp_max, t_recover, recovery_rate) = \
        calc_all_metrics_v7_numba(smoothed, THRESHOLD_RESPONSE, THRESHOLD_RECOVER,
                                   CONSECUTIVE_DAYS_RESPONSE, CONSECUTIVE_DAYS_RECOVER,
                                   RESPONSE_SEARCH_WINDOW)
    
    return {
        'response_detected': int(response_detected),
        'gpp_min': float(gpp_min),
        'gpp_mean': float(gpp_mean),
        'gpp_trend': float(gpp_trend),
        't_min': int(t_min_all) if t_min_all >= 0 else -1,
        't_response': int(t_response) if t_response >= 0 else -1,
        't_impact': int(t_impact) if t_impact >= 0 else -1,
        'amp_max': float(amp_max) if response_detected else float(gpp_min),
        't_recover': float(t_recover),
        'recovery_rate': float(recovery_rate)
    }

def process_batch(batch_info_list):
    all_results = []
    batch_error = 0
    
    if not batch_info_list:
        return [], 0
    
    try:
        min_lat = min(item['lat_idx'] for item in batch_info_list)
        max_lat = max(item['lat_idx'] for item in batch_info_list)
        
        gpp_batch = _gpp_var[:, min_lat:max_lat+1, _lon_start:_lon_end+1]
        if hasattr(gpp_batch, 'filled'):
            gpp_batch = gpp_batch.filled(np.nan).astype(np.float32)
        else:
            gpp_batch = gpp_batch.astype(np.float32)
        
        ec_batch = _ec_var[min_lat:max_lat+1, _lon_start:_lon_end+1]
        max_ec = int(np.max(ec_batch))
        
        if max_ec > 0:
            oy_batch = _oy_var[:max_ec, min_lat:max_lat+1, _lon_start:_lon_end+1]
            od_batch = _od_var[:max_ec, min_lat:max_lat+1, _lon_start:_lon_end+1]
        
        for info in batch_info_list:
            try:
                rel_lat_idx = info['lat_idx'] - min_lat
                lat_idx = info['lat_idx']
                lat_val = info['lat_val']
                lon_local_indices = info['lons']
                
                gpp_slice = gpp_batch[:, rel_lat_idx, :]
                ec_slice = ec_batch[rel_lat_idx, :]
                
                valid_locals = [idx for idx in lon_local_indices if ec_slice[idx] > 0]
                if not valid_locals:
                    continue
                
                gpp_matrix = gpp_slice[:, valid_locals]
                valid_count = np.sum(~np.isnan(gpp_matrix), axis=0)
                good_pixels = valid_count >= 100
                if not good_pixels.any():
                    continue
                
                z_matrix = calc_climatology_and_zscore_matrix(gpp_matrix[:, good_pixels], _doy_index)
                
                good_idx = 0
                for local_idx in [valid_locals[i] for i, g in enumerate(good_pixels) if g]:
                    ec = int(ec_slice[local_idx])
                    gpp_z = z_matrix[:, good_idx]
                    good_idx += 1
                    
                    global_lon_idx = _lon_start + local_idx
                    
                    for i in range(ec):
                        if max_ec > 0:
                            oy = int(oy_batch[i, rel_lat_idx, local_idx])
                            od = int(od_batch[i, rel_lat_idx, local_idx])
                        else:
                            continue
                        
                        if oy < START_YEAR or oy > END_YEAR or od <= 0 or od > 366:
                            continue
                        
                        onset = _year_offsets[oy] + od - 1
                        ws, we = onset - WINDOW_BEFORE, onset + WINDOW_AFTER
                        
                        if ws < 0 or we >= len(gpp_z):
                            continue
                        
                        m = calc_metrics_v7(gpp_z[ws:we+1])
                        if m:
                            all_results.append({
                                'lat_idx': lat_idx,
                                'lon_idx': global_lon_idx,
                                'lat': lat_val,
                                'lon': float(_lon_arr[global_lon_idx]),
                                'event_id': i,
                                'onset_year': oy,
                                'onset_doy': od,
                                **m
                            })
            except Exception as e:
                batch_error += 1
    except Exception as e:
        batch_error += len(batch_info_list)
    
    return all_results, batch_error

def main():
    print("="*70)
    print("表层土壤湿度 (SMs) 骤旱对GPP影响分析 - v7 (完整记录版)")
    print("="*70)
    print("核心改进：记录所有事件，包括无明显响应的事件")
    
    if not os.path.exists(MERGED_GPP_FILE) or not os.path.exists(DROUGHT_EVENTS_FILE):
        print("Error: 数据文件不存在")
        return
    
    print("\n" + "="*70)
    print("Step 1: 确定区域范围")
    print("="*70)
    start_time = datetime.now()
    
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
        ec = ds.variables['event_count'][:]
        
        lon_mask = (lon >= TEST_REGION['lon_min']) & (lon <= TEST_REGION['lon_max'])
        lon_indices = np.where(lon_mask)[0]
        lon_start, lon_end = int(lon_indices.min()), int(lon_indices.max())
        
        print(f"区域: {TEST_REGION['name']}")
        
        lat_groups = {}
        n_pixels = 0
        total_events = 0
        for i in range(len(lat)):
            if not (TEST_REGION['lat_min'] <= lat[i] <= TEST_REGION['lat_max']):
                continue
            local_lons = [j - lon_start for j in range(lon_start, lon_end + 1) if ec[i, j] > 0]
            if local_lons:
                lat_groups[i] = {'lat': float(lat[i]), 'lons': local_lons}
                n_pixels += len(local_lons)
                for j in local_lons:
                    total_events += int(ec[i, j + lon_start])
    
    print(f"有效像元: {n_pixels}, 总事件数: {total_events}")
    
    sorted_lat_indices = sorted(lat_groups.keys())
    tasks = []
    for i in range(0, len(sorted_lat_indices), BATCH_SIZE):
        batch_lat_indices = sorted_lat_indices[i : i + BATCH_SIZE]
        batch_info = [{'lat_idx': lat_idx, 'lat_val': lat_groups[lat_idx]['lat'], 
                       'lons': lat_groups[lat_idx]['lons']} for lat_idx in batch_lat_indices]
        tasks.append(batch_info)
    
    print(f"批次数: {len(tasks)}")
    
    print("\n" + "="*70)
    print(f"Step 2: 并行分析 ({N_WORKERS}核)")
    print("="*70)
    
    all_results = []
    total_errors = 0
    
    with Pool(N_WORKERS, initializer=worker_init, initargs=(lon_start, lon_end)) as pool:
        for r, err in tqdm(pool.imap_unordered(process_batch, tasks), total=len(tasks), desc="处理"):
            all_results.extend(r)
            total_errors += err
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    print(f"\n总耗时: {elapsed/60:.2f}分钟")
    print(f"事件结果数: {len(all_results)}")
    if total_events > 0:
        print(f"事件保留率: {len(all_results)/total_events*100:.1f}%")
    
    n_with_response = sum(1 for r in all_results if r['response_detected'] == 1)
    print(f"明显响应事件: {n_with_response} ({n_with_response/len(all_results)*100:.1f}%)")
    
    print("\n" + "="*70)
    print("Step 3: 保存结果")
    print("="*70)
    
    out_file = os.path.join(OUTPUT_DIR, f"gpp_response_SMs_events_{TEST_REGION['name']}_v7.nc")
    
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
        
        basic_vars = {
            'gpp_min': ('事件后GPP最低值', 'sigma'),
            'gpp_mean': ('事件后GPP平均值', 'sigma'),
            'gpp_trend': ('事件后GPP变化趋势', 'sigma/day'),
            't_min': ('最低点位置', 'days'),
        }
        
        for v, (long_name, units) in basic_vars.items():
            var = ds.createVariable(v, 'f4', ('event',), fill_value=np.nan)
            var[:] = [r[v] for r in all_results]
            var.long_name = long_name
            var.units = units
        
        response_vars = {
            't_response': ('响应时间', 'days'),
            't_impact': ('影响期', 'days'),
            'amp_max': ('最大下降幅度', 'sigma'),
            't_recover': ('恢复期', 'days'),
            'recovery_rate': ('恢复速率', 'sigma/day'),
        }
        
        for v, (long_name, units) in response_vars.items():
            var = ds.createVariable(v, 'f4', ('event',), fill_value=np.nan)
            data = [r[v] if r['response_detected'] else np.nan for r in all_results]
            var[:] = data
            var.long_name = long_name
            var.units = units
        
        ds.title = f'GPP Response to SMs Flash Drought - {TEST_REGION["name"]} (v7 Complete)'
        ds.comment = 'v7: All events recorded. response_detected=1 for events with clear decline.'
    
    print(f"输出: {out_file}")
    print(f"文件大小: {os.path.getsize(out_file)/1024/1024:.1f} MB")
    
    # 结果摘要
    print("\n" + "="*70)
    print("结果摘要")
    print("="*70)
    
    gpp_min_arr = np.array([r['gpp_min'] for r in all_results])
    gpp_mean_arr = np.array([r['gpp_mean'] for r in all_results])
    gpp_trend_arr = np.array([r['gpp_trend'] for r in all_results])
    
    print("【所有事件】")
    print(f"  GPP最低值: {np.nanmean(gpp_min_arr):.2f} ± {np.nanstd(gpp_min_arr):.2f} σ")
    print(f"  GPP平均值: {np.nanmean(gpp_mean_arr):.2f} ± {np.nanstd(gpp_mean_arr):.2f} σ")
    print(f"  GPP趋势: {np.nanmean(gpp_trend_arr)*1000:.3f} ± {np.nanstd(gpp_trend_arr)*1000:.3f} ×10⁻³ σ/天")
    
    resp_events = [r for r in all_results if r['response_detected'] == 1]
    if resp_events:
        t_resp_arr = np.array([r['t_response'] for r in resp_events])
        t_imp_arr = np.array([r['t_impact'] for r in resp_events])
        amp_arr = np.array([r['amp_max'] for r in resp_events])
        t_rec_arr = np.array([r['t_recover'] for r in resp_events if not np.isnan(r['t_recover'])])
        
        print(f"\n【有明显响应的事件】(n={len(resp_events)})")
        print(f"  响应时间: {np.mean(t_resp_arr):.1f} ± {np.std(t_resp_arr):.1f} 天")
        print(f"  影响期: {np.mean(t_imp_arr):.1f} ± {np.std(t_imp_arr):.1f} 天")
        print(f"  最大下降: {np.mean(amp_arr):.2f} ± {np.std(amp_arr):.2f} σ")
        if len(t_rec_arr) > 0:
            print(f"  恢复期: {np.mean(t_rec_arr):.1f} ± {np.std(t_rec_arr):.1f} 天 (恢复率{len(t_rec_arr)/len(resp_events)*100:.1f}%)")
    
    no_resp_events = [r for r in all_results if r['response_detected'] == 0]
    if no_resp_events:
        gpp_min_no = np.array([r['gpp_min'] for r in no_resp_events])
        gpp_mean_no = np.array([r['gpp_mean'] for r in no_resp_events])
        
        print(f"\n【无明显响应的事件】(n={len(no_resp_events)})")
        print(f"  GPP最低值: {np.nanmean(gpp_min_no):.2f} ± {np.nanstd(gpp_min_no):.2f} σ")
        print(f"  GPP平均值: {np.nanmean(gpp_mean_no):.2f} ± {np.nanstd(gpp_mean_no):.2f} σ")
    
    print("\n" + "="*70)
    print("✅ SMs v7 分析完成！")
    print("="*70)

if __name__ == "__main__":
    main()
