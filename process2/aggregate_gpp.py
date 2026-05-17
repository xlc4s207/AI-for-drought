
import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool

# 配置
INPUT_DIR = "/data/BESS_V2/GPP_Daily/yearly"
OUTPUT_DIR = "/data/BESS_V2/GPP_Daily/yearly0.1"
NUM_WORKERS = 50

# 原始分辨率 0.05° -> 目标分辨率 0.1° (2x2 聚合)
SCALE_FACTOR = 2

def aggregate_file(year):
    """将单个年度文件从 0.05° 聚合到 0.1°"""
    input_file = os.path.join(INPUT_DIR, f"BESS_GPP_{year}.nc")
    output_file = os.path.join(OUTPUT_DIR, f"BESS_GPP_{year}_0.1deg.nc")
    
    if not os.path.exists(input_file):
        print(f"[{year}] 输入文件不存在")
        return False
    
    if os.path.exists(output_file):
        print(f"[{year}] 已存在，跳过")
        return True
    
    print(f"[{year}] 开始聚合...")
    
    try:
        with nc.Dataset(input_file, 'r') as ds_in:
            # 读取维度
            time_size = len(ds_in.dimensions['time'])
            lat_in = ds_in.variables['lat'][:]
            lon_in = ds_in.variables['lon'][:]
            
            # 计算新的维度
            lat_out_size = len(lat_in) // SCALE_FACTOR
            lon_out_size = len(lon_in) // SCALE_FACTOR
            
            # 计算新的坐标 (取 2x2 块的中心点)
            lat_out = lat_in.reshape(lat_out_size, SCALE_FACTOR).mean(axis=1)
            lon_out = lon_in.reshape(lon_out_size, SCALE_FACTOR).mean(axis=1)
            
            # 创建输出文件
            with nc.Dataset(output_file, 'w', format='NETCDF4') as ds_out:
                # 创建维度
                ds_out.createDimension('time', None)
                ds_out.createDimension('lat', lat_out_size)
                ds_out.createDimension('lon', lon_out_size)
                
                # 复制时间变量
                time_var = ds_out.createVariable('time', 'i4', ('time',))
                time_var[:] = ds_in.variables['time'][:]
                for attr in ds_in.variables['time'].ncattrs():
                    time_var.setncattr(attr, ds_in.variables['time'].getncattr(attr))
                
                # 创建坐标变量
                lat_var = ds_out.createVariable('lat', 'f4', ('lat',))
                lat_var[:] = lat_out
                lat_var.units = 'degrees_north'
                
                lon_var = ds_out.createVariable('lon', 'f4', ('lon',))
                lon_var[:] = lon_out
                lon_var.units = 'degrees_east'
                
                # 创建 GPP 变量
                gpp_out = ds_out.createVariable(
                    'GPP', 'f4', ('time', 'lat', 'lon'),
                    zlib=True, complevel=4, fill_value=np.nan
                )
                gpp_out.units = 'gC/m2/day'
                gpp_out.long_name = 'Gross Primary Production (0.1 degree)'
                
                # 全局属性
                ds_out.title = f'BESS V2 Daily GPP {year} (0.1 degree)'
                ds_out.source = 'Aggregated from 0.05 degree data using 2x2 mean'
                
                # 逐时间步聚合
                gpp_in = ds_in.variables['GPP']
                
                for t in tqdm(range(time_size), desc=f"[{year}]", leave=False):
                    # 读取一层数据
                    data = gpp_in[t, :, :].astype(np.float32)
                    
                    # 处理缺失值 (假设 -32768 或 nan)
                    if hasattr(gpp_in, '_FillValue'):
                        fill_val = gpp_in._FillValue
                        data = np.where(data == fill_val, np.nan, data)
                    
                    # 2x2 聚合 (使用 nanmean 忽略缺失值)
                    # Reshape: (lat, lon) -> (lat/2, 2, lon/2, 2)
                    data_reshaped = data.reshape(lat_out_size, SCALE_FACTOR, 
                                                  lon_out_size, SCALE_FACTOR)
                    data_agg = np.nanmean(data_reshaped, axis=(1, 3))
                    
                    gpp_out[t, :, :] = data_agg
        
        print(f"[{year}] 完成, 保存至 {output_file}")
        return True
        
    except Exception as e:
        print(f"[{year}] 错误: {e}")
        return False

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 获取所有年度文件
    years = []
    for f in os.listdir(INPUT_DIR):
        if f.startswith("BESS_GPP_") and f.endswith(".nc"):
            try:
                year = int(f.split("_")[2].split(".")[0])
                years.append(year)
            except:
                pass
    years.sort()
    
    print(f"开始聚合 BESS GPP 数据 (0.05° → 0.1°)...")
    print(f"输入目录: {INPUT_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"年份: {min(years)}-{max(years)} ({len(years)} 个)")
    print(f"并行进程数: {NUM_WORKERS}")
    
    with Pool(processes=NUM_WORKERS) as pool:
        results = pool.map(aggregate_file, years)
    
    success_count = sum(results)
    print(f"\n全部完成! 成功: {success_count}/{len(years)}")

if __name__ == "__main__":
    main()
