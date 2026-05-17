"""
Lagged CCM Analysis V2.1 - 高性能优化版
===========================================
基于 v2 改进:
  1. 块读取 (Block I/O): 一次读取整个 chunk 的数据，避免 I/O thrashing
  2. 内存控制: 减少 workers 数量，每个 worker 只处理一行数据
  3. 保持真实 CCM: 继续使用 causal-ccm 库 + subsample 加速

核心改进:
  - process_chunk 函数先把整个 chunk 的 GPP 和 SMs 读入内存
  - 然后在内存中遍历像元进行 CCM 分析，避免重复 I/O

作者: AI Assistant
日期: 2026-01-22
"""
import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool
import warnings
from datetime import datetime
import shutil

# 导入真实CCM库
from causal_ccm.causal_ccm import ccm

warnings.filterwarnings('ignore')

# ============================================
# 配置
# ============================================
BASE_DIR = "/home/xulc/flash_drought"

# 输入数据
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/result/SMs_result/flash_drought_SMs_events_details_v2.nc")
GPP_FILE = "/data/BESS_V2/BESS_GPP_1982_2022.nc"
SMS_FILE = "/data/GLEAM/SMs_45years.nc"

# 输出路径
OUTPUT_DIR = os.path.join(BASE_DIR, "process/GPP-draught-analysis/CCM_code/results_v2.1")
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# 时间配置
START_YEAR = 1982
END_YEAR = 2022

# CCM参数
CCM_E = 3           # 嵌入维数
CCM_TAU = 7         # 时间延迟
LAG_MIN = -30       # 最小滞后
LAG_MAX = 90        # 最大滞后
LAG_STEP = 10       # 滞后步长
MIN_DATA_LENGTH = 500
CCM_SUBSAMPLE = 5   # 下采样因子

# 并行配置 (优化: 减少 workers 避免内存爆炸)
N_WORKERS = 16      # 每个 worker 约 8GB 内存占用 -> 总计 ~130GB
LAT_CHUNK_SIZE = 10 # 减小 chunk 大小进一步降低内存

# 结果字段定义
RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'),
    ('n_events', 'i2'),
    ('lag_star', 'i2'),
    ('rho_max', 'f4'),
    ('p_value', 'f4'),
    ('rho_zero', 'f4'),
    ('valid', 'i1')
])

# ============================================
# 全局变量
# ============================================
_gpp_ds = None
_sms_ds = None
_event_ds = None

