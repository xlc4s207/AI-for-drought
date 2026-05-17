#!/usr/bin/env python3
"""Grouped variance partitioning / commonality analysis for prepeak predictors.

This trial decomposes holdout R2 by mechanism groups:

- Energy: SSRD, STRD, TMP
- Water: Pre, EVA, SMrz
- AtmosDemand: VPD, Wind
- EventSeverity: Duration, Intensity

For each metric x biome, a LightGBM model is trained for every non-empty group
combination. Commonality coefficients are obtained by Mobius inversion of the
subset R2 table. The result separates unique and shared explanatory power at the
mechanism-group level.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import importlib.util
from itertools import combinations
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


ROOT = Path("/home/xulc/flash_drought")
GLEAM = ROOT / "process/SEM_analysis0401/codex/GLEAM"
PREPEAK_SCRIPT = GLEAM / "plots2/prepeak_shap_nomulticollinearity/run_prepeak_nomulticollinearity_shap.py"
OUT = GLEAM / "plots2/prepeak_shap_nomulticollinearity/variance_partitioning_commonality_20260516"
TARGET = "t_recover_to_baseline_abs_peak"
BIOMES = ("Forest", "Grassland", "Savanna", "Cropland", "Shrubland")
METRICS = ("GPP", "RECO")
RANDOM_STATE = 42


spec = importlib.util.spec_from_file_location("prepeak_nomulticollinearity_for_commonality", PREPEAK_SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to import {PREPEAK_SCRIPT}")
pre = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pre
spec.loader.exec_module(pre)


TABLES = {
    "GPP": GLEAM / "data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet",
    "RECO": GLEAM / "data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet",
}

GROUPS = {
    "Energy": ("SSRD", "STRD", "TMP"),
    "Water": ("Pre", "EVA", "SMrz"),
    "AtmosDemand": ("VPD", "Wind"),
    "EventSeverity": ("Duration", "Intensity"),
}

GROUP_ORDER = tuple(GROUPS)
GROUP_COLORS = {
    "Energy": "#fdae61",
    "Water": "#2b83ba",
    "AtmosDemand": "#abdda4",
    "EventSeverity": "#d7191c",
}


def all_group_subsets() -> list[tuple[str, ...]]:
    out: list[tuple[str, ...]] = []
    for r in range(1, len(GROUP_ORDER) + 1):
        out.extend(combinations(GROUP_ORDER, r))
    return out


def subset_key(groups: tuple[str, ...]) -> str:
    return "+".join(groups)


def subset_feature_names(groups: tuple[str, ...]) -> list[str]:
    cols: list[str] = []
    for group in groups:
        cols.extend(GROUPS[group])
    return cols


def load_raw_xy(metric: str, biome: str, row_limit: int) -> tuple[pd.DataFrame, pd.Series]:
    df_metric = pre.finalize_feature_table(pd.read_parquet(TABLES[metric]))
    sub = pre.filter_analysis_subset(
        df_metric,
        metric=metric,
        code_id="code1",
        biome=biome,
        drought_type="flash",
        soil_layer="SMrz",
    )
    if len(sub) > row_limit:
        sub = sub.sample(n=row_limit, random_state=RANDOM_STATE).sort_index().reset_index(drop=True)
    raw, y = pre.prepare_raw_xy(sub)
    return raw.reset_index(drop=True), y.reset_index(drop=True)


def fit_subset_model(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    groups: tuple[str, ...],
    n_estimators: int,
    model_threads: int,
) -> dict[str, object]:
    cols = subset_feature_names(groups)
    backend = pre.resolve_model_backend("lightgbm")
    model = pre.fit_tree_model(
        X_train[cols],
        y_train,
        backend=backend,
        random_state=RANDOM_STATE,
        n_estimators=n_estimators,
        n_jobs=model_threads,
    )
    pred = model.predict(X_test[cols])
    return {
        "subset": subset_key(groups),
        "groups": "|".join(groups),
        "n_groups": len(groups),
        "features": ",".join(cols),
        "n_features": len(cols),
        "r2_holdout": float(r2_score(y_test, pred)),
        "rmse_holdout": float(mean_squared_error(y_test, pred) ** 0.5),
        "mae_holdout": float(mean_absolute_error(y_test, pred)),
    }


def commonality_from_r2(subset_r2: dict[frozenset[str], float]) -> dict[frozenset[str], float]:
    values: dict[frozenset[str], float] = {}
    groups = list(GROUP_ORDER)
    for r in range(1, len(groups) + 1):
        for subset in combinations(groups, r):
            S = frozenset(subset)
            coef = 0.0
            for k in range(1, len(S) + 1):
                for T_tuple in combinations(S, k):
                    T = frozenset(T_tuple)
                    coef += ((-1) ** (len(S) - len(T))) * subset_r2[T]
            values[S] = float(coef)
    return values


def summarize_groups(commonality: dict[frozenset[str], float], subset_r2: dict[frozenset[str], float]) -> pd.DataFrame:
    full = frozenset(GROUP_ORDER)
    full_r2 = subset_r2[full]
    rows = []
    for group in GROUP_ORDER:
        singleton = frozenset([group])
        without = frozenset(g for g in GROUP_ORDER if g != group)
        unique = commonality.get(singleton, np.nan)
        shared = sum(v for k, v in commonality.items() if group in k and len(k) > 1)
        total_commonality = unique + shared
        drop_delta = full_r2 - subset_r2.get(without, 0.0)
        rows.append(
            {
                "group": group,
                "singleton_r2": subset_r2[singleton],
                "unique_commonality": unique,
                "shared_commonality": shared,
                "total_commonality_involving_group": total_commonality,
                "drop_group_delta_r2": drop_delta,
                "full_model_r2": full_r2,
                "unique_percent_of_full_r2": unique / full_r2 * 100.0 if full_r2 else np.nan,
                "drop_delta_percent_of_full_r2": drop_delta / full_r2 * 100.0 if full_r2 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def plot_components(component_df: pd.DataFrame, metric: str, biome: str, out_dir: Path) -> None:
    df = component_df.sort_values(["n_groups", "commonality"], ascending=[True, False]).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    colors = ["#4daf4a" if v >= 0 else "#984ea3" for v in df["commonality"]]
    ax.barh(df["subset"], df["commonality"], color=colors, alpha=0.85)
    ax.axvline(0, color="#333333", lw=0.8)
    ax.set_xlabel("Commonality coefficient (holdout R2 component)")
    ax.set_ylabel("")
    ax.set_title(f"{metric} {biome}: group commonality components")
    ax.grid(axis="x", alpha=0.18, ls="--")
    fig.tight_layout()
    fig.savefig(out_dir / f"{metric}_{biome}_commonality_components.png", dpi=240)
    plt.close(fig)


def run_metric_biome(metric: str, biome: str, args: argparse.Namespace) -> dict[str, object]:
    model_dir = OUT / "tables" / f"{metric}_{biome}"
    fig_dir = OUT / "figures"
    model_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    X, y = load_raw_xy(metric, biome, args.row_limit)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=args.test_size, random_state=RANDOM_STATE)
    subset_rows = [
        fit_subset_model(
            X_train,
            X_test,
            y_train,
            y_test,
            groups,
            n_estimators=args.n_estimators,
            model_threads=args.model_threads,
        )
        for groups in all_group_subsets()
    ]
    subset_df = pd.DataFrame(subset_rows).sort_values(["n_groups", "subset"]).reset_index(drop=True)
    subset_df.insert(0, "biome", biome)
    subset_df.insert(0, "metric", metric)
    subset_df.to_csv(model_dir / "subset_model_r2.csv", index=False)

    subset_r2 = {
        frozenset(row["groups"].split("|")): float(row["r2_holdout"])
        for _, row in subset_df.iterrows()
    }
    commonality = commonality_from_r2(subset_r2)
    comp_rows = []
    full_r2 = subset_r2[frozenset(GROUP_ORDER)]
    for groups, value in commonality.items():
        ordered = tuple(g for g in GROUP_ORDER if g in groups)
        comp_rows.append(
            {
                "metric": metric,
                "biome": biome,
                "subset": subset_key(ordered),
                "groups": "|".join(ordered),
                "n_groups": len(ordered),
                "commonality": value,
                "percent_of_full_r2": value / full_r2 * 100.0 if full_r2 else np.nan,
            }
        )
    component_df = pd.DataFrame(comp_rows).sort_values(["n_groups", "subset"]).reset_index(drop=True)
    component_df.to_csv(model_dir / "commonality_components.csv", index=False)
    plot_components(component_df, metric, biome, fig_dir)

    group_df = summarize_groups(commonality, subset_r2)
    group_df.insert(0, "biome", biome)
    group_df.insert(0, "metric", metric)
    group_df.to_csv(model_dir / "group_summary.csv", index=False)

    return {
        "metric": metric,
        "biome": biome,
        "rows": int(len(X)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "full_model_r2": float(full_r2),
        "max_single_group_r2": float(max(v for k, v in subset_r2.items() if len(k) == 1)),
        "n_estimators": args.n_estimators,
        "row_limit": args.row_limit,
    }


def plot_overview(summary: pd.DataFrame, group_summary: pd.DataFrame) -> None:
    fig_dir = OUT / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    order = summary.sort_values(["metric", "biome"]).reset_index(drop=True)
    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(11.2, 5.2))
    ax.bar(x, order["full_model_r2"], color=["#2b83ba" if m == "GPP" else "#d7191c" for m in order["metric"]], alpha=0.82)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{m}\n{b}" for m, b in zip(order["metric"], order["biome"])], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Full group model holdout R2")
    ax.set_title("Prepeak group variance partitioning: full-model explanatory power")
    ax.grid(axis="y", ls="--", alpha=0.22)
    fig.tight_layout()
    fig.savefig(fig_dir / "full_model_r2_by_metric_biome.png", dpi=260)
    plt.close(fig)

    pivot = group_summary.pivot_table(index=["metric", "biome"], columns="group", values="drop_group_delta_r2", aggfunc="first")
    pivot = pivot.reindex(index=pd.MultiIndex.from_frame(order[["metric", "biome"]]))
    fig, ax = plt.subplots(figsize=(11.8, 5.4))
    bottom = np.zeros(len(pivot))
    for group in GROUP_ORDER:
        vals = pivot[group].to_numpy(dtype=float)
        ax.bar(np.arange(len(pivot)), vals, bottom=bottom, label=group, color=GROUP_COLORS[group], alpha=0.84)
        bottom += vals
    ax.set_xticks(np.arange(len(pivot)))
    ax.set_xticklabels([f"{i[0]}\n{i[1]}" for i in pivot.index], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Drop-group delta R2")
    ax.set_title("Incremental predictive value by mechanism group")
    ax.grid(axis="y", ls="--", alpha=0.22)
    ax.legend(frameon=False, ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "drop_group_delta_r2_by_group.png", dpi=260)
    plt.close(fig)


def write_readme(summary: pd.DataFrame) -> None:
    lines = [
        "# Prepeak Grouped Variance Partitioning / Commonality Trial",
        "",
        "This folder tests mechanism-group variance partitioning as an alternative way to quantify independent and shared contributions under multicollinearity.",
        "",
        "Mechanism groups:",
        "- Energy: SSRD, STRD, TMP",
        "- Water: Pre, EVA, SMrz",
        "- AtmosDemand: VPD, Wind",
        "- EventSeverity: Duration, Intensity",
        "",
        "For each metric x biome, LightGBM models are trained for all 15 non-empty group combinations. Holdout R2 values are decomposed into commonality coefficients by Mobius inversion.",
        "",
        "Important interpretation:",
        "- `unique_commonality` is the component uniquely attributable to one group in the commonality decomposition.",
        "- `shared_commonality` is the sum of commonality components involving the group and at least one other group.",
        "- `drop_group_delta_r2` is the full-model R2 loss when the group is removed; it is often the most intuitive model-performance contribution.",
        "- Negative commonality can occur under suppression or strong multicollinearity.",
        "",
        "Summary:",
        "```csv",
        summary.to_csv(index=False).strip(),
        "```",
        "",
    ]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", nargs="+", default=list(METRICS))
    parser.add_argument("--biomes", nargs="+", default=list(BIOMES))
    parser.add_argument("--row-limit", type=int, default=15000)
    parser.add_argument("--test-size", type=float, default=0.20)
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--model-threads", type=int, default=4)
    parser.add_argument("--n-jobs", type=int, default=2)
    return parser.parse_args()


def run_task(task: tuple[str, str, argparse.Namespace]) -> dict[str, object]:
    metric, biome, args = task
    print(f"[RUN] {metric} | {biome}", flush=True)
    result = run_metric_biome(metric, biome, args)
    print(f"[DONE] {metric} | {biome}", flush=True)
    return result


def main() -> None:
    args = parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = [(metric, biome, args) for metric in args.metrics for biome in args.biomes]
    summaries = []
    if args.n_jobs <= 1:
        for task in tasks:
            summaries.append(run_task(task))
            pd.DataFrame(summaries).to_csv(OUT / "variance_partitioning_model_summary.csv", index=False)
    else:
        with ProcessPoolExecutor(max_workers=args.n_jobs) as executor:
            futures = [executor.submit(run_task, task) for task in tasks]
            for future in as_completed(futures):
                summaries.append(future.result())
                pd.DataFrame(summaries).to_csv(OUT / "variance_partitioning_model_summary.csv", index=False)
    summary = pd.DataFrame(summaries).sort_values(["metric", "biome"]).reset_index(drop=True)
    summary.to_csv(OUT / "variance_partitioning_model_summary.csv", index=False)
    subset_all = pd.concat([pd.read_csv(p) for p in (OUT / "tables").glob("*/subset_model_r2.csv")], ignore_index=True)
    comp_all = pd.concat([pd.read_csv(p) for p in (OUT / "tables").glob("*/commonality_components.csv")], ignore_index=True)
    group_all = pd.concat([pd.read_csv(p) for p in (OUT / "tables").glob("*/group_summary.csv")], ignore_index=True)
    subset_all.to_csv(OUT / "subset_model_r2_all.csv", index=False)
    comp_all.to_csv(OUT / "commonality_components_all.csv", index=False)
    group_all.to_csv(OUT / "group_summary_all.csv", index=False)
    plot_overview(summary, group_all)
    write_readme(summary)
    print(OUT)


if __name__ == "__main__":
    main()
