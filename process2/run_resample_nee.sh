#!/bin/bash

# NEE数据重采样和年度聚合运行脚本
# 在Flash_dra虚拟环境下运行

echo "激活Flash_dra虚拟环境..."
eval "$(micromamba shell hook --shell bash)"
micromamba activate Flash_dra

echo "开始运行NEE数据处理..."
python /home/xulc/flash_drought/process/process2/resample_merge_nee.py

echo "处理完成!"
