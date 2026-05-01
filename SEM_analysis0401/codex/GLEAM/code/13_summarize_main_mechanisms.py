#!/usr/bin/env python
"""Summarize primary SEM mechanism models across biomes."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


TARGET_DEFAULT = "t_recover_to_baseline_abs_peak"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-root", required=True)
    parser.add_argument("--output-csv", default=None)
    parser.add_argument("--output-effects-csv", default=None)
    parser.add_argument("--output-md", default=None)
    return parser.parse_args()


def select_primary_mechanism_models(summary_df: pd.DataFrame) -> pd.DataFrame:
    work = summary_df.copy()
    work = work[work["model_id"] != "M0_direct"].reset_index(drop=True)
    if work.empty:
        return work
    work["mechanism_rank"] = work.groupby("biome")["fit_rank_score"].rank(method="dense", ascending=True)
    selected = work.loc[work.groupby("biome")["mechanism_rank"].idxmin()].copy()
    return selected.sort_values(["biome", "model_id"]).reset_index(drop=True)


def significant_regression_rows(estimates_df: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    work = estimates_df.copy()
    if work.empty:
        return work.iloc[0:0].copy()
    work = work[work["op"] == "~"].copy()
    if "p-value" in work.columns:
        work["p-value"] = pd.to_numeric(work["p-value"], errors="coerce")
        work = work[work["p-value"].notna() & (work["p-value"] < alpha)].copy()
    work["Estimate"] = pd.to_numeric(work["Estimate"], errors="coerce")
    return work[work["Estimate"].notna()].reset_index(drop=True)


def build_children_map(estimates_df: pd.DataFrame) -> tuple[dict[str, list[str]], dict[tuple[str, str], float]]:
    children: dict[str, list[str]] = {}
    coef_map: dict[tuple[str, str], float] = {}
    for row in estimates_df.to_dict(orient="records"):
        src = str(row["rval"])
        dst = str(row["lval"])
        coef = float(row["Estimate"])
        children.setdefault(src, []).append(dst)
        coef_map[(src, dst)] = coef
    return children, coef_map


def enumerate_directed_paths(
    children: dict[str, list[str]],
    source: str,
    target: str,
    path: list[str] | None = None,
) -> list[list[str]]:
    path = (path or []) + [source]
    if source == target:
        return [path]
    paths: list[list[str]] = []
    for child in children.get(source, []):
        if child in path:
            continue
        paths.extend(enumerate_directed_paths(children, child, target, path))
    return paths


def path_effect(path: list[str], coef_map: dict[tuple[str, str], float]) -> float:
    effect = 1.0
    for src, dst in zip(path[:-1], path[1:]):
        effect *= coef_map[(src, dst)]
    return effect


def compute_effect_decomposition(
    estimates_df: pd.DataFrame,
    target: str = TARGET_DEFAULT,
    exogenous_vars: list[str] | None = None,
) -> pd.DataFrame:
    sig = significant_regression_rows(estimates_df)
    if sig.empty:
        return pd.DataFrame(columns=["source", "direct_effect", "indirect_effect", "total_effect", "indirect_path_count"])

    children, coef_map = build_children_map(sig)
    if exogenous_vars is None:
        lvals = set(sig["lval"].astype(str))
        rvals = set(sig["rval"].astype(str))
        exogenous_vars = sorted(rvals - lvals)

    rows: list[dict[str, object]] = []
    for source in exogenous_vars:
        paths = enumerate_directed_paths(children, source, target)
        direct = 0.0
        indirect = 0.0
        indirect_path_count = 0
        for path in paths:
            eff = path_effect(path, coef_map)
            if len(path) == 2:
                direct += eff
            elif len(path) > 2:
                indirect += eff
                indirect_path_count += 1
        rows.append(
            {
                "source": source,
                "direct_effect": direct,
                "indirect_effect": indirect,
                "total_effect": direct + indirect,
                "indirect_path_count": indirect_path_count,
            }
        )
    return pd.DataFrame(rows).sort_values("source").reset_index(drop=True)


def sign_text(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def summarize_primary_model(row: dict[str, object]) -> tuple[dict[str, object], pd.DataFrame]:
    estimates_path = Path(str(row["estimates_path"]))
    estimates_df = pd.read_csv(estimates_path)
    sig = significant_regression_rows(estimates_df)

    target_direct = sig[sig["lval"] == TARGET_DEFAULT][["rval", "Estimate", "p-value"]].copy()
    target_direct = target_direct.sort_values("Estimate", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)

    effect_df = compute_effect_decomposition(sig, target=TARGET_DEFAULT)
    effect_df.insert(0, "model_id", str(row["model_id"]))
    effect_df.insert(0, "biome", str(row["biome"]))

    top_direct = ""
    if not target_direct.empty:
        first = target_direct.iloc[0]
        top_direct = f"{first['rval']} ({sign_text(float(first['Estimate']))}, {float(first['Estimate']):.3f})"

    strongest_total = ""
    if not effect_df.empty:
        ranked = effect_df.iloc[effect_df["total_effect"].abs().argmax()]
        strongest_total = f"{ranked['source']} ({sign_text(float(ranked['total_effect']))}, {float(ranked['total_effect']):.3f})"

    summary_row = {
        "biome": row["biome"],
        "model_id": row["model_id"],
        "mechanism_rank": row.get("mechanism_rank"),
        "fit_rank_within_biome": row.get("fit_rank_within_biome"),
        "CFI": row.get("CFI"),
        "TLI": row.get("TLI"),
        "RMSEA": row.get("RMSEA"),
        "AIC": row.get("AIC"),
        "BIC": row.get("BIC"),
        "top_direct_path": top_direct,
        "strongest_total_driver": strongest_total,
        "direct_target_paths": "; ".join(
            f"{rec['rval']} ({sign_text(float(rec['Estimate']))}, {float(rec['Estimate']):.3f}, p={float(rec['p-value']):.3g})"
            for rec in target_direct.to_dict(orient="records")
        ),
    }
    return summary_row, effect_df


def rows_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "- missing"
    headers = list(df.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in df.iterrows():
        values = [str(row.get(col, "")) for col in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def render_markdown(
    primary_df: pd.DataFrame,
    effects_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    result_root: Path,
) -> str:
    sections = [
        "# Primary SEM Mechanism Summary",
        "",
        f"- result_root: {result_root}",
        "- note: all SEM variables were z-score standardized before fitting, so coefficients can be read as standardized path coefficients.",
        "- selection rule: exclude `M0_direct`, then choose the lowest `fit_rank_score` within each biome as the primary mechanism model.",
        "",
        "## Primary Models",
        "",
        rows_to_markdown(primary_df[[
            "biome",
            "model_id",
            "CFI",
            "TLI",
            "RMSEA",
            "AIC",
            "BIC",
            "top_direct_path",
            "strongest_total_driver",
        ]]),
        "",
        "## Baseline Comparison",
        "",
        rows_to_markdown(baseline_df[[
            "biome",
            "model_id",
            "CFI",
            "TLI",
            "RMSEA",
            "AIC",
            "BIC",
        ]]),
        "",
        "## Biome Notes",
        "",
    ]

    for _, row in primary_df.iterrows():
        biome = row["biome"]
        model_id = row["model_id"]
        subset = effects_df[effects_df["biome"] == biome].copy()
        subset = subset.sort_values("total_effect", key=lambda s: s.abs(), ascending=False)
        sections.extend(
            [
                f"### {biome}",
                "",
                f"- selected mechanism model: `{model_id}`",
                f"- direct target paths: {row['direct_target_paths']}",
                "- total driver effects:",
                rows_to_markdown(subset[["source", "direct_effect", "indirect_effect", "total_effect", "indirect_path_count"]]),
                "",
            ]
        )
    return "\n".join(sections).strip() + "\n"


def main() -> None:
    args = parse_args()
    result_root = Path(args.result_root)
    output_csv = Path(args.output_csv) if args.output_csv else result_root / "primary_mechanism_models.csv"
    output_effects_csv = (
        Path(args.output_effects_csv) if args.output_effects_csv else result_root / "primary_mechanism_effects.csv"
    )
    output_md = Path(args.output_md) if args.output_md else result_root / "primary_mechanism_summary.md"

    summary_df = pd.read_csv(result_root / "candidate_model_summary.csv")
    primary_models = select_primary_mechanism_models(summary_df)
    baseline_df = summary_df[summary_df["model_id"] == "M0_direct"].copy().sort_values("biome").reset_index(drop=True)

    primary_rows: list[dict[str, object]] = []
    effects_frames: list[pd.DataFrame] = []
    for row in primary_models.to_dict(orient="records"):
        primary_row, effect_df = summarize_primary_model(row)
        primary_rows.append(primary_row)
        effects_frames.append(effect_df)

    primary_df = pd.DataFrame(primary_rows).sort_values("biome").reset_index(drop=True)
    effects_df = pd.concat(effects_frames, ignore_index=True) if effects_frames else pd.DataFrame()

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_effects_csv.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    primary_df.to_csv(output_csv, index=False)
    effects_df.to_csv(output_effects_csv, index=False)
    output_md.write_text(render_markdown(primary_df, effects_df, baseline_df, result_root), encoding="utf-8")

    print(f"[DONE] primary mechanism csv: {output_csv}")
    print(f"[DONE] primary mechanism effects: {output_effects_csv}")
    print(f"[DONE] primary mechanism summary: {output_md}")


if __name__ == "__main__":
    main()
