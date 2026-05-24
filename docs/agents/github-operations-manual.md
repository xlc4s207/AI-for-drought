# GitHub operations manual for AI-for-drought

This manual defines the day-to-day GitHub workflow for the `AI-for-drought` repository.

Repository root:

```text
/home/xulc/flash_drought/process
```

Remote:

```text
https://github.com/xlc4s207/AI-for-drought.git
```

## 1. Core rule

Use this sequence for all non-trivial work:

```text
Issue -> branch -> work -> validate -> Pull Request -> review -> merge
```

Do not use GitHub as a storage location for bulk scientific outputs. Use GitHub to store code, documentation, configuration, small manifests, and reviewable summaries.

## 2. Issue policy

Create an Issue for:

- data preprocessing, repair, inventory, or extraction;
- scientific analysis or model comparison;
- validation, robustness checks, or regression tests;
- figure/table generation;
- manuscript/method/discussion writing;
- bugs or failed scripts;
- repository infrastructure and workflow changes.

Small typo-level documentation edits may skip an Issue if the PR explains the reason.

### 2.1 Issue title format

Use:

```text
[type] Verb + object
```

Examples:

```text
[analysis] Complete prepeak group_pca comparison for GPP/RECO
[validation] Add smoke tests for deep tabular FT-Transformer trial
[data] Repair missing ERA5 yearly dewpoint files
[writing] Consolidate orthogonal SHAP and PLS-SEM method notes
[infra] Define tracked vs generated artifact policy
[bug] Fix recovery-window time-axis padding regression
```

### 2.2 Issue body checklist

Every Issue should answer:

```md
## Objective
What question, bug, or task does this issue address?

## Inputs
Which data sources, scripts, directories, metrics, years, biomes, drought type, or soil layer are involved?

## Expected output
What code, documentation, figures, tables, summaries, or manifests should exist when done?

## Validation
How will correctness be checked?

## Artifact policy
Which outputs should stay outside Git, and what summary/manifest should be committed?
```

## 3. Branch policy

Use one branch per coherent Issue or change.

### 3.1 Branch naming

```text
<type>/<short-description>
```

Recommended prefixes:

```text
feat/
fix/
analysis/
data/
validation/
writing/
docs/
infra/
```

Examples:

```text
analysis/prepeak-group-pca-comparison
validation/deep-tabular-smoke-tests
data/era5-dewpoint-gap-repair
writing/orthogonal-shap-method-note
infra/github-artifact-policy
```

### 3.2 Branch rules

- Do not mix unrelated research tasks in one branch.
- Do not mix bulk generated outputs with code changes.
- Keep PRs reviewable; split large work into multiple Issues/PRs.

## 4. Pull Request policy

Open a PR for code, documentation, templates, configuration, curated manifests, or small reproducibility metadata.

### 4.1 PR title format

```text
<type>: <short summary>
```

Examples:

```text
analysis: complete prepeak group_pca comparison plan
validation: add smoke checks for deep tabular results collection
infra: add GitHub issue and PR templates
writing: consolidate orthogonal SHAP method notes
```

### 4.2 PR body

Use the repository PR template. Every PR must include:

```md
## Summary
What changed and why?

## Related issue
Closes #...

## Scope
Affected modules, data sources, metrics, years, and downstream outputs.

## Validation
Commands run and pass/fail result.

## Data and artifacts
Which generated outputs were produced? Were any committed? Why?

## Risks and follow-up
Scientific interpretation risks, rerun requirements, downstream effects.
```

### 4.3 PR validation standard

Prefer the smallest meaningful validation:

- Python syntax: `python -m py_compile ...`
- unit/smoke tests for changed scripts;
- result inventory checks for analysis outputs;
- checksum/shape/time-axis checks for data processing;
- summary regeneration checks for collectors.

Do not claim completion without fresh validation evidence or a clear explanation of why validation could not run.

## 5. Artifact policy

### 5.1 Track by default

Commit these when relevant:

```text
.py
.sh
.md
.yml
.yaml
.toml
small config files
.github templates
docs/adr/*.md
docs/agents/*.md
small curated manifests
```

### 5.2 Do not track by default

Do not commit bulk/generated artifacts unless explicitly justified:

```text
.nc
.tif
.tiff
.parquet
.feather
.npy
.npz
large .csv
large .json
.png
.jpg
.svg
.pdf
.docx
.pptx
model weights
logs
cache directories
```

### 5.3 If generated outputs matter

Commit a small markdown summary or manifest instead of the full artifact.

Recommended manifest fields:

```yaml
task: <issue or task name>
created_at: <timestamp>
script: <script path>
command: <exact command>
python: <python executable and version>
inputs:
  - path: <input path>
    checksum: <sha256 if feasible>
outputs:
  - path: <output path outside Git>
    description: <what it contains>
validation:
  - <command/result>
notes: <scientific interpretation caveats>
```

## 6. Labels

Create and use these labels.

### 6.1 Type labels

```text
type:data
type:model
type:analysis
type:figure
type:writing
type:validation
type:bug
type:infra
type:docs
```

### 6.2 Data-source labels

```text
data:GLEAM
data:ERA5
data:MSWEP
data:FluxSat
data:BESS
data:landuse
```

### 6.3 Module labels

