#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Build biome-specific GPP/RECO recovery-time trend figure.

The five biome classes follow the categories used in the GLEAM orthogonal SHAP
workflow: Cropland, Forest, Grassland, Savanna, and Shrubland.
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE = Path("/home/xulc/flash_drought")
GLEAM = BASE / "process/SEM_analysis0401/codex/GLEAM"
OUT_DIR = BASE / "process/result_analysis/result_weighted/conclusion/BESS_Fluxsat_valid"
OUT_PNG = OUT_DIR / "biome_gpp_reco_recovery_trend_smrz_bess.png"
OUT_ANNUAL_CSV = OUT_DIR / "biome_gpp_reco_recovery_trend_smrz_bess_annual.csv"
OUT_SLOPE_CSV = OUT_DIR / "biome_gpp_reco_recovery_trend_smrz_bess_slopes.csv"
OUT_README = OUT_DIR / "biome_gpp_reco_recovery_trend_smrz_bess_readme.md"

TARGET = "t_recover_to_baseline_abs_peak"
YEAR_COL = "onset_year"
BIOMES = ["Forest", "Grassland", "Savanna", "Cropland", "Shrubland"]
TABLES = {
    "GPP": GLEAM / "data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet",
    "RECO": GLEAM / "data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet",
}
COLORS = {
    "Forest": "#1b9e77",
    "Grassland": "#66a61e",
    "Savanna": "#e6ab02",
    "Cropland": "#7570b3",
    "Shrubland": "#a6761d",
}
MANUAL_ANNUAL_OVERRIDES = [
    {
        "metric": "RECO",
        "biome": "Cropland",
        "year": 1984,
        "recovery_mean_weighted_days": 65.4,
        "note": "Manual correction for anomalous 1984 RECO Cropland recovery value.",
    },
    {
        "metric": "RECO",
        "biome": "Savanna",
        "year": 1995,
        "recovery_mean_weighted_days": 37.1,
        "note": "Manual correction requested for 1995 RECO Savanna recovery value.",
    },
    *[
        {
            "metric": "RECO",
            "biome": "Shrubland",
            "year": year,
            "delta_days": -5.0,
            "note": "Manual correction requested: subtract 5 days from 2017-2021 RECO Shrubland recovery values.",
        }
        for year in range(2017, 2022)
    ],
    *[
        {
            "metric": "GPP",
            "biome": "Shrubland",
            "year": year,
            "delta_days": 5.0,
            "note": "Manual correction requested: add 5 days to 2018-2021 GPP Shrubland recovery values.",
        }
        for year in range(2018, 2022)
    ],
]


def latitude_area_weights(latitudes: pd.Series | np.ndarray) -> np.ndarray:
    lat = np.asarray(latitudes, dtype=np.float64)
    weights = np.cos(np.deg2rad(lat))
    weights[~np.isfinite(weights)] = np.nan
    weights[weights <= 0] = np.nan
    return weights


def finite_weighted_mean(values: pd.Series | np.ndarray, latitudes: pd.Series | np.ndarray) -> float:
    arr = np.asarray(values, dtype=np.float64)
    weights = latitude_area_weights(latitudes)
    valid = np.isfinite(arr) & np.isfinite(weights) & (weights > 0)
    if not np.any(valid):
        return float("nan")
    return float(np.average(arr[valid], weights=weights[valid]))


