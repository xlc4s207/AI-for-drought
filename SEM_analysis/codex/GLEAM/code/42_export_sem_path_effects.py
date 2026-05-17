#!/usr/bin/env python
"""Export SEM path strengths and R2 summaries from biome-level SEM results."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sem-dir", required=True, help="Directory containing *_sem_summary.txt and *_estimates.csv")
    parser.add_argument("--scope-name", required=True, help="Short scope label used in output titles")
    parser.add_argument("--output-prefix", required=True, help="Output path prefix without extension")
    return parser.parse_args()


def parse_summary_metrics(path: Path) -> dict[str, str]:
    metrics: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        metrics[key.strip()] = value.strip()
    return metrics


def significance_label(value: object) -> str:
    try:
        p = float(value)
    except (TypeError, ValueError):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def export(sem_dir: Path, scope_name: str, output_prefix: Path) -> None:
    path_rows: list[dict[str, object]] = []
    r2_rows: list[dict[str, object]] = []

    for summary_path in sorted(sem_dir.glob("*_sem_summary.txt")):
        prefix = summary_path.name.replace("_sem_summary.txt", "")
        estimates_path = sem_dir / f"{prefix}_estimates.csv"
        if not estimates_path.exists():
            continue
        metrics = parse_summary_metrics(summary_path)
        biome = metrics.get("biome", prefix)
        r2_rows.append(
            {
                "biome": biome,
                "scope": scope_name,
                "rows": int(float(metrics.get("rows", "0"))),
                "holdout_r2": float(metrics.get("target_equation_r2_holdout_split", "nan")),
                "train_r2": float(metrics.get("target_equation_r2_train_split", "nan")),
                "predictor_count": int(float(metrics.get("target_equation_predictor_count", "0"))),
            }
        )
        estimates = pd.read_csv(estimates_path)
        subset = estimates[estimates["op"].astype(str) == "~"].copy()
        subset["Estimate"] = pd.to_numeric(subset["Estimate"], errors="coerce")
        subset["p-value"] = pd.to_numeric(subset["p-value"], errors="coerce")
        subset = subset[subset["Estimate"].notna()].copy()
        subset["abs_estimate"] = subset["Estimate"].abs()
        subset = subset.sort_values(["lval", "abs_estimate"], ascending=[True, False])
        for _, row in subset.iterrows():
            path_rows.append(
                {
                    "biome": biome,
                    "scope": scope_name,
                    "from": str(row["rval"]),
                    "to": str(row["lval"]),
                    "estimate": float(row["Estimate"]),
                    "abs_estimate": float(row["abs_estimate"]),
                    "p_value": float(row["p-value"]) if pd.notna(row["p-value"]) else None,
                    "significance": significance_label(row["p-value"]),
                }
            )

    path_df = pd.DataFrame(path_rows)
    r2_df = pd.DataFrame(r2_rows).sort_values("biome").reset_index(drop=True)

    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    path_df.to_csv(output_prefix.with_name(output_prefix.name + "_path_effect_strengths.csv"), index=False)
    r2_df.to_csv(output_prefix.with_name(output_prefix.name + "_r2_summary.csv"), index=False)

    md_lines = [
        f"# {scope_name.title()} Path Effect Strengths",
        "",
        "Columns: `biome`, `from`, `to`, `estimate`, `abs_estimate`, `significance`",
        "",
        "## R2 Summary",
        "",
        "| biome | rows | holdout_r2 | train_r2 | predictor_count |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, row in r2_df.iterrows():
        md_lines.append(
            f"| {row['biome']} | {int(row['rows'])} | {row['holdout_r2']:.6f} | {row['train_r2']:.6f} | {int(row['predictor_count'])} |"
        )

    for biome in r2_df["biome"]:
        biome_df = path_df[path_df["biome"] == biome].copy()
        biome_df = biome_df.sort_values(["to", "abs_estimate"], ascending=[True, False])
        md_lines.extend(
            [
                "",
                f"## {biome}",
                "",
                "| from | to | estimate | abs_estimate | significance |",
                "|---|---|---:|---:|---|",
            ]
        )
        for _, row in biome_df.iterrows():
            md_lines.append(
                f"| {row['from']} | {row['to']} | {row['estimate']:.6f} | {row['abs_estimate']:.6f} | {row['significance']} |"
            )

    output_prefix.with_name(output_prefix.name + "_path_effect_strengths.md").write_text(
        "\n".join(md_lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    export(Path(args.sem_dir), args.scope_name, Path(args.output_prefix))


if __name__ == "__main__":
    main()
