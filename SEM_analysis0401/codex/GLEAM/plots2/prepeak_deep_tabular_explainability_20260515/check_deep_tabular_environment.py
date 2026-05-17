#!/usr/bin/env python3
"""Check dependencies and resources for prepeak deep tabular experiments."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import platform


OUT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_deep_tabular_explainability_20260515")
OUT.mkdir(parents=True, exist_ok=True)


def module_status(name: str) -> dict[str, object]:
    spec = importlib.util.find_spec(name)
    row: dict[str, object] = {"module": name, "installed": spec is not None}
    if spec is not None:
        try:
            mod = __import__(name)
            row["version"] = getattr(mod, "__version__", "")
        except Exception as exc:  # pragma: no cover
            row["import_error"] = repr(exc)
    return row


def main() -> None:
    modules = [
        "torch",
        "captum",
        "sklearn",
        "numpy",
        "pandas",
        "pyarrow",
        "lightgbm",
        "shap",
        "mambular",
        "mamba_ssm",
        "rtdl",
        "rtdl_revisiting_models",
        "pytorch_tabular",
    ]
    rows = [module_status(m) for m in modules]
    info = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "modules": rows,
        "notes": [
            "FT-Transformer trial requires torch.",
            "Integrated Gradients and DeepLIFT require captum.",
            "Mambular trial requires mambular or a custom Mamba implementation.",
            "Current scripts can run Feature Ablation without captum once torch is available.",
        ],
    }
    out_json = OUT / "deep_tabular_environment_check.json"
    out_json.write_text(json.dumps(info, indent=2), encoding="utf-8")
    for row in rows:
        version = f" {row.get('version', '')}" if row.get("version") else ""
        print(f"{row['module']}: {'OK' if row['installed'] else 'MISSING'}{version}")
    print(out_json)


if __name__ == "__main__":
    main()
