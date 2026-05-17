
import os
import numpy as np
import netCDF4 as nc
from tqdm import tqdm
from multiprocessing import Pool

# 配置
INPUT_DIR = "/data/BESS_V2/RECO/yearly"
OUTPUT_DIR = "/data/BESS_V2/RECO/yearly0.1"
NUM_WORKERS = 50
SCALE_FACTOR = 2

def aggregate_file(year):
    """将单个 RECO 年度文件从 0.05° 聚合到 0.1°"""
    input_file = os.path.join(INPUT_DIR, f"BESS_RECO_{year}.nc")
    output_file = os.path.join(OUTPUT_DIR, f"BESS_RECO_{year}_0.1deg.nc")
    
    if not os.path.exists(input_file):
        print(f"[{year}] 输入文件不存在")
        return False
    
    if os.path.exists(output_file):
        print(f"[{year}] 已存在，跳过")
        return True
    
    print(f"[{year}] 开始聚合...")
    
    try:
        with nc.Dataset(input_file, 'r') as ds_in:
            time_size = len(ds_in.dimensions['time'])
            lat_in = ds_in.variables['lat'][:]
            lon_in = ds_in.variables['lon'][:]
            
            lat_out_size = len(lat_in) // SCALE_FACTOR
            lon_out_size = len(lon_in) // SCALE_FACTOR
            
            lat_out = lat_in.reshape(lat_out_size, SCALE_FACTOR).mean(axis=1)
            lon_out = lon_in.reshape(lon_out_size, SCALE_FACTOR).mean(axis=1)
            
            with nc.Dataset(output_file, 'w', format='NETCDF4') as ds_out:
                ds_out.createDimension('time', None)
                ds_out.createDimension('lat', lat_out_size)
                ds_out.createDimension('lon', lon_out_size)
                
                time_var = ds_out.createVariable('time', 'i4', ('time',))
                time_var[:] = ds_in.variables['time'][:]
                for attr in ds_in.variables['time'].ncattrs():
                    time_var.setncattr(attr, ds_in.variables['time'].getncattr(attr))
                
                lat_var = ds_out.createVariable('lat', 'f4', ('lat',))
                lat_var[:] = lat_out
                lat_var.units = 'degrees_north'
                
                lon_var = ds_out.createVariable('lon', 'f4', ('lon',))
                lon_var[:] = lon_out
                lon_var.units = 'degrees_east'
                
                # 创建 RECO 变量
                reco_out = ds_out.createVariable(
                    'RECO', 'f4', ('time', 'lat', 'lon'),
                    zlib=True, complevel=4, fill_value=np.nan
                )
                reco_out.units = 'gC/m2/day'
                reco_out.long_name = 'Ecosystem Respiration (0.1 degree)'
                
                ds_out.title = f'BESS V2 Daily RECO {year} (0.1 degree)'
                ds_out.source = 'Aggregated from 0.05 degree data using 2x2 mean'
                
                reco_in = ds_in.variables['RECO']
                
                for t in tqdm(range(time_size), desc=f"[{year}]", leave=False):
                    data = reco_in[t, :, :].astype(np.float32)
                    
                    if hasattr(reco_in, '_FillValue'):
                        fill_val = reco_in._FillValue
                        data = np.where(data == fill_val, np.nan, data)
                    
                    data_reshaped = data.reshape(lat_out_size, SCALE_FACTOR, 
                                                  lon_out_size, SCALE_FACTOR)
                    data_agg = np.nanmean(data_reshaped, axis=(1, 3))
                    
                    reco_out[t, :, :] = data_agg
        
        print(f"[{year}] 完成, 保存至 {output_file}")
        return True
        
    except Exception as e:
        print(f"[{year}] 错误: {e}")
        return False

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    years = []
    for f in os.listdir(INPUT_DIR):
        if f.startswith("BESS_RECO_") and f.endswith(".nc"):
            try:
                year = int(f.split("_")[2].split(".")[0])
                years.append(year)
            except:
                pass
    years.sort()
    
    print(f"开始聚合 BESS RECO 数据 (0.05° → 0.1°)...")
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
