#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


MERGE_HELPER = Path("/home/xulc/flash_drought/process/process2/merge_era5_attribute_yearly.py")
GRID_FILE = Path("/data/era5_for_GRN/yearly/era5_r025_720x1440_scrip.nc")
FINAL_NAME = "E_0p25deg_1980_2024.nc"
VAR_NAME = "E"


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


def resample_single_year(
    year: int,
    input_root: str,
    output_dir: str,
    work_root: str,
    threads: int,
    deflate: int,
    force: bool,
) -> str:
    input_root_path = Path(input_root)
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    input_file = input_root_path / f"E_{year}_GLEAM_v4.2a.nc"
    output_file = output_dir_path / f"E_{year}_GLEAM_v4.2a_0p25deg.nc"

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
            VAR_NAME,
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
    run(
        [
            "ncatted",
            "-O",
            "-a",
            f"title,global,o,c,GLEAM E 0.25 degree {year}",
            "-a",
            "source,global,o,c,Resampled from GLEAM v4.2a yearly file using ncremap area-weighted averaging (ncoaave)",
            "-a",
            "spatial_resolution,global,o,c,0.25 degree",
            "-a",
            "long_name,E,o,c,Actual evaporation from GLEAM 4.2a",
            "-a",
            "units,E,o,c,mm.day-1",
            str(output_file),
        ]
    )
    return str(output_file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a new GLEAM E 0.25 degree merged product.")
    parser.add_argument("--input-root", default="/data/GLEAM/E")
    parser.add_argument("--output-root", default="/data/GLEAM/0p25deg_yearly")
    parser.add_argument("--tmp-root", default="/data/GLEAM/tmp_resample_0p25deg/E")
    parser.add_argument("--work-root", default="/tmp/gleam_e_r025_tmp")
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
    input_root = Path(args.input_root)
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

    futures = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for year in range(args.start_year, args.end_year + 1):
            futures.append(
                pool.submit(
                    resample_single_year,
                    year,
                    str(input_root),
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
        filename_regex=r"E_(\d{4})_GLEAM_v4\.2a_0p25deg\.nc$",
        var_name=VAR_NAME,
        title=f"GLEAM E 0.25 degree {args.start_year}-{args.end_year}",
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
