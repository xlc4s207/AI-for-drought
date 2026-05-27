#!/usr/bin/env python3
"""VPD sign-flipped orthogonal SHAP dependence overlay outputs."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


WORK_DIR = Path(__file__).resolve().parent
BASE_SCRIPT = WORK_DIR / "plot_orthogonal_dependence_validation_opgd_overlay.py"
COMBINED_SCRIPT = (
    WORK_DIR.parents[1]
    / "plots2/prepeak_shap_nomulticollinearity/orthogonal_decomposition/plot_orthogonal_combined_figures.py"
)
NEW_OUT = WORK_DIR / "orthogonal_comparison" / "dependenceplot_VPD"


def load_base_module():
    spec = importlib.util.spec_from_file_location("overlay_base_module", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_combined_module():
    spec = importlib.util.spec_from_file_location("combined_shap_module", COMBINED_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {COMBINED_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    base = load_base_module()
    original_out = base.OUT
    original_compute_or_load_curves = base.compute_or_load_curves

    def compute_or_load_curves_from_original_cache(module, metric: str, biome: str):
        current_out = base.OUT
        base.OUT = original_out
        try:
            return original_compute_or_load_curves(module, metric, biome)
        finally:
            base.OUT = current_out

    base.compute_or_load_curves = compute_or_load_curves_from_original_cache
    base.OUT = NEW_OUT
    base.SHAP_SIGN_FLIP_FEATURES = {"VPD_resid_after_SSRD_TMP_Wind"}
    outputs = base.draw_biome_figures(base.load_nomulti_module())
    base.write_readme(outputs)
    combined = load_combined_module()
    combined.OUT = NEW_OUT
    combined.SHAP_SIGN_FLIP_FEATURES = {"VPD_resid_after_SSRD_TMP_Wind"}
    beeswarm = combined.plot_combined_beeswarm()
    readme = NEW_OUT / "README.md"
    text = readme.read_text(encoding="utf-8")
    note = (
        "\nVPD sign convention:\n"
        "- `VPD_resid_after_SSRD_TMP_Wind` SHAP scatter values and SHAP trend lines are multiplied by `-1` in this separate output set.\n"
        "- ALE, ICE mean, and PDP curves are also flipped for VPD in this output set so the full panel follows the same sign convention.\n"
        "- Original overlay figures in `validation_overlay_by_biome` are preserved with the original SHAP sign.\n"
        f"- Beeswarm outputs: {beeswarm}\n"
        f"- Beeswarm SHAP-summary output: {NEW_OUT / 'orthogonal_beeswarm_comparison_5biomes_gpp_vs_reco_shap_summary.png'}\n"
    )
    readme.write_text(text + note, encoding="utf-8")
    for p in outputs:
        print(p)
    print(beeswarm)


if __name__ == "__main__":
    main()
