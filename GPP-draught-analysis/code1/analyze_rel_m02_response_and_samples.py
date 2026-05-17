#!/usr/bin/env python3
"""Analyze compact GPP response output and draw sampled absolute-GPP trajectories."""

import argparse
import json
import os
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np


DEFAULT_EVENT_FILE = (
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/"
    "gpp_response_SMrz_events_global_v20260323_rel_m02.nc"
)
DEFAULT_GPP_FILE = "/data/BESS_V2/BESS_GPP_1982_2022_0.25deg.nc"
BASE_OUT_DIR = "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results"
BASE_TIME = datetime(1982, 1, 1)


def _smooth_causal(x, window):
    x = np.asarray(x, dtype=np.float64)
    out = np.full(len(x), np.nan, dtype=np.float64)
    window = max(1, int(window))
    for i in range(len(x)):
        start = max(0, i - window + 1)
        vals = x[start : i + 1]
        vals = vals[np.isfinite(vals)]
        if vals.size > 0:
            out[i] = float(np.nanmean(vals))
    return out


def _to_numpy(var):
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        arr = arr.filled(np.nan)
    arr = np.asarray(arr)
    if np.issubdtype(arr.dtype, np.integer):
        arr = arr.astype(np.float64)
    return arr


def _read_fields(event_file, fields):
    out = {}
    with nc.Dataset(event_file, "r") as ds:
        for name in fields:
            if name not in ds.variables:
                continue
            var = ds.variables[name]
            arr = _to_numpy(var)
            fill_value = getattr(var, "_FillValue", None)
            if fill_value is not None and np.issubdtype(arr.dtype, np.floating):
                arr[np.isclose(arr, float(fill_value), equal_nan=False)] = np.nan
            elif fill_value is not None and np.issubdtype(arr.dtype, np.integer):
                arr[arr == fill_value] = np.nan
            out[name] = arr
    return out


def _clean_time_var(arr):
    arr = np.asarray(arr, dtype=np.float64)
    arr[arr < 0] = np.nan
    return arr


def _summary_stats(arr):
    vals = np.asarray(arr, dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"n": 0, "mean": np.nan, "median": np.nan, "p25": np.nan, "p75": np.nan}
    return {
        "n": int(vals.size),
        "mean": float(np.nanmean(vals)),
        "median": float(np.nanmedian(vals)),
        "p25": float(np.nanpercentile(vals, 25)),
        "p75": float(np.nanpercentile(vals, 75)),
    }


