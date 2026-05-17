#!/usr/bin/env python3
"""Redraw orthogonal-decomposition Pre_z dependence plots after trimming tails."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis0401/codex/GLEAM/plots2/prepeak_shap_nomulticollinearity")
ORTHO = ROOT / "orthogonal_decomposition"
FEATURE = "Pre_z"
DISPLAY = "Pre"
LOW_Q = 0.01
HIGH_Q = 0.99


def redraw(folder: Path) -> dict[str, object]:
    sample = pd.read_parquet(folder / "dependence_sample_features.parquet", columns=[FEATURE])
    shap_df = pd.read_parquet(folder / "dependence_sample_shap_values.parquet", columns=[FEATURE])
    x_all = pd.to_numeric(sample[FEATURE], errors="coerce").to_numpy(dtype=float)
    y_all = pd.to_numeric(shap_df[FEATURE], errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(x_all) & np.isfinite(y_all)
    x = x_all[finite]
    y = y_all[finite]
    if len(x) == 0:
        raise ValueError(f"No finite {FEATURE} values in {folder}")

    low = float(np.nanquantile(x, LOW_Q))
    high = float(np.nanquantile(x, HIGH_Q))
    keep = (x >= low) & (x <= high)
    x_trim = x[keep]
    y_trim = y[keep]
    order = np.argsort(x_trim)
    x_trim = x_trim[order]
    y_trim = y_trim[order]

    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.axhline(0, color="#777777", lw=0.9, ls="--")
    ax.scatter(x_trim, y_trim, s=10, alpha=0.36, color="#2f6b8a", edgecolors="none")
    if len(x_trim) >= 25:
        window = max(10, len(x_trim) // 35)
        trend = pd.Series(y_trim).rolling(window=window, center=True, min_periods=5).median().to_numpy()
        ax.plot(x_trim, trend, color="#c83349", lw=1.8)
    ax.set_xlabel(f"{DISPLAY} (standardized; {LOW_Q:.0%}-{HIGH_Q:.0%} range)")
    ax.set_ylabel(f"SHAP value for {DISPLAY}")
    ax.set_title(f"{DISPLAY} | extreme tail removed")
    fig.tight_layout()
    out = folder / "dependence_plots" / f"{FEATURE}.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)

    metric = folder.parts[-2]
    biome = folder.parts[-1]
    return {
        "metric": metric,
        "biome": biome,
        "feature": FEATURE,
        "original_points": int(len(x)),
        "points_used": int(len(x_trim)),
        "points_removed": int(len(x) - len(x_trim)),
        "removed_fraction": float((len(x) - len(x_trim)) / len(x)),
        "lower_quantile": LOW_Q,
        "upper_quantile": HIGH_Q,
        "lower_bound": low,
        "upper_bound": high,
        "original_min": float(np.nanmin(x)),
        "original_max": float(np.nanmax(x)),
        "plot_path": str(out),
    }


def main() -> None:
    records = []
    for folder in sorted(ORTHO.glob("*/*")):
        if folder.is_dir() and (folder / "dependence_sample_features.parquet").exists():
            records.append(redraw(folder))
    out_csv = ROOT / "orthogonal_pre_z_dependence_outlier_trim_index.csv"
    pd.DataFrame(records).to_csv(out_csv, index=False)
    print(f"Redrew {len(records)} Pre_z dependence plots")
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
