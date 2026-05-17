#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import argparse
from pathlib import Path

import netCDF4 as nc
import numpy as np


DEFAULT_INPUT = (
    "/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results/"
    "FluxSat_GPP_2000_2019_0.25deg.nc"
)
DEFAULT_CSV = (
    "/home/xulc/flash_drought/process/fluxsat-draught-analysis/preprocess/results/"
    "FluxSat_GPP_2000_2019_0.25deg_diagnostics.csv"
)
DEFAULT_MD = (
    "/home/xulc/flash_drought/process/fluxsat-draught-analysis/analysis/"
    "FluxSat_GPP_2000_2019_0.25deg_diagnostics.md"
)
GLEAM_EVENT_FILE = (
    "/home/xulc/flash_drought/gleam/clip_result/SMrz_result_v5.4_0p25deg_no_ice_desert/"
    "flash_lt20_drought_events_v5.4.nc"
)


def ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def summarize(input_path: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    with nc.Dataset(input_path, "r") as ds, nc.Dataset(GLEAM_EVENT_FILE, "r") as gleam:
        time_var = ds.variables["time"]
        dates = nc.num2date(
            time_var[:],
            units=time_var.units,
            calendar=getattr(time_var, "calendar", "standard"),
            only_use_cftime_datetimes=False,
            only_use_python_datetimes=True,
        )
        gpp = ds.variables["GPP"]
        lat = np.asarray(ds.variables["lat"][:], dtype=np.float32)
        lon = np.asarray(ds.variables["lon"][:], dtype=np.float32)
        gleam_lat = np.asarray(gleam.variables["lat"][:], dtype=np.float32)
        gleam_lon = np.asarray(gleam.variables["lon"][:], dtype=np.float32)

        years = sorted({d.year for d in dates})
        rows: list[dict[str, object]] = []
        for year in years:
            idx = np.array([i for i, d in enumerate(dates) if d.year == year], dtype=np.int64)
            data = np.asarray(gpp[idx, :, :], dtype=np.float32)
            valid_ratio = float(np.isfinite(data).sum() / data.size) if data.size else 0.0
            rows.append(
                {
                    "year": year,
                    "day_count": int(idx.size),
                    "valid_ratio": valid_ratio,
                }
            )

        overall = {
            "first_date": dates[0].strftime("%Y-%m-%d"),
            "last_date": dates[-1].strftime("%Y-%m-%d"),
            "total_days": len(dates),
            "lat_size": len(lat),
            "lon_size": len(lon),
            "grid_match": bool(lat.shape == gleam_lat.shape and lon.shape == gleam_lon.shape and np.allclose(lat, gleam_lat) and np.allclose(lon, gleam_lon)),
        }
        return rows, overall


def write_outputs(csv_path: str, md_path: str, rows: list[dict[str, object]], overall: dict[str, object]) -> None:
    ensure_parent(csv_path)
    ensure_parent(md_path)
    csv_lines = ["year,day_count,valid_ratio"]
    for row in rows:
        csv_lines.append(f"{row['year']},{row['day_count']},{row['valid_ratio']:.8f}")
    Path(csv_path).write_text("\n".join(csv_lines) + "\n", encoding="utf-8")

    md_lines = [
        "# FluxSat 0.25deg 预处理诊断",
        "",
        f"- 首日: `{overall['first_date']}`",
        f"- 末日: `{overall['last_date']}`",
        f"- 总天数: `{overall['total_days']}`",
        f"- 空间维度: `{overall['lat_size']} x {overall['lon_size']}`",
        f"- 与 GLEAM 事件网格完全一致: `{overall['grid_match']}`",
        "",
        "## 年度统计",
        "",
        "| 年 | 天数 | 有效值比例 |",
        "| --- | ---: | ---: |",
    ]
    for row in rows:
        md_lines.append(f"| {row['year']} | {row['day_count']} | {row['valid_ratio']:.6f} |")
    Path(md_path).write_text("\n".join(md_lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose standardized FluxSat preprocessing outputs.")
    parser.add_argument("--input-path", default=DEFAULT_INPUT)
    parser.add_argument("--csv-path", default=DEFAULT_CSV)
    parser.add_argument("--md-path", default=DEFAULT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, overall = summarize(args.input_path)
    write_outputs(args.csv_path, args.md_path, rows, overall)


if __name__ == "__main__":
    main()
