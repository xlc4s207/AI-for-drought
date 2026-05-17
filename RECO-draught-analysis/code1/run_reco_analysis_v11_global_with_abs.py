"""
根系土壤湿度 (SMrz) 骤旱对 RECO 影响分析 - v11 全球版（相对值 + 绝对值）
=================================================================
复用原有相对响应判定逻辑（z-score），并在同一次事件分析中输出 RECO 绝对值指标，
避免后续再对 event 结果文件做二次逐事件回算。
"""

import os
import shutil
from datetime import datetime

import netCDF4 as nc
import numpy as np
from multiprocessing import Pool
from numba import jit
from tqdm import tqdm
import warnings

warnings.filterwarnings('ignore')


BASE_DIR = "/home/xulc/flash_drought"
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz_5.3/flash_drought_events_v5.nc")
MERGED_GPP_FILE = "/data/BESS_V2/BESS_RECO_1982-2022_0.1deg.nc"
OUTPUT_DIR = os.path.join(BASE_DIR, "process/RECO-draught-analysis/code1/results")
TEMP_DIR = os.path.join(OUTPUT_DIR, "temp_chunks_SMrz_reco_with_abs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

START_YEAR, END_YEAR = 1982, 2022
WINDOW_BEFORE = 60
WINDOW_AFTER = 180
RESPONSE_SEARCH_WINDOW = 60
THRESHOLD_RESPONSE = -0.5
THRESHOLD_RECOVER = -0.25
CONSECUTIVE_DAYS = 3

N_WORKERS = 24
LAT_CHUNK_SIZE = 9

RESULT_DTYPE = np.dtype([
    ('lat', 'f4'), ('lon', 'f4'), ('event_id', 'i2'),
    ('onset_year', 'i2'), ('onset_doy', 'i2'),
    ('response_detected', 'i1'), ('reco_min', 'f4'), ('reco_mean', 'f4'),
    ('reco_trend', 'f4'), ('t_min', 'i2'), ('t_response', 'i2'),
    ('t_impact', 'i2'), ('amp_max', 'f4'), ('t_recover', 'f4'),
    ('recovery_rate', 'f4'),
    ('reco_baseline_abs', 'f4'), ('reco_min_abs', 'f4'), ('reco_max_abs', 'f4'),
    ('reco_mean_abs', 'f4'), ('reco_trend_abs', 'f4'), ('reco_drop_abs', 'f4'),
    ('reco_rise_abs', 'f4'), ('reco_change_to_peak_abs', 'f4'),
    ('reco_recovery_rate_abs', 'f4'),
])

RESULT_FIELDS = list(RESULT_DTYPE.names)

_gpp_ds = None
_event_ds = None
_lon_arr = None
_year_offsets = None
_doy_idx = None


def build_year_offsets():
    offsets = {}
    cumsum = 0
    for year in range(START_YEAR, END_YEAR + 1):
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        offsets[year] = cumsum
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
    global _gpp_ds, _event_ds, _lon_arr, _year_offsets, _doy_idx
    _gpp_ds = nc.Dataset(MERGED_GPP_FILE, 'r')
    _event_ds = nc.Dataset(DROUGHT_EVENTS_FILE, 'r')
    _lon_arr = _gpp_ds.variables['lon'][:]
    _year_offsets = build_year_offsets()
    _doy_idx = build_doy_index()


@jit(nopython=True)
def smooth_causal(x, window=7):
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
def process_single_event_relative(gpp_z, ws, we, threshold_resp, threshold_recov, n_consec, max_search):
    segment = gpp_z[ws:we + 1]

    if np.sum(~np.isnan(segment)) < 30:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)

    smoothed = smooth_causal(segment, 7)

    pre_vals = []
    for i in range(min(WINDOW_BEFORE, len(smoothed))):
        if not np.isnan(smoothed[i]):
            pre_vals.append(smoothed[i])

    if len(pre_vals) < 5:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)

    post = smoothed[WINDOW_BEFORE:]
    n_post = len(post)
    if n_post < 10:
        return (0, np.nan, np.nan, np.nan, -1, -1, -1, np.nan, np.nan, np.nan)

    gpp_min, t_min_all = 1e9, -1
    valid_sum, valid_cnt = 0.0, 0
    for i in range(n_post):
        if not np.isnan(post[i]):
            valid_sum += post[i]
            valid_cnt += 1
            if post[i] < gpp_min:
                gpp_min = post[i]
                t_min_all = i

    gpp_mean = valid_sum / valid_cnt if valid_cnt > 0 else np.nan
    gpp_trend = calc_trend(post)
    t_response = find_threshold_crossing(post, threshold_resp, n_consec, max_search)

    if t_response == -1:
        return (0, gpp_min, gpp_mean, gpp_trend, t_min_all, -1, -1, np.nan, np.nan, np.nan)

    t_min_local, min_val = -1, 1e9
    for i in range(t_response, n_post):
        if not np.isnan(post[i]) and post[i] < min_val:
            min_val = post[i]
            t_min_local = i

    if t_min_local == -1:
        return (1, gpp_min, gpp_mean, gpp_trend, t_min_all, t_response, -1, np.nan, np.nan, np.nan)

    t_impact = t_min_local - t_response
    t_recover_idx = find_recovery(post, t_min_local + 1, threshold_recov, n_consec)
    if t_recover_idx == -1:
        t_recover, recovery_rate = np.nan, np.nan
    else:
        t_recover = float(t_recover_idx - t_min_local)
        recovery_rate = (threshold_recov - min_val) / t_recover if t_recover > 0 else np.nan

    return (1, gpp_min, gpp_mean, gpp_trend, t_min_all, t_response, t_impact, min_val, t_recover, recovery_rate)


