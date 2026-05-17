#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析无效骤旱事件（无响应事件）中 GPP/RECO 的变化趋势
"""
import numpy as np
import pandas as pd
import netCDF4 as nc
import matplotlib.pyplot as plt
import os

BASE_DIR = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO'
OUTPUT_DIR = os.path.join(BASE_DIR, 'analysis_result')

NC_FILES = {
    'SMrz_GPP': os.path.join(BASE_DIR, 'SMrz_GPP_results/gpp_response_events_global_v10.nc'),
    'SMrz_RECO': os.path.join(BASE_DIR, 'SMrz_RECO_results/reco_response_events_global_v10.nc'),
    'SMs_GPP': os.path.join(BASE_DIR, 'SMs_GPP_results/gpp_response_SMs_events_global_v10.nc'),
    'SMs_RECO': os.path.join(BASE_DIR, 'SMs_RECO_results/reco_response_SMs_drought_v10_global_merged.nc'),
}

def analyze_invalid_events():
    print("=" * 70)
    print("分析无效（无响应）骤旱事件中 GPP/RECO 的变化趋势")
    print("=" * 70)
    
    results = []
    
    for name, filepath in NC_FILES.items():
        if not os.path.exists(filepath):
            print(f"跳过: {filepath} 不存在")
            continue
            
        print(f"\n=== {name} ===")
        
        # 确定变量前缀
        var_prefix = 'gpp' if 'GPP' in name else 'reco'
        min_var = f'{var_prefix}_min'
        trend_var = f'{var_prefix}_trend'
        mean_var = f'{var_prefix}_mean'
        
        ds = nc.Dataset(filepath, 'r')
        
        # 读取数据
        response_detected = ds.variables['response_detected'][:].data
        var_min = ds.variables[min_var][:].data
        var_trend = ds.variables[trend_var][:].data
        var_mean = ds.variables[mean_var][:].data if mean_var in ds.variables else None
        
        ds.close()
        
        # 分离有效和无效事件
        invalid_mask = response_detected == 0
        valid_mask = response_detected == 1
        
        invalid_min = var_min[invalid_mask]
        invalid_trend = var_trend[invalid_mask]
        
        valid_min = var_min[valid_mask]
        valid_trend = var_trend[valid_mask]
        
        # 统计无效事件的变化趋势
        # trend > 0 表示增加, trend < 0 表示下降, trend ≈ 0 表示无变化
        trend_increased = (invalid_trend > 0.01).sum()
        trend_decreased = (invalid_trend < -0.01).sum()
        trend_stable = ((invalid_trend >= -0.01) & (invalid_trend <= 0.01)).sum()
        total_invalid = len(invalid_trend)
        
        # 分析 min 值的分布
        min_negative = (invalid_min < -0.5).sum()  # 最低点低于 -0.5σ
        min_positive = (invalid_min > 0.5).sum()   # 最低点高于 0.5σ (异常高)
        min_near_zero = ((invalid_min >= -0.5) & (invalid_min <= 0.5)).sum()  # 接近正常
        
        result = {
            'Dataset': name,
            'Var': var_prefix.upper(),
            'Total Invalid Events': total_invalid,
            # Trend 分析
            'Trend > 0 (Increased)': trend_increased,
            'Trend ≈ 0 (Stable)': trend_stable,
            'Trend < 0 (Decreased)': trend_decreased,
            'Increase %': 100 * trend_increased / total_invalid,
            'Stable %': 100 * trend_stable / total_invalid,
            'Decrease %': 100 * trend_decreased / total_invalid,
            # Min 分析
            'Min > 0.5σ (Above Normal)': min_positive,
            'Min ∈ [-0.5σ, 0.5σ] (Normal)': min_near_zero,
            'Min < -0.5σ (Below Normal)': min_negative,
            'Min Negative %': 100 * min_negative / total_invalid,
            # 平均值
            'Invalid Mean(trend)': np.nanmean(invalid_trend),
            'Invalid Mean(min)': np.nanmean(invalid_min),
            'Valid Mean(trend)': np.nanmean(valid_trend),
            'Valid Mean(min)': np.nanmean(valid_min),
        }
        results.append(result)
        
        print(f"  总无效事件数: {total_invalid:,}")
        print(f"\n  [趋势分析 - {var_prefix.upper()} Trend]")
        print(f"    增加 (trend > 0): {trend_increased:,} ({result['Increase %']:.1f}%)")
        print(f"    稳定 (trend ≈ 0): {trend_stable:,} ({result['Stable %']:.1f}%)")
        print(f"    下降 (trend < 0): {trend_decreased:,} ({result['Decrease %']:.1f}%)")
        print(f"\n  [最低值分析 - {var_prefix.upper()} Min]")
        print(f"    高于正常 (> +0.5σ): {min_positive:,} ({100*min_positive/total_invalid:.1f}%)")
        print(f"    接近正常 (±0.5σ): {min_near_zero:,} ({100*min_near_zero/total_invalid:.1f}%)")
        print(f"    低于正常 (< -0.5σ): {min_negative:,} ({100*min_negative/total_invalid:.1f}%)")
        print(f"\n  [平均值对比]")
        print(f"    无效事件平均 min: {result['Invalid Mean(min)']:.3f}σ  vs  有效事件: {result['Valid Mean(min)']:.3f}σ")
        print(f"    无效事件平均 trend: {result['Invalid Mean(trend)']:.4f}  vs  有效事件: {result['Valid Mean(trend)']:.4f}")
    
    # 保存结果
    df = pd.DataFrame(results)
    output_csv = os.path.join(OUTPUT_DIR, 'invalid_event_trend_analysis.csv')
    df.to_csv(output_csv, index=False)
    print(f"\n结果已保存至: {output_csv}")
    
    # 绘制对比图
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    for i, result in enumerate(results):
        ax = axes.flat[i]
        name = result['Dataset']
        
        # 条形图: Trend 分布
        categories = ['Increased\n(trend>0)', 'Stable\n(trend≈0)', 'Decreased\n(trend<0)']
        values = [result['Increase %'], result['Stable %'], result['Decrease %']]
        colors = ['green', 'gray', 'red']
        
        bars = ax.bar(categories, values, color=colors, edgecolor='black')
        ax.set_title(f'{name}: Invalid Events Trend Distribution', fontsize=11)
        ax.set_ylabel('Percentage (%)')
        ax.set_ylim(0, 80)
        
        # 添加数值标签
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                   f'{val:.1f}%', ha='center', va='bottom', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'figures', 'invalid_event_trend_distribution.png'), dpi=150)
    plt.close()
    print("图表已保存: figures/invalid_event_trend_distribution.png")
    
    return df

if __name__ == '__main__':
    analyze_invalid_events()
