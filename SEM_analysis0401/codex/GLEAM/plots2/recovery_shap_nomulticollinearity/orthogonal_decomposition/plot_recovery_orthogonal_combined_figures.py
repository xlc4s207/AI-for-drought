#!/usr/bin/env python3
"""Build combined figures for recovery-window orthogonal SHAP results."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


GLEAM = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM")
SOURCE = GLEAM / "plots2/prepeak_shap_nomulticollinearity/orthogonal_decomposition/plot_orthogonal_combined_figures.py"
ROOT = GLEAM / "plots2/recovery_shap_nomulticollinearity"

spec = importlib.util.spec_from_file_location("prepeak_orthogonal_combined", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to import {SOURCE}")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

mod.ROOT = ROOT
mod.ORTHO = ROOT / "orthogonal_decomposition"
mod.OUT = mod.ORTHO / "combined_figures"


def write_readme(beeswarm: Path, dep_outputs: list[Path]) -> None:
    lines = [
        "# Recovery-window orthogonal decomposition combined figures",
        "",
        "These figures are redrawn from recovery-window orthogonal SHAP outputs.",
        "",
        "- `orthogonal_beeswarm_comparison_5biomes_gpp_vs_reco.png`: five-biome GPP/RECO beeswarm comparison for recovery-window orthogonal SHAP inputs.",
        "- `combined_by_biome/*_orthogonal_all_features_gpp_vs_reco.png`: one large dependence figure per biome, with GPP and RECO side by side for all ten transformed features.",
        "",
        "Note: x axes are transformed variables: standardized anchors such as `SSRD_z` or residual z-scores such as `TMP_resid_after_SSRD_STRD`.",
        "",
        f"Beeswarm: {beeswarm}",
        "Dependence figures:",
    ]
    lines.extend([f"- {p}" for p in dep_outputs])
    mod.OUT.mkdir(parents=True, exist_ok=True)
    (mod.OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


mod.write_readme = write_readme


if __name__ == "__main__":
    mod.main()