def worker_init():
    """Worker 初始化"""
    global _gpp_ds, _sms_ds, _event_ds
    _gpp_ds = nc.Dataset(GPP_FILE, 'r')
    _sms_ds = nc.Dataset(SMS_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')

def build_doy_index(start_year, end_year):
    """构建 DOY 索引"""
    idx_arr = []
    for year in range(start_year, end_year + 1):
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        for d in range(366 if is_leap else 365):
            doy_idx = d if is_leap else (d if d < 59 else d + 1)
            idx_arr.append(doy_idx)
    return np.array(idx_arr, dtype=np.int16)

def calc_anomaly_vectorized(ts_matrix, doy_idx):
    """
    向量化计算异常值 (Z-score)
    
    参数:
        ts_matrix: shape (time, n_pixels)
        doy_idx: shape (time,)
    
    返回:
        anomaly_matrix: shape (time, n_pixels)
    """
    n_time, n_pixels = ts_matrix.shape
    result = np.full_like(ts_matrix, np.nan, dtype=np.float32)
    
    for d in range(366):
        mask = (doy_idx == d)
        if np.sum(mask) < 5:
            continue
        
        data = ts_matrix[mask, :]
        with np.errstate(divide='ignore', invalid='ignore'):
            mean_vals = np.nanmean(data, axis=0)
            std_vals = np.nanstd(data, axis=0)
            std_vals[std_vals < 0.001] = np.nan
            result[mask, :] = (ts_matrix[mask, :] - mean_vals) / std_vals
    
    return result

def run_ccm_at_lag(sms_anom, gpp_anom, lag, E, tau, subsample):
    """在指定滞后下运行CCM"""
    try:
        if lag > 0:
            x = sms_anom[:-lag]
            y = gpp_anom[lag:]
        elif lag < 0:
            x = sms_anom[-lag:]
            y = gpp_anom[:lag]
        else:
            x = sms_anom.copy()
            y = gpp_anom.copy()
        
        valid_mask = ~np.isnan(x) & ~np.isnan(y)
        x = x[valid_mask]
        y = y[valid_mask]
        
        if len(x) < MIN_DATA_LENGTH:
            return (np.nan, np.nan)
        
        if subsample > 1:
            x = x[::subsample]
            y = y[::subsample]
        
        if len(x) < 100:
            return (np.nan, np.nan)
        
        ccm_obj = ccm(y, x, tau=tau, E=E, L=len(x))
        rho, p_value = ccm_obj.causality()
        
        return (float(rho), float(p_value))
    except:
        return (np.nan, np.nan)

def process_pixel_ccm(gpp_anom, sms_anom):
    """对单个像元进行 CCM 分析（输入已是异常值）"""
    valid_mask = ~np.isnan(gpp_anom) & ~np.isnan(sms_anom)
    if np.sum(valid_mask) < MIN_DATA_LENGTH:
        return (-999, np.nan, np.nan, np.nan, 0)
    
    lags = np.arange(LAG_MIN, LAG_MAX + 1, LAG_STEP)
    rhos = np.full(len(lags), np.nan)
    pvals = np.full(len(lags), np.nan)
    
    for i, lag in enumerate(lags):
        rho, pval = run_ccm_at_lag(sms_anom, gpp_anom, lag, CCM_E, CCM_TAU, CCM_SUBSAMPLE)
        rhos[i] = rho
        pvals[i] = pval
    
    valid_rhos = ~np.isnan(rhos)
    if not np.any(valid_rhos):
        return (-999, np.nan, np.nan, np.nan, 0)
    
    rhos_copy = rhos.copy()
    rhos_copy[~valid_rhos] = -1
    best_idx = np.argmax(rhos_copy)
    
    lag_star = int(lags[best_idx])
    rho_max = float(rhos[best_idx])
    p_value = float(pvals[best_idx]) if not np.isnan(pvals[best_idx]) else np.nan
    
    zero_idx = np.argmin(np.abs(lags))
    rho_zero = float(rhos[zero_idx]) if valid_rhos[zero_idx] else np.nan
    
    return (lag_star, rho_max, p_value, rho_zero, 1)

def process_chunk(chunk_info):
    """
    处理一个纬度块 - V2.1 块读取优化
    
    核心改进: 一次读取整个 chunk 的 GPP 和 SMs，然后在内存中处理
    """
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    
    try:
        # === 步骤1: 一次性读取整个 chunk 的数据 ===
        lat_arr = _gpp_ds.variables['lat'][lat_start:lat_end]
        lon_arr = _gpp_ds.variables['lon'][:]
        n_lats = lat_end - lat_start
        n_lons = len(lon_arr)
        
        # 块读取 GPP: (time, n_lats, n_lons)
        gpp_chunk = _gpp_ds.variables['GPP'][:, lat_start:lat_end, :]
        if hasattr(gpp_chunk, 'filled'):
            gpp_chunk = gpp_chunk.filled(np.nan)
        gpp_chunk = gpp_chunk.astype(np.float32)
        
        # 块读取 SMs: 对齐时间范围 (1982-2022)
        sms_offset = 730  # SMs从1980开始，GPP从1982开始
        n_time_gpp = gpp_chunk.shape[0]
        sms_chunk = _sms_ds.variables['SMs'][sms_offset:sms_offset + n_time_gpp, lat_start:lat_end, :]
        if hasattr(sms_chunk, 'filled'):
            sms_chunk = sms_chunk.filled(np.nan)
        sms_chunk = sms_chunk.astype(np.float32)
        
        # 读取事件计数
        ec_chunk = _event_ds.variables['event_count'][lat_start:lat_end, :]
        
        # 构建 DOY 索引
        doy_idx = build_doy_index(1982, 2022)
        
        # === 步骤2: 逐行处理（在内存中） ===
        for rel_lat in range(n_lats):
            lat_val = float(lat_arr[rel_lat])
            
            # 找有事件的像元
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            if len(lon_with_events) == 0:
                continue
            
            # 提取该行的数据子集
            gpp_row = gpp_chunk[:, rel_lat, lon_with_events]  # (time, n_valid_lons)
            sms_row = sms_chunk[:, rel_lat, lon_with_events]
            
            # 向量化计算异常值
            gpp_anom_row = calc_anomaly_vectorized(gpp_row, doy_idx)
            sms_anom_row = calc_anomaly_vectorized(sms_row, doy_idx)
            
            # 遍历有事件的像元
            for idx, lon_idx in enumerate(lon_with_events):
                lon_val = float(lon_arr[lon_idx])
                n_events = int(ec_chunk[rel_lat, lon_idx])
                
                gpp_anom = gpp_anom_row[:, idx]
                sms_anom = sms_anom_row[:, idx]
                
                # CCM 分析
                lag_star, rho_max, p_value, rho_zero, valid = process_pixel_ccm(gpp_anom, sms_anom)
                
                results.append((
                    lat_val, lon_val, n_events,
                    lag_star, rho_max, p_value, rho_zero, valid
                ))
        
        # 释放内存
        del gpp_chunk, sms_chunk
    
    except Exception as e:
        print(f"块 {chunk_id} 错误: {e}")
        import traceback
        traceback.print_exc()
        return chunk_id, np.array([], dtype=RESULT_DTYPE)
    
    if results:
        result_arr = np.array(results, dtype=RESULT_DTYPE)
    else:
        result_arr = np.array([], dtype=RESULT_DTYPE)
    
    return chunk_id, result_arr

def save_chunk_to_disk(chunk_id, result_arr):
    """保存 chunk 结果"""
    if len(result_arr) > 0:
        temp_file = os.path.join(TEMP_DIR, f"chunk_{chunk_id:04d}.npy")
        np.save(temp_file, result_arr)
        return len(result_arr)
    return 0

def main():
    print("="*70)
    print("Lagged CCM V2.1 - 高性能优化版 (块读取 + 真实CCM)")
    print("="*70)
    print("优化改进:")
    print("  - 块读取: 一次读取整个 chunk 数据")
    print("  - 内存控制: 16 workers, 10行/chunk")
    print("  - 向量化异常值计算")
    print("")
    print(f"CCM参数: E={CCM_E}, τ={CCM_TAU}")
    print(f"Lag扫描: [{LAG_MIN}, {LAG_MAX}], 步长={LAG_STEP}")
    print(f"下采样: {CCM_SUBSAMPLE}")
    print("")
    
    # 清理临时文件
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)
    
    start_time = datetime.now()
    
    # 确定有效纬度范围
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
        ec_all = ds.variables['event_count'][:]
        lat_has_events = np.any(ec_all > 0, axis=1)
        valid_lat_indices = np.where(lat_has_events)[0]
        
        if len(valid_lat_indices) == 0:
            print("无有效事件")
            return
        
        lat_start_idx = valid_lat_indices[0]
        lat_end_idx = valid_lat_indices[-1] + 1
        total_pixels_with_events = np.sum(ec_all > 0)
    
    print(f"有效纬度范围: [{lat_start_idx}, {lat_end_idx}) ({lat_end_idx - lat_start_idx}行)")
    print(f"有事件的像元数: {total_pixels_with_events}")
    
    # 生成 chunk 任务
    chunks = []
    chunk_id = 0
    for chunk_start in range(lat_start_idx, lat_end_idx, LAT_CHUNK_SIZE):
        chunk_end = min(chunk_start + LAT_CHUNK_SIZE, lat_end_idx)
        chunks.append((chunk_id, chunk_start, chunk_end))
        chunk_id += 1
    
    print(f"任务块数: {len(chunks)}")
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 并行处理
    total_saved = 0
    
    with Pool(N_WORKERS, initializer=worker_init) as pool:
        for cid, result_arr in tqdm(pool.imap_unordered(process_chunk, chunks),
                                    total=len(chunks),
                                    desc="CCM分析(V2.1)"):
            saved = save_chunk_to_disk(cid, result_arr)
            total_saved += saved
    
    mid_time = datetime.now()
    print(f"\n处理完成，已保存 {total_saved} 个像元结果")
    print(f"处理耗时: {(mid_time - start_time).total_seconds()/60:.1f}分钟")
    
    # 合并临时文件
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
    print(f"像元结果数: {len(final_results)}")
    
    # 统计
    valid_results = final_results[final_results['valid'] == 1]
    print(f"有效结果数: {len(valid_results)} ({len(valid_results)/len(final_results)*100:.1f}%)")
    
    if len(valid_results) > 0:
        lag_stars = valid_results['lag_star']
        print(f"Lag*统计: 中位数={np.median(lag_stars):.0f}天, 均值={np.mean(lag_stars):.1f}天")
        
        sig_results = valid_results[valid_results['p_value'] < 0.05]
        print(f"显著结果 (p<0.05): {len(sig_results)} ({len(sig_results)/len(valid_results)*100:.1f}%)")
    
    # 保存结果
    print("\n保存最终结果...")
    out_file = os.path.join(OUTPUT_DIR, "ccm_lag_results_v2.1.nc")
    
    with nc.Dataset(out_file, 'w') as ds:
        ds.createDimension('pixel', len(final_results))
        
        for field in RESULT_DTYPE.names:
            if field in ['lat', 'lon', 'rho_max', 'p_value', 'rho_zero']:
                var = ds.createVariable(field, 'f4', ('pixel',), fill_value=np.nan)
            elif field in ['n_events', 'lag_star']:
                var = ds.createVariable(field, 'i2', ('pixel',))
            elif field == 'valid':
                var = ds.createVariable(field, 'i1', ('pixel',))
            var[:] = final_results[field]
        
        ds.title = 'Lagged CCM V2.1: SMs -> GPP (Block I/O + causal-ccm)'
        ds.method = 'Convergent Cross Mapping with manifold reconstruction'
        ds.ccm_E = CCM_E
        ds.ccm_tau = CCM_TAU
        ds.lag_range = f"[{LAG_MIN}, {LAG_MAX}], step={LAG_STEP}"
        ds.subsample_factor = CCM_SUBSAMPLE
        ds.history = f'Created: {datetime.now()}'
    
    print(f"输出: {out_file}")
    print(f"文件大小: {os.path.getsize(out_file)/1024/1024:.1f} MB")
    
    # 清理
    print("清理临时文件...")
    shutil.rmtree(TEMP_DIR)
    
    print("\n✅ CCM V2.1 分析完成！")

if __name__ == "__main__":
    main()
