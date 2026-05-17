#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


FLASH_PYTHON = Path("/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python")
MERGE_HELPER = Path("/home/xulc/flash_drought/process/process2/merge_era5_attribute_yearly.py")
GRID_FILE = Path("/data/era5_for_GRN/yearly/era5_r025_720x1440_scrip.nc")
FINAL_NAME = "mswep_total_precipitation_0p25deg_1980_2024.nc"
VAR_NAME = "mswep_total_precipitation"


def log(message: str) -> None:
    print(message, flush=True)


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    merged_env = os.environ.copy()
    merged_env.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")
    if env:
        merged_env.update(env)
    log("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True, env=merged_env)


def load_merge_module():
    spec = importlib.util.spec_from_file_location("merge_era5_attribute_yearly", MERGE_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load merge helper: {MERGE_HELPER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def patch_missing_daily_files(daily_root: Path, patch_dir: Path, force: bool) -> tuple[Path, Path]:
    patch_dir.mkdir(parents=True, exist_ok=True)
    patch_241 = patch_dir / "1993241.nc"
    patch_243 = patch_dir / "1993243.nc"

    if force or not patch_241.exists():
        run(["nces", "-O", str(daily_root / "1993240.nc"), str(daily_root / "1993242.nc"), str(patch_241)])
    if force or not patch_243.exists():
        run(["nces", "-O", str(daily_root / "1993242.nc"), str(daily_root / "1993244.nc"), str(patch_243)])
    return patch_241, patch_243


def build_fixed_1993_yearly(daily_root: Path, yearly_patch_dir: Path, force: bool) -> Path:
    yearly_patch_dir.mkdir(parents=True, exist_ok=True)
    fixed_1993 = yearly_patch_dir / "1993.nc"
    if fixed_1993.exists() and not force:
        return fixed_1993

    patch_241, patch_243 = patch_missing_daily_files(daily_root, yearly_patch_dir / "daily_patch", force)

    files: list[str] = []
    for doy in range(1, 366):
        if doy == 241:
            files.append(str(patch_241))
        elif doy == 243:
            files.append(str(patch_243))
        else:
            files.append(str(daily_root / f"1993{doy:03d}.nc"))

    run(["ncrcat", "-O", *files, str(fixed_1993)])
    return fixed_1993


def resample_single_year(
    year: int,
    yearly_root: str,
    fixed_1993: str,
    output_dir: str,
    work_root: str,
    threads: int,
    deflate: int,
    force: bool,
) -> str:
    yearly_root_path = Path(yearly_root)
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    input_file = Path(fixed_1993) if year == 1993 else yearly_root_path / f"{year}.nc"
    output_file = output_dir_path / f"{VAR_NAME}_{year}_0p25deg.nc"

    if output_file.exists() and not force:
        return str(output_file)

    run(
        [
            "ncremap",
            "--no_stdin",
            "-4",
            "-L",
            str(deflate),
            "-a",
            "ncoaave",
            "-v",
            "precipitation",
            "-g",
            str(GRID_FILE),
            "-T",
            work_root,
            "-t",
            str(threads),
            str(input_file),
            str(output_file),
        ]
    )
    run(["ncrename", "-O", "-v", f"precipitation,{VAR_NAME}", str(output_file)])
    run(
        [
            "ncatted",
            "-O",
            "-a",
            f"title,global,o,c,MSWEP total precipitation 0.25 degree {year}",
            "-a",
            "source,global,o,c,Resampled from MSWEP V3.15 0.1 degree yearly file using ncremap area-weighted averaging (ncoaave)",
            "-a",
            "spatial_resolution,global,o,c,0.25 degree",
            "-a",
            f"long_name,{VAR_NAME},o,c,MSWEP total precipitation",
            "-a",
            f"units,{VAR_NAME},o,c,mm/day",
            str(output_file),
        ]
    )
    return str(output_file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a new MSWEP 0.25 degree merged product.")
    parser.add_argument("--daily-root", default="/data/MSWEP_V315")
    parser.add_argument("--yearly-root", default="/data/MSWEP_V315/yearly")
    parser.add_argument("--output-root", default="/data/era5_for_GRN/yearly")
    parser.add_argument("--tmp-root", default="/data/era5_for_GRN/tmp_resample_0p25deg/MSWEP_V315")
    parser.add_argument("--work-root", default="/tmp/mswep_r025_tmp")
    parser.add_argument("--start-year", type=int, default=1980)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--threads", type=int, default=int(os.environ.get("NCO_THREADS", "2")))
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--deflate", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--keep-intermediate", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    daily_root = Path(args.daily_root)
    yearly_root = Path(args.yearly_root)
    output_root = Path(args.output_root)
    tmp_root = Path(args.tmp_root)
    work_root = Path(args.work_root)
    resampled_dir = tmp_root / "resampled_yearly"
    final_path = output_root / FINAL_NAME

    output_root.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)
    tmp_root.mkdir(parents=True, exist_ok=True)
    resampled_dir.mkdir(parents=True, exist_ok=True)

    if args.force and final_path.exists():
        final_path.unlink()

    fixed_1993 = build_fixed_1993_yearly(daily_root, tmp_root / "yearly_patch", args.force)
    log(f"fixed 1993 yearly file ready: {fixed_1993}")

    futures = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for year in range(args.start_year, args.end_year + 1):
            futures.append(
                pool.submit(
                    resample_single_year,
                    year,
                    str(yearly_root),
                    str(fixed_1993),
                    str(resampled_dir),
                    str(work_root),
                    args.threads,
                    args.deflate,
                    args.force,
                )
            )
        for future in as_completed(futures):
            output = future.result()
            log(f"finished yearly regrid: {output}")

    merge_module = load_merge_module()
    merge_module.merge_files(
        input_dir=str(resampled_dir),
        output_path=str(final_path),
        force=True,
        filename_regex=rf"{VAR_NAME}_(\d{{4}})_0p25deg\.nc$",
        var_name=VAR_NAME,
        title=f"MSWEP total precipitation 0.25 degree {args.start_year}-{args.end_year}",
        start_year=args.start_year,
        end_year=args.end_year,
        deflate=args.deflate,
    )
    log(f"created merged output: {final_path}")

    if not args.keep_intermediate and tmp_root.exists():
        shutil.rmtree(tmp_root)
        log(f"removed temporary directory: {tmp_root}")


if __name__ == "__main__":
    main()
