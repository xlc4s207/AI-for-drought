# Decision: Use GitHub Issues, Projects, and PRs for research workflow management

## Status

Accepted

## Context

The repository mixes scientific code, data-processing scripts, mechanism-analysis
workflows, generated outputs, and manuscript notes. Without a clear GitHub workflow,
large generated artifacts and research scratch files can obscure reviewable code and
documentation changes.

## Decision

Use GitHub Issues for research tasks, GitHub Projects for stage tracking, milestones
for research phases, and Pull Requests for code/documentation/config changes.

Generated scientific artifacts should generally stay outside Git. PRs should commit
source code, documentation, small configs, and curated manifests that make results
auditable without storing large outputs in the repository.

## Consequences

- Research tasks become visible and reviewable.
- Code and documentation changes can be linked to specific issues.
- Large data and figure outputs remain out of Git by default.
- Each PR must include validation evidence and artifact-handling notes.

## Validation

This decision is working if new analysis work can be traced from Issue -> branch ->
PR -> validation evidence -> summary/manifest, without committing bulk generated
artifacts.

