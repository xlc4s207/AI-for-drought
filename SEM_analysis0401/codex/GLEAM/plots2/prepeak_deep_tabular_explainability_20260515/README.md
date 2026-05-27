# Prepeak Deep Tabular Explainability Trial

This folder contains a CPU-safe route-1 trial for deep tabular regression:

`prepeak/event table features -> t_recover_to_baseline_abs_peak`

## Current Status

- Resource check completed: CPU only, 80 logical cores, about 103 GB RAM available at check time.
- Installed dependencies in `Flash_dra`: `torch-2.12.0+cpu`, `captum-0.9.0`.
- Mambular/Mamba packages are not installed. This folder currently implements a lightweight PyTorch FT-Transformer-style regressor.

## Data

Input tables:

- `data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet`
- `data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet`

Target:

- `t_recover_to_baseline_abs_peak`

Input variants:

- `raw_prepeak`: standardized original ten prepeak features.
- `orthogonal_decomposition`: same sequential residualization as the no-multicollinearity SHAP workflow.
- `group_pca`: Energy, Water, AtmosDemand, and Event PC1 axes.

## Recommended CPU Settings

Use conservative settings first:

```bash
env PYTHONUNBUFFERED=1 /home/xulc/.local/share/mamba/envs/Flash_dra/bin/python \
  run_prepeak_ft_transformer_cpu_trial.py \
  --metrics GPP \
  --biomes Cropland \
  --input-variants raw_prepeak orthogonal_decomposition group_pca \
  --row-limit 20000 \
  --epochs 25 \
  --batch-size 1024 \
  --torch-threads 4 \
  --n-jobs 1 \
  --attr-rows 600
```

For broader runs on this CPU-only machine, prefer `--n-jobs 1` or `--n-jobs 2` and avoid very large per-biome row limits.

## Outputs

Each run writes:

- `run_summary.json`
- `training_history.csv`
- `test_predictions.csv`
- `feature_ablation_importance.csv`
- `integrated_gradients_importance.csv` when Captum is available
- `ft_transformer_state_dict.pt`

Use `collect_ft_transformer_trial_results.py` to rebuild a summary from all `run_summary.json` files.

## Interpretation

This is currently an architecture robustness experiment. LightGBM + SHAP remains the main model because it is faster and currently has stronger performance on the aggregated event-level features.
