"""
骤旱GPP响应的季节性分析（全球版 - 南北半球分别处理）
串行版本 - 优化内存使用和计算效率
"""
import numpy as np
import pandas as pd
import netCDF4 as nc
from osgeo import gdal, osr
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

# 配置
NC_FILE = '/home/xulc/flash_drought/process/GPP-draught-analysis/results/gpp_response_events_global_v10.nc'
OUTPUT_DIR = '/home/xulc/flash_drought/process/GPP-draught-analysis/results/seasonal_analysis'
TIF_DIR = os.path.join(OUTPUT_DIR, 'tif')
FIGURE_DIR = os.path.join(OUTPUT_DIR, 'figures')

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TIF_DIR, exist_ok=True)
os.makedirs(FIGURE_DIR, exist_ok=True)

# 季节定义（按实际物候季节，非日历月份）
SEASONS_NORTH = {
    'Spring': {'months': [3, 4, 5], 'name_zh': '春季'},
    'Summer': {'months': [6, 7, 8], 'name_zh': '夏季'},
    'Autumn': {'months': [9, 10, 11], 'name_zh': '秋季'},
    'Winter': {'months': [12, 1, 2], 'name_zh': '冬季'}
}

# 南半球季节定义（月份相同但季节相反）
SEASONS_SOUTH = {
    'Autumn': {'months': [3, 4, 5], 'name_zh': '秋季'},
    'Winter': {'months': [6, 7, 8], 'name_zh': '冬季'},
    'Spring': {'months': [9, 10, 11], 'name_zh': '春季'},
    'Summer': {'months': [12, 1, 2], 'name_zh': '夏季'}
}


def doy_to_month(doy, year):
    """将DOY转换为月份（考虑闰年）"""
    date = datetime(year, 1, 1) + timedelta(days=int(doy) - 1)
    return date.month


def get_season_from_month(month, hemisphere):
    """根据月份和半球判断季节"""
    seasons = SEASONS_NORTH if hemisphere == 'north' else SEASONS_SOUTH
    for season, info in seasons.items():
        if month in info['months']:
            return season
    return None


def calculate_drought_season_vectorized(onset_years, onset_doys, durations, lats):
    """
    向量化计算骤旱的主导季节（批量处理）
    
    参数:
        onset_years: 骤旱开始年份数组
        onset_doys: 骤旱开始的日序数组
        durations: 骤旱持续天数数组
        lats: 纬度数组
    
    返回:
        季节名称数组
    """
    n = len(onset_years)
    seasons = np.empty(n, dtype=object)
    
    # 使用tqdm显示进度
    for i in tqdm(range(n), desc="计算季节", unit="事件"):
        onset_year = int(onset_years[i])
        onset_doy = int(onset_doys[i])
        duration = durations[i]
        lat = lats[i]
        
        # 判断南北半球
        hemisphere = 'north' if lat >= 0 else 'south'
        seasons_dict = SEASONS_NORTH if hemisphere == 'north' else SEASONS_SOUTH
        
        if duration <= 0 or np.isnan(duration):
            # 如果持续时间无效，只根据onset判断
            month = doy_to_month(onset_doy, onset_year)
            seasons[i] = get_season_from_month(month, hemisphere)
            continue
        
        # 计算骤旱在各季节的天数
        season_days = {season: 0 for season in seasons_dict.keys()}
        
        for day in range(int(duration)):
            current_doy = onset_doy + day
            current_year = onset_year
            
            # 处理跨年情况
            is_leap = (onset_year % 4 == 0 and (onset_year % 100 != 0 or onset_year % 400 == 0))
            days_in_year = 366 if is_leap else 365
            
            if current_doy > days_in_year:
                current_doy -= days_in_year
                current_year += 1
            
            month = doy_to_month(current_doy, current_year)
            season = get_season_from_month(month, hemisphere)
            if season:
                season_days[season] += 1
        
        # 返回天数最多的季节
        if sum(season_days.values()) == 0:
            month = doy_to_month(onset_doy, onset_year)
            seasons[i] = get_season_from_month(month, hemisphere)
        else:
            seasons[i] = max(season_days, key=season_days.get)
    
    return seasons


