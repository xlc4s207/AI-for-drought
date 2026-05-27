# SEM specs aligned with writing3/05

These specifications translate `process/SEM_analysis0401/codex/writing3/05_SHAP_SEM_path_analysis_design_cn.docx` into runnable observed-variable SEM path models.

## Main model

The main model keeps the core variables emphasized in the 05 document:

- PRE
- SMrz
- SSRD
- TMP
- VPD
- |EVA|
- Duration

LAI is intentionally excluded from the main model and should be used only for sensitivity analysis.

## Extended model

The extended model adds:

- STRD as upstream thermal-radiation background for TMP.
- WIND as an upstream atmospheric-exchange predictor of VPD.

This follows the 05 document's recommendation to treat STRD and WIND as extension or biome-specific pathways rather than forcing them into every primary mechanism interpretation.

## Current implemented numerical results

The tables and figures in the parent directory summarize the already fitted half-unified SEM results from:

`process/SEM_analysis0401/codex/GLEAM/results/SEM_conclusion/sem_halfunified_20260502`

Those fitted models use a conservative, collinearity-controlled skeleton and do not include Duration or SSRD as endpoint-level predictors. The spec files here are therefore provided as the next event-aware/full-design SEM layer, not mixed into the half-unified coefficient tables.
