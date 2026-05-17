import os
from osgeo import gdal

# 配置
INPUT_FILE = "/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_11km.tif"
OUTPUT_FILE = "/home/xulc/flash_drought/land_use/MCD12C1_LC_Type1_2010_0.10deg.tif"

# 目标分辨率 (0.1度)
X_RES = 0.1
Y_RES = 0.1

def resample_landuse():
    print(f"开始重采样...")
    print(f"输入: {INPUT_FILE}")
    print(f"输出: {OUTPUT_FILE}")
    print(f"目标分辨率: {X_RES} x {Y_RES} 度")
    
    # 使用 gdal.Warp 进行重采样
    # resampleAlg=gdal.GRA_Mode (众数重采样，适合分类数据)
    # dstNodata=255 (MCD12C1 的填充值通常是 255)
    # outputBounds=[-180, -90, 180, 90] (全球范围)
    
    options = gdal.WarpOptions(
        format='GTiff',
        xRes=X_RES,
        yRes=Y_RES,
        resampleAlg=gdal.GRA_Mode,  # 重要：分类数据必须用众数(Mode)或最近邻(Nearest)
        outputBounds=[-180, -90, 180, 90],  # 强制对齐到全球标准网格
        creationOptions=['COMPRESS=LZW', 'TILED=YES'],
        dstNodata=255,  # 确保背景值正确
        srcNodata=255
    )
    
    ds = gdal.Warp(OUTPUT_FILE, INPUT_FILE, options=options)
    
    if ds is not None:
        print("重采样成功！")
        print(f"输出尺寸: {ds.RasterXSize} x {ds.RasterYSize}")
        gt = ds.GetGeoTransform()
        print(f"新的 GeoTransform: {gt}")
        ds = None  # 关闭文件
    else:
        print("重采样失败！")

if __name__ == "__main__":
    resample_landuse()
