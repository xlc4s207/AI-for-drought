"""
骤旱对RECO影响分析 - v10 全球版 (内存优化)
==========================================

基于GPP分析代码改编，用于分析骤旱对生态系统呼吸(RECO)的影响

v10优化：
  - 每个chunk完成后立即写入临时文件
  - 主进程内存保持恒定
  - 最后合并所有临时文件
"""
import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool
import warnings
from datetime import datetime
from numba import jit
import tempfile
import shutil
warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================
BASE_DIR = "/home/xulc/flash_drought"
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz/flash_drought_events_details_v2.nc")
MERGED_RECO_FILE = "/data/BESS_V2/RECO/BESS_RECO_1982_2022.nc"
OUTPUT_DIR = os.path.join(BASE_DIR, "process/RECO-draught-analysis/results")
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

START_YEAR, END_YEAR = 1982, 2022
WINDOW_BEFORE = 60
WINDOW_AFTER = 120
RESPONSE_SEARCH_WINDOW = 60
THRESHOLD_RESPONSE = -0.5  # RECO下降阈值（RECO也受干旱抑制）
THRESHOLD_RECOVER = -0.25   # 恢复阈值
CONSECUTIVE_DAYS = 3

N_WORKERS = 16
LAT_CHUNK_SIZE = 20

# 结果字段定义
RESULT_FIELDS = [
    'lat', 'lon', 'event_id', 'onset_year', 'onset_doy',
    'response_detected', 'reco_min', 'reco_mean', 'reco_trend', 't_min',
    't_response', 't_impact', 'amp_max', 't_recover', 'recovery_rate'
]
RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'), ('event_id', 'i2'), 
    ('onset_year', 'i2'), ('onset_doy', 'i2'),
    ('response_detected', 'i1'), ('reco_min', 'f4'), ('reco_mean', 'f4'),
    ('reco_trend', 'f4'), ('t_min', 'i2'), ('t_response', 'i2'),
    ('t_impact', 'i2'), ('amp_max', 'f4'), ('t_recover', 'f4'),
    ('recovery_rate', 'f4')
])

