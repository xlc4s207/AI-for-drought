"""
骤旱-GPP分析配置文件
Configuration for Flash Drought - GPP Impact Analysis
"""
import os

# ============== 路径配置 ==============
BASE_DIR = "/home/xulc/flash_drought"

# 输入数据
DROUGHT_EVENTS_FILE = os.path.join(BASE_DIR, "gleam/clip_result/SMrz/flash_drought_events_details_v2.nc")
SM_DATA_DIR = os.path.join(BASE_DIR, "gleam/SMrz_dd")
GPP_DATA_DIR = "/data/BESS_V2/GPP_Daily/yearly0.1"
MERGED_GPP_FILE = os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_GPPresult/GPP_merged_1982_2022.nc")
MERGED_SM_FILE = os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_GPPresult/SMrz_merged_1980_2024.nc")
LAND_USE_FILE = os.path.join(BASE_DIR, "land_use/MCD12C1_LC_Type1_2010_11km.tif")

# 输出路径
OUTPUT_DIR = os.path.join(BASE_DIR, "process/GPP-draught-analysis/SMrz_GPPresult")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============== 时间配置 ==============
START_YEAR = 1982  # GPP数据起始年
END_YEAR = 2022    # GPP数据结束年

# ============== 事件窗口配置 ==============
WINDOW_BEFORE = 60   # 事件前天数
WINDOW_AFTER = 120   # 事件后天数 (最大，可能被下一事件截断)
MIN_WINDOW_AFTER = 30  # 最小后窗口 (如果被截断后小于此值则丢弃)

# ============== CCM配置 ==============
CCM_EMBEDDING_DIM = 3     # E: 嵌入维数
CCM_TAU = 7               # τ: 时间延迟
CCM_LAG_RANGE = range(-60, 121, 2)  # lag扫描范围 (-60 to 120, step 2)
CCM_N_BOOTSTRAP = 100     # bootstrap次数
CCM_N_SURROGATE = 100     # surrogate次数

# ============== 响应指标配置 ==============
THETA_DECLINE = -0.5      # 下降阈值 (σ单位)
THETA_RECOVER = -0.25     # 恢复阈值 (σ单位)

# ============== 并行配置 ==============
N_WORKERS = 60            # 并行进程数

# ============== 测试区域配置 ==============
# 美国西部测试区域 (lat: 30-45N, lon: 100-125W -> 255-280E)
TEST_REGION = {
    'lat_min': 30,
    'lat_max': 45,
    'lon_min': -125,
    'lon_max': -100,
    'name': 'US_West'
}

# ============== 土地利用类型 ==============
# MCD12C1 IGBP分类
LAND_USE_TYPES = {
    0: 'Water',
    1: 'Evergreen Needleleaf Forest',
    2: 'Evergreen Broadleaf Forest', 
    3: 'Deciduous Needleleaf Forest',
    4: 'Deciduous Broadleaf Forest',
    5: 'Mixed Forest',
    6: 'Closed Shrubland',
    7: 'Open Shrubland',
    8: 'Woody Savanna',
    9: 'Savanna',
    10: 'Grassland',
    11: 'Permanent Wetland',
    12: 'Cropland',
    13: 'Urban',
    14: 'Cropland/Natural Mosaic',
    15: 'Snow/Ice',
    16: 'Barren'
}

# 有效植被类型 (排除水体、冰雪、裸地、城市)
VALID_LAND_USE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14]