def read_and_classify_events():
    """读取NC文件并按季节分类"""
    print("=" * 80)
    print("正在读取NC文件...")
    print("=" * 80)
    
    ds = nc.Dataset(NC_FILE, 'r')
    
    # 读取所有数据
    data = {
        'lat': ds.variables['lat'][:].data,
        'lon': ds.variables['lon'][:].data,
        'event_id': ds.variables['event_id'][:].data,
        'onset_year': ds.variables['onset_year'][:].data,
        'onset_doy': ds.variables['onset_doy'][:].data,
        'response_detected': ds.variables['response_detected'][:].data,
        't_response': ds.variables['t_response'][:].data,
        't_min': ds.variables['t_min'][:].data,
        't_impact': ds.variables['t_impact'][:].data,
        't_recover': ds.variables['t_recover'][:].data,
        'recovery_rate': ds.variables['recovery_rate'][:].data,
        'gpp_min': ds.variables['gpp_min'][:].data,
    }
    
    ds.close()
    
    print(f"总事件数: {len(data['lat'])}")
    
    # 只分析有效响应的事件
    valid_mask = data['response_detected'] == 1
    print(f"有效事件数: {np.sum(valid_mask)} ({100*np.sum(valid_mask)/len(valid_mask):.2f}%)")
    
    # 创建DataFrame
    df = pd.DataFrame({key: data[key][valid_mask] for key in data.keys()})
    
    # 计算骤旱持续时间（从onset到最低点）
    df['duration'] = df['t_min'].copy()
    
    # 计算每个事件的主导季节（串行处理，带进度条）
    print("\n正在计算事件的季节属性（考虑南北半球差异）...")
    print(f"串行处理 {len(df)} 个事件")
    
    df['season'] = calculate_drought_season_vectorized(
        df['onset_year'].values,
        df['onset_doy'].values,
        df['duration'].values,
        df['lat'].values
    )
    
    # 添加半球信息
    df['hemisphere'] = df['lat'].apply(lambda x: 'North' if x >= 0 else 'South')
    
    print("\n【总体季节事件分布】")
    season_counts = df['season'].value_counts()
    for season in ['Spring', 'Summer', 'Autumn', 'Winter']:
        count = season_counts.get(season, 0)
        pct = 100 * count / len(df)
        print(f"  {season:<8s}: {count:8d} 事件 ({pct:5.2f}%)")
    
    print("\n【按半球分季节统计】")
    for hemi in ['North', 'South']:
        hemi_df = df[df['hemisphere'] == hemi]
        print(f"\n{hemi} Hemisphere ({len(hemi_df)} 事件):")
        hemi_counts = hemi_df['season'].value_counts()
        for season in ['Spring', 'Summer', 'Autumn', 'Winter']:
            count = hemi_counts.get(season, 0)
            pct = 100 * count / len(hemi_df) if len(hemi_df) > 0 else 0
            # 显示对应的物候季节名称
            season_zh = SEASONS_NORTH[season]['name_zh'] if hemi == 'North' else SEASONS_SOUTH[season]['name_zh']
            print(f"  {season:<8s} ({season_zh}): {count:7d} ({pct:5.2f}%)")
    
    return df


def analyze_seasonal_response(df):
    """分析各季节的响应特征"""
    print("\n" + "=" * 80)
    print("各季节响应特征统计")
    print("=" * 80)
    
    results = {}
    
    for season in ['Spring', 'Summer', 'Autumn', 'Winter']:
        season_data = df[df['season'] == season]
        
        if len(season_data) == 0:
            continue
        
        # 计算统计指标
        stats = {
            'event_count': len(season_data),
            't_response_mean': season_data['t_response'].mean(),
            't_response_std': season_data['t_response'].std(),
            't_response_median': season_data['t_response'].median(),
            't_impact_mean': season_data['t_impact'].mean(),
            't_min_mean': season_data['t_min'].mean(),
            't_recover_mean': season_data['t_recover'].dropna().mean(),
            'recovery_rate': 100 * season_data['t_recover'].notna().sum() / len(season_data),
            'gpp_min_mean': season_data['gpp_min'].mean(),
        }
        
        results[season] = stats
        
        print(f"\n【{SEASONS_NORTH[season]['name_zh']} ({season})】")
        print(f"  事件数: {stats['event_count']}")
        print(f"  响应时间: {stats['t_response_mean']:.1f} ± {stats['t_response_std']:.1f} 天 (中位数: {stats['t_response_median']:.1f})")
        print(f"  影响期: {stats['t_impact_mean']:.1f} 天")
        print(f"  最低点时间: {stats['t_min_mean']:.1f} 天")
        print(f"  恢复时间: {stats['t_recover_mean']:.1f} 天")
        print(f"  恢复率: {stats['recovery_rate']:.1f}%")
        print(f"  GPP最低值: {stats['gpp_min_mean']:.2f} σ")
    
    return results


