# AI-for-drought project context

## Purpose

This repository supports flash-drought research workflows for carbon-flux response,
mechanism attribution, validation, and manuscript preparation.

The project combines:

- drought-event detection and preprocessing;
- carbon-flux response analysis for GPP, RECO, and NEE;
- SHAP, SEM, PLS-SEM, Geodetector, and robustness analyses;
- figure/table generation and manuscript-oriented method notes.

## Repository boundary

The GitHub-managed repository root is:

```text
/home/xulc/flash_drought/process
```

The parent directory `/home/xulc/flash_drought` contains local data, runtime state,
external skill repos, and other scratch assets. Treat it as the broader workspace, not
the GitHub project root.

## Main research areas

| Area | Typical paths | Notes |
| --- | --- | --- |
| Flash-drought processing | `process/`, `process2/` | Core detection and preprocessing scripts. |
| GPP/RECO/NEE analyses | `GPP-draught-analysis/`, `RECO-draught-analysis/`, `NEE-draught-analysis/` | Carbon-flux drought response workflows. |
| SEM/SHAP mechanism analysis | `SEM_analysis/`, `SEM_analysis0401/` | Main mechanism-analysis work, including GLEAM workflows. |
| Validation | `SEM_analysis0401/codex/GLEAM/validation/` | ALE, ICE, PDP, Geodetector, OPGD validation families. |
| Trend and comparison analysis | `result_analysis/` | Trend maps, cross-product comparisons, performance summaries. |
| FluxSat/BESS comparison | `fluxsat-draught-analysis/` | FluxSat/BESS comparison and recovery analyses. |

## Data sources and terms

- GLEAM: soil moisture / evaporative stress source used in several GPP/RECO workflows.
- ERA5: atmospheric and soil variables used as predictors or validation inputs.
- MSWEP: precipitation forcing used in RECO/GPP mechanism runs.
- FluxSat and BESS: carbon flux products used for comparison and robustness.
- GPP: gross primary productivity.
- RECO: ecosystem respiration.
- NEE: net ecosystem exchange.
- SMrz / SMs: soil-moisture layer variants used in analysis configs.
- prepeak: event window before drought peak.
- recovery window: post-peak recovery period.

## Version-control policy

Track in GitHub:

- source code (`.py`, `.sh`, small config files);
- markdown documentation and method notes;
- issue/PR templates and agent workflow docs;
- small reproducibility manifests when they are intentionally curated.

Do not normally track:

- large raw/intermediate data (`.nc`, `.tif`, `.parquet`, `.npy`, `.npz`);
- generated tables (`.csv`, bulk `.json`);
- rendered figures and large report exports (`.png`, `.pdf`, `.docx`, `.pptx`);
- model weights and long-running experiment outputs;
- runtime logs and caches.

When a generated artifact is scientifically important, track a markdown summary plus:

- the command used to create it;
- input paths and checksums where feasible;
- output path outside Git;
- validation evidence;
- date and environment information.

## GitHub management model

Use GitHub Issues for research tasks, bugs, data repairs, figures, validation, and
writing work. Use Pull Requests for code, documentation, and small reproducibility
metadata changes. Use GitHub Projects for stage tracking.

Recommended project stages:

```text
Backlog -> Ready -> Running -> Results Review -> Writing -> Done
```

Use milestones for research phases:

1. Data pipeline stabilization
2. GPP/RECO response analysis
3. SHAP + SEM mechanism analysis
4. Validation and robustness checks
5. Manuscript figures and writing
6. Reproducibility cleanup

## Agent expectations

Agents should:

- read this file before proposing broad project-management changes;
- keep generated data out of Git unless explicitly requested;
- prefer issue-linked branches and PRs for code/documentation changes;
- include validation evidence in every PR description;
- update ADRs for durable architecture or workflow decisions.