# ============================================
# 全局变量
# ============================================
_reco_ds = None
_event_ds = None
_lon_arr = None
_year_offsets = None
_doy_idx = None

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
    global _reco_ds, _event_ds, _lon_arr, _year_offsets, _doy_idx
    _reco_ds = nc.Dataset(MERGED_RECO_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')
    _lon_arr = _reco_ds.variables['lon'][:]
    _year_offsets = build_year_offsets()
    _doy_idx = build_doy_index()

# ============================================
# Numba加速函数
# ============================================
@jit(nopython=True)
def smooth_causal(x, window=7):
    """因果平滑（只用当前及之前的数据）"""
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
def find_threshold_crossing(x, threshold, n_consecutive, max_search):
    """查找连续n天低于阈值的首次位置"""
    n = min(len(x), max_search)
    for i in range(n - n_consecutive + 1):
        all_below = True
        for j in range(i, i + n_consecutive):
            if np.isnan(x[j]) or x[j] > threshold:
                all_below = False
                break
        if all_below:
            return i
    return -1

@jit(nopython=True)
def find_recovery(x, start_idx, threshold, n_consecutive):
    """从start_idx开始查找恢复点"""
    n = len(x)
    for i in range(start_idx, n - n_consecutive + 1):
        all_above = True
        for j in range(i, i + n_consecutive):
            if np.isnan(x[j]) or x[j] <= threshold:
                all_above = False
                break
        if all_above:
            return i
    return -1

@jit(nopython=True)
def calc_trend(y):
    """计算线性趋势"""
    valid_x, valid_y = [], []
    for i in range(len(y)):
        if not np.isnan(y[i]):
            valid_x.append(float(i))
            valid_y.append(y[i])
    if len(valid_x) < 10:
        return np.nan
    x_arr = np.array(valid_x)
    y_arr = np.array(valid_y)
    x_mean, y_mean = np.mean(x_arr), np.mean(y_arr)
    num, den = 0.0, 0.0
    for i in range(len(x_arr)):
        num += (x_arr[i] - x_mean) * (y_arr[i] - y_mean)
        den += (x_arr[i] - x_mean) ** 2
    return num / den if den > 0 else np.nan

@jit(nopython=True)
def process_single_event(reco_z, ws, we, threshold_resp, threshold_recov, n_consec, max_search):
    """处理单个骤旱事件的RECO响应"""
    segment = reco_z[ws:we+1]
    
    if np.sum(~np.isnan(segment)) < 30:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    
    smoothed = smooth_causal(segment, 7)
    
    # 计算基准期（前60天）
    pre_vals = []
    for i in range(min(60, len(smoothed))):
        if not np.isnan(smoothed[i]):
            pre_vals.append(smoothed[i])
    
    if len(pre_vals) < 5:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    
    # 分析干旱后期（从onset开始的120天）
    post = smoothed[60:]
    n_post = len(post)
    
    if n_post < 10:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    
    # 计算基本统计量
    reco_min, t_min_all = 1e9, -1
    valid_sum, valid_cnt = 0.0, 0
    for i in range(n_post):
        if not np.isnan(post[i]):
            valid_sum += post[i]
            valid_cnt += 1
            if post[i] < reco_min:
                reco_min = post[i]
                t_min_all = i
    
    reco_mean = valid_sum / valid_cnt if valid_cnt > 0 else np.nan
    reco_trend = calc_trend(post)
    
    # 检测响应（RECO下降）
    t_response = find_threshold_crossing(post, threshold_resp, n_consec, max_search)
    
    if t_response == -1:
        return (0, reco_min, reco_mean, reco_trend, t_min_all, -1, -1, np.nan, np.nan, np.nan)
    
    # 查找响应后的最低点
    t_min_local, min_val = -1, 1e9
    for i in range(t_response, n_post):
        if not np.isnan(post[i]) and post[i] < min_val:
            min_val = post[i]
            t_min_local = i
    
    if t_min_local == -1:
        return (1, reco_min, reco_mean, reco_trend, t_min_all, t_response, -1, np.nan, np.nan, np.nan)
    
    t_impact = t_min_local - t_response
    
    # 查找恢复点
    t_recover_idx = find_recovery(post, t_min_local + 1, threshold_recov, n_consec)
    if t_recover_idx == -1:
        t_recover, recovery_rate = np.nan, np.nan
    else:
        t_recover = float(t_recover_idx - t_min_local)
        recovery_rate = (threshold_recov - min_val) / t_recover if t_recover > 0 else np.nan
    
    return (1, reco_min, reco_mean, reco_trend, t_min_all, t_response, t_impact, min_val, t_recover, recovery_rate)

def calc_climatology_zscore(reco_matrix, doy_idx):
    """计算气候态和Z-score"""
    n_time, n_pixels = reco_matrix.shape
    clim_mean = np.full((366, n_pixels), np.nan, dtype=np.float32)
    clim_std = np.full((366, n_pixels), np.nan, dtype=np.float32)
    
    for d in range(366):
        mask = (doy_idx == d)
        if np.sum(mask) > 0:
            data = reco_matrix[mask, :]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                clim_mean[d, :] = np.nanmean(data, axis=0)
                clim_std[d, :] = np.nanstd(data, axis=0, ddof=0)
    
    clim_std[clim_std < 0.01] = np.nan
    full_mean = clim_mean[doy_idx, :]
    full_std = clim_std[doy_idx, :]
    
    with np.errstate(divide='ignore', invalid='ignore'):
        z_matrix = (reco_matrix - full_mean) / full_std
    return z_matrix

def process_chunk(chunk_info):
    """处理一个块并返回结果数组"""
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    
    try:
        lat_arr = _reco_ds.variables['lat'][lat_start:lat_end]
        n_lats = lat_end - lat_start
        
        # 读取RECO数据
        reco_chunk = _reco_ds.variables['RECO'][:, lat_start:lat_end, :]
        if hasattr(reco_chunk, 'filled'):
            reco_chunk = reco_chunk.filled(np.nan).astype(np.float32)
        else:
            reco_chunk = reco_chunk.astype(np.float32)
        
        ec_chunk = _event_ds.variables['event_count'][lat_start:lat_end, :]
        
        max_ec = int(np.max(ec_chunk))
        if max_ec == 0:
            return chunk_id, np.array([], dtype=RESULT_DTYPE)
        
        oy_chunk = _event_ds.variables['onset_start_year'][:max_ec, lat_start:lat_end, :]
        od_chunk = _event_ds.variables['onset_start_doy'][:max_ec, lat_start:lat_end, :]
        
        for rel_lat in range(n_lats):
            lat_val = float(lat_arr[rel_lat])
            
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            if len(lon_with_events) == 0:
                continue
            
            reco_row = reco_chunk[:, rel_lat, lon_with_events]
            valid_count = np.sum(~np.isnan(reco_row), axis=0)
            good_mask = valid_count >= 100
            
            if not np.any(good_mask):
                continue
            
            good_lon_indices = lon_with_events[good_mask]
            reco_good = reco_row[:, good_mask]
            z_matrix = calc_climatology_zscore(reco_good, _doy_idx)
            
            for idx, lon_idx in enumerate(good_lon_indices):
                ec = int(ec_chunk[rel_lat, lon_idx])
                reco_z = z_matrix[:, idx]
                lon_val = float(_lon_arr[lon_idx])
                
                for i in range(ec):
                    oy = int(oy_chunk[i, rel_lat, lon_idx])
                    od = int(od_chunk[i, rel_lat, lon_idx])
                    
                    if oy < START_YEAR or oy > END_YEAR or od <= 0 or od > 366:
                        continue
                    
                    onset = _year_offsets[oy] + od - 1
                    ws, we = onset - WINDOW_BEFORE, onset + WINDOW_AFTER
                    
                    if ws < 0 or we >= len(reco_z):
                        continue
                    
                    m = process_single_event(
                        reco_z, ws, we,
                        THRESHOLD_RESPONSE, THRESHOLD_RECOVER,
                        CONSECUTIVE_DAYS, RESPONSE_SEARCH_WINDOW
                    )
                    
                    results.append((
                        lat_val, lon_val, i, oy, od,
                        int(m[0]), float(m[1]), float(m[2]), float(m[3]),
                        int(m[4]) if m[4] >= 0 else -1,
                        int(m[5]) if m[5] >= 0 else -1,
                        int(m[6]) if m[6] >= 0 else -1,
                        float(m[7]) if m[0] else float(m[1]),
                        float(m[8]), float(m[9])
                    ))
    
    except Exception as e:
        print(f"块 {chunk_id} 错误: {e}")
        return chunk_id, np.array([], dtype=RESULT_DTYPE)
    
    # 转换为numpy结构化数组
    if results:
        result_arr = np.array(results, dtype=RESULT_DTYPE)
    else:
        result_arr = np.array([], dtype=RESULT_DTYPE)
    
    return chunk_id, result_arr

def save_chunk_to_disk(chunk_id, result_arr):
    """将chunk结果保存到临时文件"""
    if len(result_arr) > 0:
        temp_file = os.path.join(TEMP_DIR, f"chunk_{chunk_id:04d}.npy")
        np.save(temp_file, result_arr)
        return len(result_arr)
    return 0

def main():
    print("="*70)
    print("骤旱对RECO影响分析 - v10 全球版 (内存优化)")
    print("="*70)
    print("优化策略：")
    print("  - 每个chunk结果立即写入磁盘")
    print("  - 主进程内存保持恒定")
    print("  - 使用numpy结构化数组减少内存")
    print("")
    
    # 清理旧的临时文件
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)
    
    start_time = datetime.now()
    
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
        lat_arr = ds.variables['lat'][:]
        ec_all = ds.variables['event_count'][:]
        
        lat_has_events = np.any(ec_all > 0, axis=1)
        valid_lat_indices = np.where(lat_has_events)[0]
        
        if len(valid_lat_indices) == 0:
            print("无有效事件")
            return
        
        lat_start_idx = valid_lat_indices[0]
        lat_end_idx = valid_lat_indices[-1] + 1
        total_events = int(np.sum(ec_all))
    
    print(f"有效纬度范围: [{lat_start_idx}, {lat_end_idx}) ({lat_end_idx - lat_start_idx}行)")
    print(f"总事件数: {total_events}")
    
    # 生成块任务
    chunks = []
    chunk_id = 0
    for chunk_start in range(lat_start_idx, lat_end_idx, LAT_CHUNK_SIZE):
        chunk_end = min(chunk_start + LAT_CHUNK_SIZE, lat_end_idx)
        chunks.append((chunk_id, chunk_start, chunk_end))
        chunk_id += 1
    
    print(f"任务块数: {len(chunks)}")
    print(f"并行进程数: {N_WORKERS}")
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 并行处理 + 即时写入磁盘
    total_saved = 0
    
    with Pool(N_WORKERS, initializer=worker_init) as pool:
        for cid, result_arr in tqdm(pool.imap_unordered(process_chunk, chunks),
                                    total=len(chunks),
                                    desc="处理进度"):
            saved = save_chunk_to_disk(cid, result_arr)
            total_saved += saved
    
    mid_time = datetime.now()
    print(f"\n处理完成，已保存 {total_saved} 个事件到临时文件")
    print(f"处理耗时: {(mid_time - start_time).total_seconds()/60:.1f}分钟")
    
    # 合并所有临时文件
    print("\n合并临时文件...")
    temp_files = sorted([f for f in os.listdir(TEMP_DIR) if f.endswith('.npy')])
    
    all_results = []
    for tf in tqdm(temp_files, desc="合并"):
        arr = np.load(os.path.join(TEMP_DIR, tf))
        all_results.append(arr)
    
    if all_results:
        final_results = np.concatenate(all_results)
    else:
        final_results = np.array([], dtype=RESULT_DTYPE)
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    print(f"\n总耗时: {elapsed/60:.1f}分钟 ({elapsed/3600:.2f}小时)")
    print(f"事件结果数: {len(final_results)}")
    print(f"事件保留率: {len(final_results)/total_events*100:.1f}%")
    
    n_with_response = np.sum(final_results['response_detected'] == 1)
    print(f"明显响应事件: {n_with_response} ({n_with_response/len(final_results)*100:.1f}%)")
    
    # 保存最终结果
    print("\n保存最终结果...")
    out_file = os.path.join(OUTPUT_DIR, "reco_response_events_global_v10.nc")
    
    with nc.Dataset(out_file, 'w') as ds:
        ds.createDimension('event', len(final_results))
        
        for field in RESULT_FIELDS:
            if field in ['lat', 'lon', 'reco_min', 'reco_mean', 'reco_trend', 'amp_max', 't_recover', 'recovery_rate']:
                var = ds.createVariable(field, 'f4', ('event',), fill_value=np.nan)
            elif field in ['event_id', 'onset_year', 'onset_doy', 't_min', 't_response', 't_impact']:
                var = ds.createVariable(field, 'i2', ('event',))
            elif field == 'response_detected':
                var = ds.createVariable(field, 'i1', ('event',))
            
            var[:] = final_results[field]
        
        ds.title = 'RECO Response to Flash Drought - Global (v10 Memory Optimized)'
        ds.history = f'Created: {datetime.now()}'
        ds.description = 'Analysis of ecosystem respiration (RECO) response to flash drought events'
    
    print(f"输出: {out_file}")
    print(f"文件大小: {os.path.getsize(out_file)/1024/1024:.1f} MB")
    
    # 清理临时文件
    print("\n清理临时文件...")
    shutil.rmtree(TEMP_DIR)
    
    print("\n✅ RECO全球分析完成！")
    print("\n输出目录: " + OUTPUT_DIR)

if __name__ == "__main__":
    main()
