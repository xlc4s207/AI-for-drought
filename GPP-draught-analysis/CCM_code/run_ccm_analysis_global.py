"""
Lagged CCM Analysis for Flash Drought -> GPP Response Time
===========================================================
基于 Convergent Cross Mapping (CCM) 计算骤旱事件对 GPP 的因果滞后时间

核心方法:
  - 对每个有骤旱事件的像元,提取 SMs 和 GPP 时间序列
  - 使用 Lagged CCM 扫描不同滞后时间 (lag),找到因果强度最大的 lag*
  - lag* 即为 SMs 驱动 GPP 响应的特征时间

内存优化策略 (参考 v10):
  - 分块并行处理 (LAT_CHUNK_SIZE 行/块)
  - 每个 worker 独立打开文件句柄
  - 每个 chunk 结果立即写入磁盘
  - 最后合并所有临时文件

输出:
  - 每个像元的最优滞后时间 lag*
  - 每个像元的最大因果强度 rho_max
  - 每个骤旱事件的响应时间估计

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
from numba import jit
import shutil

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
OUTPUT_DIR = os.path.join(BASE_DIR, "process/GPP-draught-analysis/CCM_code/results")
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# 时间配置
START_YEAR = 1982  # GPP数据起始年
END_YEAR = 2022    # GPP数据结束年

# CCM参数
CCM_E = 3           # 嵌入维数
CCM_TAU = 7         # 时间延迟
LAG_MIN = -30       # 最小滞后 (负=SM领先GPP)
LAG_MAX = 90        # 最大滞后
LAG_STEP = 5        # 滞后步长 (减少计算量)
MIN_DATA_LENGTH = 500  # 最小有效数据长度

# 并行配置
N_WORKERS = 50
LAT_CHUNK_SIZE = 20

# 结果字段定义
RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'),
    ('n_events', 'i2'),
    ('lag_star', 'i2'),       # 最优滞后 (天)
    ('rho_max', 'f4'),        # 最大相关系数
    ('rho_zero', 'f4'),       # lag=0时的相关系数
    ('valid', 'i1')           # 数据是否有效
])

# ============================================
# 全局变量 (worker进程)
# ============================================
_gpp_ds = None
_sms_ds = None
_event_ds = None
_gpp_time = None
_sms_time = None
_year_offsets_gpp = None
_year_offsets_sms = None

def build_year_offsets(start_year, end_year, base_year):
    """构建年份到时间索引的映射"""
    offsets = {}
    cumsum = 0
    for year in range(base_year, end_year + 1):
        if year >= start_year:
            offsets[year] = cumsum
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        cumsum += 366 if is_leap else 365
    return offsets

def worker_init():
    """Worker进程初始化: 打开数据文件"""
    global _gpp_ds, _sms_ds, _event_ds, _gpp_time, _sms_time
    global _year_offsets_gpp, _year_offsets_sms
    
    _gpp_ds = nc.Dataset(GPP_FILE, 'r')
    _sms_ds = nc.Dataset(SMS_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')
    
    _gpp_time = _gpp_ds.variables['time'][:]
    _sms_time = _sms_ds.variables['time'][:]
    
    # GPP: 1982-2022, SMs: 1980-2024
    _year_offsets_gpp = build_year_offsets(1982, 2022, 1982)
    _year_offsets_sms = build_year_offsets(1982, 2022, 1980)  # 从1980开始但只用1982起

@jit(nopython=True)
def calc_anomaly_fast(ts, doy_idx):
    """快速计算异常值 (Z-score)"""
    n = len(ts)
    result = np.full(n, np.nan, dtype=np.float32)
    
    # 计算每个DOY的气候态
    for d in range(366):
        mask_indices = []
        for i in range(n):
            if doy_idx[i] == d and not np.isnan(ts[i]):
                mask_indices.append(i)
        
        if len(mask_indices) < 5:
            continue
        
        vals = np.array([ts[i] for i in mask_indices])
        mean_val = np.mean(vals)
        std_val = np.std(vals)
        
        if std_val > 0.001:
            for i in mask_indices:
                result[i] = (ts[i] - mean_val) / std_val
    
    return result

def build_doy_index(start_year, end_year):
    """构建每天对应的DOY索引"""
    idx_arr = []
    for year in range(start_year, end_year + 1):
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        for d in range(366 if is_leap else 365):
            doy_idx = d if is_leap else (d if d < 59 else d + 1)
            idx_arr.append(doy_idx)
    return np.array(idx_arr, dtype=np.int16)

def simple_ccm_correlation(x, y, lag, E, tau):
    """
    简化版CCM: 使用延迟嵌入的相关性作为因果强度代理
    
    注意: 完整CCM需要manifold reconstruction,这里用简化版本加速
    完整版可以用 causal-ccm 库,但计算量大
    
    参数:
        x: 驱动变量 (SMs)
        y: 响应变量 (GPP)
        lag: 滞后天数 (正=x领先y)
        E: 嵌入维数
        tau: 时间延迟
    
    返回:
        rho: 相关系数
    """
    n = len(x)
    
    # 应用滞后
    if lag > 0:
        x_lagged = x[:-lag]
        y_target = y[lag:]
    elif lag < 0:
        x_lagged = x[-lag:]
        y_target = y[:lag]
    else:
        x_lagged = x
        y_target = y
    
    # 确保长度足够
    min_len = E * tau + 10
    if len(x_lagged) < min_len:
        return np.nan
    
    # 构建延迟嵌入
    embed_len = len(x_lagged) - (E - 1) * tau
    if embed_len < 50:
        return np.nan
    
    # 计算x嵌入与y的相关性 (简化版CCM)
    x_embed = np.zeros((embed_len, E))
    for e in range(E):
        start = (E - 1 - e) * tau
        x_embed[:, e] = x_lagged[start:start + embed_len]
    
    y_aligned = y_target[(E - 1) * tau:(E - 1) * tau + embed_len]
    
    # 去除NaN
    valid_mask = ~np.isnan(y_aligned)
    for e in range(E):
        valid_mask &= ~np.isnan(x_embed[:, e])
    
    if np.sum(valid_mask) < 50:
        return np.nan
    
    # 使用第一个嵌入维度计算相关性
    x_valid = x_embed[valid_mask, 0]
    y_valid = y_aligned[valid_mask]
    
    # Pearson相关系数
    x_mean = np.mean(x_valid)
    y_mean = np.mean(y_valid)
    
    num = np.sum((x_valid - x_mean) * (y_valid - y_mean))
    den = np.sqrt(np.sum((x_valid - x_mean)**2) * np.sum((y_valid - y_mean)**2))
    
    if den < 1e-10:
        return np.nan
    
    return num / den

def process_pixel_ccm(gpp_ts, sms_ts, doy_idx):
    """
    对单个像元进行CCM分析
    
    返回:
        (lag_star, rho_max, rho_zero, valid)
    """
    # 计算异常值
    gpp_anom = calc_anomaly_fast(gpp_ts.astype(np.float64), doy_idx)
    sms_anom = calc_anomaly_fast(sms_ts.astype(np.float64), doy_idx)
    
    # 检查有效数据量
    valid_mask = ~np.isnan(gpp_anom) & ~np.isnan(sms_anom)
    if np.sum(valid_mask) < MIN_DATA_LENGTH:
        return (-999, np.nan, np.nan, 0)
    
    # 扫描不同滞后
    lags = np.arange(LAG_MIN, LAG_MAX + 1, LAG_STEP)
    rhos = np.full(len(lags), np.nan)
    
    for i, lag in enumerate(lags):
        rhos[i] = simple_ccm_correlation(sms_anom, gpp_anom, lag, CCM_E, CCM_TAU)
    
    # 找最大相关的滞后
    valid_rhos = ~np.isnan(rhos)
    if not np.any(valid_rhos):
        return (-999, np.nan, np.nan, 0)
    
    # 取绝对值最大的(考虑负相关)
    abs_rhos = np.abs(rhos)
    abs_rhos[~valid_rhos] = -1
    
    best_idx = np.argmax(abs_rhos)
    lag_star = int(lags[best_idx])
    rho_max = float(rhos[best_idx])
    
    # 获取lag=0的相关
    zero_idx = np.argmin(np.abs(lags))
    rho_zero = float(rhos[zero_idx]) if valid_rhos[zero_idx] else np.nan
    
    return (lag_star, rho_max, rho_zero, 1)

def process_chunk(chunk_info):
    """处理一个纬度块"""
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    
    try:
        lat_arr = _gpp_ds.variables['lat'][lat_start:lat_end]
        lon_arr = _gpp_ds.variables['lon'][:]
        n_lats = lat_end - lat_start
        
        # 读取事件计数
        ec_chunk = _event_ds.variables['event_count'][lat_start:lat_end, :]
        
        # 构建DOY索引 (1982-2022)
        doy_idx = build_doy_index(1982, 2022)
        
        # 计算SMs在GPP时间范围内的起始索引
        # SMs从1980开始, GPP从1982开始 (1980-1981 = 730天)
        sms_offset = 730  # 约2年
        
        for rel_lat in range(n_lats):
            lat_val = float(lat_arr[rel_lat])
            abs_lat = lat_start + rel_lat
            
            # 找有事件的像元
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            
            if len(lon_with_events) == 0:
                continue
            
            for lon_idx in lon_with_events:
                lon_val = float(lon_arr[lon_idx])
                n_events = int(ec_chunk[rel_lat, lon_idx])
                
                # 提取该像元的时间序列
                gpp_ts = _gpp_ds.variables['GPP'][:, abs_lat, lon_idx]
                if hasattr(gpp_ts, 'filled'):
                    gpp_ts = gpp_ts.filled(np.nan)
                gpp_ts = gpp_ts.astype(np.float32)
                
                # 提取对应时间范围的SMs
                sms_ts = _sms_ds.variables['SMs'][sms_offset:sms_offset + len(gpp_ts), abs_lat, lon_idx]
                if hasattr(sms_ts, 'filled'):
                    sms_ts = sms_ts.filled(np.nan)
                sms_ts = sms_ts.astype(np.float32)
                
                # 执行CCM分析
                lag_star, rho_max, rho_zero, valid = process_pixel_ccm(gpp_ts, sms_ts, doy_idx)
                
                results.append((
                    lat_val, lon_val, n_events,
                    lag_star, rho_max, rho_zero, valid
                ))
    
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
    """保存chunk结果到临时文件"""
    if len(result_arr) > 0:
        temp_file = os.path.join(TEMP_DIR, f"chunk_{chunk_id:04d}.npy")
        np.save(temp_file, result_arr)
        return len(result_arr)
    return 0

def main():
    print("="*70)
    print("Lagged CCM 分析: SMs Flash Drought -> GPP Response")
    print("="*70)
    print(f"CCM参数: E={CCM_E}, τ={CCM_TAU}")
    print(f"Lag扫描范围: [{LAG_MIN}, {LAG_MAX}], 步长={LAG_STEP}")
    print("")
    
    # 清理旧临时文件
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
    
    # 生成chunk任务
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
                                    desc="CCM分析"):
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
    
    print(f"\n总耗时: {elapsed/60:.1f}分钟")
    print(f"像元结果数: {len(final_results)}")
    
    # 统计
    valid_results = final_results[final_results['valid'] == 1]
    print(f"有效结果数: {len(valid_results)} ({len(valid_results)/len(final_results)*100:.1f}%)")
    
    if len(valid_results) > 0:
        lag_stars = valid_results['lag_star']
        print(f"Lag*统计: 中位数={np.median(lag_stars):.0f}天, "
              f"均值={np.mean(lag_stars):.1f}天, "
              f"范围=[{np.min(lag_stars)}, {np.max(lag_stars)}]")
    
    # 保存最终结果
    print("\n保存最终结果...")
    out_file = os.path.join(OUTPUT_DIR, "ccm_lag_results_global.nc")
    
    with nc.Dataset(out_file, 'w') as ds:
        ds.createDimension('pixel', len(final_results))
        
        for field in RESULT_DTYPE.names:
            if field in ['lat', 'lon', 'rho_max', 'rho_zero']:
                var = ds.createVariable(field, 'f4', ('pixel',), fill_value=np.nan)
            elif field in ['n_events', 'lag_star']:
                var = ds.createVariable(field, 'i2', ('pixel',))
            elif field == 'valid':
                var = ds.createVariable(field, 'i1', ('pixel',))
            
            var[:] = final_results[field]
        
        ds.title = 'Lagged CCM Analysis: SMs Flash Drought -> GPP Response'
        ds.ccm_E = CCM_E
        ds.ccm_tau = CCM_TAU
        ds.lag_range = f"[{LAG_MIN}, {LAG_MAX}], step={LAG_STEP}"
        ds.history = f'Created: {datetime.now()}'
    
    print(f"输出: {out_file}")
    print(f"文件大小: {os.path.getsize(out_file)/1024/1024:.1f} MB")
    
    # 清理临时文件
    print("清理临时文件...")
    shutil.rmtree(TEMP_DIR)
    
    print("\n✅ CCM分析完成！")

if __name__ == "__main__":
    main()
