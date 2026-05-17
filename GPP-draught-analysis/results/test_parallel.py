#!/usr/bin/env python3
"""
测试并行处理功能
"""
import time
import numpy as np
import pandas as pd
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

# 导入季节计算函数
import sys
sys.path.insert(0, '/home/xulc/flash_drought/process/GPP-draught-analysis/results')
from seasonal_analysis import calculate_season_for_row

# 创建测试数据
print("创建测试数据...")
n_test = 100000  # 10万个测试事件
test_data = pd.DataFrame({
    'onset_year': np.random.randint(2000, 2020, n_test),
    'onset_doy': np.random.randint(1, 365, n_test),
    'duration': np.random.randint(10, 90, n_test),
    'lat': np.random.uniform(-60, 80, n_test)
})

print(f"测试数据: {len(test_data)} 个事件\n")

# 测试串行处理
print("【串行处理】")
start = time.time()
seasons_serial = []
for _, row in tqdm(test_data.iterrows(), total=len(test_data), desc="串行计算"):
    seasons_serial.append(calculate_season_for_row(row))
time_serial = time.time() - start
print(f"串行用时: {time_serial:.2f} 秒\n")

# 测试并行处理
n_workers = min(cpu_count(), 16)
print(f"【并行处理 - {n_workers} 进程】")
rows = [row for _, row in test_data.iterrows()]
start = time.time()
with Pool(processes=n_workers) as pool:
    seasons_parallel = list(tqdm(
        pool.imap(calculate_season_for_row, rows, chunksize=1000),
        total=len(rows),
        desc="并行计算"
    ))
time_parallel = time.time() - start
print(f"并行用时: {time_parallel:.2f} 秒")

# 计算加速比
speedup = time_serial / time_parallel
print(f"\n加速比: {speedup:.2f}x")
print(f"效率: {100*speedup/n_workers:.1f}%")

# 验证结果一致性
print(f"\n结果验证: {'✓ 一致' if seasons_serial == seasons_parallel else '✗ 不一致'}")
