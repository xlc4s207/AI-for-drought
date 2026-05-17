# Round Goal

Prepare the main project scripts for GitHub upload, while keeping data, figures, and generated reports out of the repository.

# Key Decisions

- The real Git repository is `process/`, with remote `origin` already set to `https://github.com/xlc4s207/AI-for-drought.git`.
- I staged only executable/reusable scripts: `.py`, `.sh`, and `.R`.
- I did not stage large artifacts such as NetCDF, CSV, PNG, DOCX, HTML, ODT, or JSON outputs.
- I expanded `.gitignore` to suppress common generated artifact types that were still cluttering `git status`.

# Context / Evidence

- `git -C process status --short --branch` showed the repo was on `main...origin/main` and had one modified tracked file plus many untracked script and output directories.
- `find process -type f \( -name '*.py' -o -name '*.sh' -o -name '*.R' \)` found about 815 script files across the project.
- `git add` with pathspec filtering staged 703 script files successfully after requesting permission to write the Git index.

# Affected Files / Paths

- `process/.gitignore`
- `process/SEM_analysis/codex/.agent/2026-05-17-0000-github-script-management.md`
- Major script trees under `process/GPP-draught-analysis/`
- Major script trees under `process/RECO-draught-analysis/`
- Major script trees under `process/NEE-draught-analysis/`
- `process/process/`
- `process/process2/`
- `process/result_analysis/`
- `process/SEM_analysis0401/codex/GLEAM/code/`
- `process/SEM_analysis0401/codex/GLEAM/validation/`
- `process/SEM_analysis0401/codex/GLEAM/plots2/SEM/`

# Next Actions

- Review the staged diff for any script that should be excluded before commit.
- Commit the script bundle with a clear message.
- Push to GitHub once credentials are configured.

# Open Risks / Caveats

- Many generated outputs still exist as untracked files, but most are now hidden by ignore rules.
- Some markdown notes and analysis writeups remain untracked by design because this round focused on scripts.
- The repository is very large, so pushes may take time.
- GitHub push was attempted but failed because this machine has no usable HTTPS credential or SSH key for `xlc4s207/AI-for-drought.git`.
