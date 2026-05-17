"""
测试运行脚本
运行小区域测试，验证分析流程
"""
import os
import sys
import subprocess

# 脚本目录
CODE_DIR = os.path.dirname(os.path.abspath(__file__))

def run_script(script_name):
    """运行单个脚本"""
    script_path = os.path.join(CODE_DIR, script_name)
    print(f"\n{'='*60}")
    print(f"运行: {script_name}")
    print('='*60)
    
    result = subprocess.run(
        ['python', script_path],
        cwd=CODE_DIR,
        capture_output=False
    )
    
    if result.returncode != 0:
        print(f"错误: {script_name} 运行失败")
        return False
    return True

def main():
    print("=" * 60)
    print("骤旱-GPP影响分析 - 测试运行")
    print("=" * 60)
    
    # 按顺序运行脚本
    scripts = [
        "01_prepare_data.py",
        "02_extract_events.py", 
        "03_calc_metrics.py"
    ]
    
    for script in scripts:
        success = run_script(script)
        if not success:
            print(f"\n停止: {script} 执行失败")
            return
    
    print("\n" + "=" * 60)
    print("测试运行完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
