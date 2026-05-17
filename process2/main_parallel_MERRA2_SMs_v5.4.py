# -*- coding: utf-8 -*-
"""
骤旱检测主程序 v5.4 - 性能与内存深度优化版 (SMs 表层土壤湿度)
==================================================
基于 v5.3 的性能优化版本, 核心算法不变, 详见 drought_core_v5.py

优化内容:
1. Pool 全局复用: 避免每 chunk 重建进程池
2. NC I/O 优化: 连续时间索引使用切片读取
3. 内存优化: 消除 chunk_events 缓冲区 (~720MB → ~15MB/行)
4. 海洋行轻量返回: 减少 ~70% 无效序列化传输
5. 百分位数计算: 预构建窗口索引 + 合并分位数调用
6. 年度数据紧凑返回: 3个数组替代135个数组
7. 代码模块化: 与 SMrz 版本共享核心逻辑

作者: AI Assistant
日期: 2026-03-02
"""

import os
import sys

# 确保能导入核心模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drought_core_v5 import run_main

# ==================== SMs 数据路径配置 ====================
BASE_DIR = "/home/xulc/flash_drought/gleam"
SM_FILE = "/data/MERRA2/SM/SMs_MERRA2_1980_2024_daily_mean.nc4"
RESULT_DIR = os.path.join(BASE_DIR, "result", "SMs_MERRA2_1")
SM_VAR = "SFMC"

if __name__ == '__main__':
    run_main(
        sm_file=SM_FILE,
        sm_var=SM_VAR,
        result_dir=RESULT_DIR,
        label_long="MERRA2 SFMC 表层"
    )
