#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
骤旱事件季节性响应差异分析 - 多线程优化版本
分析有GPP响应和无响应事件在发生时间（月份/季节）和持续时间上的差异

优化特性:
- 使用ProcessPoolExecutor进行并行计算
- 分批处理事件（1M/batch）避免内存溢出
- 每个进程独立打开NetCDF文件句柄
- 优化DOY到月份的转换
"""

import os
import numpy as np
import pandas as pd
from netCDF4 import Dataset
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

# 配置
GPP_RESPONSE_FILE = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMrz_GPP_results/gpp_response_events_global_v10.nc'
DROUGHT_DETAIL_FILE = '/home/xulc/flash_drought/gleam/clip_result/SMrz/flash_drought_events_details_v2.nc'
OUTPUT_DIR = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/analysis_result/seasonal_response_analysis'

# 季节和月份定义
MONTH_NAMES = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
    7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
}

SEASONS = {
    'Spring': [3, 4, 5],
    'Summer': [6, 7, 8],
    'Autumn': [9, 10, 11],
    'Winter': [12, 1, 2]
}

# 多进程配置
N_WORKERS = 40  # 成功经验：40个进程
BATCH_SIZE = 1000000  # 每批处理100万事件


def create_output_dir():
    """创建输出目录"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, 'figures'), exist_ok=True)


def doy_to_month(doy, year):
    """将DOY转换为月份（向量化友好版本）"""
    if doy <= 0 or doy > 366:
        return np.nan
    
    # 判断闰年
    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    
    # 每月天数
    if is_leap:
        days_in_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    else:
        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    cumsum = 0
    for month_idx, days in enumerate(days_in_month, 1):
        cumsum += days
        if doy <= cumsum:
            return month_idx
    
    return 12  # 安全返回


def get_season(month):
    """根据月份获取季节"""
    if pd.isna(month) or month == 0:
        return 'Unknown'
    
    month = int(month)
    for season, months in SEASONS.items():
        if month in months:
            return season
    return 'Unknown'


def process_batch(batch_idx, start_idx, end_idx, gpp_file, drought_file):
    """
    处理单个批次的事件数据
    
    Parameters:
    -----------
    batch_idx : int
        批次编号
    start_idx, end_idx : int
        数据索引范围
    gpp_file, drought_file : str
        NetCDF文件路径
        
    Returns:
    --------
    dict : 包含处理结果的字典
    """
    # 每个进程独立打开文件
    with Dataset(gpp_file, 'r') as ds_gpp, Dataset(drought_file, 'r') as ds_drought:
        # 读取GPP响应数据
        lats = ds_gpp.variables['lat'][start_idx:end_idx]
        lons = ds_gpp.variables['lon'][start_idx:end_idx]
        event_ids = ds_gpp.variables['event_id'][start_idx:end_idx]
        onset_years = ds_gpp.variables['onset_year'][start_idx:end_idx]
        onset_doys = ds_gpp.variables['onset_doy'][start_idx:end_idx]
        response_detected = ds_gpp.variables['response_detected'][start_idx:end_idx]
        
        # 获取骤旱详情的坐标
        detail_lats = ds_drought.variables['lat'][:]
        detail_lons = ds_drought.variables['lon'][:]
        drought_days = ds_drought.variables['drought_days']
        fill_value = drought_days._FillValue
        
        # 计算索引（向量化）
        lats_rounded = np.round(lats * 10) / 10
        lons_rounded = np.round(lons * 10) / 10
        
        lat_indices = ((89.95 - lats_rounded) / 0.1).astype(int)
        lon_indices = ((lons_rounded + 179.95) / 0.1).astype(int)
        
        # 有效性检查
        valid_mask = (
            ~np.isnan(lats) & ~np.isnan(lons) &
            (lat_indices >= 0) & (lat_indices < len(detail_lats)) &
            (lon_indices >= 0) & (lon_indices < len(detail_lons)) &
            (event_ids >= 0) & (event_ids < drought_days.shape[0])
        )
        
        # 读取持续时间
        duration = np.full(len(lats), np.nan, dtype=np.float32)
        
        valid_indices = np.where(valid_mask)[0]
        for idx in valid_indices:
            e = int(event_ids[idx])
            li = lat_indices[idx]
            lo = lon_indices[idx]
            
            val = drought_days[e, li, lo]
            if val != fill_value and val > 0:
                duration[idx] = val
        
        # 转换DOY到月份（向量化）
        months = np.array([
            doy_to_month(int(doy), int(year)) 
            if not (np.isnan(doy) or doy == 0)
            else np.nan
            for doy, year in zip(onset_doys, onset_years)
        ])
        
        # 转换月份到季节
        seasons = np.array([get_season(m) for m in months])
        
        # 构建结果
        results = {
            'lat': lats,
            'lon': lons,
            'event_id': event_ids,
            'onset_year': onset_years,
            'onset_doy': onset_doys,
            'month': months,
            'season': seasons,
            'response_detected': response_detected,
            'duration': duration,
            'batch_idx': batch_idx
        }
        
        return results


