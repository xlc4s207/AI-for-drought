"""
表层土壤湿度 (SMs) 骤旱对GPP影响分析 - v5
==========================================
基于 SMrz 分析脚本 (run_gpp_analysis_v4.py) 修改

关键改动：
  1. 事件文件改为 SMs 骤旱事件
  2. 输出目录改为 code2_SMs/results

v5 核心特性（继承自 SMrz 版本）：
  1. 去除季节性周期 - 使用15天移动平均去趋势
  2. 响应时间重新定义 - 连续5天下降视为GPP开始响应
  3. 恢复时间重新定义 - 连续5天超过-0.25σ才算恢复
  4. 时间窗口扩展 - 180天观察期
  5. 矩阵化气候态计算 + Numba JIT加速
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
# 关键改动：使用SMs骤旱事件文件
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMs/flash_drought_SMs_events_details_v2.nc")
MERGED_GPP_FILE = os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_result/BESS_GPP_1982_2022.nc")
OUTPUT_DIR = os.path.join(BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

START_YEAR, END_YEAR = 1982, 2022
WINDOW_BEFORE, WINDOW_AFTER = 60, 180
THETA_RECOVER = -0.25
N_WORKERS = 16
BATCH_SIZE = 5
CONSECUTIVE_DAYS = 5

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

# ============================================
# Worker初始化
# ============================================
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

# ============================================
# 矩阵化气候态计算
# ============================================
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
            clim_std[d, :] = np.nanstd(data_chunk, axis=0, ddof=1)
    
    full_mean = clim_mean[doy_idx, :]
    full_std = clim_std[doy_idx, :]
    full_std[full_std <= 0] = np.nan
    
    with np.errstate(divide='ignore', invalid='ignore'):
        z_matrix = (gpp_matrix - full_mean) / full_std
    
    return z_matrix

# ============================================
# Numba加速函数
# ============================================
@jit(nopython=True)
def detrend_gpp_numba(gpp_segment, window=15):
    n = len(gpp_segment)
    detrended = np.full(n, np.nan)
    
    for i in range(n):
        if np.isnan(gpp_segment[i]):
            continue
        
        start = max(0, i - window // 2)
        end = min(n, i + window // 2 + 1)
        
        window_vals = []
        for j in range(start, end):
            if not np.isnan(gpp_segment[j]):
                window_vals.append(gpp_segment[j])
        
        if len(window_vals) >= 5:
            trend = np.mean(np.array(window_vals))
            detrended[i] = gpp_segment[i] - trend
    
    return detrended

@jit(nopython=True)
def find_consecutive_decline_numba(post_detrended, n_consecutive=5):
    n = len(post_detrended)
    
    for i in range(n - n_consecutive + 1):
        is_consecutive_decline = True
        valid_count = 0
        
        for j in range(i, min(i + n_consecutive + 2, n) - 1):
            if np.isnan(post_detrended[j]) or np.isnan(post_detrended[j + 1]):
                continue
            
            if post_detrended[j + 1] >= post_detrended[j]:
                is_consecutive_decline = False
                break
            valid_count += 1
        
        if is_consecutive_decline and valid_count >= n_consecutive - 1:
            return i
    
    return -1

@jit(nopython=True)
def find_consecutive_recovery_numba(post, start_idx, threshold, n_consecutive=5):
    n = len(post)
    
    for i in range(start_idx, n - n_consecutive + 1):
        is_consecutive_recovery = True
        valid_count = 0
        
        for j in range(i, i + n_consecutive):
            if np.isnan(post[j]):
                is_consecutive_recovery = False
                break
            if post[j] <= threshold:
                is_consecutive_recovery = False
                break
            valid_count += 1
        
        if is_consecutive_recovery and valid_count == n_consecutive:
            return i
    
    return -1

@jit(nopython=True)
def calculate_new_metrics_numba(post, post_detrended, threshold, n_consecutive):
    n = len(post)
    
    t_response = find_consecutive_decline_numba(post_detrended, n_consecutive)
    
    if t_response == -1:
        return -1, -1, np.nan, -1, np.nan
    
    t_min_local = -1
    min_val = 1e9
    
    for i in range(t_response, n):
        val = post[i]
        if not np.isnan(val):
            if val < min_val:
                min_val = val
                t_min_local = i
    
    if t_min_local == -1:
        return t_response, -1, np.nan, -1, np.nan
    
    t_impact = t_min_local - t_response
    
    t_recover_idx = find_consecutive_recovery_numba(post, t_min_local + 1, threshold, n_consecutive)
    
    if t_recover_idx == -1:
        t_recover = np.nan
    else:
        t_recover = t_recover_idx - t_min_local
    
    return t_response, t_impact, min_val, t_recover, float(t_min_local)

def calc_metrics_optimized(gpp_z_segment):
    pre = gpp_z_segment[:WINDOW_BEFORE]
    post = gpp_z_segment[WINDOW_BEFORE:]
    
    if np.sum(~np.isnan(pre)) < 10 or np.sum(~np.isnan(post)) < 10:
        return None
    
    baseline = np.nanmean(pre)
    
    post_detrended = detrend_gpp_numba(post, window=15)
    
    t_response, t_impact, amp_max, t_recover, t_min_abs = calculate_new_metrics_numba(
        post, post_detrended, THETA_RECOVER, CONSECUTIVE_DAYS
    )
    
    if t_response == -1:
        return None
    
    decline_rate = (amp_max - baseline) / (t_response + t_impact) if (t_response + t_impact) > 0 else 0
    recovery_rate = (THETA_RECOVER - amp_max) / t_recover if not np.isnan(t_recover) and t_recover > 0 else np.nan
    
    return {
        't_response': int(t_response),
        't_impact': int(t_impact),
        't_min': int(t_min_abs),
        'amp_max': float(amp_max),
        'decline_rate': float(decline_rate),
        't_recover': float(t_recover),
        'recovery_rate': float(recovery_rate)
    }

# ============================================
# 批量IO处理函数
# ============================================
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
                        
                        m = calc_metrics_optimized(gpp_z[ws:we+1])
                        if m:
                            all_results.append({
                                'lat_idx': lat_idx,
                                'lon_idx': global_lon_idx,
                                'lat': lat_val,
                                'lon': float(_lon_arr[global_lon_idx]),
                                'event_id': i,
                                'onset_year': oy,
                                'onset_doy': od,
                                't_response': m['t_response'],
                                't_impact': m['t_impact'],
                                't_min': m['t_min'],
                                'amp_max': m['amp_max'],
                                'decline_rate': m['decline_rate'],
                                't_recover': m['t_recover'],
                                'recovery_rate': m['recovery_rate']
                            })
            
            except Exception as e:
                batch_error += 1
    
    except Exception as e:
        batch_error += len(batch_info_list)
    
    return all_results, batch_error

# ============================================
# 主函数
# ============================================
def main():
    print("="*70)
    print("表层土壤湿度 (SMs) 骤旱对GPP影响分析 - v5")
    print("="*70)
    print("数据源:")
    print(f"  GPP: {MERGED_GPP_FILE}")
    print(f"  SMs事件: {DROUGHT_EVENTS_FILE}")
    print("")
    print("分析方法:")
    print("  - 去趋势化 + 连续5天判定")
    print("  - 180天观察窗口")
    print("  - 矩阵化计算 + Numba JIT加速")
    
    if not os.path.exists(MERGED_GPP_FILE):
        print(f"\nError: GPP文件不存在")
        return
    
    if not os.path.exists(DROUGHT_EVENTS_FILE):
        print(f"\nError: SMs事件文件不存在")
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
        print(f"Lon范围: [{lon_start}, {lon_end}] ({lon_end - lon_start + 1}列)")
        
        lat_groups = {}
        n_pixels = 0
        total_events = 0
        for i in range(len(lat)):
            if not (TEST_REGION['lat_min'] <= lat[i] <= TEST_REGION['lat_max']):
                continue
            local_lons = [j - lon_start for j in range(lon_start, lon_end + 1) 
                         if ec[i, j] > 0]
            if local_lons:
                lat_groups[i] = {'lat': float(lat[i]), 'lons': local_lons}
                n_pixels += len(local_lons)
                for j in local_lons:
                    total_events += ec[i, j + lon_start]
    
    print(f"有效行数: {len(lat_groups)}")
    print(f"有效像元: {n_pixels}")
    print(f"总事件数: {total_events}")
    
    sorted_lat_indices = sorted(lat_groups.keys())
    tasks = []
    for i in range(0, len(sorted_lat_indices), BATCH_SIZE):
        batch_lat_indices = sorted_lat_indices[i : i + BATCH_SIZE]
        batch_info = []
        for lat_idx in batch_lat_indices:
            batch_info.append({
                'lat_idx': lat_idx,
                'lat_val': lat_groups[lat_idx]['lat'],
                'lons': lat_groups[lat_idx]['lons']
            })
        tasks.append(batch_info)
    
    print(f"批次数: {len(tasks)} (每批{BATCH_SIZE}行)")
    
    print("\n" + "="*70)
    print(f"Step 2: 并行分析 ({N_WORKERS}核)")
    print("="*70)
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_results = []
    total_errors = 0
    
    with Pool(N_WORKERS, initializer=worker_init, initargs=(lon_start, lon_end)) as pool:
        for r, err in tqdm(pool.imap_unordered(process_batch, tasks),
                          total=len(tasks),
                          desc="处理进度",
                          unit="批次"):
            all_results.extend(r)
            total_errors += err
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    print("\n" + "="*70)
    print("处理完成")
    print("="*70)
    print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {elapsed:.1f}秒 ({elapsed/60:.2f}分钟)")
    print(f"事件结果数: {len(all_results)}")
    print(f"处理速度: {total_events/elapsed:.2f} 事件/秒")
    if total_errors > 0:
        print(f"错误数: {total_errors}")
    
    if not all_results:
        print("\n警告: 无有效结果")
        return
    
    print("\n" + "="*70)
    print("Step 3: 保存详细结果")
    print("="*70)
    
    out_file = os.path.join(OUTPUT_DIR, f"gpp_response_SMs_events_{TEST_REGION['name']}.nc")
    
    n_events = len(all_results)
    
    with nc.Dataset(out_file, 'w') as ds:
        ds.createDimension('event', n_events)
        
        var = ds.createVariable('lat', 'f4', ('event',))
        var[:] = [r['lat'] for r in all_results]
        var.units = 'degrees_north'
        
        var = ds.createVariable('lon', 'f4', ('event',))
        var[:] = [r['lon'] for r in all_results]
        var.units = 'degrees_east'
        
        var = ds.createVariable('event_id', 'i2', ('event',))
        var[:] = [r['event_id'] for r in all_results]
        var.long_name = 'Event ID at this pixel'
        
        var = ds.createVariable('onset_year', 'i2', ('event',))
        var[:] = [r['onset_year'] for r in all_results]
        var.long_name = 'Drought onset year'
        
        var = ds.createVariable('onset_doy', 'i2', ('event',))
        var[:] = [r['onset_doy'] for r in all_results]
        var.long_name = 'Drought onset day of year'
        
        vars_info = {
            't_response': ('响应时间（到连续5天下降）', 'days'),
            't_impact': ('影响期（响应开始到最低点）', 'days'),
            't_min': ('最低点位置（从onset起）', 'days'),
            'amp_max': ('最大下降幅度', 'sigma'),
            'decline_rate': ('影响期平均下降速率', 'sigma/day'),
            't_recover': ('恢复期（最低点到连续5天恢复）', 'days'),
            'recovery_rate': ('恢复期平均速率', 'sigma/day')
        }
        
        for v, (long_name, units) in vars_info.items():
            var = ds.createVariable(v, 'f4', ('event',), fill_value=np.nan)
            var[:] = [r[v] for r in all_results]
            var.long_name = long_name
            var.units = units
        
        ds.title = f'GPP Response to SMs (Surface Soil Moisture) Flash Drought Events - {TEST_REGION["name"]}'
        ds.source = 'BESS V2 GPP, GLEAM SMs'
        ds.history = f'Created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        ds.comment = 'v5: New metrics with detrending and consecutive-day thresholds. Window extended to 180 days.'
    
    print(f"输出文件: {out_file}")
    print(f"文件大小: {os.path.getsize(out_file)/1024/1024:.1f} MB")
    
    print("\n" + "="*70)
    print("结果摘要")
    print("="*70)
    
    t_resp_arr = np.array([r['t_response'] for r in all_results])
    t_imp_arr = np.array([r['t_impact'] for r in all_results])
    t_min_arr = np.array([r['t_min'] for r in all_results])
    amp_arr = np.array([r['amp_max'] for r in all_results])
    decline_arr = np.array([r['decline_rate'] for r in all_results])
    t_rec_arr = np.array([r['t_recover'] for r in all_results if not np.isnan(r['t_recover'])])
    rec_rate_arr = np.array([r['recovery_rate'] for r in all_results if not np.isnan(r['recovery_rate'])])
    
    print(f"响应时间（到连续5天下降）: {np.mean(t_resp_arr):.1f} ± {np.std(t_resp_arr):.1f} 天")
    print(f"影响期（响应到最低点）: {np.mean(t_imp_arr):.1f} ± {np.std(t_imp_arr):.1f} 天")
    print(f"最低点位置: {np.mean(t_min_arr):.1f} ± {np.std(t_min_arr):.1f} 天")
    print(f"最大下降幅度: {np.mean(amp_arr):.2f} ± {np.std(amp_arr):.2f} σ")
    print(f"影响期平均下降速率: {np.mean(decline_arr):.4f} ± {np.std(decline_arr):.4f} σ/天")
    print(f"恢复期（连续5天恢复）: {np.mean(t_rec_arr):.1f} ± {np.std(t_rec_arr):.1f} 天 (n={len(t_rec_arr)})")
    print(f"恢复率: {len(t_rec_arr)/len(all_results)*100:.1f}%")
    print(f"恢复期平均速率: {np.mean(rec_rate_arr):.4f} ± {np.std(rec_rate_arr):.4f} σ/天 (n={len(rec_rate_arr)})")
    
    print("\n" + "="*70)
    print("✅ SMs骤旱对GPP影响分析完成！")
    print("="*70)

if __name__ == "__main__":
    main()
