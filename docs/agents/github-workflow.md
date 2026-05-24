# GitHub workflow for AI-for-drought

## Operating model

This repository is a scientific workflow repository, not just an application codebase.
Use GitHub to manage both software changes and research tasks.

## Issues

Create issues for:

- data preprocessing or repair;
- analysis/modeling tasks;
- validation or robustness checks;
- figure/table generation;
- manuscript or methods writing;
- bugs, regressions, and reproducibility gaps;
- infrastructure and repository hygiene.

Each issue should define:

- objective;
- affected data sources and modules;
- expected outputs;
- validation plan;
- artifact policy.

## Branches

Use branch names that identify intent:

```text
feat/<short-task>
fix/<short-bug>
analysis/<module-or-question>
docs/<topic>
infra/<cleanup>
```

## Pull requests

PRs should be small enough to review. Prefer separate PRs for:

- code changes;
- documentation/method writing;
- generated-artifact policy changes;
- validation scripts.

Every PR must include validation commands and outcomes.

## Generated artifacts

Do not commit large generated outputs by default. Instead, commit:

- the script/config that generates the artifact;
- a markdown summary;
- a small manifest with command, input paths, output path, checksum, and timestamp
  when needed.

## Agent checklist before editing

1. Confirm the repository root is `process/`.
2. Read `CONTEXT.md`.
3. Check whether an Issue already exists for the requested work.
4. Avoid staging generated artifacts unless explicitly requested.
5. Run the smallest meaningful validation before reporting completion.