def calc_absolute_metrics(gpp_abs, ws, we, t_min, t_recover):
    segment = gpp_abs[ws:we + 1]
    if len(segment) <= WINDOW_BEFORE:
        return (np.nan,) * 9

    pre = segment[:WINDOW_BEFORE]
    post = segment[WINDOW_BEFORE:]
    pre_valid = np.isfinite(pre)
    post_valid = np.isfinite(post)
    if np.sum(pre_valid) < 5 or np.sum(post_valid) < 10:
        return (np.nan,) * 9

    baseline = float(np.nanmean(pre))
    post_min = float(np.nanmin(post))
    post_max = float(np.nanmax(post))
    post_mean = float(np.nanmean(post))
    post_trend = float(calc_trend(post))
    drop_abs = baseline - post_min
    rise_abs = post_max - baseline

    change_to_peak = np.nan
    recovery_rate_abs = np.nan
    if t_min >= 0 and t_min < len(post) and np.isfinite(post[t_min]):
        peak_val = float(post[t_min])
        change_to_peak = peak_val - baseline
        if np.isfinite(t_recover) and t_recover > 0:
            rec_idx = t_min + int(round(t_recover))
            if 0 <= rec_idx < len(post) and np.isfinite(post[rec_idx]):
                recovery_rate_abs = (float(post[rec_idx]) - peak_val) / float(t_recover)

    return (
        baseline, post_min, post_max, post_mean, post_trend,
        drop_abs, rise_abs, change_to_peak, recovery_rate_abs,
    )


def calc_climatology_zscore(gpp_matrix, doy_idx):
    n_time, n_pixels = gpp_matrix.shape
    clim_mean = np.full((366, n_pixels), np.nan, dtype=np.float32)
    clim_std = np.full((366, n_pixels), np.nan, dtype=np.float32)

    for d in range(366):
        mask = doy_idx == d
        if np.sum(mask) > 0:
            data = gpp_matrix[mask, :]
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                clim_mean[d, :] = np.nanmean(data, axis=0)
                clim_std[d, :] = np.nanstd(data, axis=0, ddof=0)

    clim_std[clim_std < 0.01] = np.nan
    full_mean = clim_mean[doy_idx, :]
    full_std = clim_std[doy_idx, :]
    with np.errstate(divide='ignore', invalid='ignore'):
        z_matrix = (gpp_matrix - full_mean) / full_std
    return z_matrix


