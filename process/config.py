# -*- coding: utf-8 -*-
"""
配置参数模块
定义路径、阈值参数、百分位常量等
"""

import os

# ==================== 路径配置 ====================
BASE_DIR = r"d:\download\gleam"
NC_DATA_DIR = os.path.join(BASE_DIR, "SMrz_dd")
RESULT_DIR = os.path.join(BASE_DIR, "flash_drought", "result")

# 确保结果目录存在
os.makedirs(RESULT_DIR, exist_ok=True)

# NC文件名模板
NC_FILE_TEMPLATE = "SMrz_{year}_GLEAM_v4.2a.nc"

# ==================== 时间范围 ====================
START_YEAR = 1980
END_YEAR = 2024
YEARS = list(range(START_YEAR, END_YEAR + 1))

# ==================== 空间分辨率 ====================
RESOLUTION = 0.1  # 度
LAT_SIZE = 1800   # 纬度像元数
LON_SIZE = 3600   # 经度像元数
LAT_RANGE = (-90, 90)    # 纬度范围
LON_RANGE = (-180, 180)  # 经度范围

# ==================== 骤旱检测参数 ====================
# 滑动窗口大小(天)
MOVING_WINDOW = 5

# 百分位阈值
PERCENTILE_HIGH = 40   # 起始条件：高于P40
PERCENTILE_LOW = 20    # 下降至：低于P20
PERCENTILE_RATE = 5    # 下降速率阈值

# 最小持续时间(天)
MIN_DURATION = 15

# ==================== 处理参数 ====================
# 每处理多少像元保存一次进度
SAVE_INTERVAL = 1000

# 最大事件数(每像元)
MAX_EVENTS_PER_PIXEL = 50

# 测试模式区域配置 (小范围测试用)
TEST_LAT_RANGE = (30, 40)   # 测试纬度范围
TEST_LON_RANGE = (100, 120)  # 测试经度范围(中国东部)
