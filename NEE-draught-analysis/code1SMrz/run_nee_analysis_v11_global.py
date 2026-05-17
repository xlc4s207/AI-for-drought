"""
骤旱对NEE影响分析 - v11 全球版 (180天观测期 + 裁剪版)
==========================================
基于 RECO v11 修改为 NEE 分析：
  - 输入NEE文件：0.1°分辨率 NEE数据
  - 输入事件：裁剪后的SMrz事件（已排除沙漠和冰川）
  - WINDOW_AFTER：180天观测期
  - LAT_CHUNK_SIZE：5行（减小块大小）
  - N_WORKERS：30个并行进程
  - 更好的内存管理和错误处理

v11优化：
  - 每个chunk完成后立即写入临时文件
  - 主进程内存保持恒定
  - 最后合并所有临时文件
  - 及时释放内存
"""
import os
import gc
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
# 配置 - NEE v11版本
# ============================================
BASE_DIR = "/home/xulc/flash_drought"
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/flash_drought_events_v5.nc")
NEE_FILE = "/data/BESS_V2/NEE_1982-2022_0.1deg.nc"
OUTPUT_DIR = "/home/xulc/flash_drought/process/NEE-draught-analysis/code1SMrz/result"
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks_v11")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

START_YEAR, END_YEAR = 1982, 2022
WINDOW_BEFORE = 60
WINDOW_AFTER = 180  # 延长到180天
RESPONSE_SEARCH_WINDOW = 60
THRESHOLD_RESPONSE = 0.5   # NEE恶化阈值（向碳源方向偏移）
THRESHOLD_RECOVER = 0.25   # 恢复阈值（从恶化状态回落）
CONSECUTIVE_DAYS = 3

N_WORKERS = 30  # 增加到30个并行进程
LAT_CHUNK_SIZE = 5  # 减小到5行一个块

# 结果字段定义
RESULT_FIELDS = [
    'lat', 'lon', 'event_id', 'onset_year', 'onset_doy',
    'response_detected', 'nee_min', 'nee_mean', 'nee_trend', 't_min',
    't_response', 't_impact', 'amp_max', 't_recover', 'recovery_rate'
]
RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'), ('event_id', 'i2'), 
    ('onset_year', 'i2'), ('onset_doy', 'i2'),
    ('response_detected', 'i1'), ('nee_min', 'f4'), ('nee_mean', 'f4'),
    ('nee_trend', 'f4'), ('t_min', 'i2'), ('t_response', 'i2'),
    ('t_impact', 'i2'), ('amp_max', 'f4'), ('t_recover', 'f4'),
    ('recovery_rate', 'f4')
])

# ============================================
# 全局变量
# ============================================
_nee_ds = None
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
    global _nee_ds, _event_ds, _lon_arr, _year_offsets, _doy_idx
    _nee_ds = nc.Dataset(NEE_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')
    _lon_arr = _nee_ds.variables['lon'][:]
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
    """查找连续n天高于阈值的首次位置（NEE向碳源方向恶化）"""
    n = min(len(x), max_search)
    for i in range(n - n_consecutive + 1):
        all_above = True
        for j in range(i, i + n_consecutive):
            if np.isnan(x[j]) or x[j] < threshold:
                all_above = False
                break
        if all_above:
            return i
    return -1

@jit(nopython=True)
def find_recovery(x, start_idx, threshold, n_consecutive):
    """从start_idx开始查找恢复点（连续回落到阈值以下）"""
    n = len(x)
    for i in range(start_idx, n - n_consecutive + 1):
        all_below = True
        for j in range(i, i + n_consecutive):
            if np.isnan(x[j]) or x[j] >= threshold:
                all_below = False
                break
        if all_below:
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
def process_single_event(nee_z, ws, we, threshold_resp, threshold_recov, n_consec, max_search):
    """处理单个骤旱事件的NEE响应"""
    segment = nee_z[ws:we+1]
    
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
    
    # 分析干旱后期（从onset开始的180天）
    post = smoothed[60:]
    n_post = len(post)
    
    if n_post < 10:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)
    
    # 计算基本统计量（冲击峰值用最大值，表示NEE向碳源方向偏移的最强程度）
    nee_min, t_min_all = 1e9, -1
    valid_sum, valid_cnt = 0.0, 0
    for i in range(n_post):
        if not np.isnan(post[i]):
            valid_sum += post[i]
            valid_cnt += 1
            if post[i] < nee_min:
                nee_min = post[i]
                t_min_all = i
    
    nee_mean = valid_sum / valid_cnt if valid_cnt > 0 else np.nan
    nee_trend = calc_trend(post)
    
    # 检测响应（NEE向碳源方向恶化）
    t_response = find_threshold_crossing(post, threshold_resp, n_consec, max_search)
    
    if t_response == -1:
        return (0, nee_min, nee_mean, nee_trend, t_min_all, -1, -1, np.nan, np.nan, np.nan)
    
    # 查找响应后的峰值（最大正异常）
    t_min_local, min_val = -1, -1e9
    for i in range(t_response, n_post):
        if not np.isnan(post[i]) and post[i] > min_val:
            min_val = post[i]
            t_min_local = i
    
    if t_min_local == -1:
        return (1, nee_min, nee_mean, nee_trend, t_min_all, t_response, -1, np.nan, np.nan, np.nan)
    
    t_impact = t_min_local - t_response
    
    # 查找恢复点
    t_recover_idx = find_recovery(post, t_min_local + 1, threshold_recov, n_consec)
    if t_recover_idx == -1:
        t_recover, recovery_rate = np.nan, np.nan
    else:
        t_recover = float(t_recover_idx - t_min_local)
        recovery_rate = (min_val - threshold_recov) / t_recover if t_recover > 0 else np.nan
    
    return (1, nee_min, nee_mean, nee_trend, t_min_all, t_response, t_impact, min_val, t_recover, recovery_rate)

