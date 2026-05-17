#!/usr/bin/env python
"""Build a prepeak feature table aligned to the recoverywin network feature set."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepeak-table", required=True)
    parser.add_argument("--merged-table", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def saturation_vapor_pressure_kpa(temp_c: pd.Series) -> pd.Series:
    return 0.6108 * np.exp((17.27 * temp_c) / (temp_c + 237.3))


def dewpoint_from_temp_vpd(temp_k: pd.Series, vpd_kpa: pd.Series) -> pd.Series:
    temp_c = pd.to_numeric(temp_k, errors="coerce") - 273.15
    vpd = pd.to_numeric(vpd_kpa, errors="coerce")
    es = saturation_vapor_pressure_kpa(temp_c)
    ea = (es - vpd).clip(lower=1e-6)
    ln_ratio = np.log(ea / 0.6108)
    dew_c = (237.3 * ln_ratio) / (17.27 - ln_ratio)
    return dew_c + 273.15


def main() -> None:
    args = parse_args()
    prepeak = pd.read_parquet(args.prepeak_table)
    merged = pd.read_parquet(
        args.merged_table,
        columns=[
            "event_uid",
            "onset_SMrz_delta",
        ],
    )
    merged = merged.drop_duplicates(subset=["event_uid"]).rename(columns={"onset_SMrz_delta": "prepeak_SMrz_delta"})
    out = prepeak.merge(merged, on="event_uid", how="left", validate="one_to_one")

    out["prepeak_p_minus_et"] = (
        pd.to_numeric(out["prepeak_total_precipitation_mean"], errors="coerce")
        - pd.to_numeric(out["prepeak_total_evaporation_mean"], errors="coerce")
    )
    out["prepeak_dewpoint_temperature_mean"] = dewpoint_from_temp_vpd(
        out["prepeak_temperature_2m_mean"],
        out["prepeak_VPD_mean"],
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output, index=False)
    print(f"[DONE] wrote {output}")
    print(f"rows={len(out)} cols={len(out.columns)}")
    print(
        "added_columns="
        + ",".join(
            [
                "prepeak_p_minus_et",
                "prepeak_dewpoint_temperature_mean",
                "prepeak_SMrz_delta",
            ]
        )
    )


if __name__ == "__main__":
    main()
