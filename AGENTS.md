# AI-for-drought agent instructions

## Scope

These instructions apply to the GitHub-managed repository rooted at this directory.

## Project context

Read `CONTEXT.md` before making broad workflow, data-management, or GitHub-project
recommendations. For durable workflow decisions, add an ADR under `docs/adr/`.

## GitHub workflow

- Track work as GitHub Issues whenever it is larger than a quick local inspection.
- Use one branch per issue or coherent change.
- Open PRs for code, documentation, and curated metadata changes.
- Link PRs to Issues with `Closes #...` when appropriate.
- Include validation evidence in PR descriptions.
- Do not commit generated scientific artifacts by default.

## Artifact policy

Default to tracking:

- source code;
- shell scripts;
- markdown documentation;
- small configuration files;
- issue/PR templates;
- small curated manifests.

Default to not tracking:

- `.nc`, `.tif`, `.parquet`, `.npy`, `.npz`;
- bulk `.csv` / `.json` outputs;
- figures, report exports, and model weights;
- caches, logs, and runtime state.

If a generated artifact must be versioned, explain why in the PR and keep it small.

## Pull request quality bar

Every PR should include:

- summary of the change;
- linked issue or reason no issue exists;
- affected data sources / modules;
- validation commands and outcomes;
- risks, rerun requirements, and generated-artifact handling.

