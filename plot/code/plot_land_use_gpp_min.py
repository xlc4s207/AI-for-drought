#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
绘制不同土地利用类型的SMrz和SMs GPP最小值空间分布图（带海岸线）
"""

import rasterio
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import os
import glob

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

def get_land_use_class_name(class_num):
    """根据类别编号返回土地利用类型名称"""
    land_use_names = {
        1: "Evergreen Needleleaf Forest",
        2: "Evergreen Broadleaf Forest",
        3: "Deciduous Needleleaf Forest",
        4: "Deciduous Broadleaf Forest",
        5: "Mixed Forests",
        6: "Closed Shrublands",
        7: "Open Shrublands",
        8: "Woody Savannas",
        9: "Savannas",
        10: "Grasslands",
        11: "Permanent Wetlands",
        12: "Croplands"
    }
    return land_use_names.get(class_num, f"Class {class_num}")

def plot_land_use_comparison(smrz_file, sms_file, class_num, output_path):
    """
    绘制单个土地利用类型的SMrz和SMs对比图
    
    Parameters:
    -----------
    smrz_file, sms_file: str
        文件路径
    class_num: int
        土地利用类别编号
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
                     vmin=-3,
                     vmax=-0.5)
    
    # 添加海岸线
    ax1.coastlines(resolution='50m', linewidth=0.5, color='black')
    
    # 添加色带
    cbar1 = plt.colorbar(im1, ax=ax1, orientation='horizontal', 
                         pad=0.05, shrink=0.8, aspect=30)
    cbar1.set_label('GPP Minimum (gC/m²/day)', fontsize=12)
    
    # 设置标题
    land_use_name = get_land_use_class_name(class_num)
    ax1.set_title(f'SMrz - {land_use_name}\nGPP Minimum', fontsize=14, fontweight='bold', pad=15)
    
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
                     vmin=-3,
                     vmax=-0.5)
    
    # 添加海岸线
    ax2.coastlines(resolution='50m', linewidth=0.5, color='black')
    
    # 添加色带
    cbar2 = plt.colorbar(im2, ax=ax2, orientation='horizontal',
                         pad=0.05, shrink=0.8, aspect=30)
    cbar2.set_label('GPP Minimum (gC/m²/day)', fontsize=12)
    
    # 设置标题
    ax2.set_title(f'SMs - {land_use_name}\nGPP Minimum', fontsize=14, fontweight='bold', pad=15)
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图像
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"  图像已保存: {os.path.basename(output_path)}")
    
    plt.close()

def main():
    """主函数"""
    
    # 输入目录
    smrz_dir = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMrz_GPP_results/land_use_analysis/maps'
    sms_dir = '/home/xulc/flash_drought/process/flash_draught_GPP_RECO/SMs_GPP_results/land_use_analysis/maps'
    
    # 输出目录
    output_dir = '/home/xulc/flash_drought/process/plot/jpg/land_use_gpp_min'
    os.makedirs(output_dir, exist_ok=True)
    
    print("="*80)
    print("土地利用类型GPP最小值空间分布图绘制（带海岸线）")
    print("="*80)
    
    # 获取所有gpp_min文件
    smrz_files = sorted(glob.glob(os.path.join(smrz_dir, 'Class_*_gpp_min_mean.tif')))
    
    print(f"\n找到 {len(smrz_files)} 个土地利用类型")
    
    # 处理每个类别
    for smrz_file in smrz_files:
        # 提取类别编号
        filename = os.path.basename(smrz_file)
        class_num = int(filename.split('_')[1])
        
        # 构建对应的SMs文件路径
        sms_file = os.path.join(sms_dir, filename)
        
        # 检查SMs文件是否存在
        if not os.path.exists(sms_file):
            print(f"\n警告: 未找到对应的SMs文件: {filename}")
            continue
        
        # 输出文件名
        output_file = os.path.join(output_dir, f'Class_{class_num}_gpp_min_comparison.jpg')
        
        print(f"\n处理 Class {class_num} - {get_land_use_class_name(class_num)}")
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
        plot_land_use_comparison(smrz_file, sms_file, class_num, output_file)
    
    print("\n" + "="*80)
    print(f"绘图完成！所有图像保存在: {output_dir}")
    print("="*80)

if __name__ == '__main__':
    main()
