#!/usr/bin/env python
"""Cross-biome comparison scaffold for SHAP and SEM outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from sem_gleam_common import RESULTS_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=str(RESULTS_DIR))
    parser.add_argument("--output", default=str(RESULTS_DIR / "cross_biome_comparison.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(
            [
                "# Cross-biome comparison scaffold",
                "",
                f"- input_dir: {args.input_dir}",
                "- next_step: summarize SHAP rank overlap and SEM path-coefficient differences across biomes",
            ]
        ),
        encoding="utf-8",
    )
    print(f"[DONE] saved to {output}")


if __name__ == "__main__":
    main()