def create_seasonal_spatial_maps(df):
    """创建季节性空间分布TIF文件"""
    print("\n" + "=" * 80)
    print("生成季节性空间分布TIF文件")
    print("=" * 80)
    
    resolution = 0.1
    lat_min, lat_max = -56, 83
    lon_min, lon_max = -180, 180
    n_rows = int((lat_max - lat_min) / resolution)
    n_cols = int((lon_max - lon_min) / resolution)
    
    # 为每个季节创建TIF
    for season in ['Spring', 'Summer', 'Autumn', 'Winter']:
        print(f"\n处理 {SEASONS_NORTH[season]['name_zh']} ({season})...")
        
        season_data = df[df['season'] == season]
        
        if len(season_data) == 0:
            print(f"  跳过（无数据）")
            continue
        
        # 按像元聚合
        pixel_stats = season_data.groupby(['lat', 'lon']).agg({
            't_response': 'mean',
            't_impact': 'mean',
            't_min': 'mean',
            't_recover': 'mean',
            'gpp_min': 'mean',
            'event_id': 'count'  # 事件数
        }).reset_index()
        
        pixel_stats.rename(columns={'event_id': 'event_count'}, inplace=True)
        
        # 创建多个指标的TIF
        metrics = {
            't_response': '响应时间',
            't_impact': '影响期',
            't_min': '最低点时间',
            't_recover': '恢复时间',
            'gpp_min': 'GPP最低值',
            'event_count': '事件数'
        }
        
        for metric, desc in metrics.items():
            # 创建空白栅格
            raster = np.full((n_rows, n_cols), np.nan, dtype=np.float32)
            
            # 填充数据
            lats = pixel_stats['lat'].values
            lons = pixel_stats['lon'].values
            values = pixel_stats[metric].values
            
            rows = ((lat_max - lats) / resolution).astype(int)
            cols = ((lons - lon_min) / resolution).astype(int)
            
            valid_mask = (
                (rows >= 0) & (rows < n_rows) & 
                (cols >= 0) & (cols < n_cols) & 
                ~np.isnan(values)
            )
            
            raster[rows[valid_mask], cols[valid_mask]] = values[valid_mask]
            
            # 保存TIF
            output_file = os.path.join(TIF_DIR, f'{season}_{metric}.tif')
            save_geotiff(raster, output_file, lon_min, lat_max, resolution, 
                        f'{season} {desc}')
            
            valid_pixels = np.sum(~np.isnan(raster))
            print(f"  {metric}: {valid_pixels} 有效像元")


def save_geotiff(raster, output_file, lon_min, lat_max, resolution, description):
    """保存GeoTIFF文件"""
    driver = gdal.GetDriverByName('GTiff')
    n_rows, n_cols = raster.shape
    
    out_ds = driver.Create(
        output_file,
        n_cols,
        n_rows,
        1,
        gdal.GDT_Float32,
        options=['COMPRESS=LZW']
    )
    
    geotransform = [lon_min, resolution, 0, lat_max, 0, -resolution]
    out_ds.SetGeoTransform(geotransform)
    
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    out_ds.SetProjection(srs.ExportToWkt())
    
    band = out_ds.GetRasterBand(1)
    band.WriteArray(raster)
    band.SetNoDataValue(np.nan)
    band.SetDescription(description)
    band.ComputeStatistics(False)
    
    band.FlushCache()
    out_ds.FlushCache()
    band = None
    out_ds = None


