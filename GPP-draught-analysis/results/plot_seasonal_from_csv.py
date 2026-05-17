"""
从CSV文件直接绘制季节性分析图表
无需重新计算数据
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# 配置
CSV_FILE = '/home/xulc/flash_drought/process/GPP-draught-analysis/results/seasonal_analysis/seasonal_statistics.csv'
OUTPUT_DIR = '/home/xulc/flash_drought/process/GPP-draught-analysis/results/seasonal_analysis/figures'

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 读取CSV数据
print("读取统计数据...")
stats_df = pd.read_csv(CSV_FILE, index_col=0)
print(stats_df)

# 使用英文字体避免乱码
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
colors = ['#2ecc71', '#e74c3c', '#f39c12', '#3498db']

# ================================================================================
# 图1: seasonal_comparison.png
# 含义：展示各季节骤旱GPP响应的关键统计指标对比
# - (a) 各季节骤旱事件总数
# - (b) 各季节平均响应时间（GPP开始下降到骤旱发生的时间差）
# - (c) 各季节平均影响期（GPP持续受影响的时间长度）
# - (d) 各季节恢复率（在观测期内GPP恢复到正常水平的事件比例）
# ================================================================================

print("\n生成图1: seasonal_comparison.png")
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Seasonal Flash Drought GPP Response Analysis', fontsize=16, fontweight='bold')

# (a) 事件数
ax = axes[0, 0]
event_counts = [stats_df.loc[s, 'event_count'] for s in seasons]
bars = ax.bar(seasons, event_counts, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
ax.set_ylabel('Event Count', fontsize=13, fontweight='bold')
ax.set_title('(a) Flash Drought Events by Season', fontsize=13, fontweight='bold')
ax.grid(axis='y', alpha=0.3, linestyle='--')
ax.set_ylim([0, max(event_counts) * 1.15])
for bar in bars:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{int(height):,}',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

# (b) 响应时间
ax = axes[0, 1]
t_response = [stats_df.loc[s, 't_response_mean'] for s in seasons]
t_response_std = [stats_df.loc[s, 't_response_std'] for s in seasons]
bars = ax.bar(seasons, t_response, yerr=t_response_std, 
              color=colors, alpha=0.7, edgecolor='black', linewidth=1.5, capsize=5, error_kw={'linewidth': 2})
ax.set_ylabel('Response Time (days)', fontsize=13, fontweight='bold')
ax.set_title('(b) Mean Response Time by Season', fontsize=13, fontweight='bold')
ax.grid(axis='y', alpha=0.3, linestyle='--')
ax.set_ylim([0, max(t_response) * 1.3])
for i, (bar, val) in enumerate(zip(bars, t_response)):
    ax.text(bar.get_x() + bar.get_width()/2., val,
            f'{val:.1f}',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

# (c) 影响期
ax = axes[1, 0]
t_impact = [stats_df.loc[s, 't_impact_mean'] for s in seasons]
bars = ax.bar(seasons, t_impact, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
ax.set_ylabel('Impact Duration (days)', fontsize=13, fontweight='bold')
ax.set_title('(c) Mean Impact Duration by Season', fontsize=13, fontweight='bold')
ax.grid(axis='y', alpha=0.3, linestyle='--')
ax.set_ylim([0, max(t_impact) * 1.15])
for bar, val in zip(bars, t_impact):
    ax.text(bar.get_x() + bar.get_width()/2., val,
            f'{val:.1f}',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

# (d) 恢复率
ax = axes[1, 1]
recovery_rates = [stats_df.loc[s, 'recovery_rate'] for s in seasons]
bars = ax.bar(seasons, recovery_rates, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
ax.set_ylabel('Recovery Rate (%)', fontsize=13, fontweight='bold')
ax.set_title('(d) Recovery Rate by Season', fontsize=13, fontweight='bold')
ax.set_ylim([0, 100])
ax.grid(axis='y', alpha=0.3, linestyle='--')
for bar, val in zip(bars, recovery_rates):
    ax.text(bar.get_x() + bar.get_width()/2., val,
            f'{val:.1f}%',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

plt.tight_layout()
output_file = os.path.join(OUTPUT_DIR, 'seasonal_comparison.png')
plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
print(f"✓ 保存: {output_file}")
plt.close()

# ================================================================================
# 图2: seasonal_distribution.png
# 注意：这个图需要原始数据分布才能绘制箱线图
# 由于CSV只有统计值，我们改为绘制关键指标的综合对比图
# ================================================================================

print("\n生成图2: seasonal_distribution.png (综合指标对比)")
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle('Seasonal Response Metrics Comparison', fontsize=16, fontweight='bold')

# (a) 响应时间对比（均值±标准差）
ax = axes[0]
x_pos = np.arange(len(seasons))
means = [stats_df.loc[s, 't_response_mean'] for s in seasons]
stds = [stats_df.loc[s, 't_response_std'] for s in seasons]
medians = [stats_df.loc[s, 't_response_median'] for s in seasons]

bars = ax.bar(x_pos, means, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5, 
              label='Mean ± Std')
ax.errorbar(x_pos, means, yerr=stds, fmt='none', ecolor='black', capsize=5, linewidth=2)
ax.scatter(x_pos, medians, color='red', s=100, zorder=5, marker='D', 
           edgecolor='darkred', linewidth=1.5, label='Median')
ax.set_xticks(x_pos)
ax.set_xticklabels(seasons)
ax.set_ylabel('Response Time (days)', fontsize=12, fontweight='bold')
ax.set_title('(a) Response Time Statistics', fontsize=12, fontweight='bold')
ax.legend(loc='upper right', fontsize=10)
ax.grid(axis='y', alpha=0.3, linestyle='--')

# (b) 影响期 vs 最低点时间
ax = axes[1]
impact = [stats_df.loc[s, 't_impact_mean'] for s in seasons]
t_min = [stats_df.loc[s, 't_min_mean'] for s in seasons]

x = np.arange(len(seasons))
width = 0.35
bars1 = ax.bar(x - width/2, impact, width, label='Impact Duration', 
               color='#e74c3c', alpha=0.7, edgecolor='black', linewidth=1.5)
bars2 = ax.bar(x + width/2, t_min, width, label='Time to Minimum', 
               color='#3498db', alpha=0.7, edgecolor='black', linewidth=1.5)
ax.set_xticks(x)
ax.set_xticklabels(seasons)
ax.set_ylabel('Duration (days)', fontsize=12, fontweight='bold')
ax.set_title('(b) Impact vs Minimum Time', fontsize=12, fontweight='bold')
ax.legend(loc='upper right', fontsize=10)
ax.grid(axis='y', alpha=0.3, linestyle='--')

# (c) 恢复时间对比
ax = axes[2]
recovery_time = [stats_df.loc[s, 't_recover_mean'] for s in seasons]
recovery_rate = [stats_df.loc[s, 'recovery_rate'] for s in seasons]

ax2 = ax.twinx()
bars = ax.bar(seasons, recovery_time, color=colors, alpha=0.7, 
              edgecolor='black', linewidth=1.5, label='Recovery Time')
line = ax2.plot(seasons, recovery_rate, color='darkred', marker='o', 
                linewidth=3, markersize=10, label='Recovery Rate')

ax.set_ylabel('Recovery Time (days)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Recovery Rate (%)', fontsize=12, fontweight='bold', color='darkred')
ax.set_title('(c) Recovery Metrics', fontsize=12, fontweight='bold')
ax.tick_params(axis='y')
ax2.tick_params(axis='y', labelcolor='darkred')
ax.grid(axis='y', alpha=0.3, linestyle='--')

# 合并图例
lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=10)

plt.tight_layout()
output_file = os.path.join(OUTPUT_DIR, 'seasonal_distribution.png')
plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
print(f"✓ 保存: {output_file}")
plt.close()

print("\n" + "=" * 80)
print("图表含义说明：")
print("=" * 80)
print("""
【图1: seasonal_comparison.png】- 季节性骤旱GPP响应对比分析
  (a) 各季节骤旱事件数：展示不同季节发生的骤旱事件总数
      → 夏季事件最多（约318万），春秋次之，冬季最少
      
  (b) 平均响应时间：GPP对骤旱的响应速度（骤旱发生到GPP开始下降的时间）
      → 夏季响应最慢（~17天），冬季响应最快（~14天）
      → 误差线表示季节内变异程度
      
  (c) 平均影响期：GPP持续受影响的时间长度
      → 冬季影响最长（~43天），秋季最短（~31天）
      
  (d) 恢复率：在观测期内GPP恢复到正常水平的事件比例
      → 春季恢复率最高（76%），秋季最低（68%）

【图2: seasonal_distribution.png】- 季节性响应指标综合对比
  (a) 响应时间统计：柱状图=均值，误差线=标准差，红色菱形=中位数
      → 展示各季节响应时间的集中趋势和离散程度
      
  (b) 影响期 vs 最低点时间对比：
      → 红色=影响持续期，蓝色=达到GPP最低值的时间
      → 帮助理解骤旱对GPP影响的时间动态
      
  (c) 恢复指标：柱状图=恢复时间（左轴），红线=恢复率（右轴）
      → 综合展示恢复速度和恢复成功率的季节差异

关键发现：
- 夏季骤旱事件最频繁但响应较慢
- 冬季影响持续时间最长
- 春季恢复能力最强
- 秋季虽然影响期短但恢复率较低
""")
print("=" * 80)
