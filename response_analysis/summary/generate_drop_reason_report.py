#!/usr/bin/env python3
"""Generate a post-hoc drop-reason report from event and compact output files."""

import argparse
import json
import os

import netCDF4 as nc
import numpy as np
import xarray as xr


def _event_total(event_file):
    with nc.Dataset(event_file, "r") as ds:
        ec = ds.variables["event_count"][:]
        if np.ma.isMaskedArray(ec):
            ec = ec.filled(0)
        return int(np.asarray(ec, dtype=np.int64).sum())


def build_report(event_file, output_file):
    total_events = _event_total(event_file)
    ds = xr.open_dataset(output_file)

    report = {
        "event_file": event_file,
        "output_file": output_file,
        "events_from_event_file_total": int(total_events),
        "events_output_written_total": int(ds.sizes["event"]),
    }

    report["events_not_written_total"] = (
        report["events_from_event_file_total"] - report["events_output_written_total"]
    )

    if "response_detected" in ds:
        response_detected = np.asarray(ds["response_detected"].values) == 1
        report["events_output_response_detected"] = int(np.sum(response_detected))
        report["events_output_no_response_detected"] = int(np.sum(~response_detected))
    else:
        response_detected = None

    if "lu_event_valid" in ds:
        lu_valid = np.asarray(ds["lu_event_valid"].values) == 1
        report["events_output_lu_valid"] = int(np.sum(lu_valid))
        report["events_output_not_lu_valid"] = int(np.sum(~lu_valid))
    else:
        lu_valid = None

    if "exclude_from_baseline_recovery" in ds:
        excluded = np.asarray(ds["exclude_from_baseline_recovery"].values) == 1
        report["events_output_excluded_from_baseline_recovery"] = int(np.sum(excluded))

    if "t_recover_to_baseline" in ds:
        tr = np.asarray(ds["t_recover_to_baseline"].values, dtype=float)
        tr[np.isclose(tr, -9999)] = np.nan
        recover_detected = np.isfinite(tr)
        report["events_output_recovery_detected"] = int(np.sum(recover_detected))
    else:
        recover_detected = None

    if response_detected is not None and lu_valid is not None and recover_detected is not None:
        report["events_output_response_valid_but_no_recovery"] = int(
            np.sum(response_detected & lu_valid & (~recover_detected))
        )

    # Ratios for quick diagnosis
    if report["events_from_event_file_total"] > 0:
        report["ratio_output_written_vs_event_total"] = (
            report["events_output_written_total"] / report["events_from_event_file_total"]
        )
    if report["events_output_written_total"] > 0 and "events_output_recovery_detected" in report:
        report["ratio_recovery_vs_output_written"] = (
            report["events_output_recovery_detected"] / report["events_output_written_total"]
        )

    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-file", required=True, help="Path to drought event netCDF file.")
    parser.add_argument("--output-file", required=True, help="Path to compact analysis output netCDF file.")
    parser.add_argument(
        "--report-file",
        default="",
        help="Optional output JSON path. Default: <output-file-without-ext>_drop_reason_report_posthoc.json",
    )
    args = parser.parse_args()

    report_file = args.report_file
    if not report_file:
        report_file = os.path.splitext(args.output_file)[0] + "_drop_reason_report_posthoc.json"

    report = build_report(args.event_file, args.output_file)
    with open(report_file, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Saved post-hoc drop reason report: {report_file}")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
