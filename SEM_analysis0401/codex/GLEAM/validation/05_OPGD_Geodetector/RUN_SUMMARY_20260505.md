# OPGD Geodetector Run Summary

## Run

```bash
/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python process/SEM_analysis0401/codex/GLEAM/validation/05_OPGD_Geodetector/run_opgd_geodetector_validation.py
```

## Scope

- Target: `t_recover_to_baseline_abs_peak`
- Metrics: `GPP`, `RECO`
- Biomes: `Forest`, `Grassland`, `Savanna`, `Cropland`, `Shrubland`
- Features: same ten prepeak/event features used by `04_Geodetector`
- Discretization search:
  - `quantile`
  - `equal_interval`
  - `geometric_interval`
  - `standard_deviation`
  - bins `3-10`

## Output Check

- `opgd_factor_q.csv`: 100 rows, all metric-biome subsets use `80000` rows
- `opgd_interactions.csv`: 100 rows
- `reliability/bootstrap_q_stability.csv`: 100 rows, `100` bootstraps
- `reliability/strata_sensitivity.csv`: 100 rows
- `reliability/shap_opgd_consistency.csv`: 10 rows
- `reliability/reliability_score.csv`: 100 rows
- `figures/shap_opgd_reliability_matrix.png` and `.pdf`
- `figures/opgd_interaction_heatmaps.png` and `.pdf`
- `opgd_shap_comparison_cn.docx`: includes both figures as embedded images
- selected methods:
  - `quantile`: 55
  - `standard_deviation`: 27
  - `geometric_interval`: 10
  - `equal_interval`: 8
- reliability grades:
  - `High`: 19
  - `Medium`: 29
  - `Low`: 52

## Preliminary Top Factors

- GPP Cropland: `STRD`, `TMP`, `PRE`
- GPP Forest: `|EVA|`, `TMP`, `STRD`
- GPP Grassland: `TMP`, `STRD`, `SSRD`
- GPP Savanna: `STRD`, `TMP`, `|EVA|`
- GPP Shrubland: `TMP`, `VPD`, `SMrz`
- RECO Cropland: `STRD`, `TMP`, `VPD`
- RECO Forest: `|EVA|`, `TMP`, `STRD`
- RECO Grassland: `TMP`, `STRD`, `SSRD`
- RECO Savanna: `TMP`, `STRD`, `VPD`
- RECO Shrubland: `SSRD`, `TMP`, `VPD`

## Caveat

The latest outputs in this directory are from the script default `--max-rows 80000` and reliability checks with `100` bootstraps. For full-sample manuscript numbers, rerun with a documented full-sample setting and regenerate `opgd_shap_comparison_cn.docx`.
