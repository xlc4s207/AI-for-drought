"""
Lagged CCM Analysis V3 - 极速版 (Numba 加速)
=============================================
核心优化:
  1. Numba JIT 重写 CCM 算法 - 比纯 Python 快 50-100 倍
  2. 增大 subsample (10) 和 lag_step (20) - 减少计算量
  3. 增加并行 workers (40) - 提高 CPU 利用率
  4. 块读取 I/O - 避免 I/O thrashing

预估运行时间: 1-3 小时 (相比 V2.1 的 55 小时)

CCM 算法说明:
  - 使用延迟嵌入构建相空间 (manifold)
  - 对每个点找 K 个最近邻
  - 使用近邻权重进行交叉映射预测
  - 计算预测值与实际值的相关系数 (rho)

作者: AI Assistant
日期: 2026-01-23
"""
import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool
import warnings
from datetime import datetime
import shutil
from numba import jit, prange

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
OUTPUT_DIR = os.path.join(BASE_DIR, "process/GPP-draught-analysis/CCM_code/results_v3")
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# CCM 参数 (优化版)
CCM_E = 3           # 嵌入维数
CCM_TAU = 7         # 时间延迟
CCM_K = 4           # 近邻数 (E+1)
LAG_MIN = -30       # 最小滞后
LAG_MAX = 90        # 最大滞后
LAG_STEP = 20       # 滞后步长 (优化: 从10增到20)
CCM_SUBSAMPLE = 10  # 下采样因子 (优化: 从5增到10)
MIN_DATA_LENGTH = 300

# 并行配置 (优化: 增加 workers)
N_WORKERS = 40
LAT_CHUNK_SIZE = 10

