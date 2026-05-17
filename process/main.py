# -*- coding: utf-8 -*-
"""
骤旱检测主程序
协调各模块,管理处理流程和进度
"""

import os
import sys
import argparse
import time
import numpy as np
from datetime import datetime

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    YEARS, LAT_SIZE, LON_SIZE, RESULT_DIR,
    TEST_LAT_RANGE, TEST_LON_RANGE, SAVE_INTERVAL
)
from data_reader import (
    get_coordinate_arrays, read_pixel_timeseries, 
    check_pixel_validity, get_index_ranges_for_region
)
from flash_drought import analyze_pixel
from result_writer import ResultCollector


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='全球骤旱检测程序')
    parser.add_argument('--test-mode', action='store_true',
                        help='测试模式(只处理小区域)')
    parser.add_argument('--lat-range', nargs=2, type=float, default=None,
                        help='纬度范围 (lat_min lat_max)')
    parser.add_argument('--lon-range', nargs=2, type=float, default=None,
                        help='经度范围 (lon_min lon_max)')
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    print("="*60)
    print("         全球骤旱(Flash Drought)检测程序")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"数据年份: {YEARS[0]} - {YEARS[-1]}")
    print(f"结果目录: {RESULT_DIR}")
    print()
    
    # 获取坐标数组
    print("[初始化] 读取坐标信息...")
    lat_array, lon_array = get_coordinate_arrays()
    print(f"  纬度范围: {lat_array.min():.2f} ~ {lat_array.max():.2f}")
    print(f"  经度范围: {lon_array.min():.2f} ~ {lon_array.max():.2f}")
    
    # 确定处理范围
    if args.test_mode:
        lat_range = args.lat_range if args.lat_range else TEST_LAT_RANGE
        lon_range = args.lon_range if args.lon_range else TEST_LON_RANGE
        print(f"\n[测试模式] 处理区域:")
        print(f"  纬度: {lat_range[0]} ~ {lat_range[1]}")
        print(f"  经度: {lon_range[0]} ~ {lon_range[1]}")
        
        lat_indices, lon_indices = get_index_ranges_for_region(lat_range, lon_range)
        # 使用子区域的坐标
        lat_sub = lat_array[lat_indices]
        lon_sub = lon_array[lon_indices]
    else:
        if args.lat_range and args.lon_range:
            lat_range = tuple(args.lat_range)
            lon_range = tuple(args.lon_range)
            lat_indices, lon_indices = get_index_ranges_for_region(lat_range, lon_range)
            lat_sub = lat_array[lat_indices]
            lon_sub = lon_array[lon_indices]
        else:
            lat_indices = range(LAT_SIZE)
            lon_indices = range(LON_SIZE)
            lat_sub = lat_array
            lon_sub = lon_array
    
    n_lat = len(lat_indices)
    n_lon = len(lon_indices)
    total_pixels = n_lat * n_lon
    
    print(f"\n[处理范围] 像元数: {n_lat} x {n_lon} = {total_pixels}")
    
    # 初始化结果收集器
    print("\n[初始化] 创建结果存储...")
    collector = ResultCollector(n_lat, n_lon, lat_sub, lon_sub)
    collector.initialize_nc()
    
    # 主处理循环
    print("\n[处理开始]")
    print("-"*60)
    
    start_time = time.time()
    processed = 0
    
    try:
        for i, lat_idx_global in enumerate(lat_indices):
            for j, lon_idx_global in enumerate(lon_indices):
                # 本地索引(用于存储)
                lat_idx_local = i
                lon_idx_local = j
                
                # 快速检查像元有效性
                if not check_pixel_validity(lat_idx_global, lon_idx_global):
                    collector.mark_invalid(lat_idx_local, lon_idx_local)
                    processed += 1
                    continue
                
                # 读取像元时序数据
                data, dates, is_valid = read_pixel_timeseries(lat_idx_global, lon_idx_global)
                
                if not is_valid:
                    collector.mark_invalid(lat_idx_local, lon_idx_local)
                    processed += 1
                    continue
                
                # 分析骤旱事件
                events, total_count, yearly_counts = analyze_pixel(data, dates)
                
                # 收集结果
                collector.add_pixel_result(lat_idx_local, lon_idx_local, events, yearly_counts)
                
                processed += 1
                
                # 打印进度
                if processed % 10 == 0 or processed == total_pixels:
                    collector.print_progress(processed, total_pixels)
        
        print()  # 换行
        
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断处理")
    
    # 计算耗时
    elapsed = time.time() - start_time
    
    # 保存结果
    collector.save_all()
    
    # 打印汇总
    print("\n" + "="*60)
    print("                     处理完成")
    print("="*60)
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")
    print(f"处理速度: {processed/elapsed:.1f} 像元/秒")
    print()
    print("[输出文件]")
    print(f"  - 总频率: flash_drought_frequency_total_{YEARS[0]}_{YEARS[-1]}.tif")
    print(f"  - 年度频率: flash_drought_frequency_{{year}}.tif (共{len(YEARS)}个)")
    print(f"  - 事件详情: flash_drought_events_details.nc")
    print()
    
    # 显示部分结果样例
    print("[结果样例] 前10个有效像元的骤旱事件数:")
    valid_mask = ~np.isnan(collector.total_freq)
    valid_counts = collector.total_freq[valid_mask]
    if len(valid_counts) > 0:
        sample = valid_counts[:min(10, len(valid_counts))]
        print(f"  {sample}")
        print(f"  平均频率: {np.nanmean(collector.total_freq):.2f} 次/像元")
        print(f"  最大频率: {np.nanmax(collector.total_freq):.0f} 次")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
