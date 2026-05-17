#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析有GPP响应和无响应骤旱事件的季节性差异
对比发生时间（月份/季节）和持续时间的差异
"""

import numpy as np
import pandas as pd
import netCDF4 as nc
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import os
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# 配置
GPP_RESPONSE_FILE = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMrz_GPP_results/gpp_response_events_global_v10.nc'
DROUGHT_DETAILS_FILE = '/home/xulc/flash_drought/gleam/clip_result/SMrz/flash_drought_events_details_v2.nc'
OUTPUT_DIR = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/analysis_result/seasonal_response_analysis'

# 季节定义（北半球为主）
SEASONS = {
    'Spring': [3, 4, 5],      # 春季：3-5月
    'Summer': [6, 7, 8],      # 夏季：6-8月
    'Autumn': [9, 10, 11],    # 秋季：9-11月
    'Winter': [12, 1, 2]      # 冬季：12-2月
}

MONTH_NAMES = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
    7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
}

def create_output_dir():
    """创建输出目录"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, 'figures'), exist_ok=True)
    print(f"输出目录: {OUTPUT_DIR}\n")

def doy_to_month(doy, year):
    """将day of year转换为月份"""
    # 处理闰年
    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    
    if is_leap:
        days_in_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    else:
        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    cumsum = np.cumsum([0] + days_in_month)
    
    for month in range(1, 13):
        if cumsum[month-1] < doy <= cumsum[month]:
            return month
    
    return 12  # 默认返回12月

def get_season(month):
    """根据月份获取季节"""
    for season, months in SEASONS.items():
        if month in months:
            return season
    return 'Winter'  # 默认

