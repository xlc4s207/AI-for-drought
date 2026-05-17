# -*- coding: utf-8 -*-

from __future__ import annotations


EVENT_TYPE_ORDER = ["rapid_1to4", "flash_5to20", "slow_gt20", "dry_to_drier"]
MAIN_EVENT_TYPES = ["rapid_1to4", "flash_5to20", "slow_gt20"]
OUTPUT_EVENT_TYPES = ["total", *EVENT_TYPE_ORDER]

EVENT_TYPE_LABELS_CN = {
    "rapid_1to4": "1-4天",
    "flash_5to20": "5-20天",
    "slow_gt20": ">20天",
    "dry_to_drier": "持续偏干",
}


def classify_onset_days_v54(onset_days: int | float, has_onset_start: bool) -> str:
    if not has_onset_start:
        return "dry_to_drier"
    if onset_days <= 4:
        return "rapid_1to4"
    if onset_days <= 20:
        return "flash_5to20"
    return "slow_gt20"