def trend_slope_per_decade(years: np.ndarray, values: np.ndarray) -> float:
    years = np.asarray(years, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(years) & np.isfinite(values)
    if np.count_nonzero(valid) < 2:
        return float("nan")
    slope, _ = np.polyfit(years[valid], values[valid], 1)
    return float(slope * 10.0)


def load_metric(metric: str) -> pd.DataFrame:
    cols = ["biome", "lat", YEAR_COL, TARGET]
    df = pd.read_parquet(TABLES[metric], columns=cols)
    df = df[df["biome"].isin(BIOMES)].copy()
    df[YEAR_COL] = pd.to_numeric(df[YEAR_COL], errors="coerce")
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df.loc[df[TARGET] < 0, TARGET] = np.nan
    df = df.dropna(subset=["biome", "lat", YEAR_COL, TARGET])
    df["year"] = df[YEAR_COL].astype(int)
    df["metric"] = metric
    return df[["metric", "biome", "year", "lat", TARGET]]


def apply_manual_overrides(annual: pd.DataFrame) -> pd.DataFrame:
    annual = annual.copy()
    annual["manual_override_note"] = ""
    for item in MANUAL_ANNUAL_OVERRIDES:
        mask = (
            (annual["metric"] == item["metric"])
            & (annual["biome"] == item["biome"])
            & (annual["year"] == item["year"])
        )
        if not mask.any():
            raise ValueError(f"Manual override target not found: {item}")
        if "recovery_mean_weighted_days" in item:
            annual.loc[mask, "recovery_mean_weighted_days"] = item["recovery_mean_weighted_days"]
        elif "delta_days" in item:
            annual.loc[mask, "recovery_mean_weighted_days"] = (
                annual.loc[mask, "recovery_mean_weighted_days"] + item["delta_days"]
            )
        else:
            raise ValueError(f"Manual override must provide a fixed value or delta_days: {item}")
        annual.loc[mask, "manual_override_note"] = item["note"]
    return annual


def build_annual_summary() -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = [load_metric(metric) for metric in ["GPP", "RECO"]]
    df = pd.concat(frames, ignore_index=True)
    annual_rows: list[dict[str, object]] = []
    for (metric, biome, year), group in df.groupby(["metric", "biome", "year"], sort=True):
        values = group[TARGET].to_numpy(dtype=np.float64)
        annual_rows.append(
            {
                "metric": metric,
                "biome": biome,
                "year": int(year),
                "event_count": int(values.size),
                "recovery_mean_weighted_days": finite_weighted_mean(values, group["lat"].to_numpy(dtype=np.float64)),
                "recovery_mean_unweighted_days": float(np.nanmean(values)),
                "recovery_median_days": float(np.nanmedian(values)),
            }
        )
    annual = pd.DataFrame(annual_rows).sort_values(["metric", "biome", "year"]).reset_index(drop=True)
    annual = apply_manual_overrides(annual)

    slope_rows: list[dict[str, object]] = []
    for (metric, biome), group in annual.groupby(["metric", "biome"], sort=True):
        slope_rows.append(
            {
                "metric": metric,
                "biome": biome,
                "year_start": int(group["year"].min()),
                "year_end": int(group["year"].max()),
                "n_years": int(group["year"].nunique()),
                "mean_event_count_per_year": float(group["event_count"].mean()),
                "mean_recovery_weighted_days": float(group["recovery_mean_weighted_days"].mean()),
                "slope_days_per_decade": trend_slope_per_decade(
                    group["year"].to_numpy(dtype=np.float64),
                    group["recovery_mean_weighted_days"].to_numpy(dtype=np.float64),
                ),
            }
        )
    slopes = pd.DataFrame(slope_rows).sort_values(["metric", "biome"]).reset_index(drop=True)
    return annual, slopes


def add_lines(ax: plt.Axes, annual: pd.DataFrame, metric: str) -> None:
    subset = annual[annual["metric"] == metric]
    for biome in BIOMES:
        rows = subset[subset["biome"] == biome].sort_values("year")
        if rows.empty:
            continue
        years = rows["year"].to_numpy(dtype=np.float64)
        vals = rows["recovery_mean_weighted_days"].to_numpy(dtype=np.float64)
        ax.plot(
            years,
            vals,
            color=COLORS[biome],
            linewidth=2.2,
            marker="o",
            markersize=3.2,
            alpha=0.92,
            label=biome,
        )
        valid = np.isfinite(years) & np.isfinite(vals)
        if np.count_nonzero(valid) >= 2:
            slope, intercept = np.polyfit(years[valid], vals[valid], 1)
            ax.plot(
                years[valid],
                intercept + slope * years[valid],
                color=COLORS[biome],
                linewidth=1.3,
                linestyle="--",
                alpha=0.45,
            )


def plot_figure(annual: pd.DataFrame, slopes: pd.DataFrame) -> None:
    fig = plt.figure(figsize=(16.0, 9.2))
    gs = fig.add_gridspec(2, 2, width_ratios=[3.35, 1.15], wspace=0.10, hspace=0.18)
    line_axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[1, 0])]
    bar_axes = [fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, 1])]

    all_vals = annual["recovery_mean_weighted_days"].to_numpy(dtype=np.float64)
    finite = all_vals[np.isfinite(all_vals)]
    ymin = max(0.0, float(np.nanpercentile(finite, 1)) - 3.0)
    ymax = float(np.nanpercentile(finite, 99)) + 3.0
    reco_ylim = (20.0, 70.0)

    for ax, metric in zip(line_axes, ["GPP", "RECO"], strict=True):
        add_lines(ax, annual, metric)
        ax.set_title(f"{metric} recovery time by biome", fontsize=17, fontweight="bold")
        ax.set_ylabel("Area-weighted recovery time (days)", fontsize=13)
        ax.set_ylim(reco_ylim if metric == "RECO" else (ymin, ymax))
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.32)
        ax.tick_params(axis="both", labelsize=11.5)
    line_axes[1].set_xlabel("Onset year", fontsize=13)
    line_axes[0].legend(frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.17), fontsize=11.5)

    for ax, metric in zip(bar_axes, ["GPP", "RECO"], strict=True):
        sub = slopes[slopes["metric"] == metric].set_index("biome").loc[BIOMES].reset_index()
        x = np.arange(len(sub))
        vals = sub["mean_recovery_weighted_days"].to_numpy(dtype=np.float64)
        ax.bar(x, vals, color=[COLORS[b] for b in sub["biome"]], width=0.72, edgecolor="#444444", linewidth=0.5)
        ax.set_xticks(x)
        if metric == "GPP":
            ax.set_xticklabels([])
            ax.tick_params(axis="x", length=0)
        else:
            ax.set_xticklabels(sub["biome"], rotation=35, ha="right", fontsize=10.5)
        ax.set_title(f"{metric} biome mean", fontsize=16, fontweight="bold")
        ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.28)
        ax.tick_params(axis="y", labelsize=11)
        ax.set_ylim(reco_ylim if metric == "RECO" else (ymin, ymax))
        if metric == "GPP":
            ax.set_ylabel("Mean recovery time (days)", fontsize=12.5)
        else:
            ax.set_ylabel("")
        pad = 1.2 if metric == "RECO" else (ymax - ymin) * 0.015
        for xi, yi in zip(x, vals, strict=True):
            ax.text(xi, yi + pad, f"{yi:.1f}", ha="center", va="bottom", fontsize=9.5)
    fig.suptitle("SMrz flash-drought recovery time trends by biome", fontsize=20, fontweight="bold")
    fig.savefig(OUT_PNG, dpi=240, bbox_inches="tight")
    plt.close(fig)


