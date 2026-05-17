#!/usr/bin/env python3
"""Compare 0401 half-unified SEM results against simplified7 by biome."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/results/SEM_conclusion")
OUT_ROOT = ROOT / "sem_halfunified_20260502/comparison_vs_simplified7_20260502"

SCENARIOS = {
    "gpp_prepeak": {
        "half_r2": ROOT / "sem_halfunified_20260502/gpp_code1_flash_smrz_v20260401_halfunified/sem_prepeak/gpp_prepeak_halfunified_0401_r2_summary.csv",
        "half_paths": ROOT / "sem_halfunified_20260502/gpp_code1_flash_smrz_v20260401_halfunified/sem_prepeak/gpp_prepeak_halfunified_0401_path_effect_strengths.csv",
        "simp_r2": ROOT / "gpp_code1_flash_smrz_v20260401_sem_simplified7_20260429/sem_prepeak/gpp_prepeak_simplified7_0401_r2_summary.csv",
        "simp_paths": ROOT / "gpp_code1_flash_smrz_v20260401_sem_simplified7_20260429/sem_prepeak/gpp_prepeak_simplified7_0401_path_effect_strengths.csv",
    },
    "gpp_recoverywin": {
        "half_r2": ROOT / "sem_halfunified_20260502/gpp_code1_flash_smrz_v20260401_halfunified/sem_recoverywin/gpp_recoverywin_halfunified_0401_r2_summary.csv",
        "half_paths": ROOT / "sem_halfunified_20260502/gpp_code1_flash_smrz_v20260401_halfunified/sem_recoverywin/gpp_recoverywin_halfunified_0401_path_effect_strengths.csv",
        "simp_r2": ROOT / "gpp_code1_flash_smrz_v20260401_sem_simplified7_20260429/sem_recoverywin/gpp_recoverywin_simplified7_0401_r2_summary.csv",
        "simp_paths": ROOT / "gpp_code1_flash_smrz_v20260401_sem_simplified7_20260429/sem_recoverywin/gpp_recoverywin_simplified7_0401_path_effect_strengths.csv",
    },
    "reco_prepeak": {
        "half_r2": ROOT / "sem_halfunified_20260502/reco_code1_flash_smrz_v20260401_halfunified/sem_prepeak/reco_prepeak_halfunified_0401_r2_summary.csv",
        "half_paths": ROOT / "sem_halfunified_20260502/reco_code1_flash_smrz_v20260401_halfunified/sem_prepeak/reco_prepeak_halfunified_0401_path_effect_strengths.csv",
        "simp_r2": ROOT / "reco_code1_flash_smrz_v20260401_sem_simplified7_20260429/sem_prepeak/reco_prepeak_simplified7_0401_r2_summary.csv",
        "simp_paths": ROOT / "reco_code1_flash_smrz_v20260401_sem_simplified7_20260429/sem_prepeak/reco_prepeak_simplified7_0401_path_effect_strengths.csv",
    },
    "reco_recoverywin": {
        "half_r2": ROOT / "sem_halfunified_20260502/reco_code1_flash_smrz_v20260401_halfunified/sem_recoverywin/reco_recoverywin_halfunified_0401_r2_summary.csv",
        "half_paths": ROOT / "sem_halfunified_20260502/reco_code1_flash_smrz_v20260401_halfunified/sem_recoverywin/reco_recoverywin_halfunified_0401_path_effect_strengths.csv",
        "simp_r2": ROOT / "reco_code1_flash_smrz_v20260401_sem_simplified7_20260429/sem_recoverywin/reco_recoverywin_simplified7_0401_r2_summary.csv",
        "simp_paths": ROOT / "reco_code1_flash_smrz_v20260401_sem_simplified7_20260429/sem_recoverywin/reco_recoverywin_simplified7_0401_path_effect_strengths.csv",
    },
}


def compare_r2(scenario: str, cfg: dict[str, Path]) -> pd.DataFrame:
    half = pd.read_csv(cfg["half_r2"]).copy()
    simp = pd.read_csv(cfg["simp_r2"]).copy()
    cols = ["biome", "rows", "holdout_r2", "train_r2", "predictor_count"]
    half = half[cols].rename(
        columns={
            "rows": "rows_half",
            "holdout_r2": "holdout_r2_half",
            "train_r2": "train_r2_half",
            "predictor_count": "predictor_count_half",
        }
    )
    simp = simp[cols].rename(
        columns={
            "rows": "rows_simplified7",
            "holdout_r2": "holdout_r2_simplified7",
            "train_r2": "train_r2_simplified7",
            "predictor_count": "predictor_count_simplified7",
        }
    )
    out = half.merge(simp, on="biome", how="outer")
    out.insert(0, "scenario", scenario)
    out["delta_holdout_r2"] = out["holdout_r2_half"] - out["holdout_r2_simplified7"]
    out["delta_train_r2"] = out["train_r2_half"] - out["train_r2_simplified7"]
    out["change_flag"] = out["delta_holdout_r2"].map(
        lambda x: "improved" if pd.notna(x) and x > 0.005 else ("worse" if pd.notna(x) and x < -0.005 else "similar")
    )
    return out.sort_values("biome").reset_index(drop=True)


def compare_paths(scenario: str, cfg: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    half = pd.read_csv(cfg["half_paths"]).copy()
    simp = pd.read_csv(cfg["simp_paths"]).copy()

    key_cols = ["biome", "from", "to"]
    use_cols = key_cols + ["estimate", "abs_estimate", "significance"]
    half = half[use_cols].rename(
        columns={
            "estimate": "estimate_half",
            "abs_estimate": "abs_estimate_half",
            "significance": "significance_half",
        }
    )
    simp = simp[use_cols].rename(
        columns={
            "estimate": "estimate_simplified7",
            "abs_estimate": "abs_estimate_simplified7",
            "significance": "significance_simplified7",
        }
    )
    merged = half.merge(simp, on=key_cols, how="outer")
    merged.insert(0, "scenario", scenario)
    merged["presence"] = merged.apply(
        lambda r: "both"
        if pd.notna(r["estimate_half"]) and pd.notna(r["estimate_simplified7"])
        else ("half_only" if pd.notna(r["estimate_half"]) else "simplified7_only"),
        axis=1,
    )
    merged["delta_estimate"] = merged["estimate_half"] - merged["estimate_simplified7"]
    merged["delta_abs_estimate"] = merged["abs_estimate_half"] - merged["abs_estimate_simplified7"]

    target_only = merged[merged["to"] == "t_recover_to_baseline_abs_peak"].copy()
    target_only["interpretation"] = target_only.apply(_interpret_target_row, axis=1)
    return merged.sort_values(["biome", "to", "from"]).reset_index(drop=True), target_only.sort_values(
        ["biome", "presence", "delta_abs_estimate"], ascending=[True, True, False]
    ).reset_index(drop=True)


def _interpret_target_row(row: pd.Series) -> str:
    presence = row["presence"]
    if presence == "half_only":
        return "new direct path in half-unified"
    if presence == "simplified7_only":
        return "removed direct path from simplified7"
    delta = row["delta_abs_estimate"]
    if pd.isna(delta):
        return ""
    if delta > 0.05:
        return "stronger direct effect in half-unified"
    if delta < -0.05:
        return "weaker direct effect in half-unified"
    return "similar direct effect"


def build_markdown(r2_all: pd.DataFrame, target_all: pd.DataFrame) -> str:
    lines = [
        "# Half-unified vs Simplified7 SEM Comparison",
        "",
        "This note compares 0401 half-unified SEM against the previous simplified7 version by biome.",
        "",
    ]
    for scenario in SCENARIOS:
        lines.append(f"## {scenario}")
        lines.append("")
        r2_df = r2_all[r2_all["scenario"] == scenario].copy()
        lines.append("| biome | half_holdout_r2 | simplified7_holdout_r2 | delta | flag |")
        lines.append("|---|---:|---:|---:|---|")
        for _, row in r2_df.iterrows():
            lines.append(
                f"| {row['biome']} | {row['holdout_r2_half']:.6f} | {row['holdout_r2_simplified7']:.6f} | {row['delta_holdout_r2']:.6f} | {row['change_flag']} |"
            )
        lines.append("")
        lines.append("### Target-path changes")
        lines.append("")
        lines.append("| biome | from | half_est | simp7_est | delta_abs | interpretation |")
        lines.append("|---|---|---:|---:|---:|---|")
        subset = target_all[target_all["scenario"] == scenario].copy()
        for _, row in subset.iterrows():
            half_est = "" if pd.isna(row["estimate_half"]) else f"{row['estimate_half']:.6f}"
            simp_est = "" if pd.isna(row["estimate_simplified7"]) else f"{row['estimate_simplified7']:.6f}"
            delta_abs = "" if pd.isna(row["delta_abs_estimate"]) else f"{row['delta_abs_estimate']:.6f}"
            lines.append(
                f"| {row['biome']} | {row['from']} | {half_est} | {simp_est} | {delta_abs} | {row['interpretation']} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    r2_frames = []
    path_frames = []
    target_frames = []
    for scenario, cfg in SCENARIOS.items():
        r2_df = compare_r2(scenario, cfg)
        all_paths, target_paths = compare_paths(scenario, cfg)
        r2_df.to_csv(OUT_ROOT / f"{scenario}_r2_comparison.csv", index=False)
        all_paths.to_csv(OUT_ROOT / f"{scenario}_all_path_comparison.csv", index=False)
        target_paths.to_csv(OUT_ROOT / f"{scenario}_target_path_comparison.csv", index=False)
        r2_frames.append(r2_df)
        path_frames.append(all_paths)
        target_frames.append(target_paths)

    r2_all = pd.concat(r2_frames, ignore_index=True)
    path_all = pd.concat(path_frames, ignore_index=True)
    target_all = pd.concat(target_frames, ignore_index=True)
    r2_all.to_csv(OUT_ROOT / "all_scenarios_r2_comparison.csv", index=False)
    path_all.to_csv(OUT_ROOT / "all_scenarios_all_path_comparison.csv", index=False)
    target_all.to_csv(OUT_ROOT / "all_scenarios_target_path_comparison.csv", index=False)
    (OUT_ROOT / "comparison_summary.md").write_text(build_markdown(r2_all, target_all), encoding="utf-8")


if __name__ == "__main__":
    main()