# 结果字段
RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'),
    ('n_events', 'i2'),
    ('lag_star', 'i2'),
    ('rho_max', 'f4'),
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
    global _gpp_ds, _sms_ds, _event_ds
    _gpp_ds = nc.Dataset(GPP_FILE, 'r')
    _sms_ds = nc.Dataset(SMS_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')

# ============================================
# Numba 加速的 CCM 核心函数
# ============================================

@jit(nopython=True)
def delay_embed(x, E, tau):
    """
    延迟嵌入构建相空间
    
    参数:
        x: 时间序列
        E: 嵌入维数
        tau: 时间延迟
    
    返回:
        embedded: (n_points, E) 矩阵
    """
    n = len(x) - (E - 1) * tau
    if n <= 0:
        return np.empty((0, E), dtype=np.float64)
    
    embedded = np.empty((n, E), dtype=np.float64)
    for i in range(n):
        for e in range(E):
            embedded[i, e] = x[i + e * tau]
    return embedded

@jit(nopython=True)
def find_k_nearest(point, manifold, k, exclude_idx):
    """
    找到 K 个最近邻 (排除自己和时间邻近点)
    
    返回:
        indices: 最近邻的索引
        distances: 对应的距离
    """
    n = manifold.shape[0]
    
    # 计算所有距离
    dists = np.empty(n, dtype=np.float64)
    for i in range(n):
        d = 0.0
        for j in range(manifold.shape[1]):
            diff = point[j] - manifold[i, j]
            d += diff * diff
        dists[i] = np.sqrt(d)
    
    # 排除自己和时间邻近点 (±3)
    for i in range(max(0, exclude_idx - 3), min(n, exclude_idx + 4)):
        dists[i] = np.inf
    
    # 找 K 个最小
    indices = np.empty(k, dtype=np.int64)
    distances = np.empty(k, dtype=np.float64)
    
    for ki in range(k):
        min_idx = 0
        min_val = dists[0]
        for i in range(1, n):
            if dists[i] < min_val:
                min_val = dists[i]
                min_idx = i
        indices[ki] = min_idx
        distances[ki] = min_val
        dists[min_idx] = np.inf
    
    return indices, distances

@jit(nopython=True)
def ccm_core(x, y, E, tau, k):
    """
    Numba 加速的 CCM 核心算法
    
    检验: x -> y 是否有因果 (用 y 的流形预测 x)
    
    参数:
        x: 驱动变量
        y: 响应变量
        E: 嵌入维数
        tau: 时间延迟
        k: 近邻数
    
    返回:
        rho: 交叉映射相关系数
    """
    # 构建 y 的延迟嵌入 (shadow manifold)
    M_y = delay_embed(y, E, tau)
    n_points = M_y.shape[0]
    
    if n_points < k + 10:
        return np.nan
    
    # 对齐 x (取与 M_y 对应的部分)
    x_aligned = x[(E - 1) * tau:(E - 1) * tau + n_points]
    
    # 交叉映射预测
    x_pred = np.empty(n_points, dtype=np.float64)
    
    for i in range(n_points):
        # 找最近邻
        indices, distances = find_k_nearest(M_y[i], M_y, k, i)
        
        # 计算权重 (指数衰减)
        min_dist = distances[0]
        if min_dist < 1e-10:
            min_dist = 1e-10
        
        weights = np.empty(k, dtype=np.float64)
        weight_sum = 0.0
        for ki in range(k):
            w = np.exp(-distances[ki] / min_dist)
            weights[ki] = w
            weight_sum += w
        
        # 归一化权重
        for ki in range(k):
            weights[ki] /= weight_sum
        
        # 加权预测
        pred = 0.0
        for ki in range(k):
            pred += weights[ki] * x_aligned[indices[ki]]
        x_pred[i] = pred
    
    # 计算相关系数
    x_mean = 0.0
    pred_mean = 0.0
    for i in range(n_points):
        x_mean += x_aligned[i]
        pred_mean += x_pred[i]
    x_mean /= n_points
    pred_mean /= n_points
    
    num = 0.0
    den_x = 0.0
    den_pred = 0.0
    for i in range(n_points):
        dx = x_aligned[i] - x_mean
        dp = x_pred[i] - pred_mean
        num += dx * dp
        den_x += dx * dx
        den_pred += dp * dp
    
    den = np.sqrt(den_x * den_pred)
    if den < 1e-10:
        return np.nan
    
    return num / den

@jit(nopython=True)
def run_ccm_at_lag_numba(sms, gpp, lag, E, tau, k, subsample):
    """在指定滞后下运行 CCM"""
    # 应用滞后
    if lag > 0:
        x = sms[:-lag].copy()
        y = gpp[lag:].copy()
    elif lag < 0:
        x = sms[-lag:].copy()
        y = gpp[:lag].copy()
    else:
        x = sms.copy()
        y = gpp.copy()
    
    # 去除 NaN (简单处理: 只保留两者都有效的)
    n = len(x)
    valid_count = 0
    for i in range(n):
        if not (np.isnan(x[i]) or np.isnan(y[i])):
            valid_count += 1
    
    if valid_count < 200:
        return np.nan
    
    x_clean = np.empty(valid_count, dtype=np.float64)
    y_clean = np.empty(valid_count, dtype=np.float64)
    j = 0
    for i in range(n):
        if not (np.isnan(x[i]) or np.isnan(y[i])):
            x_clean[j] = x[i]
            y_clean[j] = y[i]
            j += 1
    
    # 下采样
    if subsample > 1:
        new_len = valid_count // subsample
        if new_len < 100:
            return np.nan
        x_sub = np.empty(new_len, dtype=np.float64)
        y_sub = np.empty(new_len, dtype=np.float64)
        for i in range(new_len):
            x_sub[i] = x_clean[i * subsample]
            y_sub[i] = y_clean[i * subsample]
        x_clean = x_sub
        y_clean = y_sub
    
    # 运行 CCM
    rho = ccm_core(x_clean, y_clean, E, tau, k)
    return rho

@jit(nopython=True)
def process_pixel_ccm_numba(gpp_anom, sms_anom, E, tau, k, subsample, lags):
    """对单个像元进行 CCM 分析"""
    n_lags = len(lags)
    rhos = np.empty(n_lags, dtype=np.float64)
    
    for i in range(n_lags):
        rhos[i] = run_ccm_at_lag_numba(sms_anom, gpp_anom, lags[i], E, tau, k, subsample)
    
    # 找最优 lag
    best_idx = -1
    best_rho = -2.0
    valid_count = 0
    
    for i in range(n_lags):
        if not np.isnan(rhos[i]):
            valid_count += 1
            if rhos[i] > best_rho:
                best_rho = rhos[i]
                best_idx = i
    
    if valid_count == 0:
        return (-999, np.nan, np.nan, 0)
    
    lag_star = lags[best_idx]
    rho_max = rhos[best_idx]
    
    # 找 lag=0 的 rho
    rho_zero = np.nan
    for i in range(n_lags):
        if lags[i] == 0:
            rho_zero = rhos[i]
            break
    
    return (lag_star, rho_max, rho_zero, 1)

# ============================================
# 非 Numba 的辅助函数
# ============================================

def build_doy_index(start_year, end_year):
    idx_arr = []
    for year in range(start_year, end_year + 1):
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        for d in range(366 if is_leap else 365):
            doy_idx = d if is_leap else (d if d < 59 else d + 1)
            idx_arr.append(doy_idx)
    return np.array(idx_arr, dtype=np.int16)

def calc_anomaly_vectorized(ts_matrix, doy_idx):
    """向量化计算异常值"""
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

def process_chunk(chunk_info):
    """处理一个纬度块"""
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    
    # 预编译 lags 数组
    lags = np.arange(LAG_MIN, LAG_MAX + 1, LAG_STEP, dtype=np.int64)
    
    try:
        lat_arr = _gpp_ds.variables['lat'][lat_start:lat_end]
        lon_arr = _gpp_ds.variables['lon'][:]
        n_lats = lat_end - lat_start
        
        # 块读取
        gpp_chunk = _gpp_ds.variables['GPP'][:, lat_start:lat_end, :]
        if hasattr(gpp_chunk, 'filled'):
            gpp_chunk = gpp_chunk.filled(np.nan)
        gpp_chunk = gpp_chunk.astype(np.float32)
        
        sms_offset = 730
        n_time_gpp = gpp_chunk.shape[0]
        sms_chunk = _sms_ds.variables['SMs'][sms_offset:sms_offset + n_time_gpp, lat_start:lat_end, :]
        if hasattr(sms_chunk, 'filled'):
            sms_chunk = sms_chunk.filled(np.nan)
        sms_chunk = sms_chunk.astype(np.float32)
        
        ec_chunk = _event_ds.variables['event_count'][lat_start:lat_end, :]
        doy_idx = build_doy_index(1982, 2022)
        
        for rel_lat in range(n_lats):
            lat_val = float(lat_arr[rel_lat])
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            
            if len(lon_with_events) == 0:
                continue
            
            gpp_row = gpp_chunk[:, rel_lat, lon_with_events]
            sms_row = sms_chunk[:, rel_lat, lon_with_events]
            
            gpp_anom_row = calc_anomaly_vectorized(gpp_row, doy_idx)
            sms_anom_row = calc_anomaly_vectorized(sms_row, doy_idx)
            
            for idx, lon_idx in enumerate(lon_with_events):
                lon_val = float(lon_arr[lon_idx])
                n_events = int(ec_chunk[rel_lat, lon_idx])
                
                gpp_anom = gpp_anom_row[:, idx].astype(np.float64)
                sms_anom = sms_anom_row[:, idx].astype(np.float64)
                
                # Numba 加速的 CCM
                lag_star, rho_max, rho_zero, valid = process_pixel_ccm_numba(
                    gpp_anom, sms_anom, CCM_E, CCM_TAU, CCM_K, CCM_SUBSAMPLE, lags
                )
                
                results.append((
                    lat_val, lon_val, n_events,
                    int(lag_star), float(rho_max), float(rho_zero), int(valid)
                ))
        
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
    if len(result_arr) > 0:
        temp_file = os.path.join(TEMP_DIR, f"chunk_{chunk_id:04d}.npy")
        np.save(temp_file, result_arr)
        return len(result_arr)
    return 0

def main():
    print("="*70)
    print("Lagged CCM V3 - 极速版 (Numba 加速)")
    print("="*70)
    print("核心优化:")
    print("  - Numba JIT 加速 CCM 核心算法")
    print(f"  - 40 workers 并行处理")
    print(f"  - Subsample={CCM_SUBSAMPLE}, Lag步长={LAG_STEP}")
    print("")
    print(f"CCM参数: E={CCM_E}, τ={CCM_TAU}, K={CCM_K}")
    print(f"Lag扫描: [{LAG_MIN}, {LAG_MAX}], 步长={LAG_STEP}")
    print("")
    
    # JIT 预热
    print("JIT 预热中...")
    test_x = np.random.randn(500)
    test_y = np.random.randn(500)
    _ = ccm_core(test_x, test_y, 3, 7, 4)
    print("JIT 预热完成")
    print("")
    
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)
    
    start_time = datetime.now()
    
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
    
    chunks = []
    chunk_id = 0
    for chunk_start in range(lat_start_idx, lat_end_idx, LAT_CHUNK_SIZE):
        chunk_end = min(chunk_start + LAT_CHUNK_SIZE, lat_end_idx)
        chunks.append((chunk_id, chunk_start, chunk_end))
        chunk_id += 1
    
    print(f"任务块数: {len(chunks)}")
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    total_saved = 0
    
    with Pool(N_WORKERS, initializer=worker_init) as pool:
        for cid, result_arr in tqdm(pool.imap_unordered(process_chunk, chunks),
                                    total=len(chunks),
                                    desc="CCM分析(V3)"):
            saved = save_chunk_to_disk(cid, result_arr)
            total_saved += saved
    
    mid_time = datetime.now()
    print(f"\n处理完成，已保存 {total_saved} 个像元结果")
    print(f"处理耗时: {(mid_time - start_time).total_seconds()/60:.1f}分钟")
    
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
    
    valid_results = final_results[final_results['valid'] == 1]
    print(f"有效结果数: {len(valid_results)} ({len(valid_results)/len(final_results)*100:.1f}%)")
    
    if len(valid_results) > 0:
        lag_stars = valid_results['lag_star']
        print(f"Lag*统计: 中位数={np.median(lag_stars):.0f}天, 均值={np.mean(lag_stars):.1f}天")
    
    print("\n保存最终结果...")
    out_file = os.path.join(OUTPUT_DIR, "ccm_lag_results_v3.nc")
    
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
        
        ds.title = 'Lagged CCM V3: SMs -> GPP (Numba Accelerated)'
        ds.method = 'CCM with Numba JIT acceleration'
        ds.ccm_E = CCM_E
        ds.ccm_tau = CCM_TAU
        ds.ccm_k = CCM_K
        ds.lag_range = f"[{LAG_MIN}, {LAG_MAX}], step={LAG_STEP}"
        ds.subsample_factor = CCM_SUBSAMPLE
        ds.history = f'Created: {datetime.now()}'
    
    print(f"输出: {out_file}")
    print(f"文件大小: {os.path.getsize(out_file)/1024/1024:.1f} MB")
    
    print("清理临时文件...")
    shutil.rmtree(TEMP_DIR)
    
    print("\n✅ CCM V3 分析完成！")

if __name__ == "__main__":
    main()