def create_comparison_figures(df, stats):
    """创建对比图表"""
    print("\n" + "=" * 80)
    print("生成对比图表")
    print("=" * 80)
    
    # 使用默认字体，避免中文乱码
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False
    
    seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
    season_names = seasons  # 直接使用英文季节名
    
    # 1. 事件数对比
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Seasonal Flash Drought GPP Response Analysis', fontsize=16, fontweight='bold')
    
    # 1.1 事件数
    ax = axes[0, 0]
    event_counts = [stats[s]['event_count'] for s in seasons]
    colors = ['#2ecc71', '#e74c3c', '#f39c12', '#3498db']
    bars = ax.bar(season_names, event_counts, color=colors, alpha=0.7, edgecolor='black')
    ax.set_ylabel('Event Count', fontsize=12)
    ax.set_title('(a) Flash Drought Events by Season', fontsize=12, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=10)
    
    # 1.2 响应时间
    ax = axes[0, 1]
    t_response = [stats[s]['t_response_mean'] for s in seasons]
    t_response_std = [stats[s]['t_response_std'] for s in seasons]
    bars = ax.bar(season_names, t_response, yerr=t_response_std, 
                  color=colors, alpha=0.7, edgecolor='black', capsize=5)
    ax.set_ylabel('Response Time (days)', fontsize=12)
    ax.set_title('(b) Mean Response Time by Season', fontsize=12, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    for i, (bar, val) in enumerate(zip(bars, t_response)):
        ax.text(bar.get_x() + bar.get_width()/2., val,
                f'{val:.1f}',
                ha='center', va='bottom', fontsize=10)
    
    # 1.3 影响期
    ax = axes[1, 0]
    t_impact = [stats[s]['t_impact_mean'] for s in seasons]
    bars = ax.bar(season_names, t_impact, color=colors, alpha=0.7, edgecolor='black')
    ax.set_ylabel('Impact Duration (days)', fontsize=12)
    ax.set_title('(c) Mean Impact Duration by Season', fontsize=12, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    
    # 1.4 恢复率
    ax = axes[1, 1]
    recovery_rates = [stats[s]['recovery_rate'] for s in seasons]
    bars = ax.bar(season_names, recovery_rates, color=colors, alpha=0.7, edgecolor='black')
    ax.set_ylabel('Recovery Rate (%)', fontsize=12)
    ax.set_title('(d) Recovery Rate by Season', fontsize=12, fontweight='bold')
    ax.set_ylim([0, 100])
    ax.grid(axis='y', alpha=0.3)
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%',
                ha='center', va='bottom', fontsize=10)
    
    plt.tight_layout()
    output_file = os.path.join(FIGURE_DIR, 'seasonal_comparison.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"保存: {output_file}")
    plt.close()
    
    # 2. 箱线图
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle('Seasonal Response Metric Distributions', fontsize=16, fontweight='bold')
    
    # 2.1 响应时间箱线图
    ax = axes[0]
    data_to_plot = [df[df['season'] == s]['t_response'].values for s in seasons]
    bp = ax.boxplot(data_to_plot, labels=season_names, patch_artist=True)
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_ylabel('Response Time (days)', fontsize=12)
    ax.set_title('(a) Response Time Distribution', fontsize=12, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    
    # 2.2 影响期箱线图
    ax = axes[1]
    data_to_plot = [df[df['season'] == s]['t_impact'].values for s in seasons]
    bp = ax.boxplot(data_to_plot, labels=season_names, patch_artist=True)
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_ylabel('Impact Duration (days)', fontsize=12)
    ax.set_title('(b) Impact Duration Distribution', fontsize=12, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    
    # 2.3 恢复时间箱线图
    ax = axes[2]
    data_to_plot = [df[df['season'] == s]['t_recover'].dropna().values for s in seasons]
    bp = ax.boxplot(data_to_plot, labels=season_names, patch_artist=True)
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_ylabel('Recovery Time (days)', fontsize=12)
    ax.set_title('(c) Recovery Time Distribution', fontsize=12, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    output_file = os.path.join(FIGURE_DIR, 'seasonal_distribution.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"保存: {output_file}")
    plt.close()


def main():
    import time
    start_time = time.time()
    
    print("\n" + "=" * 80)
    print("骤旱GPP响应的季节性分析 (串行版本)")
    print("=" * 80)
    
    # 1. 读取数据并分类
    df = read_and_classify_events()
    
    # 2. 统计分析
    stats = analyze_seasonal_response(df)
    
    # 3. 创建空间分布图
    create_seasonal_spatial_maps(df)
    
    # 4. 创建对比图表
    create_comparison_figures(df, stats)
    
    # 5. 保存统计结果
    print("\n" + "=" * 80)
    print("保存统计结果")
    print("=" * 80)
    
    stats_df = pd.DataFrame(stats).T
    stats_file = os.path.join(OUTPUT_DIR, 'seasonal_statistics.csv')
    stats_df.to_csv(stats_file)
    print(f"统计结果已保存: {stats_file}")
    
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 80)
    print("✅ 季节性分析完成!")
    print("=" * 80)
    print(f"总运行时间: {elapsed_time/60:.2f} 分钟")
    print(f"\n输出目录: {OUTPUT_DIR}")
    print(f"  - TIF文件: {TIF_DIR}")
    print(f"  - 图表: {FIGURE_DIR}")
    print(f"  - 统计表: {stats_file}")


if __name__ == '__main__':
    main()
