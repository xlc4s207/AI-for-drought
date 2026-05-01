#!/usr/bin/env python
"""Summarize scope-split SHAP and SEM outputs into a markdown report."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-root", required=True)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def parse_key_value_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def top_features_csv(path: Path, top_k: int = 5) -> str:
    if not path.exists():
        return "NA"
    df = pd.read_csv(path)
    if "feature" not in df.columns or df.empty:
        return "NA"
    return ", ".join(df["feature"].dropna().astype(str).head(top_k).tolist())


def rows_to_markdown_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "- missing"
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        values = [str(row.get(header, "NA")) for header in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_scope_section(result_root: Path, scope: str) -> list[str]:
    lines = [f"## Scope: `{scope}`", ""]

    global_dir = result_root / f"shap_{scope}"
    global_summary = parse_key_value_file(global_dir / "run_summary.txt")
    if global_summary:
        lines.extend(
            [
                "### Global SHAP",
                "",
                f"- rows: {global_summary.get('rows', 'NA')}",
                f"- feature_scope: {global_summary.get('feature_scope', 'NA')}",
                f"- backend: {global_summary.get('model_backend', 'NA')}",
                f"- feature_count: {global_summary.get('feature_count', 'NA')}",
                f"- top5: {top_features_csv(global_dir / 'feature_importance.csv')}",
                "",
            ]
        )
    else:
        lines.extend(["### Global SHAP", "", "- missing", ""])

    biome_root = result_root / f"shap_{scope}_by_biome"
    biome_rows: list[dict[str, str]] = []
    if biome_root.exists():
        for biome_dir in sorted(p for p in biome_root.iterdir() if p.is_dir()):
            summary = parse_key_value_file(biome_dir / "run_summary.txt")
            if not summary:
                continue
            biome_rows.append(
                {
                    "biome": biome_dir.name,
                    "rows": summary.get("rows", "NA"),
                    "feature_count": summary.get("feature_count", "NA"),
                    "backend": summary.get("model_backend", "NA"),
                    "top5_features": top_features_csv(biome_dir / "feature_importance.csv"),
                }
            )
    lines.append("### Biome SHAP")
    lines.append("")
    lines.append(rows_to_markdown_table(biome_rows))
    lines.append("")

    sem_root = result_root / f"sem_{scope}" / "by_biome"
    sem_rows: list[dict[str, str]] = []
    if sem_root.exists():
        for summary_path in sorted(sem_root.glob("*_sem_summary.txt")):
            summary = parse_key_value_file(summary_path)
            if not summary:
                continue
            sem_rows.append(
                {
                    "biome": summary.get("biome", "NA"),
                    "rows": summary.get("rows", "NA"),
                    "feature_scope": summary.get("feature_scope", "NA"),
                    "feature_count": summary.get("feature_count", "NA"),
                    "backend": summary.get("backend", "NA"),
                    "shap_results": summary.get("shap_results", "NA"),
                }
            )
    lines.append("### Biome SEM")
    lines.append("")
    lines.append(rows_to_markdown_table(sem_rows))
    lines.append("")
    return lines


def main() -> None:
    args = parse_args()
    result_root = Path(args.result_root)
    output = Path(args.output) if args.output else result_root / "scope_summary.md"
    lines = [
        "# GLEAM Scope Split Summary",
        "",
        f"- result_root: {result_root}",
        "",
    ]
    for scope in ("predictive", "process", "process_recoverywin"):
        lines.extend(build_scope_section(result_root, scope))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"[DONE] summary saved to {output}")


if __name__ == "__main__":
    main()