def load_and_process_data():
    """加载GPP响应数据和骤旱详情"""
    print("="*80)
    print("加载和处理数据")
    print("="*80 + "\n")
    
    # 读取GPP响应数据
    print("读取GPP响应数据...")
    with nc.Dataset(GPP_RESPONSE_FILE, 'r') as ds:
        lats = ds.variables['lat'][:]
        lons = ds.variables['lon'][:]
        event_ids = ds.variables['event_id'][:]
        onset_years = ds.variables['onset_year'][:]
        onset_doys = ds.variables['onset_doy'][:]
        response_detected = ds.variables['response_detected'][:]
    
    print(f"总事件数: {len(lats):,}")
    print(f"有响应: {np.sum(response_detected == 1):,}")
    print(f"无响应: {np.sum(response_detected == 0):,}\n")
    
    # 读取骤旱详情（持续时间）
    print("读取骤旱持续时间...")
    # 使用之前分析的匹配结果
    detail_lats_grid = None
    detail_lons_grid = None
    
    with nc.Dataset(DROUGHT_DETAILS_FILE, 'r') as ds:
        detail_lats = ds.variables['lat'][:]
        detail_lons = ds.variables['lon'][:]
        drought_days = ds.variables['drought_days']
        fill_value_days = drought_days._FillValue
        
        # 向量化获取持续时间
        print("匹配持续时间数据...")
        lats_rounded = np.round(lats * 10) / 10
        lons_rounded = np.round(lons * 10) / 10
        
        lat_indices = ((89.95 - lats_rounded) / 0.1).astype(int)
        lon_indices = ((lons_rounded + 179.95) / 0.1).astype(int)
        
        valid_mask = (~np.isnan(lats) & ~np.isnan(lons) &
                      (lat_indices >= 0) & (lat_indices < len(detail_lats)) &
                      (lon_indices >= 0) & (lon_indices < len(detail_lons)) &
                      (event_ids >= 0) & (event_ids < drought_days.shape[0]))
        
        duration = np.full(len(lats), np.nan, dtype=np.float32)
        
        print(f"有效事件: {np.sum(valid_mask):,}")
        
        # 批量读取
        batch_size = 1000000
        n_valid = np.sum(valid_mask)
        valid_indices = np.where(valid_mask)[0]
        
        for i in range(0, n_valid, batch_size):
            end_i = min(i + batch_size, n_valid)
            batch_indices = valid_indices[i:end_i]
            
            e_idx = event_ids[batch_indices].astype(int)
            li = lat_indices[batch_indices]
            lo = lon_indices[batch_indices]
            
            for j, idx in enumerate(batch_indices):
                val = drought_days[e_idx[j], li[j], lo[j]]
                if val != fill_value_days and val > 0:
                    duration[idx] = val
            
            if (i // batch_size) % 5 == 0:
                print(f"  进度: {i:,}/{n_valid:,}")
    
    print("\n转换日期信息...")
    # 转换DOY到月份
    months = np.array([doy_to_month(int(doy), int(year)) 
                      if not (np.isnan(doy) or doy == 0)
                      else np.nan
                      for doy, year in zip(onset_doys, onset_years)])
    
    # 获取季节
    seasons = np.array([get_season(int(m)) if not np.isnan(m) else 'Unknown'
                       for m in months])
    
    print("创建DataFrame...")
    # 创建DataFrame
    df = pd.DataFrame({
        'lat': lats,
        'lon': lons,
        'event_id': event_ids,
        'onset_year': onset_years,
        'onset_doy': onset_doys,
        'month': months,
        'season': seasons,
        'response_detected': response_detected,
        'duration': duration
    })
    
    # 过滤有效数据
    df = df[~df['month'].isna() & ~df['duration'].isna()].copy()
    
    print(f"\n有效数据: {len(df):,} 个事件")
    print(f"  有响应: {len(df[df['response_detected']==1]):,}")
    print(f"  无响应: {len(df[df['response_detected']==0]):,}\n")
    
    return df

def analyze_monthly_distribution(df):
    """分析月份分布差异"""
    print("="*80)
    print("分析月份分布")
    print("="*80 + "\n")
    
    # 分别统计
    resp_monthly = df[df['response_detected']==1]['month'].value_counts().sort_index()
    non_resp_monthly = df[df['response_detected']==0]['month'].value_counts().sort_index()
    
    # 转换为百分比
    resp_monthly_pct = resp_monthly / resp_monthly.sum() * 100
    non_resp_monthly_pct = non_resp_monthly / non_resp_monthly.sum() * 100
    
    # 创建对比表
    monthly_stats = pd.DataFrame({
        'Month': [MONTH_NAMES[m] for m in range(1, 13)],
        'Response_Count': [resp_monthly.get(m, 0) for m in range(1, 13)],
        'Response_Pct': [resp_monthly_pct.get(m, 0) for m in range(1, 13)],
        'NonResponse_Count': [non_resp_monthly.get(m, 0) for m in range(1, 13)],
        'NonResponse_Pct': [non_resp_monthly_pct.get(m, 0) for m in range(1, 13)]
    })
    
    monthly_stats['Difference_Pct'] = monthly_stats['Response_Pct'] - monthly_stats['NonResponse_Pct']
    
    print("月份分布统计:")
    print(monthly_stats.to_string(index=False))
    
    return monthly_stats

def analyze_seasonal_distribution(df):
    """分析季节分布差异"""
    print("\n" + "="*80)
    print("分析季节分布")
    print("="*80 + "\n")
    
    # 季节统计
    resp_seasonal = df[df['response_detected']==1]['season'].value_counts()
    non_resp_seasonal = df[df['response_detected']==0]['season'].value_counts()
    
    resp_seasonal_pct = resp_seasonal / resp_seasonal.sum() * 100
    non_resp_seasonal_pct = non_resp_seasonal / non_resp_seasonal.sum() * 100
    
    seasonal_stats = pd.DataFrame({
        'Season': ['Spring', 'Summer', 'Autumn', 'Winter'],
        'Response_Count': [resp_seasonal.get(s, 0) for s in ['Spring', 'Summer', 'Autumn', 'Winter']],
        'Response_Pct': [resp_seasonal_pct.get(s, 0) for s in ['Spring', 'Summer', 'Autumn', 'Winter']],
        'NonResponse_Count': [non_resp_seasonal.get(s, 0) for s in ['Spring', 'Summer', 'Autumn', 'Winter']],
        'NonResponse_Pct': [non_resp_seasonal_pct.get(s, 0) for s in ['Spring', 'Summer', 'Autumn', 'Winter']]
    })
    
    seasonal_stats['Difference_Pct'] = seasonal_stats['Response_Pct'] - seasonal_stats['NonResponse_Pct']
    
    print("季节分布统计:")
    print(seasonal_stats.to_string(index=False))
    
    return seasonal_stats

def analyze_duration_by_season(df):
    """分析不同季节的持续时间差异"""
    print("\n" + "="*80)
    print("分析季节持续时间差异")
    print("="*80 + "\n")
    
    season_duration_stats = []
    
    for season in ['Spring', 'Summer', 'Autumn', 'Winter']:
        resp_data = df[(df['response_detected']==1) & (df['season']==season)]['duration']
        non_resp_data = df[(df['response_detected']==0) & (df['season']==season)]['duration']
        
        if len(resp_data) > 0 and len(non_resp_data) > 0:
            stats = {
                'Season': season,
                'Response_Mean': np.mean(resp_data),
                'Response_Std': np.std(resp_data),
                'Response_Median': np.median(resp_data),
                'NonResponse_Mean': np.mean(non_resp_data),
                'NonResponse_Std': np.std(non_resp_data),
                'NonResponse_Median': np.median(non_resp_data),
                'Difference': np.mean(resp_data) - np.mean(non_resp_data),
                'Difference_Pct': (np.mean(resp_data) - np.mean(non_resp_data)) / np.mean(non_resp_data) * 100
            }
            
            season_duration_stats.append(stats)
            
            print(f"{season}:")
            print(f"  有响应: {stats['Response_Mean']:.2f} ± {stats['Response_Std']:.2f} 天")
            print(f"  无响应: {stats['NonResponse_Mean']:.2f} ± {stats['NonResponse_Std']:.2f} 天")
            print(f"  差异: {stats['Difference']:+.2f} 天 ({stats['Difference_Pct']:+.1f}%)\n")
    
    return pd.DataFrame(season_duration_stats)

def analyze_duration_by_month(df):
    """分析不同月份的持续时间差异"""
    print("="*80)
    print("分析月份持续时间差异")
    print("="*80 + "\n")
    
    month_duration_stats = []
    
    for month in range(1, 13):
        resp_data = df[(df['response_detected']==1) & (df['month']==month)]['duration']
        non_resp_data = df[(df['response_detected']==0) & (df['month']==month)]['duration']
        
        if len(resp_data) > 0 and len(non_resp_data) > 0:
            stats = {
                'Month': MONTH_NAMES[month],
                'Month_Num': month,
                'Response_Mean': np.mean(resp_data),
                'Response_Std': np.std(resp_data),
                'NonResponse_Mean': np.mean(non_resp_data),
                'NonResponse_Std': np.std(non_resp_data),
                'Difference': np.mean(resp_data) - np.mean(non_resp_data),
                'Difference_Pct': (np.mean(resp_data) - np.mean(non_resp_data)) / np.mean(non_resp_data) * 100
            }
            
            month_duration_stats.append(stats)
    
    month_df = pd.DataFrame(month_duration_stats)
    print(month_df.to_string(index=False))
    
    return month_df

def create_visualizations(df, monthly_stats, seasonal_stats, season_duration, month_duration):
    """创建可视化图表"""
    print("\n" + "="*80)
    print("创建可视化图表")
    print("="*80 + "\n")
    
    fig_dir = os.path.join(OUTPUT_DIR, 'figures')
    
    # 1. 月份分布对比
    fig, ax = plt.subplots(figsize=(14, 6))
    
    x = np.arange(12)
    width = 0.35
    
    ax.bar(x - width/2, monthly_stats['Response_Pct'], width, 
           label='With GPP Response', alpha=0.8, color='#2ecc71')
    ax.bar(x + width/2, monthly_stats['NonResponse_Pct'], width,
           label='Without GPP Response', alpha=0.8, color='#e74c3c')
    
    ax.set_xlabel('Month', fontsize=12)
    ax.set_ylabel('Percentage (%)', fontsize=12)
    ax.set_title('Monthly Distribution of Drought Events with/without GPP Response', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(monthly_stats['Month'])
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(fig_dir, 'monthly_distribution.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ 已保存: monthly_distribution.png")
    
    # 2. 季节分布对比
    fig, ax = plt.subplots(figsize=(10, 6))
    
    x = np.arange(4)
    width = 0.35
    
    ax.bar(x - width/2, seasonal_stats['Response_Pct'], width,
           label='With GPP Response', alpha=0.8, color='#3498db')
    ax.bar(x + width/2, seasonal_stats['NonResponse_Pct'], width,
           label='Without GPP Response', alpha=0.8, color='#e67e22')
    
    ax.set_xlabel('Season', fontsize=12)
    ax.set_ylabel('Percentage (%)', fontsize=12)
    ax.set_title('Seasonal Distribution of Drought Events with/without GPP Response', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(seasonal_stats['Season'])
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(fig_dir, 'seasonal_distribution.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ 已保存: seasonal_distribution.png")
    
    # 3. 月份持续时间对比
    fig, ax = plt.subplots(figsize=(14, 6))
    
    x = np.arange(len(month_duration))
    width = 0.35
    
    ax.bar(x - width/2, month_duration['Response_Mean'], width,
           label='With GPP Response', alpha=0.8, color='#9b59b6', 
           yerr=month_duration['Response_Std'], capsize=3)
    ax.bar(x + width/2, month_duration['NonResponse_Mean'], width,
           label='Without GPP Response', alpha=0.8, color='#f39c12',
           yerr=month_duration['NonResponse_Std'], capsize=3)
    
    ax.set_xlabel('Month', fontsize=12)
    ax.set_ylabel('Duration (days)', fontsize=12)
    ax.set_title('Monthly Average Drought Duration with/without GPP Response', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(month_duration['Month'])
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(fig_dir, 'monthly_duration.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ 已保存: monthly_duration.png")
    
    # 4. 季节持续时间对比
    fig, ax = plt.subplots(figsize=(10, 6))
    
    x = np.arange(len(season_duration))
    width = 0.35
    
    ax.bar(x - width/2, season_duration['Response_Mean'], width,
           label='With GPP Response', alpha=0.8, color='#1abc9c',
           yerr=season_duration['Response_Std'], capsize=5)
    ax.bar(x + width/2, season_duration['NonResponse_Mean'], width,
           label='Without GPP Response', alpha=0.8, color='#e84393',
           yerr=season_duration['NonResponse_Std'], capsize=5)
    
    ax.set_xlabel('Season', fontsize=12)
    ax.set_ylabel('Duration (days)', fontsize=12)
    ax.set_title('Seasonal Average Drought Duration with/without GPP Response', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(season_duration['Season'])
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(fig_dir, 'seasonal_duration.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ 已保存: seasonal_duration.png")
    
    # 5. 月份差异热图
    fig, ax = plt.subplots(figsize=(14, 4))
    
    diff_data = monthly_stats[['Difference_Pct']].T
    diff_data.columns = monthly_stats['Month']
    
    sns.heatmap(diff_data, annot=True, fmt='.1f', cmap='RdYlGn', center=0,
                cbar_kws={'label': 'Difference (%)'}, ax=ax, linewidths=1)
    
    ax.set_ylabel('')
    ax.set_xlabel('Month', fontsize=12)
    ax.set_title('Monthly Distribution Difference (Response - NonResponse)', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(fig_dir, 'monthly_difference_heatmap.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ 已保存: monthly_difference_heatmap.png")

def create_markdown_report(df, monthly_stats, seasonal_stats, season_duration, month_duration):
    """创建Markdown报告"""
    output_path = os.path.join(OUTPUT_DIR, 'seasonal_response_analysis_report.md')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# 骤旱事件季节性响应差异分析报告\n\n")
        f.write(f"**分析日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        # 数据概览
        f.write("## 1. 数据概览\n\n")
        total_events = len(df)
        resp_events = len(df[df['response_detected']==1])
        non_resp_events = len(df[df['response_detected']==0])
        
        f.write(f"- **总事件数**: {total_events:,}\n")
        f.write(f"- **有GPP响应事件**: {resp_events:,} ({resp_events/total_events*100:.1f}%)\n")
        f.write(f"- **无GPP响应事件**: {non_resp_events:,} ({non_resp_events/total_events*100:.1f}%)\n\n")
        
        # 月份分布
        f.write("---\n\n")
        f.write("## 2. 月份分布差异\n\n")
        f.write("### 2.1 月份分布统计\n\n")
        f.write("| 月份 | 有响应事件数 | 有响应占比(%) | 无响应事件数 | 无响应占比(%) | 差异(%) |\n")
        f.write("|------|-------------|--------------|-------------|--------------|--------|\n")
        
        for _, row in monthly_stats.iterrows():
            f.write(f"| {row['Month']} | {row['Response_Count']:,} | {row['Response_Pct']:.2f} | "
                   f"{row['NonResponse_Count']:,} | {row['NonResponse_Pct']:.2f} | "
                   f"{row['Difference_Pct']:+.2f} |\n")
        
        f.write("\n### 2.2 关键发现\n\n")
        
        # 找出差异最大的月份
        max_diff_idx = monthly_stats['Difference_Pct'].abs().idxmax()
        max_diff_row = monthly_stats.iloc[max_diff_idx]
        
        if max_diff_row['Difference_Pct'] > 0:
            f.write(f"- **{max_diff_row['Month']}月**显示最大差异：有响应事件占比**高出{max_diff_row['Difference_Pct']:.2f}%**\n")
        else:
            f.write(f"- **{max_diff_row['Month']}月**显示最大差异：无响应事件占比**高出{abs(max_diff_row['Difference_Pct']):.2f}%**\n")
        
        # 季节分布
        f.write("\n---\n\n")
        f.write("## 3. 季节分布差异\n\n")
        f.write("### 3.1 季节分布统计\n\n")
        f.write("| 季节 | 有响应事件数 | 有响应占比(%) | 无响应事件数 | 无响应占比(%) | 差异(%) |\n")
        f.write("|------|-------------|--------------|-------------|--------------|--------|\n")
        
        for _, row in seasonal_stats.iterrows():
            f.write(f"| {row['Season']} | {row['Response_Count']:,} | {row['Response_Pct']:.2f} | "
                   f"{row['NonResponse_Count']:,} | {row['NonResponse_Pct']:.2f} | "
                   f"{row['Difference_Pct']:+.2f} |\n")
        
        # 持续时间分析
        f.write("\n---\n\n")
        f.write("## 4. 季节持续时间差异\n\n")
        f.write("| 季节 | 有响应平均(天) | 无响应平均(天) | 差异(天) | 差异(%) |\n")
        f.write("|------|---------------|---------------|---------|--------|\n")
        
        for _, row in season_duration.iterrows():
            f.write(f"| {row['Season']} | {row['Response_Mean']:.2f} ± {row['Response_Std']:.2f} | "
                   f"{row['NonResponse_Mean']:.2f} ± {row['NonResponse_Std']:.2f} | "
                   f"{row['Difference']:+.2f} | {row['Difference_Pct']:+.1f}% |\n")
        
        # 月份持续时间
        f.write("\n---\n\n")
        f.write("## 5. 月份持续时间差异\n\n")
        f.write("| 月份 | 有响应平均(天) | 无响应平均(天) | 差异(天) | 差异(%) |\n")
        f.write("|------|---------------|---------------|---------|--------|\n")
        
        for _, row in month_duration.iterrows():
            f.write(f"| {row['Month']} | {row['Response_Mean']:.2f} ± {row['Response_Std']:.2f} | "
                   f"{row['NonResponse_Mean']:.2f} ± {row['NonResponse_Std']:.2f} | "
                   f"{row['Difference']:+.2f} | {row['Difference_Pct']:+.1f}% |\n")
        
        # 关键结论
        f.write("\n---\n\n")
        f.write("## 6. 关键结论\n\n")
        
        # 季节性特征
        max_season_resp = seasonal_stats.loc[seasonal_stats['Response_Pct'].idxmax()]
        max_season_nonresp = seasonal_stats.loc[seasonal_stats['NonResponse_Pct'].idxmax()]
        
        f.write("### 6.1 发生时间特征\n\n")
        f.write(f"- 有响应事件主要发生在**{max_season_resp['Season']}**（{max_season_resp['Response_Pct']:.1f}%）\n")
        f.write(f"- 无响应事件主要发生在**{max_season_nonresp['Season']}**（{max_season_nonresp['NonResponse_Pct']:.1f}%）\n\n")
        
        # 持续时间特征
        f.write("### 6.2 持续时间特征\n\n")
        
        max_dur_diff = season_duration.loc[season_duration['Difference'].abs().idxmax()]
        if max_dur_diff['Difference'] > 0:
            f.write(f"- **{max_dur_diff['Season']}**季节差异最大：有响应事件平均长{max_dur_diff['Difference']:.2f}天（{max_dur_diff['Difference_Pct']:+.1f}%）\n")
        else:
            f.write(f"- **{max_dur_diff['Season']}**季节差异最大：无响应事件平均长{abs(max_dur_diff['Difference']):.2f}天（{abs(max_dur_diff['Difference_Pct']):.1f}%）\n")
        
        # 图表说明
        f.write("\n---\n\n")
        f.write("## 7. 可视化图表\n\n")
        f.write("所有图表保存在 `figures/` 目录下：\n\n")
        f.write("1. `monthly_distribution.png` - 月份分布对比\n")
        f.write("2. `seasonal_distribution.png` - 季节分布对比\n")
        f.write("3. `monthly_duration.png` - 月份持续时间对比\n")
        f.write("4. `seasonal_duration.png` - 季节持续时间对比\n")
        f.write("5. `monthly_difference_heatmap.png` - 月份差异热图\n\n")
        
        f.write("---\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"\n✓ 报告已保存: {output_path}")

def main():
    print("\n" + "="*80)
    print("骤旱事件季节性响应差异分析")
    print("="*80 + "\n")
    
    # 创建输出目录
    create_output_dir()
    
    # 加载数据
    df = load_and_process_data()
    
    # 月份分布分析
    monthly_stats = analyze_monthly_distribution(df)
    
    # 季节分布分析
    seasonal_stats = analyze_seasonal_distribution(df)
    
    # 季节持续时间分析
    season_duration = analyze_duration_by_season(df)
    
    # 月份持续时间分析
    month_duration = analyze_duration_by_month(df)
    
    # 创建可视化
    create_visualizations(df, monthly_stats, seasonal_stats, season_duration, month_duration)
    
    # 保存结果
    print("\n" + "="*80)
    print("保存统计结果")
    print("="*80 + "\n")
    
    monthly_stats.to_csv(os.path.join(OUTPUT_DIR, 'monthly_statistics.csv'), 
                        index=False, encoding='utf-8-sig')
    print("✓ 已保存: monthly_statistics.csv")
    
    seasonal_stats.to_csv(os.path.join(OUTPUT_DIR, 'seasonal_statistics.csv'),
                         index=False, encoding='utf-8-sig')
    print("✓ 已保存: seasonal_statistics.csv")
    
    season_duration.to_csv(os.path.join(OUTPUT_DIR, 'seasonal_duration_stats.csv'),
                          index=False, encoding='utf-8-sig')
    print("✓ 已保存: seasonal_duration_stats.csv")
    
    month_duration.to_csv(os.path.join(OUTPUT_DIR, 'monthly_duration_stats.csv'),
                         index=False, encoding='utf-8-sig')
    print("✓ 已保存: monthly_duration_stats.csv")
    
    # 创建报告
    create_markdown_report(df, monthly_stats, seasonal_stats, season_duration, month_duration)
    
    print("\n" + "="*80)
    print("分析完成！")
    print("="*80)
    print(f"\n所有结果已保存到: {OUTPUT_DIR}")
    print("\n生成的文件:")
    print("  - 4个统计CSV文件")
    print("  - 5张可视化图表 (PNG)")
    print("  - 1个Markdown分析报告")
    print()

if __name__ == '__main__':
    main()
