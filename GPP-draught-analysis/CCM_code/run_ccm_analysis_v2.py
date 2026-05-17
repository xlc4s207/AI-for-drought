"""
Lagged CCM Analysis V2 - 使用 causal-ccm 库的真实 CCM 方法
===========================================================
使用 Convergent Cross Mapping (CCM) 计算骤旱事件对 GPP 的因果滞后时间

CCM原理:
  - 如果 X 驱动 Y,则 Y 的相空间("attractor")包含 X 的信息
  - 使用 Y 的延迟嵌入重构 manifold,然后"cross-map"预测 X
  - Cross-mapping 技能(相关性)随数据长度增加而收敛是因果的关键证据

本脚本:
  - 对每个有骤旱事件的像元,提取 SMs 和 GPP 时间序列
  - 使用 causal-ccm 库进行真实的 CCM 分析
  - 扫描不同滞后时间,找到因果强度最大的 lag*

内存优化:
  - 分块并行处理
  - 每个 chunk 结果立即写入磁盘

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
OUTPUT_DIR = os.path.join(BASE_DIR, "process/GPP-draught-analysis/CCM_code/results_v2")
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
LAG_STEP = 10       # 滞后步长 (CCM计算较慢,用大步长)
MIN_DATA_LENGTH = 500  # 最小有效数据长度
CCM_SUBSAMPLE = 5   # 下采样因子 (加速CCM计算)

# 并行配置
N_WORKERS = 50
LAT_CHUNK_SIZE = 20

# 结果字段定义
RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'),
    ('n_events', 'i2'),
    ('lag_star', 'i2'),       # 最优滞后 (天)
    ('rho_max', 'f4'),        # 最大CCM相关系数
    ('p_value', 'f4'),        # 最优lag的p值
    ('rho_zero', 'f4'),       # lag=0时的相关系数
    ('valid', 'i1')           # 数据是否有效
])

# ============================================
# 全局变量 (worker进程)
# ============================================
_gpp_ds = None
_sms_ds = None
_event_ds = None

def worker_init():
    """Worker进程初始化: 打开数据文件"""
    global _gpp_ds, _sms_ds, _event_ds
    _gpp_ds = nc.Dataset(GPP_FILE, 'r')
    _sms_ds = nc.Dataset(SMS_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')

def calc_anomaly(ts, doy_idx):
    """计算异常值 (Z-score) - 去除季节性"""
    n = len(ts)
    result = np.full(n, np.nan, dtype=np.float32)
    
    for d in range(366):
        mask = (doy_idx == d) & ~np.isnan(ts)
        if np.sum(mask) < 5:
            continue
        
        vals = ts[mask]
        mean_val = np.nanmean(vals)
        std_val = np.nanstd(vals)
        
        if std_val > 0.001:
            result[mask] = (ts[mask] - mean_val) / std_val
    
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

def run_ccm_at_lag(sms_anom, gpp_anom, lag, E, tau, subsample):
    """
    在指定滞后下运行CCM分析
    
    参数:
        sms_anom: SMs异常序列
        gpp_anom: GPP异常序列
        lag: 滞后天数 (正=SMs领先GPP)
        E: 嵌入维数
        tau: 时间延迟
        subsample: 下采样因子
    
    返回:
        (rho, p_value) 或 (nan, nan)
    """
    try:
        # 应用滞后
        if lag > 0:
            x = sms_anom[:-lag]
            y = gpp_anom[lag:]
        elif lag < 0:
            x = sms_anom[-lag:]
            y = gpp_anom[:lag]
        else:
            x = sms_anom.copy()
            y = gpp_anom.copy()
        
        # 去除NaN
        valid_mask = ~np.isnan(x) & ~np.isnan(y)
        x = x[valid_mask]
        y = y[valid_mask]
        
        if len(x) < MIN_DATA_LENGTH:
            return (np.nan, np.nan)
        
        # 下采样以加速
        if subsample > 1:
            x = x[::subsample]
            y = y[::subsample]
        
        if len(x) < 100:
            return (np.nan, np.nan)
        
        # 运行CCM: 检验 x -> y (SMs驱动GPP)
        # 在CCM中, 用 y 的 manifold 来重构 x
        ccm_obj = ccm(y, x, tau=tau, E=E, L=len(x))
        rho, p_value = ccm_obj.causality()
        
        return (float(rho), float(p_value))
    
    except Exception as e:
        return (np.nan, np.nan)

def process_pixel_ccm(gpp_ts, sms_ts, doy_idx):
    """
    对单个像元进行真实CCM分析
    
    返回:
        (lag_star, rho_max, p_value, rho_zero, valid)
    """
    # 计算异常值
    gpp_anom = calc_anomaly(gpp_ts.astype(np.float64), doy_idx)
    sms_anom = calc_anomaly(sms_ts.astype(np.float64), doy_idx)
    
    # 检查有效数据量
    valid_mask = ~np.isnan(gpp_anom) & ~np.isnan(sms_anom)
    if np.sum(valid_mask) < MIN_DATA_LENGTH:
        return (-999, np.nan, np.nan, np.nan, 0)
    
    # 扫描不同滞后
    lags = np.arange(LAG_MIN, LAG_MAX + 1, LAG_STEP)
    rhos = np.full(len(lags), np.nan)
    pvals = np.full(len(lags), np.nan)
    
    for i, lag in enumerate(lags):
        rho, pval = run_ccm_at_lag(sms_anom, gpp_anom, lag, CCM_E, CCM_TAU, CCM_SUBSAMPLE)
        rhos[i] = rho
        pvals[i] = pval
    
    # 找最大相关的滞后
    valid_rhos = ~np.isnan(rhos)
    if not np.any(valid_rhos):
        return (-999, np.nan, np.nan, np.nan, 0)
    
    # 取rho最大值
    rhos_copy = rhos.copy()
    rhos_copy[~valid_rhos] = -1
    best_idx = np.argmax(rhos_copy)
    
    lag_star = int(lags[best_idx])
    rho_max = float(rhos[best_idx])
    p_value = float(pvals[best_idx]) if not np.isnan(pvals[best_idx]) else np.nan
    
    # 获取lag=0的相关
    zero_idx = np.argmin(np.abs(lags))
    rho_zero = float(rhos[zero_idx]) if valid_rhos[zero_idx] else np.nan
    
    return (lag_star, rho_max, p_value, rho_zero, 1)

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
        
        # 构建DOY索引
        doy_idx = build_doy_index(1982, 2022)
        
        # SMs从1980开始, GPP从1982开始 
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
                
                # 提取时间序列
                gpp_ts = _gpp_ds.variables['GPP'][:, abs_lat, lon_idx]
                if hasattr(gpp_ts, 'filled'):
                    gpp_ts = gpp_ts.filled(np.nan)
                gpp_ts = gpp_ts.astype(np.float32)
                
                sms_ts = _sms_ds.variables['SMs'][sms_offset:sms_offset + len(gpp_ts), abs_lat, lon_idx]
                if hasattr(sms_ts, 'filled'):
                    sms_ts = sms_ts.filled(np.nan)
                sms_ts = sms_ts.astype(np.float32)
                
                # 执行CCM分析
                lag_star, rho_max, p_value, rho_zero, valid = process_pixel_ccm(gpp_ts, sms_ts, doy_idx)
                
                results.append((
                    lat_val, lon_val, n_events,
                    lag_star, rho_max, p_value, rho_zero, valid
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
    print("Lagged CCM V2 - 使用 causal-ccm 库的真实 CCM 分析")
    print("="*70)
    print(f"CCM参数: E={CCM_E}, τ={CCM_TAU}")
    print(f"Lag扫描范围: [{LAG_MIN}, {LAG_MAX}], 步长={LAG_STEP}")
    print(f"下采样因子: {CCM_SUBSAMPLE} (加速计算)")
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
                                    desc="CCM分析(V2)"):
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
        print(f"Lag*统计: 中位数={np.median(lag_stars):.0f}天, "
              f"均值={np.mean(lag_stars):.1f}天")
        
        # 显著性统计
        sig_results = valid_results[valid_results['p_value'] < 0.05]
        print(f"显著结果 (p<0.05): {len(sig_results)} ({len(sig_results)/len(valid_results)*100:.1f}%)")
    
    # 保存最终结果
    print("\n保存最终结果...")
    out_file = os.path.join(OUTPUT_DIR, "ccm_lag_results_v2.nc")
    
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
        
        ds.title = 'Lagged CCM V2 Analysis: SMs -> GPP (using causal-ccm)'
        ds.method = 'Convergent Cross Mapping with manifold reconstruction'
        ds.ccm_E = CCM_E
        ds.ccm_tau = CCM_TAU
        ds.lag_range = f"[{LAG_MIN}, {LAG_MAX}], step={LAG_STEP}"
        ds.subsample_factor = CCM_SUBSAMPLE
        ds.history = f'Created: {datetime.now()}'
    
    print(f"输出: {out_file}")
    print(f"文件大小: {os.path.getsize(out_file)/1024/1024:.1f} MB")
    
    # 清理临时文件
    print("清理临时文件...")
    shutil.rmtree(TEMP_DIR)
    
    print("\n✅ CCM V2分析完成！")

if __name__ == "__main__":
    main()