def calc_climatology_zscore(nee_matrix, doy_idx):
    """计算气候态和Z-score"""
    n_time, n_pixels = nee_matrix.shape
    clim_mean = np.full((366, n_pixels), np.nan, dtype=np.float32)
    clim_std = np.full((366, n_pixels), np.nan, dtype=np.float32)
    
    for d in range(366):
        mask = (doy_idx == d)
        if np.sum(mask) > 0:
            data = nee_matrix[mask, :]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                clim_mean[d, :] = np.nanmean(data, axis=0)
                clim_std[d, :] = np.nanstd(data, axis=0, ddof=0)
    
    clim_std[clim_std < 0.01] = np.nan
    full_mean = clim_mean[doy_idx, :]
    full_std = clim_std[doy_idx, :]
    
    with np.errstate(divide='ignore', invalid='ignore'):
        z_matrix = (nee_matrix - full_mean) / full_std
    
    # 及时释放内存
    del clim_mean, clim_std, full_mean, full_std
    
    return z_matrix

def process_chunk(chunk_info):
    """处理一个块并返回结果数组"""
    chunk_id, lat_start, lat_end = chunk_info
    results = []
    
    try:
        lat_arr = _nee_ds.variables['lat'][lat_start:lat_end]
        n_lats = lat_end - lat_start
        
        # 读取NEE数据 (注意：NEE可能是int16类型，需要先转float再填充nan)
        nee_chunk = _nee_ds.variables['NEE'][:, lat_start:lat_end, :]
        # 先转换为float32，然后处理masked值
        if hasattr(nee_chunk, 'mask'):
            # 对于masked array，先转float再填充
            nee_chunk = nee_chunk.astype(np.float32)
            nee_chunk = np.ma.filled(nee_chunk, np.nan)
        else:
            nee_chunk = nee_chunk.astype(np.float32)
        
        ec_chunk = _event_ds.variables['event_count'][lat_start:lat_end, :]
        # 处理 masked array
        if hasattr(ec_chunk, 'filled'):
            ec_chunk = ec_chunk.filled(0)
        
        max_ec = int(np.max(ec_chunk))
        if max_ec == 0:
            del nee_chunk, ec_chunk
            return chunk_id, np.array([], dtype=RESULT_DTYPE)
        
        # 使用 .filled(-1) 处理masked值
        oy_raw = _event_ds.variables['onset_start_year'][:max_ec, lat_start:lat_end, :]
        od_raw = _event_ds.variables['onset_start_doy'][:max_ec, lat_start:lat_end, :]
        oy_chunk = oy_raw.filled(-1) if hasattr(oy_raw, 'filled') else oy_raw
        od_chunk = od_raw.filled(-1) if hasattr(od_raw, 'filled') else od_raw
        del oy_raw, od_raw  # 及时删除
        
        for rel_lat in range(n_lats):
            lat_val = float(lat_arr[rel_lat])
            
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            if len(lon_with_events) == 0:
                continue
            
            nee_row = nee_chunk[:, rel_lat, lon_with_events]
            valid_count = np.sum(~np.isnan(nee_row), axis=0)
            good_mask = valid_count >= 100
            
            if not np.any(good_mask):
                continue
            
            good_lon_indices = lon_with_events[good_mask]
            nee_good = nee_row[:, good_mask]
            z_matrix = calc_climatology_zscore(nee_good, _doy_idx)
            del nee_row, nee_good  # 及时释放
            
            for idx, lon_idx in enumerate(good_lon_indices):
                ec = int(ec_chunk[rel_lat, lon_idx])
                nee_z = z_matrix[:, idx]
                lon_val = float(_lon_arr[lon_idx])
                
                for i in range(ec):
                    oy = int(oy_chunk[i, rel_lat, lon_idx])
                    od = int(od_chunk[i, rel_lat, lon_idx])
                    
                    if oy < START_YEAR or oy > END_YEAR or od <= 0 or od > 366:
                        continue
                    
                    onset = _year_offsets[oy] + od - 1
                    ws, we = onset - WINDOW_BEFORE, onset + WINDOW_AFTER
                    
                    if ws < 0 or we >= len(nee_z):
                        continue
                    
                    m = process_single_event(
                        nee_z, ws, we,
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
            del z_matrix  # 释放z分数矩阵
        
        # 释放所有chunk数据
        del nee_chunk, ec_chunk, oy_chunk, od_chunk
        gc.collect()
    
    except Exception as e:
        print(f"块 {chunk_id} 错误: {e}")
        import traceback
        traceback.print_exc()
        gc.collect()
        return chunk_id, np.array([], dtype=RESULT_DTYPE)
    
    # 转换为numpy结构化数组
    if results:
        result_arr = np.array(results, dtype=RESULT_DTYPE)
        del results
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
    print("骤旱对NEE影响分析 - v11 全球版")
    print("="*70)
    print("数据源:")
    print(f"  NEE: {NEE_FILE}")
    print(f"  SMrz事件: {DROUGHT_EVENTS_FILE}")
    print(f"  观测窗口: 前{WINDOW_BEFORE}天 + 后{WINDOW_AFTER}天")
    print(f"  块大小: {LAT_CHUNK_SIZE}行/块")
    print(f"  并行进程: {N_WORKERS}")
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
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 并行处理 + 即时写入磁盘
    total_saved = 0
    completed = 0
    
    with Pool(N_WORKERS, initializer=worker_init) as pool:
        try:
            for cid, result_arr in tqdm(pool.imap_unordered(process_chunk, chunks),
                                        total=len(chunks),
                                        desc="处理进度"):
                saved = save_chunk_to_disk(cid, result_arr)
                total_saved += saved
                completed += 1
                del result_arr  # 及时释放
                gc.collect()
        except KeyboardInterrupt:
            print("\n用户中断，正在清理...")
            pool.terminate()
            pool.join()
        except Exception as e:
            print(f"\n处理出错: {e}")
            pool.terminate()
            pool.join()
    
    print(f"\n已完成 {completed}/{len(chunks)} 个chunk")
    mid_time = datetime.now()
    print(f"处理完成，已保存 {total_saved} 个事件到临时文件")
    print(f"处理耗时: {(mid_time - start_time).total_seconds()/60:.1f}分钟")
    
    # 合并所有临时文件
    print("\n合并临时文件...")
    temp_files = sorted([f for f in os.listdir(TEMP_DIR) if f.endswith('.npy')])
    
    all_results = []
    for tf in tqdm(temp_files, desc="合并"):
        arr = np.load(os.path.join(TEMP_DIR, tf))
        all_results.append(arr)
        del arr  # 及时释放
    
    if all_results:
        final_results = np.concatenate(all_results)
        del all_results
        gc.collect()
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
    out_file = os.path.join(OUTPUT_DIR, "nee_response_events_global_v11.nc")
    
    with nc.Dataset(out_file, 'w') as ds:
        ds.createDimension('event', len(final_results))
        
        for field in RESULT_FIELDS:
            if field in ['lat', 'lon', 'nee_min', 'nee_mean', 'nee_trend', 'amp_max', 't_recover', 'recovery_rate']:
                var = ds.createVariable(field, 'f4', ('event',), fill_value=np.nan, zlib=True, complevel=4)
            elif field in ['event_id', 'onset_year', 'onset_doy', 't_min', 't_response', 't_impact']:
                var = ds.createVariable(field, 'i2', ('event',), fill_value=-9999, zlib=True, complevel=4)
            elif field == 'response_detected':
                var = ds.createVariable(field, 'i1', ('event',), fill_value=-127, zlib=True, complevel=4)
            
            var[:] = final_results[field]
        
        ds.title = 'NEE Response to SMrz Flash Drought - Global (v11, 180-day window, clipped)'
        ds.history = f'Created: {datetime.now()}'
        ds.description = ('Analysis of net ecosystem exchange (NEE) response to flash drought events. '
                  'Response is defined as positive NEE anomaly (toward carbon source), '
                  'and recovery is defined as returning below recovery threshold.')
        ds.source_nee = NEE_FILE
        ds.source_drought = DROUGHT_EVENTS_FILE
        ds.parameters = (f'WINDOW_BEFORE={WINDOW_BEFORE}, WINDOW_AFTER={WINDOW_AFTER}, '
                        f'THRESHOLD_RESPONSE={THRESHOLD_RESPONSE}, '
                        f'THRESHOLD_RECOVER={THRESHOLD_RECOVER}, '
                        f'CONSECUTIVE_DAYS={CONSECUTIVE_DAYS}, '
                        f'N_WORKERS={N_WORKERS}, LAT_CHUNK_SIZE={LAT_CHUNK_SIZE}')
    
    print(f"输出: {out_file}")
    print(f"文件大小: {os.path.getsize(out_file)/1024/1024:.1f} MB")
    
    # 清理临时文件
    print("\n清理临时文件...")
    shutil.rmtree(TEMP_DIR)
    
    print("\n✅ NEE v11 全球分析完成！")
    print("\n输出目录: " + OUTPUT_DIR)

if __name__ == "__main__":
    main()