def process_chunk(chunk_info):
    chunk_id, lat_start, lat_end = chunk_info
    results = []

    try:
        lat_arr = _gpp_ds.variables['lat'][lat_start:lat_end]
        n_lats = lat_end - lat_start

        gpp_chunk = _gpp_ds.variables['RECO'][:, lat_start:lat_end, :]
        if hasattr(gpp_chunk, 'filled'):
            gpp_chunk = gpp_chunk.filled(np.nan).astype(np.float32)
        else:
            gpp_chunk = gpp_chunk.astype(np.float32)

        ec_chunk = _event_ds.variables['event_count'][lat_start:lat_end, :]
        max_ec = int(np.max(ec_chunk))
        if max_ec == 0:
            return chunk_id, np.array([], dtype=RESULT_DTYPE)

        oy_raw = _event_ds.variables['onset_start_year'][:max_ec, lat_start:lat_end, :]
        od_raw = _event_ds.variables['onset_start_doy'][:max_ec, lat_start:lat_end, :]
        oy_chunk = oy_raw.filled(-1) if hasattr(oy_raw, 'filled') else oy_raw
        od_chunk = od_raw.filled(-1) if hasattr(od_raw, 'filled') else od_raw

        for rel_lat in range(n_lats):
            lat_val = float(lat_arr[rel_lat])
            lon_with_events = np.where(ec_chunk[rel_lat, :] > 0)[0]
            if len(lon_with_events) == 0:
                continue

            gpp_row = gpp_chunk[:, rel_lat, lon_with_events]
            valid_count = np.sum(~np.isnan(gpp_row), axis=0)
            good_mask = valid_count >= 100
            if not np.any(good_mask):
                continue

            good_lon_indices = lon_with_events[good_mask]
            gpp_good = gpp_row[:, good_mask]
            z_matrix = calc_climatology_zscore(gpp_good, _doy_idx)

            for idx, lon_idx in enumerate(good_lon_indices):
                ec = int(ec_chunk[rel_lat, lon_idx])
                gpp_z = z_matrix[:, idx]
                gpp_abs = gpp_good[:, idx]
                lon_val = float(_lon_arr[lon_idx])

                for event_id in range(ec):
                    oy = int(oy_chunk[event_id, rel_lat, lon_idx])
                    od = int(od_chunk[event_id, rel_lat, lon_idx])
                    if oy < START_YEAR or oy > END_YEAR or od <= 0 or od > 366:
                        continue

                    onset = _year_offsets[oy] + od - 1
                    ws, we = onset - WINDOW_BEFORE, onset + WINDOW_AFTER
                    if ws < 0 or we >= len(gpp_z):
                        continue

                    rel_metrics = process_single_event_relative(
                        gpp_z, ws, we,
                        THRESHOLD_RESPONSE, THRESHOLD_RECOVER,
                        CONSECUTIVE_DAYS, RESPONSE_SEARCH_WINDOW,
                    )
                    abs_metrics = calc_absolute_metrics(
                        gpp_abs, ws, we,
                        int(rel_metrics[4]) if rel_metrics[4] >= 0 else -1,
                        float(rel_metrics[8]),
                    )

                    results.append((
                        lat_val, lon_val, event_id, oy, od,
                        int(rel_metrics[0]), float(rel_metrics[1]), float(rel_metrics[2]), float(rel_metrics[3]),
                        int(rel_metrics[4]) if rel_metrics[4] >= 0 else -1,
                        int(rel_metrics[5]) if rel_metrics[5] >= 0 else -1,
                        int(rel_metrics[6]) if rel_metrics[6] >= 0 else -1,
                        float(rel_metrics[7]) if rel_metrics[0] else float(rel_metrics[1]),
                        float(rel_metrics[8]), float(rel_metrics[9]),
                        float(abs_metrics[0]), float(abs_metrics[1]), float(abs_metrics[2]),
                        float(abs_metrics[3]), float(abs_metrics[4]), float(abs_metrics[5]),
                        float(abs_metrics[6]), float(abs_metrics[7]), float(abs_metrics[8]),
                    ))

    except Exception as exc:
        print(f"块 {chunk_id} 错误: {exc}")
        return chunk_id, np.array([], dtype=RESULT_DTYPE)

    if results:
        return chunk_id, np.array(results, dtype=RESULT_DTYPE)
    return chunk_id, np.array([], dtype=RESULT_DTYPE)


def save_chunk_to_disk(chunk_id, result_arr):
    if len(result_arr) > 0:
        temp_file = os.path.join(TEMP_DIR, f"chunk_{chunk_id:04d}.npy")
        np.save(temp_file, result_arr)
        return len(result_arr)
    return 0


def save_to_netcdf(final_results, out_file):
    with nc.Dataset(out_file, 'w') as ds:
        ds.createDimension('event', len(final_results))

        float_fields = {
            'lat', 'lon', 'reco_min', 'reco_mean', 'reco_trend', 'amp_max', 't_recover', 'recovery_rate',
            'reco_baseline_abs', 'reco_min_abs', 'reco_max_abs', 'reco_mean_abs', 'reco_trend_abs',
            'reco_drop_abs', 'reco_rise_abs', 'reco_change_to_peak_abs', 'reco_recovery_rate_abs',
        }
        int16_fields = {'event_id', 'onset_year', 'onset_doy', 't_min', 't_response', 't_impact'}

        for field in RESULT_FIELDS:
            if field in float_fields:
                var = ds.createVariable(field, 'f4', ('event',), fill_value=np.nan)
            elif field in int16_fields:
                var = ds.createVariable(field, 'i2', ('event',))
            elif field == 'response_detected':
                var = ds.createVariable(field, 'i1', ('event',))
            else:
                raise ValueError(f"未处理字段类型: {field}")
            var[:] = final_results[field]

        ds.title = 'RECO Response to SMrz Flash Drought - Global (v11, relative + absolute metrics)'
        ds.history = f'Created: {datetime.now()}'
        ds.source_reco = MERGED_GPP_FILE
        ds.source_events = DROUGHT_EVENTS_FILE
        ds.window_before = WINDOW_BEFORE
        ds.window_after = WINDOW_AFTER
        ds.description = (
            'Relative drought response is detected from RECO z-score anomalies. '
            'Absolute RECO metrics are computed from the raw RECO series over the same event window.'
        )


