# -*- coding: utf-8 -*-
"""
干旱检测主程序 v5.4 - SMrz 根系土壤湿度三分类版
=================================================
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


SM_FILE = "/data/GLEAM/0p25deg_yearly/SMrz_45years_0p25deg.nc"
RESULT_DIR = "/home/xulc/flash_drought/gleam/result/SMrz_result_v5.4_0p25deg"
SM_VAR = "SMrz"


if __name__ == "__main__":
    run_main(
        sm_file=SM_FILE,
        sm_var=SM_VAR,
        result_dir=RESULT_DIR,
        label_long="GLEAM SMrz 根系土壤湿度三分类 (0.25度)",
    )
