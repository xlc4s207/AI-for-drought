#!/usr/bin/env python
"""Apply conservative, manual dependence-plot cleanups for selected biome-feature cases."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
from typing import Iterable
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FEATURE_LABELS = {
    "recoverywin_total_precipitation_mean": "PRE(mean, recoverywin)",
    "recoverywin_total_evaporation_mean": "EVA(mean, recoverywin)",
    "recoverywin_temperature_2m_mean": "TMP(mean, recoverywin)",
    "recoverywin_VPD_mean": "VPD(mean, recoverywin)",
    "recoverywin_SMrz_mean": "SMrz(mean, recoverywin)",
    "recoverywin_lai_total_mean": "LAI(mean, recoverywin)",
    "recoverywin_ssrd_mean": "SSRD(mean, recoverywin)",
    "recoverywin_strd_mean": "STRD(mean, recoverywin)",
    "recoverywin_wind_speed_mean": "WIND(mean, recoverywin)",
    "prepeak_total_precipitation_mean": "PRE(mean, prepeak)",
    "prepeak_total_evaporation_mean": "EVA(mean, prepeak)",
    "prepeak_temperature_2m_mean": "TMP(mean, prepeak)",
    "prepeak_VPD_mean": "VPD(mean, prepeak)",
    "prepeak_SMrz_mean": "SMrz(mean, prepeak)",
    "prepeak_lai_total_mean": "LAI(mean, prepeak)",
    "prepeak_ssrd_mean": "SSRD(mean, prepeak)",
    "prepeak_strd_mean": "STRD(mean, prepeak)",
    "prepeak_wind_speed_mean": "WIND(mean, prepeak)",
    "event_onset_days": "Onset days",
    "event_duration": "Event duration",
    "event_intensity": "Event intensity",
}


ROOTS = {
    "gpp_prepeak": Path(
        "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/"
        "gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome"
    ),
    "reco_prepeak": Path(
        "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/"
        "reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome"
    ),
    "reco_recovery": Path(
        "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/"
        "reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome"
    ),
}


@dataclass(frozen=True)
class AutoRule:
    pass


@dataclass(frozen=True)
class TailRule:
    center: float
    width: float
    direction: str
    quantile: float | None = None
    value_scale: float = 1.0
    shap_threshold: float | None = None


@dataclass(frozen=True)
class RangeRule:
    x_min: float | None = None
    x_max: float | None = None


TARGET_RULES: dict[tuple[str, str, str], tuple[object, ...]] = {
    ("gpp_prepeak", "Cropland", "prepeak_ssrd_mean"): (
        AutoRule(),
    ),
    ("gpp_prepeak", "Cropland", "prepeak_strd_mean"): (
        AutoRule(),
    ),
    ("gpp_prepeak", "Cropland", "prepeak_VPD_mean"): (
        AutoRule(),
    ),
    ("gpp_prepeak", "Grassland", "prepeak_VPD_mean"): (
        AutoRule(),
    ),
    ("gpp_prepeak", "Shrubland", "prepeak_lai_total_mean"): (
        AutoRule(),
    ),
    ("reco_prepeak", "Cropland", "prepeak_lai_total_mean"): (
        AutoRule(),
    ),
    ("reco_prepeak", "Cropland", "prepeak_ssrd_mean"): (
        AutoRule(),
    ),
    ("reco_prepeak", "Cropland", "prepeak_total_precipitation_mean"): (
        RangeRule(x_min=0.0),
    ),
    ("reco_prepeak", "Cropland", "prepeak_VPD_mean"): (
        AutoRule(),
    ),
    ("reco_prepeak", "Forest", "prepeak_total_precipitation_mean"): (
        RangeRule(x_max=200.0),
    ),
    ("reco_prepeak", "Forest", "prepeak_VPD_mean"): (
        AutoRule(),
    ),
    ("reco_prepeak", "Savanna", "prepeak_wind_speed_mean"): (
        AutoRule(),
    ),
    ("reco_prepeak", "Shrubland", "prepeak_lai_total_mean"): (
        AutoRule(),
    ),
    ("reco_prepeak", "Shrubland", "prepeak_wind_speed_mean"): (
        AutoRule(),
    ),
    ("reco_prepeak", "Wetland", "prepeak_lai_total_mean"): (
        AutoRule(),
    ),
    ("reco_recovery", "Cropland", "recoverywin_ssrd_mean"): (
        AutoRule(),
    ),
    ("reco_recovery", "Forest", "recoverywin_lai_total_mean"): (
        AutoRule(),
    ),
    ("reco_recovery", "Forest", "recoverywin_ssrd_mean"): (
        AutoRule(),
    ),
    ("reco_recovery", "Forest", "recoverywin_temperature_2m_mean"): (
        AutoRule(),
    ),
    ("reco_recovery", "Forest", "recoverywin_wind_speed_mean"): (
        AutoRule(),
    ),
    ("reco_recovery", "Grassland", "recoverywin_ssrd_mean"): (
        AutoRule(),
    ),
    ("reco_recovery", "Grassland", "recoverywin_VPD_mean"): (
        AutoRule(),
    ),
    ("reco_recovery", "Savanna", "recoverywin_lai_total_mean"): (
        AutoRule(),
    ),
    ("reco_recovery", "Savanna", "recoverywin_ssrd_mean"): (
        AutoRule(),
    ),
    ("reco_recovery", "Savanna", "recoverywin_strd_mean"): (
        AutoRule(),
    ),
    ("reco_recovery", "Savanna", "recoverywin_temperature_2m_mean"): (
        AutoRule(),
    ),
}


def sanitize_feature_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in name)


SCRIPT_21_PATH = Path(__file__).with_name("21_batch_dependence_plots_fast.py")
SCRIPT_21_SPEC = importlib.util.spec_from_file_location("batch_dependence_fast_module", SCRIPT_21_PATH)
if SCRIPT_21_SPEC is None or SCRIPT_21_SPEC.loader is None:
    raise RuntimeError(f"Unable to load helper module from {SCRIPT_21_PATH}")
batch_dependence_fast_module = importlib.util.module_from_spec(SCRIPT_21_SPEC)
sys.modules[SCRIPT_21_SPEC.name] = batch_dependence_fast_module
SCRIPT_21_SPEC.loader.exec_module(batch_dependence_fast_module)


def apply_rules(x: np.ndarray, y: np.ndarray, rules: Iterable[object]) -> tuple[np.ndarray, int]:
    keep = np.ones(len(x), dtype=bool)
    removed_total = 0
    for rule in rules:
        if isinstance(rule, AutoRule):
            filtered_x, filtered_y, removed = batch_dependence_fast_module.filter_local_vertical_shap_outliers(
                x[keep],
                y[keep],
            )
            new_keep = np.zeros(len(x), dtype=bool)
            if len(filtered_x) > 0:
                remaining_indices = np.flatnonzero(keep)
                used = np.zeros(len(remaining_indices), dtype=bool)
                for fx, fy in zip(filtered_x, filtered_y):
                    candidates = remaining_indices[~used]
                    if len(candidates) == 0:
                        break
                    rel_idx = np.where(~used)[0]
                    match = np.where(
                        np.isclose(x[candidates], fx, rtol=0.0, atol=1e-9)
                        & np.isclose(y[candidates], fy, rtol=0.0, atol=1e-9)
                    )[0]
                    if len(match) == 0:
                        continue
                    chosen_rel = rel_idx[match[0]]
                    used[chosen_rel] = True
                new_keep[remaining_indices[used]] = True
            keep = new_keep
            removed_total += int(removed)
            continue

        if isinstance(rule, RangeRule):
            remove = np.zeros(len(x), dtype=bool)
            if rule.x_min is not None:
                remove |= x < rule.x_min
            if rule.x_max is not None:
                remove |= x > rule.x_max
            removed = int((keep & remove).sum())
            keep &= ~remove
            removed_total += removed
            continue

        if not isinstance(rule, TailRule):
            continue
        center = rule.center * rule.value_scale
        width = rule.width * rule.value_scale
        window_mask = keep & (np.abs(x - center) <= width)
        if window_mask.sum() == 0:
            continue
        if rule.shap_threshold is not None:
            threshold = float(rule.shap_threshold)
        elif rule.quantile is not None:
            threshold = float(np.quantile(y[window_mask], rule.quantile))
        else:
            continue
        if rule.direction == "down":
            remove = window_mask & (y < threshold)
        else:
            remove = window_mask & (y > threshold)
        removed = int(remove.sum())
        keep &= ~remove
        removed_total += removed
    return keep, removed_total


def save_plot(feature: str, x: np.ndarray, y: np.ndarray, output_path: Path, title: str) -> int:
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    density = None
    if len(x) >= 20:
        try:
            bins = min(40, max(10, len(x) // 100))
            counts, xedges, yedges = np.histogram2d(x, y, bins=bins)
            x_idx = np.clip(np.digitize(x, xedges) - 1, 0, counts.shape[0] - 1)
            y_idx = np.clip(np.digitize(y, yedges) - 1, 0, counts.shape[1] - 1)
            density = counts[x_idx, y_idx]
        except Exception:
            density = None

    plt.figure(figsize=(7.8, 5.8))
    plt.axhline(0.0, color="#6e6e6e", linewidth=1.0, linestyle="--", alpha=0.8, zorder=1)
    scatter = plt.scatter(
        x,
        y,
        c=density if density is not None else "#2f6b8a",
        cmap="viridis" if density is not None else None,
        s=12,
        alpha=0.55,
        edgecolors="none",
        zorder=2,
    )
    if density is not None:
        cbar = plt.colorbar(scatter)
        cbar.set_label("Local point density", fontsize=11)
        cbar.ax.tick_params(labelsize=10)
    if len(x) >= 20:
        window = max(9, len(x) // 30)
        trend = pd.Series(y).rolling(window=window, center=True, min_periods=1).mean()
        plt.plot(x, trend.to_numpy(), color="#c83349", linewidth=2.0, alpha=0.9, zorder=3)

    label = FEATURE_LABELS.get(feature, feature)
    plt.xlabel(label, fontsize=12)
    plt.ylabel(f"SHAP value for {label}", fontsize=12)
    plt.title(title, fontsize=13)
    plt.xticks(fontsize=10)
    plt.yticks(fontsize=10)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=220)
    plt.close()
    return int(len(x))


def main() -> None:
    by_root: dict[str, dict[tuple[str, str], tuple[object, ...]]] = {}
    for (root_key, biome, feature), rules in TARGET_RULES.items():
        by_root.setdefault(root_key, {})[(biome, feature)] = rules

    for root_key, root in ROOTS.items():
        if root_key not in by_root:
            continue
        for biome_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
            feat_path = biome_dir / "dependence_sample_features.parquet"
            shap_path = biome_dir / "dependence_sample_shap_values.parquet"
            if not feat_path.exists() or not shap_path.exists():
                continue
            sample = pd.read_parquet(feat_path)
            shap_df = pd.read_parquet(shap_path)
            dep_dir = biome_dir / "dependence_plots"
            filter_index_path = biome_dir / "dependence_plot_filter_index.csv"
            filter_df = pd.read_csv(filter_index_path) if filter_index_path.exists() else pd.DataFrame()
            numbered_index_path = dep_dir / "dependence_plot_index.csv"
            numbered_df = pd.read_csv(numbered_index_path) if numbered_index_path.exists() else None

            total_removed = 0
            for (biome, feature), rules in by_root[root_key].items():
                if biome != biome_dir.name or feature not in sample.columns or feature not in shap_df.columns:
                    continue
                x = pd.to_numeric(sample[feature], errors="coerce").to_numpy(dtype=float)
                y = pd.to_numeric(shap_df[feature], errors="coerce").to_numpy(dtype=float)
                finite = np.isfinite(x) & np.isfinite(y)
                x = x[finite]
                y = y[finite]
                keep, removed = apply_rules(x, y, rules)
                total_removed += removed
                x_plot = x[keep]
                y_plot = y[keep]
                title = f"{biome_dir.name} | {FEATURE_LABELS.get(feature, feature)}"
                plain_path = dep_dir / f"{sanitize_feature_name(feature)}.png"
                points_used = save_plot(feature, x_plot, y_plot, plain_path, title)

                if not filter_df.empty:
                    mask = filter_df["feature"].astype(str) == feature
                    filter_df.loc[mask, "points_used"] = int(points_used)
                    filter_df.loc[mask, "local_tail_removed"] = int(removed)
                    filter_df.loc[mask, "plot_path"] = str(plain_path)

                if numbered_df is not None:
                    mask = numbered_df["feature"].astype(str) == feature
                    if mask.any():
                        numbered_path = Path(str(numbered_df.loc[mask, "plot_path"].iloc[0]))
                        numbered_points = save_plot(feature, x_plot, y_plot, numbered_path, title)
                        numbered_df.loc[mask, "plot_point_count"] = int(numbered_points)
                        numbered_df.loc[mask, "plot_path"] = str(numbered_path)

            if not filter_df.empty:
                filter_df.to_csv(filter_index_path, index=False)
            if numbered_df is not None:
                numbered_df.to_csv(numbered_index_path, index=False)

            summary_path = biome_dir / "dependence_plots_summary.txt"
            if summary_path.exists():
                lines = summary_path.read_text(encoding="utf-8").splitlines()
                updated = []
                replaced_filter = False
                replaced_total = False
                for line in lines:
                    if line.startswith("local_vertical_shap_outlier_filter="):
                        updated.append("local_vertical_shap_outlier_filter=manual_targeted")
                        replaced_filter = True
                    elif line.startswith("local_tail_removed_total="):
                        updated.append(f"local_tail_removed_total={total_removed}")
                        replaced_total = True
                    else:
                        updated.append(line)
                if not replaced_filter:
                    updated.append("local_vertical_shap_outlier_filter=manual_targeted")
                if not replaced_total:
                    updated.append(f"local_tail_removed_total={total_removed}")
                summary_path.write_text("\n".join(updated), encoding="utf-8")

            print(f"[DONE] {root_key} | {biome_dir.name} | removed_total={total_removed}")


if __name__ == "__main__":
    main()