def load_and_process_data_parallel():
    """
    并行加载和处理数据
    
    Returns:
    --------
    pd.DataFrame : 包含所有事件信息的DataFrame
    """
    print("="*80)
    print("加载和处理数据（多线程版本）")
    print("="*80 + "\n")
    
    # 获取数据总量
    with Dataset(GPP_RESPONSE_FILE, 'r') as ds:
        total_events = len(ds.dimensions['event'])
    
    print(f"总事件数: {total_events:,}")
    print(f"批次大小: {BATCH_SIZE:,}")
    print(f"工作进程: {N_WORKERS}")
    
    # 计算批次
    n_batches = (total_events + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"总批次数: {n_batches}\n")
    
    # 准备批次任务
    batch_tasks = []
    for i in range(n_batches):
        start_idx = i * BATCH_SIZE
        end_idx = min((i + 1) * BATCH_SIZE, total_events)
        batch_tasks.append((i, start_idx, end_idx, GPP_RESPONSE_FILE, DROUGHT_DETAIL_FILE))
    
    # 并行处理
    print("开始并行处理...")
    all_results = []
    
    with ProcessPoolExecutor(max_workers=N_WORKERS) as executor:
        # 提交所有任务
        future_to_batch = {
            executor.submit(process_batch, *task): task[0]
            for task in batch_tasks
        }
        
        # 收集结果
        completed = 0
        for future in as_completed(future_to_batch):
            batch_idx = future_to_batch[future]
            try:
                result = future.result()
                all_results.append(result)
                completed += 1
                
                if completed % 5 == 0 or completed == n_batches:
                    print(f"  进度: {completed}/{n_batches} 批次完成 ({completed/n_batches*100:.1f}%)")
                
            except Exception as exc:
                print(f"  批次 {batch_idx} 处理失败: {exc}")
    
    print("\n合并结果...")
    
    # 合并所有批次结果
    df_list = []
    for result in all_results:
        df_batch = pd.DataFrame(result)
        df_list.append(df_batch)
    
    df = pd.concat(df_list, ignore_index=True)
    
    # 过滤有效数据
    print("\n过滤有效数据...")
    df = df[~df['month'].isna() & ~df['duration'].isna()].copy()
    
    print(f"\n有效事件: {len(df):,}")
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
    print("骤旱事件季节性响应差异分析 - 多线程优化版本")
    print("="*80 + "\n")
    
    start_time = datetime.now()
    
    # 创建输出目录
    create_output_dir()
    
    # 并行加载数据
    df = load_and_process_data_parallel()
    
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
    
    # 计算总耗时
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    print("\n" + "="*80)
    print("分析完成！")
    print("="*80)
    print(f"\n总耗时: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分钟)")
    print(f"\n所有结果已保存到: {OUTPUT_DIR}")
    print("\n生成的文件:")
    print("  - 4个统计CSV文件")
    print("  - 5张可视化图表 (PNG)")
    print("  - 1个Markdown分析报告")
    print()


if __name__ == '__main__':
    main()