def main():
    print('=' * 70)
    print('根系土壤湿度 (SMrz) 骤旱对 RECO 影响分析 - v11 全球版（相对值 + 绝对值）')
    print('=' * 70)
    print('数据源:')
    print(f'  RECO: {MERGED_GPP_FILE}')
    print(f'  SMrz事件: {DROUGHT_EVENTS_FILE}')
    print(f'  观测窗口: 前{WINDOW_BEFORE}天 + 后{WINDOW_AFTER}天')
    print('')

    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)

    start_time = datetime.now()
    with nc.Dataset(DROUGHT_EVENTS_FILE, 'r') as ds:
        ec_all = ds.variables['event_count'][:]
        lat_has_events = np.any(ec_all > 0, axis=1)
        valid_lat_indices = np.where(lat_has_events)[0]
        if len(valid_lat_indices) == 0:
            print('无有效事件')
            return

        lat_start_idx = valid_lat_indices[0]
        lat_end_idx = valid_lat_indices[-1] + 1
        total_events = int(np.sum(ec_all))

    print(f'有效纬度范围: [{lat_start_idx}, {lat_end_idx}) ({lat_end_idx - lat_start_idx}行)')
    print(f'总事件数: {total_events}')

    chunks = []
    chunk_id = 0
    for chunk_start in range(lat_start_idx, lat_end_idx, LAT_CHUNK_SIZE):
        chunk_end = min(chunk_start + LAT_CHUNK_SIZE, lat_end_idx)
        chunks.append((chunk_id, chunk_start, chunk_end))
        chunk_id += 1

    print(f'任务块数: {len(chunks)}')
    print(f'开始时间: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')

    total_saved = 0
    completed = 0
    with Pool(N_WORKERS, initializer=worker_init) as pool:
        try:
            for cid, result_arr in tqdm(pool.imap_unordered(process_chunk, chunks), total=len(chunks), desc='处理进度'):
                total_saved += save_chunk_to_disk(cid, result_arr)
                completed += 1
        except KeyboardInterrupt:
            print('\n用户中断，正在清理...')
            pool.terminate()
            pool.join()
            return
        except Exception as exc:
            print(f'\n处理出错: {exc}')
            pool.terminate()
            pool.join()
            return

    mid_time = datetime.now()
    print(f'\n已完成 {completed}/{len(chunks)} 个 chunk')
    print(f'处理完成，已保存 {total_saved} 个事件到临时文件')
    print(f'处理耗时: {(mid_time - start_time).total_seconds() / 60:.1f} 分钟')

    print('\n合并临时文件...')
    temp_files = sorted(f for f in os.listdir(TEMP_DIR) if f.endswith('.npy'))
    all_results = []
    for tf in tqdm(temp_files, desc='合并'):
        arr = np.load(os.path.join(TEMP_DIR, tf))
        all_results.append(arr)

    final_results = np.concatenate(all_results) if all_results else np.array([], dtype=RESULT_DTYPE)
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print(f'\n总耗时: {elapsed / 60:.1f} 分钟 ({elapsed / 3600:.2f} 小时)')
    print(f'事件结果数: {len(final_results)}')
    print(f'事件保留率: {len(final_results) / total_events * 100:.1f}%')

    n_with_response = np.sum(final_results['response_detected'] == 1)
    print(f'明显响应事件: {n_with_response} ({n_with_response / len(final_results) * 100:.1f}%)')

    out_file = os.path.join(OUTPUT_DIR, 'reco_response_events_global_v11_with_abs.nc')
    print('\n保存最终结果...')
    save_to_netcdf(final_results, out_file)
    print(f'输出: {out_file}')
    print(f'文件大小: {os.path.getsize(out_file) / 1024 / 1024:.1f} MB')

    print('清理临时文件...')
    shutil.rmtree(TEMP_DIR)
    print('\n✅ SMrz 全球分析完成！')


if __name__ == '__main__':
    main()