#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NEE数据完整性分析脚本
检查1982-2022年数据的时间连续性和完整性
"""

import netCDF4 as nc
import numpy as np
from datetime import datetime, timedelta

# 文件路径
NC_FILE = "/data/BESS_V2/NEE_1982-2022_0.1deg.nc"

def get_days_in_year(year):
    """计算某年的天数"""
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        return 366
    return 365

def analyze_nee_data():
    """分析NEE数据的完整性"""
    
    print("=" * 80)
    print("NEE数据完整性分析")
    print("=" * 80)
    print(f"文件: {NC_FILE}")
    print()
    
    # 打开文件
    with nc.Dataset(NC_FILE, 'r') as ds:
        # 读取时间维度
        time_var = ds.variables['time']
        time_values = time_var[:]
        time_units = time_var.units
        time_calendar = time_var.calendar if hasattr(time_var, 'calendar') else 'standard'
        
        # 读取其他维度信息
        lat = ds.variables['lat'][:]
        lon = ds.variables['lon'][:]
        
        print(f"时间单位: {time_units}")
        print(f"日历类型: {time_calendar}")
        print(f"时间步数: {len(time_values)}")
        print(f"空间维度: lat={len(lat)}, lon={len(lon)}")
        print()
        
        # 解析时间单位
        # 格式: "days since 1982-01-01"
        base_date_str = time_units.split('since')[1].strip()
        base_date = datetime.strptime(base_date_str, "%Y-%m-%d")
        
        # 转换为实际日期
        dates = [base_date + timedelta(days=int(d)) for d in time_values]
        
        # 分析时间范围
        start_date = dates[0]
        end_date = dates[-1]
        
        print("时间范围分析:")
        print(f"起始日期: {start_date.strftime('%Y-%m-%d')}")
        print(f"结束日期: {end_date.strftime('%Y-%m-%d')}")
        print()
        
        # 检查是否包含1981年数据
        print("年份范围检查:")
        if start_date.year == 1981:
            print("✓ 包含1981年数据")
        elif start_date.year == 1982:
            print("✗ 不包含1981年数据，从1982年开始")
        else:
            print(f"! 起始年份为 {start_date.year}")
        
        if end_date.year == 2022:
            print("✓ 包含2022年数据")
        else:
            print(f"! 结束年份为 {end_date.year}")
        print()
        
        # 按年份统计数据天数
        print("=" * 80)
        print("按年份统计数据天数:")
        print("-" * 80)
        print(f"{'年份':<8} {'实际天数':<12} {'应有天数':<12} {'状态':<15} {'缺失天数'}")
        print("-" * 80)
        
        year_stats = {}
        for date in dates:
            year = date.year
            if year not in year_stats:
                year_stats[year] = []
            year_stats[year].append(date)
        
        total_expected = 0
        total_actual = 0
        total_missing = 0
        
        for year in sorted(year_stats.keys()):
            actual_days = len(year_stats[year])
            expected_days = get_days_in_year(year)
            missing_days = expected_days - actual_days
            
            total_expected += expected_days
            total_actual += actual_days
            total_missing += missing_days
            
            if actual_days == expected_days:
                status = "✓ 完整"
            elif actual_days > expected_days:
                status = "! 超出"
            else:
                status = "✗ 不完整"
            
            print(f"{year:<8} {actual_days:<12} {expected_days:<12} {status:<15} {missing_days if missing_days > 0 else '-'}")
        
        print("-" * 80)
        print(f"{'总计':<8} {total_actual:<12} {total_expected:<12} {'':<15} {total_missing}")
        print("=" * 80)
        print()
        
        # 检查时间连续性
        print("时间连续性检查:")
        gaps = []
        for i in range(1, len(dates)):
            delta = (dates[i] - dates[i-1]).days
            if delta != 1:
                gaps.append((dates[i-1], dates[i], delta))
        
        if gaps:
            print(f"✗ 发现 {len(gaps)} 个时间间隙:")
            for prev_date, curr_date, delta in gaps[:10]:  # 最多显示10个
                print(f"  {prev_date.strftime('%Y-%m-%d')} -> {curr_date.strftime('%Y-%m-%d')} (间隔 {delta} 天)")
            if len(gaps) > 10:
                print(f"  ... 还有 {len(gaps)-10} 个间隙")
        else:
            print("✓ 时间连续，无间隙")
        print()
        
        # 检查数据质量
        print("数据质量检查 (采样前100个时间步):")
        nee_data = ds.variables['NEE']
        fill_value = nee_data._FillValue if hasattr(nee_data, '_FillValue') else -9999
        
        # 采样分析
        sample_size = min(100, len(time_values))
        valid_count = 0
        fill_count = 0
        
        for t in range(sample_size):
            data_slice = nee_data[t, :, :]
            valid_pixels = np.sum(data_slice != fill_value)
            fill_pixels = np.sum(data_slice == fill_value)
            
            if valid_pixels > 0:
                valid_count += 1
            if fill_pixels == data_slice.size:
                fill_count += 1
        
        print(f"采样时间步数: {sample_size}")
        print(f"包含有效数据的时间步: {valid_count}/{sample_size}")
        print(f"全部为填充值的时间步: {fill_count}/{sample_size}")
        print()
        
        # 总结
        print("=" * 80)
        print("总结:")
        print("-" * 80)
        
        if start_date.year == 1981 and end_date.year == 2022:
            print("✓ 数据覆盖1981-2022年")
        elif start_date.year == 1982 and end_date.year == 2022:
            print("! 数据覆盖1982-2022年 (缺少1981年)")
        else:
            print(f"! 数据覆盖{start_date.year}-{end_date.year}年")
        
        if total_missing == 0:
            print("✓ 所有年份数据完整")
        else:
            print(f"✗ 总计缺失 {total_missing} 天数据")
        
        if not gaps:
            print("✓ 时间序列连续")
        else:
            print(f"✗ 存在 {len(gaps)} 个时间间隙")
        
        completeness = (total_actual / total_expected) * 100
        print(f"数据完整度: {completeness:.2f}%")
        print("=" * 80)

if __name__ == "__main__":
    analyze_nee_data()
