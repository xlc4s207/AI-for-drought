#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
绘制不同季节的SMrz和SMs GPP响应时间空间分布图（带海岸线）
"""

import rasterio
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import cartopy.crs as ccrs
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def read_tif(file_path):
    """读取TIFF文件并返回数据和地理信息"""
    with rasterio.open(file_path) as src:
        data = src.read(1)
        bounds = src.bounds
        transform = src.transform
        crs = src.crs
    return data, bounds, transform, crs

def plot_seasonal_comparison(season, smrz_file, sms_file, output_path):
    """
    绘制单个季节的SMrz和SMs对比图
    
    Parameters:
    -----------
    season: str
        季节名称
    smrz_file, sms_file: str
        文件路径
    output_path: str
        输出图像路径
    """
    
    # 创建彩虹色colormap（从蓝到红）
    colors = ['#0000FF', '#0080FF', '#00FFFF', '#00FF00', '#FFFF00', '#FF8000', '#FF0000']
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('rainbow_blue_to_red', colors, N=n_bins)
    
    # 读取数据
    smrz_data, smrz_bounds, _, _ = read_tif(smrz_file)
    sms_data, sms_bounds, _, _ = read_tif(sms_file)
    
    # 创建图形
    fig = plt.figure(figsize=(18, 7))
    
    # 绘制第一个子图 - SMrz
    ax1 = fig.add_subplot(1, 2, 1, projection=ccrs.PlateCarree())
    
    # 处理无效值
    data1_plot = np.ma.masked_where((smrz_data == -9999) | np.isnan(smrz_data) | np.isinf(smrz_data), smrz_data)
    
    # 绘制数据
    im1 = ax1.imshow(data1_plot, 
                     extent=[smrz_bounds.left, smrz_bounds.right, smrz_bounds.bottom, smrz_bounds.top],
                     origin='upper',
                     cmap=cmap,
                     transform=ccrs.PlateCarree(),
                     interpolation='nearest',
                     vmin=0,
                     vmax=60)
    
    # 添加海岸线
    ax1.coastlines(resolution='50m', linewidth=0.5, color='black')
    
    # 添加色带
    cbar1 = plt.colorbar(im1, ax=ax1, orientation='horizontal', 
                         pad=0.05, shrink=0.8, aspect=30)
    cbar1.set_label('GPP Response Time (days)', fontsize=12)
    
    # 设置标题
    ax1.set_title(f'SMrz - {season}\nGPP Response Time', fontsize=14, fontweight='bold', pad=15)
    
    # 绘制第二个子图 - SMs
    ax2 = fig.add_subplot(1, 2, 2, projection=ccrs.PlateCarree())
    
    # 处理无效值
    data2_plot = np.ma.masked_where((sms_data == -9999) | np.isnan(sms_data) | np.isinf(sms_data), sms_data)
    
    # 绘制数据
    im2 = ax2.imshow(data2_plot,
                     extent=[sms_bounds.left, sms_bounds.right, sms_bounds.bottom, sms_bounds.top],
                     origin='upper',
                     cmap=cmap,
                     transform=ccrs.PlateCarree(),
                     interpolation='nearest',
                     vmin=0,
                     vmax=60)
    
    # 添加海岸线
    ax2.coastlines(resolution='50m', linewidth=0.5, color='black')
    
    # 添加色带
    cbar2 = plt.colorbar(im2, ax=ax2, orientation='horizontal',
                         pad=0.05, shrink=0.8, aspect=30)
    cbar2.set_label('GPP Response Time (days)', fontsize=12)
    
    # 设置标题
    ax2.set_title(f'SMs - {season}\nGPP Response Time', fontsize=14, fontweight='bold', pad=15)
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图像
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"  图像已保存: {os.path.basename(output_path)}")
    
    plt.close()

def main():
    """主函数"""
    
    # 输入目录
    smrz_dir = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMrz_GPP_results/SMrz_GPP_tif'
    sms_dir = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMs_GPP_results/seasonal_analysis/tif'
    
    # 输出目录
    output_dir = '/home/xulc/flash_drought/process/plot/jpg/seasonal_t_response'
    os.makedirs(output_dir, exist_ok=True)
    
    print("="*80)
    print("季节性GPP响应时间空间分布图绘制（带海岸线）")
    print("="*80)
    
    # 季节列表
    seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
    
    # 处理每个季节
    for season in seasons:
        # 构建文件路径
        smrz_file = os.path.join(smrz_dir, f'SMrz_GPP_{season}_t_response.tif')
        sms_file = os.path.join(sms_dir, f'{season}_t_response.tif')
        
        # 检查文件是否存在
        if not os.path.exists(smrz_file):
            print(f"\n警告: 未找到SMrz文件: {os.path.basename(smrz_file)}")
            continue
        if not os.path.exists(sms_file):
            print(f"\n警告: 未找到SMs文件: {os.path.basename(sms_file)}")
            continue
        
        # 输出文件名
        output_file = os.path.join(output_dir, f'{season}_t_response_comparison.jpg')
        
        print(f"\n处理 {season}")
        print(f"  SMrz: {os.path.basename(smrz_file)}")
        print(f"  SMs:  {os.path.basename(sms_file)}")
        
        # 读取数据统计
        smrz_data, _, _, _ = read_tif(smrz_file)
        sms_data, _, _, _ = read_tif(sms_file)
        
        valid_smrz = smrz_data[(smrz_data != -9999) & ~np.isnan(smrz_data) & ~np.isinf(smrz_data)]
        valid_sms = sms_data[(sms_data != -9999) & ~np.isnan(sms_data) & ~np.isinf(sms_data)]
        
        if len(valid_smrz) > 0:
            print(f"  SMrz 数值范围: {np.min(valid_smrz):.2f} - {np.max(valid_smrz):.2f}")
        if len(valid_sms) > 0:
            print(f"  SMs  数值范围: {np.min(valid_sms):.2f} - {np.max(valid_sms):.2f}")
        
        # 绘制图像
        plot_seasonal_comparison(season, smrz_file, sms_file, output_file)
    
    print("\n" + "="*80)
    print(f"绘图完成！所有图像保存在: {output_dir}")
    print("="*80)

if __name__ == '__main__':
    main()