def write_readme(slopes: pd.DataFrame) -> None:
    lines = [
        "# Biome-specific GPP/RECO recovery trend",
        "",
        "This figure uses the same five biome classes as the GLEAM orthogonal SHAP workflow: Forest, Grassland, Savanna, Cropland, and Shrubland.",
        "",
        f"Target recovery field: `{TARGET}`.",
        "Annual means are latitude-area-weighted with `cos(latitude)`, following the existing weighted recovery-summary workflow.",
        "",
        "Outputs:",
        f"- `{OUT_PNG.name}`",
        f"- `{OUT_ANNUAL_CSV.name}`",
        f"- `{OUT_SLOPE_CSV.name}`",
        "",
        "Manual corrections:",
        "- RECO Cropland 1984 annual area-weighted recovery time was set to 65.4 days after identifying it as an anomalous point.",
        "- RECO Savanna 1995 annual area-weighted recovery time was set to 37.1 days.",
        "- RECO Shrubland annual area-weighted recovery times for 2017-2021 were each reduced by 5 days.",
        "- GPP Shrubland annual area-weighted recovery times for 2018-2021 were each increased by 5 days.",
        "",
        "Slope summary:",
        "```csv",
        slopes.to_csv(index=False).strip(),
        "```",
    ]
    OUT_README.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    annual, slopes = build_annual_summary()
    annual.to_csv(OUT_ANNUAL_CSV, index=False)
    slopes.to_csv(OUT_SLOPE_CSV, index=False)
    plot_figure(annual, slopes)
    write_readme(slopes)
    print(f"Wrote {OUT_PNG}")
    print(f"Wrote {OUT_ANNUAL_CSV}")
    print(f"Wrote {OUT_SLOPE_CSV}")


if __name__ == "__main__":
    main()
