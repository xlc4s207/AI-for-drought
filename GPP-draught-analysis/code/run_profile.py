"""
测试运行脚本 (带pyinstrument性能分析)
运行小区域测试，验证分析流程并分析性能瓶颈
"""
import os
import sys
import subprocess
from pyinstrument import Profiler

# 脚本目录
CODE_DIR = os.path.dirname(os.path.abspath(__file__))

def run_script_with_profile(script_name):
    """运行单个脚本并分析性能"""
    script_path = os.path.join(CODE_DIR, script_name)
    print(f"\n{'='*60}")
    print(f"运行并分析: {script_name}")
    print('='*60)
    
    # 构建命令: pyinstrument -r html -o profile_output.html script.py
    output_html = os.path.join(CODE_DIR, f"profile_{script_name.replace('.py', '.html')}")
    
    cmd = [
        'pyinstrument',
        '-r', 'html',
        '-o', output_html,
        script_path
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"\n性能报告已生成: {output_html}")
        return True
    except subprocess.CalledProcessError:
        print(f"错误: {script_name} 运行失败")
        return False

def main():
    print("=" * 60)
    print("骤旱-GPP影响分析 - 性能测试运行")
    print("=" * 60)
    
    # 只需要分析核心瓶颈脚本: 02_extract_events.py
    # 01_prepare_data.py通常很快，03_calc_metrics.py是纯计算
    # 瓶颈主要在02的大量IO
    
    target_script = "02_extract_events.py"
    
    # 确保前置数据已准备
    if not os.path.exists(os.path.join(CODE_DIR, "../SMrz_GPPresult/valid_pixels_US_West.pkl")):
        print("未找到预处理数据，正在运行 01_prepare_data.py...")
        subprocess.run(['python', os.path.join(CODE_DIR, "01_prepare_data.py")], check=True)
    
    # 运行性能分析
    run_script_with_profile(target_script)

if __name__ == "__main__":
    main()