def _trend_by_year(years, values):
    years = np.asarray(years, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(years) & np.isfinite(values)
    if not np.any(valid):
        return {
            "slope_day_per_year": np.nan,
            "first_year": np.nan,
            "last_year": np.nan,
            "first_mean": np.nan,
            "last_mean": np.nan,
            "delta_days": np.nan,
            "years": [],
            "means": [],
            "counts": [],
        }

    ymin = int(np.nanmin(years[valid]))
    ymax = int(np.nanmax(years[valid]))
    years_out, means_out, counts_out = [], [], []
    for y in range(ymin, ymax + 1):
        m = valid & (years == y)
        if np.any(m):
            years_out.append(int(y))
            means_out.append(float(np.nanmean(values[m])))
            counts_out.append(int(np.sum(m)))

    if len(years_out) >= 2:
        slope = float(np.polyfit(np.asarray(years_out), np.asarray(means_out), 1)[0])
        first_year = int(years_out[0])
        last_year = int(years_out[-1])
        first_mean = float(means_out[0])
        last_mean = float(means_out[-1])
        delta = float(last_mean - first_mean)
    elif len(years_out) == 1:
        slope = np.nan
        first_year = int(years_out[0])
        last_year = int(years_out[0])
        first_mean = float(means_out[0])
        last_mean = float(means_out[0])
        delta = 0.0
    else:
        slope = np.nan
        first_year = np.nan
        last_year = np.nan
        first_mean = np.nan
        last_mean = np.nan
        delta = np.nan

    return {
        "slope_day_per_year": slope,
        "first_year": first_year,
        "last_year": last_year,
        "first_mean": first_mean,
        "last_mean": last_mean,
        "delta_days": delta,
        "years": years_out,
        "means": means_out,
        "counts": counts_out,
    }


def _date_from_year_doy(year_val, doy_val):
    if not np.isfinite(year_val) or not np.isfinite(doy_val):
        return None
    y = int(year_val)
    d = int(doy_val)
    if d < 1 or d > 366:
        return None
    try:
        return datetime(y, 1, 1) + timedelta(days=d - 1)
    except ValueError:
        return None


def _pick_sample_indices(valid_indices, values, n_samples):
    if len(valid_indices) == 0:
        return []
    order = np.asarray(valid_indices)[np.argsort(np.asarray(values, dtype=np.float64))]
    chunks = np.array_split(order, min(n_samples, len(order)))
    picks = []
    for ch in chunks:
        if len(ch) == 0:
            continue
        picks.append(int(ch[len(ch) // 2]))
    return picks


def _series_value_at(x_days, y_vals, day):
    if not np.isfinite(day):
        return np.nan
    day_int = int(round(float(day)))
    where = np.where(x_days == day_int)[0]
    if len(where) == 0:
        return np.nan
    val = y_vals[int(where[0])]
    return float(val) if np.isfinite(val) else np.nan


def _plot_trend_panels(trend_dict, out_png):
    panel_order = [
        ("response_onset_days", "Response (Onset)"),
        ("response_drought_days", "Response (Drought Start)"),
        ("recover_from_peak_days", "Recover (From Peak)"),
        ("recover_from_onset_days", "Recover (From Onset)"),
        ("recover_from_drought_days", "Recover (From Drought Start)"),
    ]
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), dpi=220)
    axes = axes.ravel()
    for i, (key, title) in enumerate(panel_order):
        ax = axes[i]
        rec = trend_dict.get(key, {})
        ys = np.asarray(rec.get("years", []), dtype=np.float64)
        ms = np.asarray(rec.get("means", []), dtype=np.float64)
        if len(ys) > 0:
            ax.plot(ys, ms, color="#1f77b4", lw=1.7, marker="o", ms=3)
            if len(ys) >= 2 and np.isfinite(rec.get("slope_day_per_year", np.nan)):
                slope = rec["slope_day_per_year"]
                intercept = float(np.nanmean(ms) - slope * np.nanmean(ys))
                ax.plot(ys, slope * ys + intercept, color="#d62728", lw=1.2, ls="--")
        ax.set_title(f"{title} | slope={rec.get('slope_day_per_year', np.nan):.3f} d/yr")
        ax.set_xlabel("Year")
        ax.set_ylabel("Days")
        ax.grid(alpha=0.25)
    axes[-1].axis("off")
    fig.tight_layout()
    fig.savefig(out_png, dpi=220)
    plt.close(fig)


def _plot_sample_group(
    d,
    gpp_ds,
    lat_arr,
    lon_arr,
    n_time,
    out_dir,
    sample_idx,
    response_onset,
    response_drought,
    recover_peak,
    recover_onset,
    group_name,
    file_prefix,
    smooth_window,
):
    sample_records = []
    for i, evt_idx in enumerate(sample_idx, start=1):
        lat = float(d["lat"][evt_idx])
        lon = float(d["lon"][evt_idx])
        onset_date = _date_from_year_doy(d["onset_year"][evt_idx], d["onset_doy"][evt_idx])
        drought_date = _date_from_year_doy(d["drought_start_year"][evt_idx], d["drought_start_doy"][evt_idx])
        if onset_date is None:
            continue

        lat_i = int(np.argmin(np.abs(lat_arr - lat)))
        lon_i = int(np.argmin(np.abs(lon_arr - lon)))
        onset_t = int((onset_date - BASE_TIME).days)
        if onset_t >= n_time:
            continue

        recover_onset_day = float(recover_onset[evt_idx]) if np.isfinite(recover_onset[evt_idx]) else np.nan
        peak_day = float(d["t_peak"][evt_idx]) if np.isfinite(d["t_peak"][evt_idx]) else np.nan
        window_after = float(d["actual_window_after"][evt_idx]) if np.isfinite(d["actual_window_after"][evt_idx]) else np.nan

        if np.isfinite(recover_onset_day):
            max_day = int(np.ceil(recover_onset_day))
        elif np.isfinite(window_after):
            max_day = int(window_after)
        else:
            max_day = 180
        if np.isfinite(peak_day):
            max_day = max(max_day, int(np.ceil(peak_day)))
        max_day = max(max_day, 10)
        if np.isfinite(window_after):
            max_day = min(max_day, int(window_after))

        t0 = max(0, onset_t)
        t1 = min(n_time - 1, onset_t + max_day)
        if t1 <= t0:
            continue

        series = np.asarray(gpp_ds.variables["GPP"][t0 : t1 + 1, lat_i, lon_i], dtype=np.float64)
        smoothed_series = _smooth_causal(series, smooth_window)
        x_days = np.arange(t0 - onset_t, t1 - onset_t + 1, dtype=int)
        baseline = float(d["gpp_baseline_abs"][evt_idx])

        drought_offset = np.nan
        if drought_date is not None:
            drought_offset = float((drought_date - onset_date).days)

        fig_path = os.path.join(out_dir, f"{file_prefix}_{i:02d}_event_{evt_idx}.png")
        fig, ax = plt.subplots(figsize=(9.6, 5.0), dpi=220)
        ax.plot(x_days, series, color="#9ecae1", lw=1.0, alpha=0.9, label="GPP absolute raw")
        ax.plot(x_days, smoothed_series, color="#1f77b4", lw=2.0, label=f"GPP absolute {smooth_window}d smooth")
        if np.isfinite(baseline):
            ax.axhline(baseline, color="#2ca02c", lw=1.2, ls="--", label="Baseline")
        ax.axvline(0, color="#7f7f7f", lw=1.0, ls="-.", label="Onset")
        if np.isfinite(drought_offset):
            ax.axvline(drought_offset, color="#9467bd", lw=1.0, ls="-.", label="Drought start")

        marker_items = [
            ("t_response_onset_start", float(response_onset[evt_idx]), "#ff7f0e", "Response"),
            ("t_peak", float(d["t_peak"][evt_idx]), "#d62728", "Peak"),
            ("t_recover_onset_start", float(recover_onset[evt_idx]), "#17becf", "Recover"),
        ]
        for _, day_val, color, label in marker_items:
            yv = _series_value_at(x_days, smoothed_series, day_val)
            if np.isfinite(day_val) and np.isfinite(yv):
                ax.scatter([int(round(day_val))], [yv], color=color, s=34, zorder=4, label=label)

        ax.set_xlabel("Days since onset")
        ax.set_ylabel("GPP (gC m$^{-2}$ day$^{-1}$)")
        ax.set_title(
            f"{group_name} sample {i:02d} | event={evt_idx} | lat={lat:.3f}, lon={lon:.3f} | onset={onset_date.strftime('%Y-%m-%d')}"
        )
        ax.grid(alpha=0.25)
        ax.legend(loc="best", fontsize=8)
        fig.tight_layout()
        fig.savefig(fig_path, dpi=220)
        plt.close(fig)

        sample_records.append(
            {
                "sample_no": i,
                "event_index": int(evt_idx),
                "lat": lat,
                "lon": lon,
                "onset_year": int(d["onset_year"][evt_idx]),
                "onset_doy": int(d["onset_doy"][evt_idx]),
                "drought_start_year": int(d["drought_start_year"][evt_idx]),
                "drought_start_doy": int(d["drought_start_doy"][evt_idx]),
                "actual_window_after": float(d["actual_window_after"][evt_idx]),
                "t_response_onset_start": float(response_onset[evt_idx]),
                "t_response_drought_start": float(response_drought[evt_idx]),
                "t_peak": float(d["t_peak"][evt_idx]),
                "t_peak_abs": float(d["t_peak_abs"][evt_idx]),
                "t_recover_to_baseline": float(recover_peak[evt_idx]) if np.isfinite(recover_peak[evt_idx]) else None,
                "t_recover_onset_start": float(recover_onset[evt_idx]) if np.isfinite(recover_onset[evt_idx]) else None,
                "amp_max_z": float(d["amp_max"][evt_idx]),
                "gpp_baseline_abs": baseline,
                "smooth_window": int(smooth_window),
                "figure_file": fig_path,
            }
        )
    return sample_records


def run_analysis(event_file, gpp_file, out_dir, sample_n, smooth_window):
    os.makedirs(out_dir, exist_ok=True)
    tag = os.path.splitext(os.path.basename(event_file))[0].replace("gpp_response_SMrz_events_global_", "")

    fields = [
        "lat",
        "lon",
        "event_id",
        "onset_year",
        "onset_doy",
        "drought_start_year",
        "drought_start_doy",
        "actual_window_after",
        "lu_event_valid",
        "response_detected",
        "t_response_onset_start",
        "t_response_drought_start",
        "t_peak",
        "t_peak_abs",
        "amp_max",
        "gpp_baseline_abs",
        "t_recover_to_baseline",
        "t_recover_onset_start",
        "t_recover_drought_start",
        "recovery_rate_to_baseline",
    ]
    d = _read_fields(event_file, fields)
    n_event = len(d["lat"])

    onset_year = np.asarray(d["onset_year"], dtype=np.float64)
    response_flag = np.asarray(d["response_detected"], dtype=np.float64) == 1

    response_onset = _clean_time_var(d["t_response_onset_start"])
    response_drought = _clean_time_var(d["t_response_drought_start"])
    recover_peak = _clean_time_var(d["t_recover_to_baseline"])
    recover_onset = _clean_time_var(d["t_recover_onset_start"])
    recover_drought = _clean_time_var(d["t_recover_drought_start"])

    # Keep "usual" response/recovery summaries on response-detected events only.
    response_onset[~response_flag] = np.nan
    response_drought[~response_flag] = np.nan
    recover_peak[~response_flag] = np.nan
    recover_onset[~response_flag] = np.nan
    recover_drought[~response_flag] = np.nan

    summary = {
        "events_total_output": int(n_event),
        "response_onset_days": _summary_stats(response_onset),
        "response_drought_days": _summary_stats(response_drought),
        "recover_from_peak_days": _summary_stats(recover_peak),
        "recover_from_onset_days": _summary_stats(recover_onset),
        "recover_from_drought_days": _summary_stats(recover_drought),
    }

    trend = {
        "response_onset_days": _trend_by_year(onset_year, response_onset),
        "response_drought_days": _trend_by_year(onset_year, response_drought),
        "recover_from_peak_days": _trend_by_year(onset_year, recover_peak),
        "recover_from_onset_days": _trend_by_year(onset_year, recover_onset),
        "recover_from_drought_days": _trend_by_year(onset_year, recover_drought),
    }

    drop_json = os.path.splitext(event_file)[0] + "_drop_reason_stats.json"
    if os.path.exists(drop_json):
        with open(drop_json, "r", encoding="utf-8") as f:
            drop_funnel = json.load(f)
    else:
        drop_funnel = {
            "events_output_written_total": int(n_event),
            "events_output_response_detected": int(np.sum(np.asarray(d["response_detected"]) == 1)),
            "events_output_lu_valid": int(np.sum(np.asarray(d["lu_event_valid"]) == 1)),
            "events_output_recovery_detected": int(np.sum(np.isfinite(recover_peak))),
        }

    summary_out = {"summary": summary, "trend": trend, "drop_funnel": drop_funnel}
    summary_file = os.path.join(out_dir, f"summary_metrics_{tag}.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary_out, f, ensure_ascii=False, indent=2)

    trend_png = os.path.join(out_dir, f"trend_timeseries_{tag}.png")
    _plot_trend_panels(trend, trend_png)

    recovered_mask = (
        (np.asarray(d["response_detected"]) == 1)
        & (np.asarray(d["lu_event_valid"]) == 1)
        & np.isfinite(recover_peak)
        & np.isfinite(recover_onset)
        & np.isfinite(np.asarray(d["gpp_baseline_abs"], dtype=np.float64))
        & np.isfinite(np.asarray(d["lat"], dtype=np.float64))
        & np.isfinite(np.asarray(d["lon"], dtype=np.float64))
        & np.isfinite(np.asarray(d["onset_year"], dtype=np.float64))
        & np.isfinite(np.asarray(d["onset_doy"], dtype=np.float64))
    )
    nonrecovery_mask = (
        (np.asarray(d["response_detected"]) == 1)
        & (np.asarray(d["lu_event_valid"]) == 1)
        & ~np.isfinite(recover_peak)
        & np.isfinite(np.asarray(d["gpp_baseline_abs"], dtype=np.float64))
        & np.isfinite(np.asarray(d["lat"], dtype=np.float64))
        & np.isfinite(np.asarray(d["lon"], dtype=np.float64))
        & np.isfinite(np.asarray(d["onset_year"], dtype=np.float64))
        & np.isfinite(np.asarray(d["onset_doy"], dtype=np.float64))
    )
    recovered_idx = np.where(recovered_mask)[0]
    nonrecovery_idx = np.where(nonrecovery_mask)[0]
    recovered_samples = _pick_sample_indices(recovered_idx, recover_peak[recovered_idx], sample_n)
    nonrecovery_values = np.asarray(d["t_peak"], dtype=np.float64)
    nonrecovery_values[~np.isfinite(nonrecovery_values)] = np.nan
    nonrecovery_samples = _pick_sample_indices(nonrecovery_idx, nonrecovery_values[nonrecovery_idx], sample_n)

    with nc.Dataset(gpp_file, "r") as gpp_ds:
        lat_arr = np.asarray(gpp_ds.variables["lat"][:], dtype=np.float64)
        lon_arr = np.asarray(gpp_ds.variables["lon"][:], dtype=np.float64)
        n_time = int(gpp_ds.dimensions["time"].size)
        recovered_records = _plot_sample_group(
            d=d,
            gpp_ds=gpp_ds,
            lat_arr=lat_arr,
            lon_arr=lon_arr,
            n_time=n_time,
            out_dir=out_dir,
            sample_idx=recovered_samples,
            response_onset=response_onset,
            response_drought=response_drought,
            recover_peak=recover_peak,
            recover_onset=recover_onset,
            group_name="Recovered",
            file_prefix="sample",
            smooth_window=smooth_window,
        )
        nonrecovery_dir = os.path.join(out_dir, "nonrecovery_samples")
        os.makedirs(nonrecovery_dir, exist_ok=True)
        nonrecovery_records = _plot_sample_group(
            d=d,
            gpp_ds=gpp_ds,
            lat_arr=lat_arr,
            lon_arr=lon_arr,
            n_time=n_time,
            out_dir=nonrecovery_dir,
            sample_idx=nonrecovery_samples,
            response_onset=response_onset,
            response_drought=response_drought,
            recover_peak=recover_peak,
            recover_onset=recover_onset,
            group_name="Nonrecovery",
            file_prefix="nonrecovery",
            smooth_window=smooth_window,
        )

    sample_file = os.path.join(out_dir, f"sample_events_{tag}.json")
    with open(sample_file, "w", encoding="utf-8") as f:
        json.dump(recovered_records, f, ensure_ascii=False, indent=2)

    nonrecovery_file = os.path.join(out_dir, "nonrecovery_samples", f"nonrecovery_sample_events_{tag}.json")
    with open(nonrecovery_file, "w", encoding="utf-8") as f:
        json.dump(nonrecovery_records, f, ensure_ascii=False, indent=2)

    print(f"Summary saved: {summary_file}")
    print(f"Trend figure : {trend_png}")
    print(f"Samples saved: {sample_file}")
    print(f"Recovered sample count : {len(recovered_records)}")
    print(f"Nonrecovery samples   : {nonrecovery_file}")
    print(f"Nonrecovery count     : {len(nonrecovery_records)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-file", default=DEFAULT_EVENT_FILE, help="Compact event output netCDF file.")
    parser.add_argument("--gpp-file", default=DEFAULT_GPP_FILE, help="Daily absolute GPP netCDF file.")
    parser.add_argument("--out-dir", default="", help="Output directory for figures and summary JSON.")
    parser.add_argument("--sample-n", type=int, default=6, help="Number of sampled events for line plots.")
    parser.add_argument("--smooth-window", type=int, default=5, help="Causal smoothing window for displayed absolute series.")
    args = parser.parse_args()

    tag = os.path.splitext(os.path.basename(args.event_file))[0].replace("gpp_response_SMrz_events_global_", "")
    out_dir = args.out_dir if args.out_dir else os.path.join(BASE_OUT_DIR, f"figures_{tag}")
    run_analysis(
        event_file=args.event_file,
        gpp_file=args.gpp_file,
        out_dir=out_dir,
        sample_n=max(1, int(args.sample_n)),
        smooth_window=max(1, int(args.smooth_window)),
    )


if __name__ == "__main__":
    main()
