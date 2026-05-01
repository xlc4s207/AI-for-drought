#!/usr/bin/env python
"""Summarize candidate SEM models and generate simple path diagrams."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd

try:
    from semopy import Model, calc_stats
except Exception:  # pragma: no cover - optional dependency in some environments
    Model = None
    calc_stats = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-root", required=True)
    parser.add_argument("--output-csv", default=None)
    parser.add_argument("--output-md", default=None)
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


def normalize_spec_text(spec_text: str) -> str:
    lines: list[str] = []
    for raw_line in str(spec_text).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def read_spec_lines(path: Path) -> list[str]:
    text = normalize_spec_text(path.read_text(encoding="utf-8"))
    return [line for line in text.splitlines() if line]


def parse_spec_edges(spec_lines: Iterable[str]) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for line in spec_lines:
        lhs, rhs = line.split("~", 1)
        lhs = lhs.strip()
        for raw_term in rhs.split("+"):
            term = raw_term.strip()
            if not term:
                continue
            if "*" in term:
                term = term.split("*")[-1].strip()
            edges.append((term, lhs))
    return edges


def infer_mechanism_flags(spec_lines: Iterable[str]) -> tuple[bool, bool, bool]:
    text = "\n".join(spec_lines).lower()
    has_water = any(token in text for token in ("smrz", "sms", "p_minus_et"))
    has_canopy = "lai" in text
    has_baseline = "pre30_" in text
    return has_water, has_canopy, has_baseline


def direct_target_predictors(estimates_df: pd.DataFrame, target: str) -> str:
    if estimates_df.empty:
        return ""
    required = {"lval", "op", "rval"}
    if not required.issubset(estimates_df.columns):
        return ""
    subset = estimates_df[(estimates_df["lval"] == target) & (estimates_df["op"] == "~")]
    values = subset["rval"].dropna().astype(str).tolist()
    return ", ".join(values)


def safe_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def compute_fit_statistics(spec_text: str, dataset_path: Path | None) -> dict[str, float | None]:
    keys = [
        "DoF",
        "chi2",
        "chi2 p-value",
        "CFI",
        "GFI",
        "AGFI",
        "NFI",
        "TLI",
        "RMSEA",
        "AIC",
        "BIC",
        "LogLik",
    ]
    empty = {key: None for key in keys}
    if Model is None or calc_stats is None or dataset_path is None or not dataset_path.exists():
        return empty

    dataset = pd.read_parquet(dataset_path)
    model = Model(spec_text)
    model.fit(dataset)
    stats_df = calc_stats(model)
    if stats_df.empty:
        return empty
    row = stats_df.iloc[0].to_dict()
    return {key: safe_float(row.get(key)) for key in keys}


def summarize_candidate_model_dir(model_dir: Path) -> dict[str, object]:
    summary_path = next(model_dir.glob("*_sem_summary.txt"))
    spec_path = next(model_dir.glob("*_model_spec.txt"))
    estimates_path = next(model_dir.glob("*_estimates.csv"))
    dataset_path = next(model_dir.glob("*_sem_dataset.parquet"), None)

    summary = parse_key_value_file(summary_path)
    spec_lines = read_spec_lines(spec_path)
    spec_text = "\n".join(spec_lines)
    estimates_df = pd.read_csv(estimates_path)
    has_water, has_canopy, has_baseline = infer_mechanism_flags(spec_lines)
    target = summary.get("target", "t_recover_to_baseline_abs_peak")
    fit_stats = compute_fit_statistics(spec_text=spec_text, dataset_path=dataset_path)

    return {
        "biome": summary.get("biome", model_dir.parent.name),
        "model_id": model_dir.name,
        "rows": int(summary.get("rows", 0)),
        "feature_count": int(summary.get("feature_count", 0)),
        "backend": summary.get("backend", "NA"),
        "equation_count": len(spec_lines),
        "path_count": int(((estimates_df["op"] == "~").sum()) if "op" in estimates_df.columns else 0),
        "has_water": has_water,
        "has_canopy": has_canopy,
        "has_baseline": has_baseline,
        "target_direct_predictors": direct_target_predictors(estimates_df, target=target),
        "dataset_path": str(dataset_path) if dataset_path else "",
        **fit_stats,
        "summary_path": str(summary_path),
        "model_spec_path": str(spec_path),
        "estimates_path": str(estimates_path),
    }


def mermaid_node_id(name: str) -> str:
    out = []
    for ch in str(name):
        out.append(ch if ch.isalnum() else "_")
    return "".join(out).strip("_") or "node"


def render_mermaid_diagram(spec_text: str, target: str) -> str:
    spec_lines = [line for line in normalize_spec_text(spec_text).splitlines() if line]
    edges = parse_spec_edges(spec_lines)
    lines = ["flowchart LR"]
    seen_nodes: dict[str, str] = {}
    for src, dst in edges:
        for node in (src, dst):
            if node not in seen_nodes:
                node_id = mermaid_node_id(node)
                seen_nodes[node] = node_id
                lines.append(f'    {node_id}["{node}"]')
        lines.append(f"    {seen_nodes[src]} --> {seen_nodes[dst]}")
    target_id = seen_nodes.get(target)
    if target_id:
        lines.append(f"    style {target_id} fill:#f5d0a9,stroke:#8a4b08,stroke-width:2px")
    return "\n".join(lines)


def build_layers(edges: list[tuple[str, str]]) -> list[list[str]]:
    nodes: list[str] = []
    for src, dst in edges:
        if src not in nodes:
            nodes.append(src)
        if dst not in nodes:
            nodes.append(dst)
    indegree = {node: 0 for node in nodes}
    children: dict[str, list[str]] = {node: [] for node in nodes}
    for src, dst in edges:
        children[src].append(dst)
        indegree[dst] += 1
    layers: list[list[str]] = []
    remaining = set(nodes)
    current = [node for node in nodes if indegree[node] == 0]
    while current:
        layers.append(current)
        next_nodes: list[str] = []
        for node in current:
            if node in remaining:
                remaining.remove(node)
            for child in children[node]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    next_nodes.append(child)
        current = [node for node in nodes if node in next_nodes]
    if remaining:
        layers.append([node for node in nodes if node in remaining])
    return layers


def draw_path_diagram(spec_text: str, output_png: Path, target: str) -> None:
    spec_lines = [line for line in normalize_spec_text(spec_text).splitlines() if line]
    edges = parse_spec_edges(spec_lines)
    if not edges:
        return
    layers = build_layers(edges)
    positions: dict[str, tuple[float, float]] = {}
    for x_idx, layer in enumerate(layers):
        count = len(layer)
        for y_idx, node in enumerate(layer):
            y = 0.5 if count == 1 else 1.0 - (y_idx / max(1, count - 1))
            positions[node] = (float(x_idx), float(y))

    fig_w = max(8, len(layers) * 2.2)
    fig_h = max(4, max(len(layer) for layer in layers) * 1.1)
    plt.figure(figsize=(fig_w, fig_h))
    ax = plt.gca()
    ax.set_axis_off()

    for src, dst in edges:
        x1, y1 = positions[src]
        x2, y2 = positions[dst]
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->", color="#556b8d", lw=1.5, shrinkA=18, shrinkB=18),
        )

    for node, (x, y) in positions.items():
        is_target = node == target
        face = "#f5d0a9" if is_target else "#dce9f7"
        edge = "#8a4b08" if is_target else "#355c7d"
        ax.text(
            x,
            y,
            node,
            ha="center",
            va="center",
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.35", facecolor=face, edgecolor=edge, linewidth=1.5),
        )

    xs = [pos[0] for pos in positions.values()]
    ax.set_xlim(min(xs) - 0.8, max(xs) + 0.8)
    ax.set_ylim(-0.1, 1.1)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_png, dpi=180, bbox_inches="tight")
    plt.close()


def rows_to_markdown(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "- missing"
    headers = [
        "biome",
        "model_id",
        "fit_rank_within_biome",
        "rows",
        "feature_count",
        "backend",
        "equation_count",
        "path_count",
        "has_water",
        "has_canopy",
        "has_baseline",
        "CFI",
        "TLI",
        "RMSEA",
        "AIC",
        "BIC",
        "target_direct_predictors",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        values = [str(row.get(header, "")) for header in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def add_fit_rankings(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return summary_df.copy()

    ranked = summary_df.copy()
    metric_specs = [
        ("BIC", True),
        ("AIC", True),
        ("RMSEA", True),
        ("CFI", False),
        ("TLI", False),
    ]
    rank_columns: list[str] = []
    for metric, ascending in metric_specs:
        if metric not in ranked.columns:
            continue
        rank_col = f"{metric.lower().replace(' ', '_')}_rank"
        ranked[rank_col] = ranked.groupby("biome")[metric].rank(method="dense", ascending=ascending)
        rank_columns.append(rank_col)

    if rank_columns:
        ranked["fit_rank_score"] = ranked[rank_columns].sum(axis=1, min_count=len(rank_columns))
        ranked["fit_rank_within_biome"] = ranked.groupby("biome")["fit_rank_score"].rank(
            method="dense",
            ascending=True,
        )
    else:
        ranked["fit_rank_score"] = None
        ranked["fit_rank_within_biome"] = None
    return ranked


def main() -> None:
    args = parse_args()
    result_root = Path(args.result_root)
    output_csv = Path(args.output_csv) if args.output_csv else result_root / "candidate_model_summary.csv"
    output_md = Path(args.output_md) if args.output_md else result_root / "candidate_model_summary.md"

    rows: list[dict[str, object]] = []
    for summary_path in sorted(result_root.glob("*/*/*_sem_summary.txt")):
        model_dir = summary_path.parent
        row = summarize_candidate_model_dir(model_dir)
        rows.append(row)

        spec_path = Path(str(row["model_spec_path"]))
        spec_text = spec_path.read_text(encoding="utf-8")
        target = parse_key_value_file(summary_path).get("target", "t_recover_to_baseline_abs_peak")
        mermaid = render_mermaid_diagram(spec_text, target=target)
        (model_dir / "path_diagram.mmd").write_text(mermaid, encoding="utf-8")
        draw_path_diagram(spec_text, model_dir / "path_diagram.png", target=target)

    summary_df = pd.DataFrame(rows)
    summary_df = add_fit_rankings(summary_df).sort_values(["biome", "fit_rank_within_biome", "model_id"]).reset_index(drop=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(output_csv, index=False)
    output_md.write_text(
        "\n".join(
            [
                "# Candidate SEM Model Summary",
                "",
                f"- result_root: {result_root}",
                f"- model_count: {len(summary_df)}",
                "",
                rows_to_markdown(summary_df.to_dict(orient="records")),
            ]
        ),
        encoding="utf-8",
    )
    print(f"[DONE] summary csv: {output_csv}")
    print(f"[DONE] summary md : {output_md}")


if __name__ == "__main__":
    main()
