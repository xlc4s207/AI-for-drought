# -*- coding: utf-8 -*-
"""
干旱检测主程序 v5.4 - ERA5-Land 根系土壤湿度三分类版
=======================================================
基于共享核心 `drought_core_v54_threeclass.py` 运行, 输出:
- total
- rapid_1to4
- flash_5to20
- slow_gt20
- dry_to_drier
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drought_core_v54_threeclass import run_main


SM_FILE_RAW = "/data/era5_for_GRN/yearly/volumetric_root_soil_water_0p25deg_1980_2024.nc"
SM_FILE_OPT = "/home/xulc/flash_drought/era5/optimized_input/volumetric_root_soil_water_0p25deg_1980_2024_chunk_t365_lat1_lon1440.nc"
SM_FILE = SM_FILE_OPT if os.path.exists(SM_FILE_OPT) else SM_FILE_RAW
RESULT_DIR = "/home/xulc/flash_drought/era5/result/ERA5L_root_result_v5.4_0p25deg"
SM_VAR = "root_water"


if __name__ == "__main__":
    run_main(
        sm_file=SM_FILE,
        sm_var=SM_VAR,
        result_dir=RESULT_DIR,
        label_long="ERA5-Land root_water 根系土壤湿度三分类 (0.25度, 优先优化分块输入)",
    )
