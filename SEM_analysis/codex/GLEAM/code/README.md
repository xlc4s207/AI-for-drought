# GLEAM SHAP+SEM Code

当前目录为 `GLEAM` 版本恢复时间解释分析的实施脚本。

建议执行顺序：

1. `01_build_event_master_table.py`
2. `02_extract_era5_features.py`
3. `03_extract_gleam_sm_features.py`
4. `04_extract_drought_characteristics.py`
5. `09_merge_feature_tables.py`
6. 合并特征表后运行 `05_eda_and_quality_check.py`
7. 再进入 `06_shap_analysis.py`、`07_sem_analysis.py`、`08_cross_biome_comparison.py`

当前版本特点：

1. `01-04` 已经是可直接接数据的实现版。
2. `09` 负责把主表和三类特征表拼成主分析表。
3. `05-08` 先落了可运行骨架，便于后面逐步接上 SHAP 和 SEM 的细节。
4. 公共常量、路径、阶段窗口、变量统计口径统一放在 `sem_gleam_common.py`。

`01_build_event_master_table.py` 当前支持低内存参数：

- `--chunk-size`
  - 按事件维分块读取 netCDF，默认 `250000`
- `--workers`
  - 用于唯一像元土地利用映射的线程数，默认 `4`
- `--reuse-anti`
  - 不重新读 12 个 netCDF，而是以流式方式复用 `anti/GLEAM` 已有 parquet，再补齐 `event_uid` 和日期字段

推荐启动方式：

```bash
/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python 01_build_event_master_table.py --chunk-size 200000 --workers 4
```

如果只是快速接通后续流水线：

```bash
/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python 01_build_event_master_table.py --reuse-anti --chunk-size 200000
```