```text
module:SEM
module:SHAP
module:PLS-SEM
module:Geodetector
module:response-analysis
module:trend-analysis
module:deep-tabular
```

### 6.4 Priority labels

```text
priority:P0
priority:P1
priority:P2
priority:P3
```

Meaning:

- `P0`: blocks core research or repository safety.
- `P1`: important for current manuscript or active analysis.
- `P2`: useful improvement, not blocking.
- `P3`: nice-to-have.

### 6.5 Status labels

```text
status:blocked
status:needs-data
status:needs-review
status:ready-to-run
status:running
status:validated
```

## 7. Milestones

Use these milestones for stage-level planning:

```text
M1 Data pipeline stabilization
M2 GPP/RECO response analysis
M3 SHAP + SEM mechanism analysis
M4 Validation and robustness checks
M5 Manuscript figures and writing
M6 Reproducibility cleanup
```

Each active Issue should belong to a milestone when it supports a known research phase.

## 8. GitHub Project board

Recommended Project name:

```text
AI-for-drought Research Workflow
```

Recommended columns:

```text
Backlog
Ready
Running
Results Review
Writing
Done
Blocked
```

### 8.1 Column meanings

- `Backlog`: useful but not scheduled.
- `Ready`: inputs and acceptance criteria are clear.
- `Running`: actively being worked on.
- `Results Review`: outputs exist and need validation/interpretation.
- `Writing`: ready to turn into manuscript/method/discussion text.
- `Done`: merged or otherwise complete with evidence.
- `Blocked`: waiting for data, compute, decision, or dependency.

### 8.2 Suggested custom fields

```text
Priority: P0/P1/P2/P3
Module: SEM/SHAP/PLS-SEM/Geodetector/Trend/Deep-tabular
Data source: GLEAM/ERA5/MSWEP/FluxSat/BESS
Stage: Data/Model/Figure/Writing/Validation
Effort: S/M/L/XL
Due date
```

## 9. Task-specific workflows

### 9.1 Data task

```text
Issue -> branch data/... -> implement/repair -> quality checks -> manifest/summary -> PR
```

Required validation examples:

- dimensions and coordinate checks;
- time-axis continuity;
- missing-value summary;
- sample pixel comparison;
- checksum or file inventory.

### 9.2 Analysis task

```text
Issue -> branch analysis/... -> run scripts -> validate outputs -> write summary -> PR
```

Required validation examples:

- row counts and expected combinations;
- metrics sanity checks;
- rerun or smoke check;
- comparison to baseline;
- interpretation caveats.

### 9.3 Validation task

```text
Issue -> branch validation/... -> define expected behavior -> run check -> document evidence -> PR
```

Required validation examples:

- smoke tests;
- reproducibility checks;
- seed sensitivity;
- group/time/space split comparison;
- regression checks against known summaries.

### 9.4 Writing task

```text
Issue -> branch writing/... -> draft text -> link evidence -> review caveats -> PR
```

Required evidence:

- source analysis paths;
- figure/table paths;
- key metrics;
- limitations and uncertainty.

### 9.5 Infrastructure task

```text
Issue -> branch infra/... -> change templates/config/docs -> validate formatting -> PR
```

Required validation examples:

- file presence checks;
- template syntax review;
- no generated-artifact staging;
- local smoke check where relevant.

## 10. Commit message guidance

Use concise decision-oriented commit messages.

Recommended style:

```text
<why this change exists>

Constraint: <external constraint>
Confidence: <low|medium|high>
Scope-risk: <narrow|moderate|broad>
Tested: <what was verified>
Not-tested: <known gaps>
```

Example:

```text
Make research tasks reviewable through GitHub templates

Constraint: Repository mixes code, generated outputs, and manuscript notes.
Confidence: high
Scope-risk: narrow
Tested: Verified template files exist and are markdown/YAML-readable.
Not-tested: GitHub UI rendering before push.
```

## 11. First seed issues

Create these first:

1. `[infra] Define tracked vs generated artifact policy`
2. `[docs] Maintain repository context for AI-for-drought`
3. `[infra] Add GitHub labels, milestones, and project fields`
4. `[analysis] Inventory untracked SEM_analysis0401 outputs`
5. `[validation] Add reproducibility manifest for deep tabular experiments`
6. `[analysis] Complete group_pca matrix for GPP/RECO x biomes`
7. `[writing] Consolidate orthogonal SHAP and PLS-SEM method notes`
8. `[infra] Add lightweight smoke tests for key analysis scripts`

## 12. Daily operating rhythm

### Start of work

1. Check the GitHub Project board.
2. Pick or create one Issue.
3. Move it to `Running`.
4. Create a branch.

### During work

1. Keep generated outputs outside Git.
2. Save commands and key outputs.
3. Update summary/manifest if results matter.

### End of work

1. Run validation.
2. Open PR.
3. Link Issue.
4. Move Project item to `Results Review` or `Done`.

## 13. AI agent usage

When asking an AI agent to work in this repo, specify:

- target Issue or task;
- affected paths;
- expected validation;
- whether code edits are allowed;
- whether generated artifacts may be staged.

Default instruction:

```text
Read CONTEXT.md and docs/agents/github-operations-manual.md first. Do not commit generated artifacts unless explicitly instructed. Include validation evidence in the final report.
```
