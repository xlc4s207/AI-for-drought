#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import netCDF4 as nc
import numpy as np


OUT_DIR = Path("/home/xulc/flash_drought/process/fluxsat-draught-analysis/results")
SUMMARY_CSV = OUT_DIR / "fluxsat_vs_bess_summary_2000_2019.csv"
SUMMARY_MD = OUT_DIR / "fluxsat_vs_bess_summary_2000_2019.md"


@dataclass(frozen=True)
class Item:
    source: str
    scenario: str
    path: str


ITEMS = [
    Item(
        "FluxSat",
        "SMrz",
        "/home/xulc/flash_drought/process/fluxsat-draught-analysis/code1/results/fluxsat_gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc",
    ),
    Item(
        "FluxSat",
        "SMs",
        "/home/xulc/flash_drought/process/fluxsat-draught-analysis/code2_SMs/results/fluxsat_gpp_response_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc",
    ),
    Item(
        "BESS",
        "SMrz",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc",
    ),
    Item(
        "BESS",
        "SMs",
        "/home/xulc/flash_drought/process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v20260401_growingseason_recovery_gsdays_rel0_abspeak_absrec_c30x095_w420_decline30_d5_norecmax.nc",
    ),
]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def to_numpy(var) -> np.ndarray:
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        arr = arr.filled(np.nan)
    arr = np.asarray(arr)
    if np.issubdtype(arr.dtype, np.integer):
        arr = arr.astype(np.float64)
    fill_value = getattr(var, "_FillValue", None)
    if fill_value is not None:
        arr = arr.astype(np.float64, copy=False)
        arr[np.isclose(arr, float(fill_value), equal_nan=False)] = np.nan
    return arr


def clean_nonnegative(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    arr[~np.isfinite(arr)] = np.nan
    arr[arr < 0.0] = np.nan
    return arr


def finite_mean(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    return float(np.nanmean(arr)) if arr.size else math.nan


def finite_median(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    return float(np.nanmedian(arr)) if arr.size else math.nan


def summarize_item(item: Item) -> dict[str, object]:
    with nc.Dataset(item.path, "r") as ds:
        onset_year = to_numpy(ds.variables["onset_year"])
        period_mask = np.isfinite(onset_year) & (onset_year >= 2000) & (onset_year <= 2019)
        response = clean_nonnegative(to_numpy(ds.variables["t_response_drought_start"]))
        recovery = clean_nonnegative(to_numpy(ds.variables["t_recover_to_baseline"]))
        event_total = int(np.sum(period_mask))
        response_valid = int(np.sum(period_mask & np.isfinite(response)))
        recovery_valid = int(np.sum(period_mask & np.isfinite(recovery)))
        response_subset = response[period_mask]
        recovery_subset = recovery[period_mask]

    return {
        "source": item.source,
        "scenario": item.scenario,
        "event_total_2000_2019": event_total,
        "response_valid_count": response_valid,
        "recovery_valid_count": recovery_valid,
        "response_mean_days": finite_mean(response_subset),
        "response_median_days": finite_median(response_subset),
        "recovery_mean_days": finite_mean(recovery_subset),
        "recovery_median_days": finite_median(recovery_subset),
    }


def write_outputs(rows: list[dict[str, object]]) -> None:
    ensure_parent(SUMMARY_CSV)
    headers = [
        "source",
        "scenario",
        "event_total_2000_2019",
        "response_valid_count",
        "recovery_valid_count",
        "response_mean_days",
        "response_median_days",
        "recovery_mean_days",
        "recovery_median_days",
    ]
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# FluxSat vs BESS 2000-2019 对比汇总",
        "",
        "| 数据源 | 情景 | 事件数 | 响应有效数 | 恢复有效数 | 响应均值(d) | 响应中位数(d) | 恢复均值(d) | 恢复中位数(d) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['source']} | {row['scenario']} | {row['event_total_2000_2019']} | "
            f"{row['response_valid_count']} | {row['recovery_valid_count']} | "
            f"{row['response_mean_days']:.2f} | {row['response_median_days']:.2f} | "
            f"{row['recovery_mean_days']:.2f} | {row['recovery_median_days']:.2f} |"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = [summarize_item(item) for item in ITEMS]
    write_outputs(rows)


if __name__ == "__main__":
    main()
