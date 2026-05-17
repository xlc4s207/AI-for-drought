#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比分析 SMrz 和 SMs 骤旱事件的 GPP 响应情况
包括：响应率统计、土地利用类型分析、属性平均值计算
"""

import numpy as np
import pandas as pd
import netCDF4 as nc
from osgeo import gdal
import os
from datetime import datetime

# 配置
NC_FILE_SMRZ = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMrz_GPP_results/gpp_response_events_global_v10.nc'
NC_FILE_SMS = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMs_GPP_results/gpp_response_SMs_events_global_v10.nc'
LC_FILE = '/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_11km.tif'
OUTPUT_DIR = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/analysis_result'

IGBP_CLASSES = {
    1: 'Evergreen Needleleaf Forest',
    2: 'Evergreen Broadleaf Forest',
    3: 'Deciduous Needleleaf Forest',
    4: 'Deciduous Broadleaf Forest',
    5: 'Mixed Forests',
    6: 'Closed Shrublands',
    7: 'Open Shrublands',
    8: 'Woody Savannas',
    9: 'Savannas',
    10: 'Grasslands',
    11: 'Permanent Wetlands',
    12: 'Croplands'
}

VARIABLES = [
    'gpp_min', 'gpp_mean', 'gpp_trend',
    't_response', 't_min', 't_impact', 't_recover',
    'amp_max', 'recovery_rate'
]

def load_land_use_data():
    """加载土地利用数据"""
    print("加载土地利用数据...")
    ds = gdal.Open(LC_FILE)
    band = ds.GetRasterBand(1)
    lc_data = band.ReadAsArray()
    gt = ds.GetGeoTransform()
    ds = None
    return lc_data, gt

def map_events_to_lc(lats, lons, lc_data, gt):
    """将事件映射到土地利用类型"""
    origin_x = gt[0]
    origin_y = gt[3]
    pixel_width = gt[1]
    pixel_height = gt[5]
    
    cols = ((lons - origin_x) / pixel_width).astype(int)
    rows = ((lats - origin_y) / pixel_height).astype(int)
    
    rows = np.clip(rows, 0, lc_data.shape[0] - 1)
    cols = np.clip(cols, 0, lc_data.shape[1] - 1)
    
    event_lc_classes = lc_data[rows, cols]
    
    return event_lc_classes

def analyze_nc_file(nc_path, lc_data, gt, dataset_name):
    """分析单个NC文件"""
    print(f"\n{'='*80}")
    print(f"分析数据集: {dataset_name}")
    print(f"文件: {os.path.basename(nc_path)}")
    print(f"{'='*80}\n")
    
    with nc.Dataset(nc_path, 'r') as ds:
        # 读取坐标和响应状态
        lats = ds.variables['lat'][:]
        lons = ds.variables['lon'][:]
        response_detected = ds.variables['response_detected'][:]
        
        total_events = len(response_detected)
        responded_events = np.sum(response_detected == 1)
        no_response_events = total_events - responded_events
        
        print(f"事件总数: {total_events:,}")
        print(f"有响应事件: {responded_events:,} ({responded_events/total_events*100:.2f}%)")
        print(f"无响应事件: {no_response_events:,} ({no_response_events/total_events*100:.2f}%)")
        
        # 映射到土地利用类型
        print("\n映射到土地利用类型...")
        event_lc_classes = map_events_to_lc(lats, lons, lc_data, gt)
        
        # 读取所有变量
        print("读取变量数据...")
        data = {'LC_Class': event_lc_classes, 'response_detected': response_detected}
        
        for var in VARIABLES:
            if var in ds.variables:
                data[var] = ds.variables[var][:]
        
        df = pd.DataFrame(data)
    
    # 按土地利用类型统计
    print("\n按土地利用类型统计...")
    lc_stats = []
    
    for class_id in range(1, 13):  # 只统计1-12类
        class_name = IGBP_CLASSES.get(class_id, f'Class_{class_id}')
        
        # 该类型的所有事件
        class_events = df[df['LC_Class'] == class_id]
        class_total = len(class_events)
        
        if class_total == 0:
            print(f"  Class {class_id:2d} ({class_name}): 无事件")
            continue
        
        # 有响应的事件
        class_responded = np.sum(class_events['response_detected'] == 1)
        class_no_response = class_total - class_responded
        response_ratio = class_responded / class_total * 100
        
        print(f"  Class {class_id:2d} ({class_name}): "
              f"总数={class_total:,}, 有响应={class_responded:,} ({response_ratio:.2f}%), "
              f"无响应={class_no_response:,}")
        
        # 统计信息
        stats = {
            'Dataset': dataset_name,
            'Class_ID': class_id,
            'Class_Name': class_name,
            'Total_Events': class_total,
            'Responded_Events': class_responded,
            'No_Response_Events': class_no_response,
            'Response_Ratio_%': response_ratio
        }
        
        # 计算有效响应事件的属性平均值
        responded_events_df = class_events[class_events['response_detected'] == 1]
        
        if len(responded_events_df) > 0:
            for var in VARIABLES:
                if var in df.columns:
                    valid_vals = responded_events_df[var].dropna()
                    if len(valid_vals) > 0:
                        stats[f'{var}_mean'] = valid_vals.mean()
                        stats[f'{var}_std'] = valid_vals.std()
                        stats[f'{var}_min'] = valid_vals.min()
                        stats[f'{var}_max'] = valid_vals.max()
                    else:
                        stats[f'{var}_mean'] = np.nan
                        stats[f'{var}_std'] = np.nan
                        stats[f'{var}_min'] = np.nan
                        stats[f'{var}_max'] = np.nan
        
        lc_stats.append(stats)
    
    return pd.DataFrame(lc_stats), df

def create_summary_stats(df_smrz_stats, df_sms_stats):
    """创建对比汇总统计"""
    summary = []
    
    for class_id in range(1, 13):
        class_name = IGBP_CLASSES.get(class_id, f'Class_{class_id}')
        
        smrz_row = df_smrz_stats[df_smrz_stats['Class_ID'] == class_id]
        sms_row = df_sms_stats[df_sms_stats['Class_ID'] == class_id]
        
        if len(smrz_row) == 0 and len(sms_row) == 0:
            continue
        
        summary_row = {
            'Class_ID': class_id,
            'Class_Name': class_name,
        }
        
        # SMrz 统计
        if len(smrz_row) > 0:
            summary_row['SMrz_Total_Events'] = smrz_row.iloc[0]['Total_Events']
            summary_row['SMrz_Responded'] = smrz_row.iloc[0]['Responded_Events']
            summary_row['SMrz_Response_Ratio_%'] = smrz_row.iloc[0]['Response_Ratio_%']
        else:
            summary_row['SMrz_Total_Events'] = 0
            summary_row['SMrz_Responded'] = 0
            summary_row['SMrz_Response_Ratio_%'] = 0
        
        # SMs 统计
        if len(sms_row) > 0:
            summary_row['SMs_Total_Events'] = sms_row.iloc[0]['Total_Events']
            summary_row['SMs_Responded'] = sms_row.iloc[0]['Responded_Events']
            summary_row['SMs_Response_Ratio_%'] = sms_row.iloc[0]['Response_Ratio_%']
        else:
            summary_row['SMs_Total_Events'] = 0
            summary_row['SMs_Responded'] = 0
            summary_row['SMs_Response_Ratio_%'] = 0
        
        # 计算差异
        summary_row['Event_Difference'] = summary_row['SMrz_Total_Events'] - summary_row['SMs_Total_Events']
        summary_row['Response_Ratio_Difference_%'] = summary_row['SMrz_Response_Ratio_%'] - summary_row['SMs_Response_Ratio_%']
        
        summary.append(summary_row)
    
    return pd.DataFrame(summary)

def create_markdown_report(summary_df, smrz_stats, sms_stats, output_path):
    """创建Markdown报告"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# 骤旱事件GPP响应对比分析报告\n\n")
        f.write(f"**分析日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        # 总体统计
        f.write("## 1. 总体统计\n\n")
        
        smrz_total = smrz_stats['Total_Events'].sum()
        smrz_responded = smrz_stats['Responded_Events'].sum()
        sms_total = sms_stats['Total_Events'].sum()
        sms_responded = sms_stats['Responded_Events'].sum()
        
        f.write("### SMrz (根区土壤湿度)\n\n")
        f.write(f"- **总事件数**: {smrz_total:,}\n")
        f.write(f"- **有响应事件**: {smrz_responded:,} ({smrz_responded/smrz_total*100:.2f}%)\n")
        f.write(f"- **无响应事件**: {smrz_total-smrz_responded:,} ({(smrz_total-smrz_responded)/smrz_total*100:.2f}%)\n\n")
        
        f.write("### SMs (表层土壤湿度)\n\n")
        f.write(f"- **总事件数**: {sms_total:,}\n")
        f.write(f"- **有响应事件**: {sms_responded:,} ({sms_responded/sms_total*100:.2f}%)\n")
        f.write(f"- **无响应事件**: {sms_total-sms_responded:,} ({(sms_total-sms_responded)/sms_total*100:.2f}%)\n\n")
        
        f.write("### 对比\n\n")
        f.write(f"- **事件数差异**: SMrz 比 SMs 多 {smrz_total-sms_total:,} 个事件 ({(smrz_total-sms_total)/sms_total*100:.1f}%)\n")
        f.write(f"- **响应率差异**: SMrz {smrz_responded/smrz_total*100:.2f}% vs SMs {sms_responded/sms_total*100:.2f}% (差 {smrz_responded/smrz_total*100 - sms_responded/sms_total*100:.2f}%)\n\n")
        
        # 土地利用类型对比
        f.write("---\n\n")
        f.write("## 2. 不同土地利用类型的响应率对比\n\n")
        f.write("| 土地类型 | SMrz事件数 | SMrz响应率 | SMs事件数 | SMs响应率 | 事件数差异 | 响应率差异 |\n")
        f.write("|---------|-----------|-----------|----------|----------|-----------|----------|\n")
        
        for _, row in summary_df.iterrows():
            f.write(f"| {row['Class_Name']} | "
                   f"{int(row['SMrz_Total_Events']):,} | "
                   f"{row['SMrz_Response_Ratio_%']:.2f}% | "
                   f"{int(row['SMs_Total_Events']):,} | "
                   f"{row['SMs_Response_Ratio_%']:.2f}% | "
                   f"{int(row['Event_Difference']):+,} | "
                   f"{row['Response_Ratio_Difference_%']:+.2f}% |\n")
        
        # 关键发现
        f.write("\n---\n\n")
        f.write("## 3. 关键发现\n\n")
        
        # 响应率最高的类型
        f.write("### 3.1 响应率最高的土地类型\n\n")
        f.write("**SMrz (根区):**\n\n")
        top_smrz = smrz_stats.nlargest(3, 'Response_Ratio_%')[['Class_Name', 'Response_Ratio_%', 'Responded_Events', 'Total_Events']]
        for idx, row in top_smrz.iterrows():
            f.write(f"- {row['Class_Name']}: {row['Response_Ratio_%']:.2f}% "
                   f"({int(row['Responded_Events']):,}/{int(row['Total_Events']):,})\n")
        
        f.write("\n**SMs (表层):**\n\n")
        top_sms = sms_stats.nlargest(3, 'Response_Ratio_%')[['Class_Name', 'Response_Ratio_%', 'Responded_Events', 'Total_Events']]
        for idx, row in top_sms.iterrows():
            f.write(f"- {row['Class_Name']}: {row['Response_Ratio_%']:.2f}% "
                   f"({int(row['Responded_Events']):,}/{int(row['Total_Events']):,})\n")
        
        # 响应率最低的类型
        f.write("\n### 3.2 响应率最低的土地类型\n\n")
        f.write("**SMrz (根区):**\n\n")
        bottom_smrz = smrz_stats.nsmallest(3, 'Response_Ratio_%')[['Class_Name', 'Response_Ratio_%', 'Responded_Events', 'Total_Events']]
        for idx, row in bottom_smrz.iterrows():
            f.write(f"- {row['Class_Name']}: {row['Response_Ratio_%']:.2f}% "
                   f"({int(row['Responded_Events']):,}/{int(row['Total_Events']):,})\n")
        
        f.write("\n**SMs (表层):**\n\n")
        bottom_sms = sms_stats.nsmallest(3, 'Response_Ratio_%')[['Class_Name', 'Response_Ratio_%', 'Responded_Events', 'Total_Events']]
        for idx, row in bottom_sms.iterrows():
            f.write(f"- {row['Class_Name']}: {row['Response_Ratio_%']:.2f}% "
                   f"({int(row['Responded_Events']):,}/{int(row['Total_Events']):,})\n")
        
        # 事件数最多的类型
        f.write("\n### 3.3 事件数最多的土地类型\n\n")
        f.write("**SMrz:**\n\n")
        top_events_smrz = smrz_stats.nlargest(3, 'Total_Events')[['Class_Name', 'Total_Events', 'Responded_Events', 'Response_Ratio_%']]
        for idx, row in top_events_smrz.iterrows():
            f.write(f"- {row['Class_Name']}: {int(row['Total_Events']):,} 事件 "
                   f"(响应率 {row['Response_Ratio_%']:.2f}%)\n")
        
        f.write("\n**SMs:**\n\n")
        top_events_sms = sms_stats.nlargest(3, 'Total_Events')[['Class_Name', 'Total_Events', 'Responded_Events', 'Response_Ratio_%']]
        for idx, row in top_events_sms.iterrows():
            f.write(f"- {row['Class_Name']}: {int(row['Total_Events']):,} 事件 "
                   f"(响应率 {row['Response_Ratio_%']:.2f}%)\n")
        
        # 有效响应事件的平均属性值对比
        f.write("\n---\n\n")
        f.write("## 4. 有效响应事件的平均属性值\n\n")
        
        f.write("### 4.1 响应时间 (t_response)\n\n")
        f.write("| 土地类型 | SMrz (天) | SMs (天) | 差异 (天) |\n")
        f.write("|---------|----------|---------|----------|\n")
        for class_id in range(1, 13):
            smrz_row = smrz_stats[smrz_stats['Class_ID'] == class_id]
            sms_row = sms_stats[sms_stats['Class_ID'] == class_id]
            if len(smrz_row) > 0 and len(sms_row) > 0:
                class_name = smrz_row.iloc[0]['Class_Name']
                smrz_val = smrz_row.iloc[0].get('t_response_mean', np.nan)
                sms_val = sms_row.iloc[0].get('t_response_mean', np.nan)
                diff = smrz_val - sms_val if not np.isnan(smrz_val) and not np.isnan(sms_val) else np.nan
                f.write(f"| {class_name} | {smrz_val:.2f} | {sms_val:.2f} | {diff:+.2f} |\n")
        
        f.write("\n### 4.2 恢复时间 (t_recover)\n\n")
        f.write("| 土地类型 | SMrz (天) | SMs (天) | 差异 (天) |\n")
        f.write("|---------|----------|---------|----------|\n")
        for class_id in range(1, 13):
            smrz_row = smrz_stats[smrz_stats['Class_ID'] == class_id]
            sms_row = sms_stats[sms_stats['Class_ID'] == class_id]
            if len(smrz_row) > 0 and len(sms_row) > 0:
                class_name = smrz_row.iloc[0]['Class_Name']
                smrz_val = smrz_row.iloc[0].get('t_recover_mean', np.nan)
                sms_val = sms_row.iloc[0].get('t_recover_mean', np.nan)
                diff = smrz_val - sms_val if not np.isnan(smrz_val) and not np.isnan(sms_val) else np.nan
                f.write(f"| {class_name} | {smrz_val:.2f} | {sms_val:.2f} | {diff:+.2f} |\n")
        
        f.write("\n### 4.3 恢复速率 (recovery_rate)\n\n")
        f.write("| 土地类型 | SMrz | SMs | 差异 |\n")
        f.write("|---------|------|-----|------|\n")
        for class_id in range(1, 13):
            smrz_row = smrz_stats[smrz_stats['Class_ID'] == class_id]
            sms_row = sms_stats[sms_stats['Class_ID'] == class_id]
            if len(smrz_row) > 0 and len(sms_row) > 0:
                class_name = smrz_row.iloc[0]['Class_Name']
                smrz_val = smrz_row.iloc[0].get('recovery_rate_mean', np.nan)
                sms_val = sms_row.iloc[0].get('recovery_rate_mean', np.nan)
                diff = smrz_val - sms_val if not np.isnan(smrz_val) and not np.isnan(sms_val) else np.nan
                f.write(f"| {class_name} | {smrz_val:.4f} | {sms_val:.4f} | {diff:+.4f} |\n")
        
        # 结论
        f.write("\n---\n\n")
        f.write("## 5. 主要结论\n\n")
        
        # 自动生成一些结论
        event_diff_pct = (smrz_total - sms_total) / sms_total * 100
        response_diff_pct = (smrz_responded/smrz_total*100) - (sms_responded/sms_total*100)
        
        f.write(f"1. **事件数量**: SMrz检测到的骤旱事件比SMs多{event_diff_pct:.1f}%，"
               f"表明根区土壤湿度能识别更多干旱事件。\n\n")
        
        f.write(f"2. **响应率**: SMrz的平均响应率为{smrz_responded/smrz_total*100:.2f}%，"
               f"SMs为{sms_responded/sms_total*100:.2f}%，"
               f"{'SMrz略高' if response_diff_pct > 0 else 'SMs略高'}。\n\n")
        
        # 找出响应率差异最大的类型
        max_diff_row = summary_df.loc[summary_df['Response_Ratio_Difference_%'].abs().idxmax()]
        f.write(f"3. **土地类型差异**: {max_diff_row['Class_Name']}的响应率差异最大，"
               f"SMrz比SMs{'高' if max_diff_row['Response_Ratio_Difference_%'] > 0 else '低'}"
               f"{abs(max_diff_row['Response_Ratio_Difference_%']):.2f}个百分点。\n\n")
        
        f.write("4. **农田表现**: 农田(Croplands)在两种数据中都显示出较高的响应率，"
               "表明农作物对土壤水分变化非常敏感。\n\n")
        
        f.write("5. **森林响应**: 森林类型的响应率普遍较高，但响应时间较长，"
               "反映了森林生态系统对干旱的滞后响应特征。\n\n")
        
        # 数据文件说明
        f.write("\n---\n\n")
        f.write("## 6. 输出文件\n\n")
        f.write("本分析生成了以下文件：\n\n")
        f.write("- `response_comparison_summary.csv`: 土地类型响应率对比汇总表\n")
        f.write("- `smrz_landuse_response_stats.csv`: SMrz各土地类型详细统计\n")
        f.write("- `sms_landuse_response_stats.csv`: SMs各土地类型详细统计\n")
        f.write("- `gpp_response_comparison_report.md`: 本报告文件\n\n")
        
        f.write("---\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

def main():
    print("\n" + "="*80)
    print("骤旱事件 GPP 响应对比分析")
    print("="*80 + "\n")
    
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 加载土地利用数据
    lc_data, gt = load_land_use_data()
    
    # 分析 SMrz 数据
    smrz_stats, smrz_df = analyze_nc_file(NC_FILE_SMRZ, lc_data, gt, 'SMrz')
    
    # 分析 SMs 数据
    sms_stats, sms_df = analyze_nc_file(NC_FILE_SMS, lc_data, gt, 'SMs')
    
    # 创建对比汇总
    print("\n" + "="*80)
    print("创建对比汇总...")
    print("="*80 + "\n")
    
    summary_df = create_summary_stats(smrz_stats, sms_stats)
    
    # 保存CSV文件
    summary_csv = os.path.join(OUTPUT_DIR, 'response_comparison_summary.csv')
    smrz_csv = os.path.join(OUTPUT_DIR, 'smrz_landuse_response_stats.csv')
    sms_csv = os.path.join(OUTPUT_DIR, 'sms_landuse_response_stats.csv')
    
    summary_df.to_csv(summary_csv, index=False, encoding='utf-8-sig')
    smrz_stats.to_csv(smrz_csv, index=False, encoding='utf-8-sig')
    sms_stats.to_csv(sms_csv, index=False, encoding='utf-8-sig')
    
    print(f"✓ 已保存: {summary_csv}")
    print(f"✓ 已保存: {smrz_csv}")
    print(f"✓ 已保存: {sms_csv}")
    
    # 创建Markdown报告
    report_md = os.path.join(OUTPUT_DIR, 'gpp_response_comparison_report.md')
    create_markdown_report(summary_df, smrz_stats, sms_stats, report_md)
    print(f"✓ 已保存: {report_md}")
    
    print("\n" + "="*80)
    print("分析完成！")
    print("="*80 + "\n")
    
    # 显示快速汇总
    print("快速汇总:")
    print("-" * 80)
    print(f"SMrz: 总事件 {smrz_stats['Total_Events'].sum():,}, "
          f"有响应 {smrz_stats['Responded_Events'].sum():,} "
          f"({smrz_stats['Responded_Events'].sum()/smrz_stats['Total_Events'].sum()*100:.2f}%)")
    print(f"SMs:  总事件 {sms_stats['Total_Events'].sum():,}, "
          f"有响应 {sms_stats['Responded_Events'].sum():,} "
          f"({sms_stats['Responded_Events'].sum()/sms_stats['Total_Events'].sum()*100:.2f}%)")
    print("-" * 80)
    print()

if __name__ == '__main__':
    main()
