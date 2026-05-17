#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
绘制SMrz和SMs GPP最小值空间分布图
"""

import rasterio
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
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

def plot_spatial_distribution(data1, bounds1, data2, bounds2, output_path):
    """
    绘制两个空间分布图
    
    Parameters:
    -----------
    data1, data2: numpy array
        要绘制的数据
    bounds1, bounds2: rasterio bounds
        数据的地理范围
    output_path: str
        输出图像路径
    """
    
    # 创建彩虹色colormap（从蓝到红）
    colors = ['#0000FF', '#0080FF', '#00FFFF', '#00FF00', '#FFFF00', '#FF8000', '#FF0000']
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('rainbow_blue_to_red', colors, N=n_bins)
    
    # 创建图形，设置为两列
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))
    
    # 处理无效值
    data1_plot = np.ma.masked_where((data1 == -9999) | np.isnan(data1) | np.isinf(data1), data1)
    data2_plot = np.ma.masked_where((data2 == -9999) | np.isnan(data2) | np.isinf(data2), data2)
    
    # 绘制第一个子图 - SMrz
    im1 = ax1.imshow(data1_plot, 
                     extent=[bounds1.left, bounds1.right, bounds1.bottom, bounds1.top],
                     origin='upper',
                     cmap=cmap,
                     interpolation='nearest',
                     aspect='auto',
                     vmin=-3,
                     vmax=-0.5)
    
    # 添加色带
    cbar1 = plt.colorbar(im1, ax=ax1, orientation='horizontal', 
                         pad=0.05, shrink=0.8, aspect=30)
    cbar1.set_label('GPP Minimum (gC/m²/day)', fontsize=12)
    
    # 设置标题和标签
    ax1.set_title('SMrz GPP Minimum (Mean)', fontsize=14, fontweight='bold', pad=15)
    ax1.set_xlabel('Longitude (°)', fontsize=11)
    ax1.set_ylabel('Latitude (°)', fontsize=11)
    ax1.grid(True, linestyle='--', alpha=0.3)
    ax1.set_xlim([bounds1.left, bounds1.right])
    ax1.set_ylim([bounds1.bottom, bounds1.top])
    
    # 绘制第二个子图 - SMs
    im2 = ax2.imshow(data2_plot,
                     extent=[bounds2.left, bounds2.right, bounds2.bottom, bounds2.top],
                     origin='upper',
                     cmap=cmap,
                     interpolation='nearest',
                     aspect='auto',
                     vmin=-3,
                     vmax=-0.5)
    
    # 添加色带
    cbar2 = plt.colorbar(im2, ax=ax2, orientation='horizontal',
                         pad=0.05, shrink=0.8, aspect=30)
    cbar2.set_label('GPP Minimum (gC/m²/day)', fontsize=12)
    
    # 设置标题和标签
    ax2.set_title('SMs GPP Minimum (Mean)', fontsize=14, fontweight='bold', pad=15)
    ax2.set_xlabel('Longitude (°)', fontsize=11)
    ax2.set_ylabel('Latitude (°)', fontsize=11)
    ax2.grid(True, linestyle='--', alpha=0.3)
    ax2.set_xlim([bounds2.left, bounds2.right])
    ax2.set_ylim([bounds2.bottom, bounds2.top])
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图像
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"图像已保存到: {output_path}")
    
    plt.close()

def main():
    """主函数"""
    
    # 输入文件路径
    smrz_file = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMrz_GPP_results/tif/SMrz_GPP_gpp_min_mean.tif'
    sms_file = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMs_GPP_results/spatial_tif/SMs_GPP_gpp_min_mean.tif'
    
    # 输出目录和文件
    output_dir = '/home/xulc/flash_drought/process/plot/jpg'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'GPP_minimum_comparison.jpg')
    
    print("="*80)
    print("GPP最小值空间分布图绘制")
    print("="*80)
    
    # 读取数据
    print(f"\n读取SMrz GPP最小值数据: {smrz_file}")
    smrz_data, smrz_bounds, _, _ = read_tif(smrz_file)
    print(f"  数据形状: {smrz_data.shape}")
    valid_smrz = smrz_data[(smrz_data != -9999) & ~np.isnan(smrz_data) & ~np.isinf(smrz_data)]
    if len(valid_smrz) > 0:
        print(f"  数值范围: {np.min(valid_smrz):.2f} - {np.max(valid_smrz):.2f}")
    else:
        print(f"  数值范围: 无有效数据")
    
    print(f"\n读取SMs GPP最小值数据: {sms_file}")
    sms_data, sms_bounds, _, _ = read_tif(sms_file)
    print(f"  数据形状: {sms_data.shape}")
    valid_sms = sms_data[(sms_data != -9999) & ~np.isnan(sms_data) & ~np.isinf(sms_data)]
    if len(valid_sms) > 0:
        print(f"  数值范围: {np.min(valid_sms):.2f} - {np.max(valid_sms):.2f}")
    else:
        print(f"  数值范围: 无有效数据")
    
    # 绘制图像
    print(f"\n绘制空间分布图...")
    plot_spatial_distribution(smrz_data, smrz_bounds, sms_data, sms_bounds, output_file)
    
    print("\n" + "="*80)
    print("绘图完成！")
    print("="*80)

if __name__ == '__main__':
    main()
