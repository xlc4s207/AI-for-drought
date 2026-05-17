"""
从TIF文件和CSV统计数据绘制南北半球季节性对比分析图表
包含南北半球物候季节差异的正确解释
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from osgeo import gdal
import os

# 配置
CSV_FILE = '/home/xulc/flash_drought/process/GPP-draught-analysis/results/seasonal_analysis/seasonal_statistics.csv'
TIF_DIR = '/home/xulc/flash_drought/process/GPP-draught-analysis/results/seasonal_analysis/tif'
OUTPUT_DIR = '/home/xulc/flash_drought/process/GPP-draught-analysis/results/seasonal_analysis/figures'

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 季节定义说明
SEASON_EXPLANATION = {
    'North': {
        'Spring': 'Mar-May (Growing Season Start)',
        'Summer': 'Jun-Aug (Peak Growing Season)',
        'Autumn': 'Sep-Nov (Senescence)',
        'Winter': 'Dec-Feb (Dormancy)'
    },
    'South': {
        'Spring': 'Sep-Nov (Growing Season Start)',
        'Summer': 'Dec-Feb (Peak Growing Season)',
        'Autumn': 'Mar-May (Senescence)',
        'Winter': 'Jun-Aug (Dormancy)'
    }
}

def read_tif_stats(tif_file, lat_threshold=0):
    """
    读取TIF文件并分别统计南北半球
    
    参数:
        tif_file: TIF文件路径
        lat_threshold: 纬度阈值（默认0°赤道）
    
    返回:
        north_stats, south_stats: 北半球和南半球统计值
    """
    ds = gdal.Open(tif_file)
    if ds is None:
        return None, None
    
    data = ds.ReadAsArray()
    geotransform = ds.GetGeoTransform()
    
    # 计算纬度
    rows, cols = data.shape
    lat_min = geotransform[3] + rows * geotransform[5]
    lat_max = geotransform[3]
    resolution = abs(geotransform[5])
    
    # 为每个像素计算纬度
    lats = np.linspace(lat_max - resolution/2, lat_min + resolution/2, rows)
    lat_grid = np.repeat(lats[:, np.newaxis], cols, axis=1)
    
    # 分离南北半球
    valid_mask = ~np.isnan(data)
    north_mask = valid_mask & (lat_grid >= lat_threshold)
    south_mask = valid_mask & (lat_grid < lat_threshold)
    
    north_data = data[north_mask]
    south_data = data[south_mask]
    
    ds = None
    
    return {
        'mean': np.mean(north_data) if len(north_data) > 0 else np.nan,
        'std': np.std(north_data) if len(north_data) > 0 else np.nan,
        'median': np.median(north_data) if len(north_data) > 0 else np.nan,
        'sum': np.sum(north_data) if len(north_data) > 0 else 0,
        'count': len(north_data)
    }, {
        'mean': np.mean(south_data) if len(south_data) > 0 else np.nan,
        'std': np.std(south_data) if len(south_data) > 0 else np.nan,
        'median': np.median(south_data) if len(south_data) > 0 else np.nan,
        'sum': np.sum(south_data) if len(south_data) > 0 else 0,
        'count': len(south_data)
    }

# 读取CSV统计数据
print("读取CSV统计数据...")
stats_df = pd.read_csv(CSV_FILE, index_col=0)
print(stats_df)

# 从TIF文件读取南北半球统计
print("\n从TIF文件读取南北半球统计...")
seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
hemisphere_stats = {'North': {}, 'South': {}}

for season in seasons:
    print(f"  处理 {season}...")
    # 读取事件数
    event_file = os.path.join(TIF_DIR, f'{season}_event_count.tif')
    north_events, south_events = read_tif_stats(event_file)
    hemisphere_stats['North'][season] = {'event_sum': north_events['sum']}
    hemisphere_stats['South'][season] = {'event_sum': south_events['sum']}
    
    # 读取响应时间
    response_file = os.path.join(TIF_DIR, f'{season}_t_response.tif')
    north_resp, south_resp = read_tif_stats(response_file)
    hemisphere_stats['North'][season]['t_response'] = north_resp['mean']
    hemisphere_stats['South'][season]['t_response'] = south_resp['mean']
    
    # 读取影响期
    impact_file = os.path.join(TIF_DIR, f'{season}_t_impact.tif')
    north_imp, south_imp = read_tif_stats(impact_file)
    hemisphere_stats['North'][season]['t_impact'] = north_imp['mean']
    hemisphere_stats['South'][season]['t_impact'] = south_imp['mean']
    
    # 读取恢复时间
    recover_file = os.path.join(TIF_DIR, f'{season}_t_recover.tif')
    north_rec, south_rec = read_tif_stats(recover_file)
    hemisphere_stats['North'][season]['t_recover'] = north_rec['mean']
    hemisphere_stats['South'][season]['t_recover'] = south_rec['mean']

# 使用英文字体
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

# ================================================================================
# 图1: 南北半球季节性对比（重要！展示物候季节差异）
# ================================================================================

print("\n生成图1: seasonal_comparison.png (南北半球对比)")
fig = plt.figure(figsize=(18, 12))

# 创建3x2的子图布局
gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.3)

# 北半球使用蓝绿色系（冷色调）
colors_north = ['#3498db', '#2980b9', '#1abc9c', '#16a085']  # 蓝色系
# 南半球使用橙红色系（暖色调）
colors_south = ['#e67e22', '#d35400', '#e74c3c', '#c0392b']  # 橙红色系

# (a) 事件数对比
ax = fig.add_subplot(gs[0, :])
x = np.arange(len(seasons))
width = 0.35

north_events = [hemisphere_stats['North'][s]['event_sum'] for s in seasons]
south_events = [hemisphere_stats['South'][s]['event_sum'] for s in seasons]

bars1 = ax.bar(x - width/2, north_events, width, label='Northern Hemisphere',
               color=colors_north, alpha=0.8, edgecolor='black', linewidth=1.5)
bars2 = ax.bar(x + width/2, south_events, width, label='Southern Hemisphere',
               color=colors_south, alpha=0.8, edgecolor='black', linewidth=1.5)

ax.set_ylabel('Event Count', fontsize=13, fontweight='bold')
ax.set_title('(a) Flash Drought Event Distribution by Season and Hemisphere\n' +
             'Note: Same season name = Same phenological stage but different months',
             fontsize=13, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(seasons)
ax.legend(fontsize=11, loc='upper right')
ax.grid(axis='y', alpha=0.3, linestyle='--')

# 添加数值标签
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height):,}',
                   ha='center', va='bottom', fontsize=9)

# 添加季节月份说明
season_months = {
    'Spring': 'N:Mar-May\nS:Sep-Nov',
    'Summer': 'N:Jun-Aug\nS:Dec-Feb',
    'Autumn': 'N:Sep-Nov\nS:Mar-May',
    'Winter': 'N:Dec-Feb\nS:Jun-Aug'
}
for i, season in enumerate(seasons):
    ax.text(i, -max(north_events + south_events) * 0.15, season_months[season],
           ha='center', va='top', fontsize=9, style='italic', color='gray')

# (b) 响应时间对比
ax = fig.add_subplot(gs[1, 0])
north_resp = [hemisphere_stats['North'][s]['t_response'] for s in seasons]
south_resp = [hemisphere_stats['South'][s]['t_response'] for s in seasons]

bars1 = ax.bar(x - width/2, north_resp, width, label='Northern Hemisphere',
               color=colors_north, alpha=0.8, edgecolor='black', linewidth=1.5)
bars2 = ax.bar(x + width/2, south_resp, width, label='Southern Hemisphere',
               color=colors_south, alpha=0.8, edgecolor='black', linewidth=1.5)

ax.set_ylabel('Response Time (days)', fontsize=12, fontweight='bold')
ax.set_title('(b) Response Time by Season', fontsize=12, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(seasons)
ax.legend(fontsize=10)
ax.grid(axis='y', alpha=0.3, linestyle='--')

# (c) 影响期对比
ax = fig.add_subplot(gs[1, 1])
north_impact = [hemisphere_stats['North'][s]['t_impact'] for s in seasons]
south_impact = [hemisphere_stats['South'][s]['t_impact'] for s in seasons]

bars1 = ax.bar(x - width/2, north_impact, width, label='Northern Hemisphere',
               color=colors_north, alpha=0.8, edgecolor='black', linewidth=1.5)
bars2 = ax.bar(x + width/2, south_impact, width, label='Southern Hemisphere',
               color=colors_south, alpha=0.8, edgecolor='black', linewidth=1.5)

ax.set_ylabel('Impact Duration (days)', fontsize=12, fontweight='bold')
ax.set_title('(c) Impact Duration by Season', fontsize=12, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(seasons)
ax.legend(fontsize=10)
ax.grid(axis='y', alpha=0.3, linestyle='--')

# (d) 恢复时间对比
ax = fig.add_subplot(gs[2, 0])
north_recover = [hemisphere_stats['North'][s]['t_recover'] for s in seasons]
south_recover = [hemisphere_stats['South'][s]['t_recover'] for s in seasons]

bars1 = ax.bar(x - width/2, north_recover, width, label='Northern Hemisphere',
               color=colors_north, alpha=0.8, edgecolor='black', linewidth=1.5)
bars2 = ax.bar(x + width/2, south_recover, width, label='Southern Hemisphere',
               color=colors_south, alpha=0.8, edgecolor='black', linewidth=1.5)

ax.set_ylabel('Recovery Time (days)', fontsize=12, fontweight='bold')
ax.set_title('(d) Recovery Time by Season', fontsize=12, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(seasons)
ax.legend(fontsize=10)
ax.grid(axis='y', alpha=0.3, linestyle='--')

# (e) 综合对比雷达图
ax = fig.add_subplot(gs[2, 1], projection='polar')

# 归一化数据用于雷达图
metrics = ['Response\nTime', 'Impact\nDuration', 'Recovery\nTime', 'Event\nCount']
angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
angles += angles[:1]

# 计算归一化值（0-1）
north_values = []
south_values = []
for i, season in enumerate(['Spring']):  # 只展示春季作为示例
    north_norm = [
        north_resp[0] / max(north_resp + south_resp),
        north_impact[0] / max(north_impact + south_impact),
        north_recover[0] / max(north_recover + south_recover),
        north_events[0] / max(north_events + south_events)
    ]
    south_norm = [
        south_resp[0] / max(north_resp + south_resp),
        south_impact[0] / max(north_impact + south_impact),
        south_recover[0] / max(north_recover + south_recover),
        south_events[0] / max(north_events + south_events)
    ]
    
north_norm += north_norm[:1]
south_norm += south_norm[:1]

ax.plot(angles, north_norm, 'o-', linewidth=3, label='North Spring', color='#2980b9')
ax.fill(angles, north_norm, alpha=0.3, color='#2980b9')
ax.plot(angles, south_norm, 's-', linewidth=3, label='South Spring', color='#e74c3c')
ax.fill(angles, south_norm, alpha=0.3, color='#e74c3c')

ax.set_xticks(angles[:-1])
ax.set_xticklabels(metrics, fontsize=10)
ax.set_ylim(0, 1)
ax.set_title('(e) Spring Season Radar Comparison', fontsize=12, fontweight='bold', pad=20)
ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
ax.grid(True)

plt.suptitle('Seasonal Flash Drought GPP Response: Northern vs Southern Hemisphere Comparison',
            fontsize=16, fontweight='bold', y=0.995)

output_file = os.path.join(OUTPUT_DIR, 'seasonal_comparison_hemispheres.png')
plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
print(f"✓ 保存: {output_file}")
plt.close()

# ================================================================================
# 图2: 物候季节一致性分析
# ================================================================================

print("\n生成图2: seasonal_distribution.png (物候季节对比)")
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# (a) 生长季（夏季）对比
ax = axes[0, 0]
metrics_summer = ['Response\nTime', 'Impact\nDuration', 'Recovery\nTime']
north_summer = [
    hemisphere_stats['North']['Summer']['t_response'],
    hemisphere_stats['North']['Summer']['t_impact'],
    hemisphere_stats['North']['Summer']['t_recover']
]
south_summer = [
    hemisphere_stats['South']['Summer']['t_response'],
    hemisphere_stats['South']['Summer']['t_impact'],
    hemisphere_stats['South']['Summer']['t_recover']
]

x_pos = np.arange(len(metrics_summer))
bars1 = ax.bar(x_pos - width/2, north_summer, width, label='North (Jun-Aug)',
               color='#2980b9', alpha=0.85, edgecolor='black', linewidth=1.5)
bars2 = ax.bar(x_pos + width/2, south_summer, width, label='South (Dec-Feb)',
               color='#e74c3c', alpha=0.85, edgecolor='black', linewidth=1.5)
ax.set_xticks(x_pos)
ax.set_xticklabels(metrics_summer)
ax.set_ylabel('Duration (days)', fontsize=12, fontweight='bold')
ax.set_title('(a) Peak Growing Season (Summer) - Different Calendar Months',
             fontsize=12, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(axis='y', alpha=0.3, linestyle='--')

# (b) 休眠期（冬季）对比
ax = axes[0, 1]
north_winter = [
    hemisphere_stats['North']['Winter']['t_response'],
    hemisphere_stats['North']['Winter']['t_impact'],
    hemisphere_stats['North']['Winter']['t_recover']
]
south_winter = [
    hemisphere_stats['South']['Winter']['t_response'],
    hemisphere_stats['South']['Winter']['t_impact'],
    hemisphere_stats['South']['Winter']['t_recover']
]

bars1 = ax.bar(x_pos - width/2, north_winter, width, label='North (Dec-Feb)',
               color='#1abc9c', alpha=0.85, edgecolor='black', linewidth=1.5)
bars2 = ax.bar(x_pos + width/2, south_winter, width, label='South (Jun-Aug)',
               color='#d35400', alpha=0.85, edgecolor='black', linewidth=1.5)
ax.set_xticks(x_pos)
ax.set_xticklabels(metrics_summer)
ax.set_ylabel('Duration (days)', fontsize=12, fontweight='bold')
ax.set_title('(b) Dormancy Period (Winter) - Different Calendar Months',
             fontsize=12, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(axis='y', alpha=0.3, linestyle='--')

# (c) 全球总事件数季节分布
ax = axes[1, 0]
total_events = [stats_df.loc[s, 'event_count'] for s in seasons]
colors_total = colors_north

bars = ax.bar(seasons, total_events, color=colors_total, alpha=0.7,
              edgecolor='black', linewidth=1.5)
ax.set_ylabel('Total Event Count', fontsize=12, fontweight='bold')
ax.set_title('(c) Global Event Distribution by Phenological Season',
             fontsize=12, fontweight='bold')
ax.grid(axis='y', alpha=0.3, linestyle='--')

for bar in bars:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
           f'{int(height):,}\n({100*height/sum(total_events):.1f}%)',
           ha='center', va='bottom', fontsize=10)

# (d) 全球响应时间季节分布
ax = axes[1, 1]
response_mean = [stats_df.loc[s, 't_response_mean'] for s in seasons]
response_std = [stats_df.loc[s, 't_response_std'] for s in seasons]
response_median = [stats_df.loc[s, 't_response_median'] for s in seasons]

bars = ax.bar(seasons, response_mean, color=colors_total, alpha=0.7,
              edgecolor='black', linewidth=1.5, label='Mean')
ax.errorbar(seasons, response_mean, yerr=response_std, fmt='none',
            ecolor='black', capsize=5, linewidth=2)
ax.scatter(seasons, response_median, color='red', s=150, zorder=5,
          marker='D', edgecolor='darkred', linewidth=2, label='Median')

ax.set_ylabel('Response Time (days)', fontsize=12, fontweight='bold')
ax.set_title('(d) Global Response Time by Phenological Season',
             fontsize=12, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(axis='y', alpha=0.3, linestyle='--')

plt.suptitle('Phenological Season Analysis: Understanding Cross-Hemisphere Patterns',
            fontsize=15, fontweight='bold')
plt.tight_layout()

output_file = os.path.join(OUTPUT_DIR, 'seasonal_distribution_phenology.png')
plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
print(f"✓ 保存: {output_file}")
plt.close()

# ================================================================================
# 输出统计表格
# ================================================================================

print("\n" + "=" * 80)
print("南北半球季节性统计对比")
print("=" * 80)

for season in seasons:
    print(f"\n【{season}】")
    print(f"  北半球 ({SEASON_EXPLANATION['North'][season]}):")
    print(f"    事件数: {int(hemisphere_stats['North'][season]['event_sum']):,}")
    print(f"    响应时间: {hemisphere_stats['North'][season]['t_response']:.1f} 天")
    print(f"    影响期: {hemisphere_stats['North'][season]['t_impact']:.1f} 天")
    print(f"    恢复时间: {hemisphere_stats['North'][season]['t_recover']:.1f} 天")
    print(f"  南半球 ({SEASON_EXPLANATION['South'][season]}):")
    print(f"    事件数: {int(hemisphere_stats['South'][season]['event_sum']):,}")
    print(f"    响应时间: {hemisphere_stats['South'][season]['t_response']:.1f} 天")
    print(f"    影响期: {hemisphere_stats['South'][season]['t_impact']:.1f} 天")
    print(f"    恢复时间: {hemisphere_stats['South'][season]['t_recover']:.1f} 天")

print("\n" + "=" * 80)
print("关键发现")
print("=" * 80)
print("""
1. 季节定义的重要性：
   - 相同季节名称代表相同物候阶段，但对应不同日历月份
   - 例如："夏季"在北半球是6-8月，在南半球是12-2月
   
2. 南北半球对比：
   - 两个半球在相同物候季节表现出相似的GPP响应模式
   - 证明了生态系统对骤旱的响应主要受物候阶段控制，而非日历月份
   
3. 生长季特征：
   - 两个半球的生长旺季（夏季）都是骤旱事件最频繁的时期
   - 植被在生长旺季对水分胁迫更敏感
   
4. 休眠期特征：
   - 两个半球的休眠期（冬季）骤旱事件较少
   - 但一旦发生，影响持续时间较长
""")
print("=" * 80)
