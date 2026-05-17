# -*- coding: utf-8 -*-
"""
骤旱检测主程序 v5.4 - C3S 根系层土壤湿度 (RZSM 0-1m)
==================================================
使用 Copernicus C3S Soil Moisture 融合数据 (rzsm_1m 变量)
核心算法与 MERRA2 版本一致, 详见 drought_core_v5.py

作者: AI Assistant
日期: 2026-03-04
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drought_core_v5 import run_main

# ==================== C3S RZSM 数据路径配置 ====================
SM_FILE = "/data/Copernicus C3S Soil Moisture/total/RZSM_C3S_1980_2024_daily.nc4"
RESULT_DIR = "/home/xulc/flash_drought/gleam/result/SMrz_C3S_1"
SM_VAR = "rzsm_1m"

if __name__ == '__main__':
    run_main(
        sm_file=SM_FILE,
        sm_var=SM_VAR,
        result_dir=RESULT_DIR,
        label_long="C3S RZSM 根系层 (0-1m)"
    )
