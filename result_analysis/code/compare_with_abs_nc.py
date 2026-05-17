#!/usr/bin/env python3

import csv
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

import netCDF4 as nc
import numpy as np


BASE_DIR = "/home/xulc/flash_drought"
OUTPUT_DIR = os.path.join(BASE_DIR, "process", "result_analysis", "compare_analysis")
FIGURE_DIR = os.path.join(OUTPUT_DIR, "figures")
SAMPLE_SIZE = 200000
STRATIFIED_CHUNK_SIZE = 500000
RECOVERY_BINS = [
    ("<=7", 0.0, 7.0),
    ("8-30", 8.0, 30.0),
    ("31-90", 31.0, 90.0),
    (">90", 91.0, float("inf")),
]
YEAR_PERIOD_BINS = [
    (1982, 1989, "1982-1989"),
    (1990, 1999, "1990-1999"),
    (2000, 2009, "2000-2009"),
    (2010, 2022, "2010-2022"),
]
STRATIFIED_METRICS = [
    "response_detected",
    "drought_duration",
    "t_response",
    "t_impact",
    "t_recover",
    "recovery_rate",
    "baseline_abs",
    "drop_abs",
    "change_to_peak_abs",
    "recovery_rate_abs",
]
CONTINENT_DIR = os.path.join(OUTPUT_DIR, "continent_analysis")
YEAR_DIR = os.path.join(OUTPUT_DIR, "year_group_analysis")
RECOVERY_DIR = os.path.join(OUTPUT_DIR, "recovery_bin_analysis")
CLIMATE_VEG_DIR = os.path.join(OUTPUT_DIR, "climate_vegetation_analysis")

DATASET_PATHS = [
    os.path.join(BASE_DIR, "process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v11_with_abs.nc"),
    os.path.join(BASE_DIR, "process/GPP-draught-analysis/code2_SMs/results/gpp_response_SMs_events_global_v11_with_abs.nc"),
    os.path.join(BASE_DIR, "process/GPP-draught-analysis/code3_nonflash_SMrz/result/gpp_response_nonflash_SMrz_drought_v11_global_with_abs.nc"),
    os.path.join(BASE_DIR, "process/GPP-draught-analysis/code4_nonflash_SMs/result/gpp_response_nonflash_SMs_drought_v11_global_with_abs.nc"),
    os.path.join(BASE_DIR, "process/NEE-draught-analysis/code1SMrz/result/nee_response_events_global_v11_with_abs.nc"),
    os.path.join(BASE_DIR, "process/NEE-draught-analysis/code2SMs/result/nee_response_SMs_events_global_v11_with_abs.nc"),
    os.path.join(BASE_DIR, "process/NEE-draught-analysis/code3_nonflash_SMrz/result/nee_response_nonflash_SMrz_drought_v11_global_with_abs.nc"),
    os.path.join(BASE_DIR, "process/NEE-draught-analysis/code4_nonflash_SMs/result/nee_response_nonflash_SMs_drought_v11_global_with_abs.nc"),
    os.path.join(BASE_DIR, "process/RECO-draught-analysis/code1/results/reco_response_events_global_v11_with_abs.nc"),
    os.path.join(BASE_DIR, "process/RECO-draught-analysis/code2_SMs/results/reco_response_SMs_events_global_v11_with_abs.nc"),
    os.path.join(BASE_DIR, "process/RECO-draught-analysis/code3_nonflash_SMrz/result/reco_response_nonflash_SMrz_drought_v11_global_with_abs.nc"),
    os.path.join(BASE_DIR, "process/RECO-draught-analysis/code4_nonflash_SMs/result/reco_response_nonflash_SMs_drought_v11_global_with_abs.nc"),
]

METRIC_PRIORITY = [
    "response_detected",
    "drought_duration",
    "actual_window_after",
    "min",
    "mean",
    "trend",
    "t_min",
    "t_response",
    "t_impact",
    "t_peak",
    "t_recover",
    "recovery_rate",
    "amp_max",
    "baseline_abs",
    "min_abs",
    "max_abs",
    "mean_abs",
    "trend_abs",
    "drop_abs",
    "rise_abs",
    "change_to_peak_abs",
    "recovery_rate_abs",
]

LITERATURE_EVIDENCE = [
    {
        "topic": "GPP sensitivity",
        "source": "深度研究报告_骤旱与非骤旱对碳通量影响差异.md",
        "year": "2026 note",
        "claim": "GPP 对骤旱通常比对非骤旱更快、更敏感，且其变化经常主导后续 NEE 的变化。",
        "link_to_analysis": "用于解释 flash 与 nonflash 间的 value_drop_abs、t_response、recovery 相关差异。",
    },
    {
        "topic": "Lagged drought effects",
        "source": "Jiao et al. 2022",
        "year": "2022",
        "claim": "滞后干旱影响比同步影响更显著地影响生态系统碳吸收，生态系统生产对干旱时间尺度更敏感，呼吸相对较弱。",
        "link_to_analysis": "用于解释 value_change_to_peak_abs、t_recover_to_baseline 与 legacy_duration 的重要性。",
    },
    {
        "topic": "Post-drought recovery",
        "source": "Zhang et al. 2021",
        "year": "2021",
        "claim": "森林和半干旱/半湿润生态系统恢复时间更长，存在长期不完全恢复风险。",
        "link_to_analysis": "用于解释 t_recover、t_recover_to_baseline 与 recovery_rate_to_baseline 的空间平均差异。",
    },
    {
        "topic": "GPP vs RECO sensitivity",
        "source": "Higher sensitivity of gross primary production than ecosystem respiration...",
        "year": "2023",
        "claim": "GPP 对干旱与增温的敏感性高于 RECO，NEE 变化通常更多由 GPP 侧驱动。",
        "link_to_analysis": "用于解释三类碳通量中 GPP/NEE/RECO 对绝对值指标的对比格局。",
    },
    {
        "topic": "Post-drought GPP loss",
        "source": "Zhao et al. 2025",
        "year": "2025",
        "claim": "显著的 GPP 损失会发生在干旱结束后，恢复阶段是总干旱损失的重要组成部分。",
        "link_to_analysis": "用于解释 value_change_to_peak_abs、legacy_integral 和恢复相关指标的意义。",
    },
    {
        "topic": "NEE source-sink shifts",
        "source": "补充分析_NEE响应机制与碳汇源动态.md",
        "year": "2026 note",
        "claim": "NEE 在强干旱下可从碳汇转为碳源，且短期水分变化对其影响往往强于长期缓变胁迫。",
        "link_to_analysis": "用于解释 NEE 的 cross_zero_after_onset、source_days 和 source_integral。",
    },
]


@dataclass(frozen=True)
class DatasetSpec:
    path: str
    variable: str
    drought_type: str
    soil_layer: str
    code_label: str

    @property
    def dataset_id(self) -> str:
        return f"{self.variable}_{self.drought_type}_{self.soil_layer}"


def _normalize_lon_value(lon: float) -> float:
    return ((float(lon) + 180.0) % 360.0) - 180.0


def classify_continent(lat: float, lon: float) -> str:
    lat = float(lat)
    lon = _normalize_lon_value(lon)
    if lat < -60.0:
        return "Antarctica"
    if -170.0 <= lon <= -50.0 and 7.0 <= lat <= 84.0:
        return "North America"
    if -92.0 <= lon <= -30.0 and -60.0 <= lat < 15.0:
        return "South America"
    if -25.0 <= lon <= 60.0 and 35.0 <= lat <= 72.0:
        return "Europe"
    if -20.0 <= lon <= 55.0 and -35.0 <= lat < 38.0:
        return "Africa"
    if ((25.0 <= lon <= 180.0 and 5.0 <= lat <= 82.0) or (60.0 <= lon <= 150.0 and -10.0 <= lat < 5.0) or (lon <= -170.0 and 50.0 <= lat <= 72.0)):
        return "Asia"
    if 110.0 <= lon <= 180.0 and -50.0 <= lat < 10.0:
        return "Oceania"
    return "Unassigned"


def select_year_field(field_names: Sequence[str]) -> str:
    if "drought_start_year" in field_names:
        return "drought_start_year"
    if "onset_year" in field_names:
        return "onset_year"
    raise KeyError("Neither drought_start_year nor onset_year is available.")


def recovery_bin_label(t_recover: float) -> str:
    if not math.isfinite(float(t_recover)) or float(t_recover) < 0:
        return "missing_or_unrecovered"
    value = float(t_recover)
    for label, low, high in RECOVERY_BINS:
        if low <= value <= high:
            return label
    return "missing_or_unrecovered"


def year_period_label(year: int) -> str:
    year = int(year)
    for start, end, label in YEAR_PERIOD_BINS:
        if start <= year <= end:
            return label
    return "outside_range"


def classify_climate_zone(lat: float) -> str:
    abs_lat = abs(float(lat))
    if abs_lat < 23.5:
        return "Tropical"
    if abs_lat < 35.0:
        return "Subtropical"
    if abs_lat < 55.0:
        return "Temperate"
    return "Boreal_Polar"


def classify_continent_array(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    lat = np.asarray(lat, dtype=np.float64)
    lon = ((np.asarray(lon, dtype=np.float64) + 180.0) % 360.0) - 180.0
    out = np.full(lat.shape, "Unassigned", dtype=object)
    out[lat < -60.0] = "Antarctica"
    mask = (-170.0 <= lon) & (lon <= -50.0) & (7.0 <= lat) & (lat <= 84.0)
    out[mask] = "North America"
    mask = (-92.0 <= lon) & (lon <= -30.0) & (-60.0 <= lat) & (lat < 15.0)
    out[mask] = "South America"
    mask = (-25.0 <= lon) & (lon <= 60.0) & (35.0 <= lat) & (lat <= 72.0)
    out[mask] = "Europe"
    mask = (-20.0 <= lon) & (lon <= 55.0) & (-35.0 <= lat) & (lat < 38.0)
    out[mask] = "Africa"
    mask = ((25.0 <= lon) & (lon <= 180.0) & (5.0 <= lat) & (lat <= 82.0)) | ((60.0 <= lon) & (lon <= 150.0) & (-10.0 <= lat) & (lat < 5.0)) | ((lon <= -170.0) & (50.0 <= lat) & (lat <= 72.0))
    out[mask] = "Asia"
    mask = (110.0 <= lon) & (lon <= 180.0) & (-50.0 <= lat) & (lat < 10.0)
    out[mask] = "Oceania"
    return out


def classify_climate_zone_array(lat: np.ndarray) -> np.ndarray:
    abs_lat = np.abs(np.asarray(lat, dtype=np.float64))
    out = np.full(abs_lat.shape, "Boreal_Polar", dtype=object)
    out[abs_lat < 55.0] = "Temperate"
    out[abs_lat < 35.0] = "Subtropical"
    out[abs_lat < 23.5] = "Tropical"
    return out


def year_period_label_array(years: np.ndarray) -> np.ndarray:
    years = np.asarray(years, dtype=np.int32)
    out = np.full(years.shape, "outside_range", dtype=object)
    for start, end, label in YEAR_PERIOD_BINS:
        out[(years >= start) & (years <= end)] = label
    return out


def recovery_bin_label_array(values: np.ndarray) -> np.ndarray:
    vals = np.asarray(values, dtype=np.float64)
    out = np.full(vals.shape, "missing_or_unrecovered", dtype=object)
    finite = np.isfinite(vals) & (vals >= 0)
    out[finite & (vals <= 7.0)] = "<=7"
    out[finite & (vals >= 8.0) & (vals <= 30.0)] = "8-30"
    out[finite & (vals >= 31.0) & (vals <= 90.0)] = "31-90"
    out[finite & (vals > 90.0)] = ">90"
    return out


def classify_dataset(path: str) -> DatasetSpec:
    lower = path.lower()

    if "gpp" in lower:
        variable = "GPP"
    elif "nee" in lower:
        variable = "NEE"
    elif "reco" in lower:
        variable = "RECO"
    else:
        raise ValueError(f"Cannot infer variable from path: {path}")

    drought_type = "nonflash" if "nonflash" in lower else "flash"

    if "code1" in lower:
        code_label = "code1"
    elif "code2" in lower:
        code_label = "code2"
    elif "code3" in lower:
        code_label = "code3"
    elif "code4" in lower:
        code_label = "code4"
    else:
        code_label = "unknown"

    if "smrz" in lower or code_label in {"code1", "code3"}:
        soil_layer = "SMrz"
    else:
        soil_layer = "SMs"

    return DatasetSpec(
        path=path,
        variable=variable,
        drought_type=drought_type,
        soil_layer=soil_layer,
        code_label=code_label,
    )


def extract_common_fields(field_lists: Sequence[Sequence[str]]) -> List[str]:
    if not field_lists:
        return []
    common = set(field_lists[0])
    for fields in field_lists[1:]:
        common &= set(fields)
    return [field for field in field_lists[0] if field in common]


def select_core_metrics(fields: Iterable[str]) -> List[str]:
    ordered_fields = list(fields)
    keep = []
    prefixes = (
        "response_",
        "t_",
        "amp_",
        "recovery_",
        "value_",
        "legacy_",
        "source_",
        "cross_zero",
    )
    skip = {"lat", "lon", "lat_coord", "lon_coord", "event_id", "title"}
    for field in ordered_fields:
        if field in skip:
            continue
        if field.startswith(prefixes):
            keep.append(field)
    return keep


def normalize_metric_name(field: str, variable: str) -> str:
    prefix = f"{variable.lower()}_"
    lower = field.lower()
    if lower.startswith(prefix):
        return field[len(prefix) :]
    return field


def _round_float(value: float) -> Optional[float]:
    if not math.isfinite(value):
        return None
    return round(float(value), 6)


def _to_array(var_obj, sample_size: Optional[int] = None) -> np.ndarray:
    if sample_size is None or "event" not in var_obj.dimensions:
        data = var_obj[:]
    else:
        axis = var_obj.dimensions.index("event")
        shape = var_obj.shape
        count = shape[axis]
        take = min(sample_size, count)
        step = max(count // take, 1)
        if axis == 0:
            slices = [slice(None)] * len(shape)
            slices[axis] = slice(0, count, step)
            data = var_obj[tuple(slices)]
            data = np.asarray(data)[:take]
        else:
            slices = [slice(None)] * len(shape)
            slices[axis] = slice(0, take)
            data = var_obj[tuple(slices)]
    if hasattr(data, "filled"):
        data = data.filled(np.nan)
    return np.asarray(data)


def _numeric_stats(data: np.ndarray) -> Dict[str, Optional[float]]:
    arr = np.asarray(data)
    out = {
        "size": int(arr.size),
        "finite_count": 0,
        "nan_count": 0,
        "finite_ratio": None,
        "min": None,
        "max": None,
        "mean": None,
        "median": None,
        "std": None,
        "p05": None,
        "p25": None,
        "p75": None,
        "p95": None,
    }
    if arr.size == 0:
        return out

    numeric = np.issubdtype(arr.dtype, np.number) or np.issubdtype(arr.dtype, np.bool_)
    if not numeric:
        return out

    arr = arr.astype(np.float64, copy=False)
    valid = np.isfinite(arr)
    finite_count = int(np.count_nonzero(valid))
    out["finite_count"] = finite_count
    out["nan_count"] = int(arr.size - finite_count)
    out["finite_ratio"] = _round_float(finite_count / arr.size) if arr.size else None
    if finite_count == 0:
        return out

    vals = arr[valid]
    out["min"] = _round_float(np.min(vals))
    out["max"] = _round_float(np.max(vals))
    out["mean"] = _round_float(np.mean(vals))
    out["median"] = _round_float(np.median(vals))
    out["std"] = _round_float(np.std(vals))
    out["p05"] = _round_float(np.percentile(vals, 5))
    out["p25"] = _round_float(np.percentile(vals, 25))
    out["p75"] = _round_float(np.percentile(vals, 75))
    out["p95"] = _round_float(np.percentile(vals, 95))
    return out


def inventory_dataset(spec: DatasetSpec, sample_size: Optional[int] = 200000) -> Dict:
    with nc.Dataset(spec.path, "r") as ds:
        dims = {name: len(dim) for name, dim in ds.dimensions.items()}
        title = getattr(ds, "title", "")
        variable_rows: List[Dict] = []
        for field_name, var in ds.variables.items():
            row = {
                "dataset_id": spec.dataset_id,
                "file_path": spec.path,
                "variable": spec.variable,
                "drought_type": spec.drought_type,
                "soil_layer": spec.soil_layer,
                "code_label": spec.code_label,
                "field": field_name,
                "dtype": str(var.dtype),
                "dimensions": ",".join(var.dimensions),
                "units": getattr(var, "units", ""),
                "long_name": getattr(var, "long_name", ""),
                "sample_size": None,
            }
            data = _to_array(var, sample_size=sample_size)
            row["sample_size"] = int(data.size)
            row.update(_numeric_stats(data))
            variable_rows.append(row)

    return {
        "dataset_id": spec.dataset_id,
        "file_path": spec.path,
        "variable": spec.variable,
        "drought_type": spec.drought_type,
        "soil_layer": spec.soil_layer,
        "code_label": spec.code_label,
        "title": title,
        "dims": dims,
        "event_count": dims.get("event"),
        "variable_count": len(variable_rows),
        "fields": [row["field"] for row in variable_rows],
        "variable_rows": variable_rows,
    }


def write_csv(path: str, rows: List[Dict], headers: Sequence[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(headers))
        writer.writeheader()
        for row in rows:
            out = {}
            for header in headers:
                value = row.get(header, "")
                if value is None:
                    out[header] = ""
                elif isinstance(value, float):
                    out[header] = f"{value:.6f}" if math.isfinite(value) else ""
                else:
                    out[header] = value
            writer.writerow(out)


def write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def load_dataset_specs() -> List[DatasetSpec]:
    missing = [path for path in DATASET_PATHS if not os.path.exists(path)]
    if missing:
        raise FileNotFoundError(f"Missing expected files: {missing}")
    return [classify_dataset(path) for path in DATASET_PATHS]


def build_file_inventory_rows(inventories: Sequence[Dict]) -> List[Dict]:
    rows: List[Dict] = []
    for inv in inventories:
        rows.append(
            {
                "dataset_id": inv["dataset_id"],
                "variable": inv["variable"],
                "drought_type": inv["drought_type"],
                "soil_layer": inv["soil_layer"],
                "code_label": inv["code_label"],
                "event_count": inv["event_count"],
                "variable_count": inv["variable_count"],
                "field_count": len(inv["fields"]),
                "title": inv["title"],
                "dims": str(inv["dims"]),
                "file_path": inv["file_path"],
            }
        )
    return rows


def build_field_presence_rows(inventories: Sequence[Dict]) -> List[Dict]:
    dataset_ids = [inv["dataset_id"] for inv in inventories]
    field_to_presence: Dict[str, Dict[str, int]] = defaultdict(dict)
    for inv in inventories:
        field_set = set(inv["fields"])
        for field in field_set:
            field_to_presence[field][inv["dataset_id"]] = 1

    rows: List[Dict] = []
    for field in sorted(field_to_presence, key=lambda x: (-len(field_to_presence[x]), x)):
        row = {
            "field": field,
            "present_count": len(field_to_presence[field]),
        }
        for dataset_id in dataset_ids:
            row[dataset_id] = field_to_presence[field].get(dataset_id, 0)
        rows.append(row)
    return rows


def build_core_metric_rows(variable_rows: Sequence[Dict]) -> List[Dict]:
    priority_index = {field: idx for idx, field in enumerate(METRIC_PRIORITY)}
    selected = []
    for row in variable_rows:
        normalized = normalize_metric_name(row["field"], row["variable"])
        if normalized not in set(METRIC_PRIORITY):
            continue
        enriched = dict(row)
        enriched["normalized_field"] = normalized
        selected.append(enriched)
    selected.sort(
        key=lambda row: (
            row["dataset_id"],
            priority_index.get(row["normalized_field"], 999),
            row["normalized_field"],
            row["field"],
        )
    )
    return selected


def build_pairwise_delta_rows(core_metric_rows: Sequence[Dict]) -> List[Dict]:
    row_lookup = {(row["dataset_id"], row["normalized_field"]): row for row in core_metric_rows}

    rows: List[Dict] = []
    for variable in ("GPP", "NEE", "RECO"):
        for soil_layer in ("SMrz", "SMs"):
            left_id = f"{variable}_flash_{soil_layer}"
            right_id = f"{variable}_nonflash_{soil_layer}"
            for normalized_field in METRIC_PRIORITY:
                left = row_lookup.get((left_id, normalized_field))
                right = row_lookup.get((right_id, normalized_field))
                if not left or not right or left["mean"] is None or right["mean"] is None:
                    continue
                rows.append(
                    {
                        "comparison_type": "flash_vs_nonflash",
                        "variable": variable,
                        "soil_layer": soil_layer,
                        "field": normalized_field,
                        "left_field": left["field"],
                        "right_field": right["field"],
                        "left_dataset": left_id,
                        "right_dataset": right_id,
                        "left_mean": left["mean"],
                        "right_mean": right["mean"],
                        "delta_right_minus_left": round(right["mean"] - left["mean"], 6),
                    }
                )
        for drought_type in ("flash", "nonflash"):
            left_id = f"{variable}_{drought_type}_SMrz"
            right_id = f"{variable}_{drought_type}_SMs"
            for normalized_field in METRIC_PRIORITY:
                left = row_lookup.get((left_id, normalized_field))
                right = row_lookup.get((right_id, normalized_field))
                if not left or not right or left["mean"] is None or right["mean"] is None:
                    continue
                rows.append(
                    {
                        "comparison_type": "SMrz_vs_SMs",
                        "variable": variable,
                        "soil_layer": drought_type,
                        "field": normalized_field,
                        "left_field": left["field"],
                        "right_field": right["field"],
                        "left_dataset": left_id,
                        "right_dataset": right_id,
                        "left_mean": left["mean"],
                        "right_mean": right["mean"],
                        "delta_right_minus_left": round(right["mean"] - left["mean"], 6),
                    }
                )
    return rows


def metric_field_lookup(ds: nc.Dataset, variable: str) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for field in ds.variables:
        normalized = normalize_metric_name(field, variable)
        if normalized not in lookup:
            lookup[normalized] = field
    return lookup


def _to_float_data(data) -> np.ndarray:
    if hasattr(data, "filled"):
        data = data.filled(np.nan)
    return np.asarray(data, dtype=np.float64)


def _read_chunk(ds: nc.Dataset, var_name: str, start: int, end: int) -> np.ndarray:
    return _to_float_data(ds.variables[var_name][start:end])


def _update_group_stats(
    accumulator: Dict[tuple, Dict[str, float]],
    spec: DatasetSpec,
    group_type: str,
    labels: np.ndarray,
    metric_values: Dict[str, np.ndarray],
) -> None:
    unique_labels = np.unique(labels)
    for label in unique_labels:
        mask = labels == label
        if not np.any(mask):
            continue
        key = (spec.dataset_id, group_type, str(label))
        bucket = accumulator.setdefault(
            key,
            {
                "event_count": 0.0,
                "response_sum": 0.0,
                **{f"{metric}_sum": 0.0 for metric in STRATIFIED_METRICS if metric != "response_detected"},
                **{f"{metric}_count": 0.0 for metric in STRATIFIED_METRICS if metric != "response_detected"},
            },
        )
        bucket["event_count"] += float(np.count_nonzero(mask))
        response = metric_values["response_detected"]
        resp_valid = mask & np.isfinite(response)
        if np.any(resp_valid):
            bucket["response_sum"] += float(np.sum(response[resp_valid] > 0))
        for metric in STRATIFIED_METRICS:
            if metric == "response_detected":
                continue
            values = metric_values.get(metric)
            if values is None:
                continue
            valid = mask & np.isfinite(values)
            if not np.any(valid):
                continue
            bucket[f"{metric}_sum"] += float(np.sum(values[valid]))
            bucket[f"{metric}_count"] += float(np.count_nonzero(valid))


def build_group_rows(
    accumulator: Dict[tuple, Dict[str, float]],
    dataset_specs: Sequence[DatasetSpec],
    group_type: str,
) -> List[Dict]:
    meta = {spec.dataset_id: spec for spec in dataset_specs}
    rows: List[Dict] = []
    for (dataset_id, current_group_type, group_label), bucket in sorted(accumulator.items()):
        if current_group_type != group_type:
            continue
        spec = meta[dataset_id]
        row = {
            "dataset_id": dataset_id,
            "variable": spec.variable,
            "drought_type": spec.drought_type,
            "soil_layer": spec.soil_layer,
            "group_type": group_type,
            "group_label": group_label,
            "event_count": int(bucket["event_count"]),
            "response_rate": round(bucket["response_sum"] / bucket["event_count"], 6) if bucket["event_count"] > 0 else None,
        }
        for metric in STRATIFIED_METRICS:
            if metric == "response_detected":
                continue
            count = bucket.get(f"{metric}_count", 0.0)
            row[f"{metric}_mean"] = round(bucket[f"{metric}_sum"] / count, 6) if count > 0 else None
        rows.append(row)
    return rows


def build_group_pairwise_rows(group_rows: Sequence[Dict], group_type: str) -> List[Dict]:
    lookup = {(row["dataset_id"], row["group_label"]): row for row in group_rows if row["group_type"] == group_type}
    rows: List[Dict] = []
    metrics = ["response_rate"] + [f"{metric}_mean" for metric in STRATIFIED_METRICS if metric != "response_detected"]
    for variable in ("GPP", "NEE", "RECO"):
        group_labels = sorted({row["group_label"] for row in group_rows if row["group_type"] == group_type and row["variable"] == variable})
        for group_label in group_labels:
            for soil_layer in ("SMrz", "SMs"):
                left_id = f"{variable}_flash_{soil_layer}"
                right_id = f"{variable}_nonflash_{soil_layer}"
                left = lookup.get((left_id, group_label))
                right = lookup.get((right_id, group_label))
                if left and right:
                    for metric in metrics:
                        if left.get(metric) is None or right.get(metric) is None:
                            continue
                        rows.append(
                            {
                                "comparison_type": "flash_vs_nonflash",
                                "group_type": group_type,
                                "group_label": group_label,
                                "variable": variable,
                                "soil_layer": soil_layer,
                                "metric": metric,
                                "left_dataset": left_id,
                                "right_dataset": right_id,
                                "left_value": left[metric],
                                "right_value": right[metric],
                                "delta_right_minus_left": round(right[metric] - left[metric], 6),
                            }
                        )
            for drought_type in ("flash", "nonflash"):
                left_id = f"{variable}_{drought_type}_SMrz"
                right_id = f"{variable}_{drought_type}_SMs"
                left = lookup.get((left_id, group_label))
                right = lookup.get((right_id, group_label))
                if left and right:
                    for metric in metrics:
                        if left.get(metric) is None or right.get(metric) is None:
                            continue
                        rows.append(
                            {
                                "comparison_type": "SMrz_vs_SMs",
                                "group_type": group_type,
                                "group_label": group_label,
                                "variable": variable,
                                "soil_layer": drought_type,
                                "metric": metric,
                                "left_dataset": left_id,
                                "right_dataset": right_id,
                                "left_value": left[metric],
                                "right_value": right[metric],
                                "delta_right_minus_left": round(right[metric] - left[metric], 6),
                            }
                        )
    return rows


def aggregate_stratified_rows(dataset_specs: Sequence[DatasetSpec]) -> Dict[str, List[Dict]]:
    accumulator: Dict[tuple, Dict[str, float]] = {}
    for spec in dataset_specs:
        with nc.Dataset(spec.path, "r") as ds:
            n_events = len(ds.dimensions["event"])
            year_field = select_year_field(tuple(ds.variables.keys()))
            field_lookup = metric_field_lookup(ds, spec.variable)
            available_metrics = [metric for metric in STRATIFIED_METRICS if metric in field_lookup]
            for start in range(0, n_events, STRATIFIED_CHUNK_SIZE):
                end = min(start + STRATIFIED_CHUNK_SIZE, n_events)
                lat = _read_chunk(ds, "lat", start, end)
                lon = _read_chunk(ds, "lon", start, end)
                years = _read_chunk(ds, year_field, start, end).astype(np.int32, copy=False)
                t_recover = _read_chunk(ds, "t_recover", start, end)
                valid = np.isfinite(lat) & np.isfinite(lon)
                if not np.any(valid):
                    continue

                metric_values = {metric: _read_chunk(ds, field_lookup[metric], start, end)[valid] for metric in available_metrics}
                continents = classify_continent_array(lat[valid], lon[valid])
                climates = classify_climate_zone_array(lat[valid])
                year_labels = years[valid].astype(str)
                year_periods = year_period_label_array(years[valid])
                recovery_bins = recovery_bin_label_array(t_recover[valid])

                _update_group_stats(accumulator, spec, "continent", continents, metric_values)
                _update_group_stats(accumulator, spec, "climate_zone", climates, metric_values)
                _update_group_stats(accumulator, spec, "year", year_labels, metric_values)
                _update_group_stats(accumulator, spec, "year_period", year_periods, metric_values)
                _update_group_stats(accumulator, spec, "recovery_bin", recovery_bins, metric_values)

    return {
        "continent": build_group_rows(accumulator, dataset_specs, "continent"),
        "climate_zone": build_group_rows(accumulator, dataset_specs, "climate_zone"),
        "year": build_group_rows(accumulator, dataset_specs, "year"),
        "year_period": build_group_rows(accumulator, dataset_specs, "year_period"),
        "recovery_bin": build_group_rows(accumulator, dataset_specs, "recovery_bin"),
    }


def _import_plotting():
    import matplotlib.pyplot as plt

    return plt


def plot_event_counts(file_rows: Sequence[Dict]) -> None:
    plt = _import_plotting()
    dataset_ids = [row["dataset_id"] for row in file_rows]
    values = [row["event_count"] / 1_000_000.0 for row in file_rows]
    colors = []
    for row in file_rows:
        if row["variable"] == "GPP":
            colors.append("#4c956c")
        elif row["variable"] == "NEE":
            colors.append("#2c7fb8")
        else:
            colors.append("#bc4749")
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(range(len(values)), values, color=colors)
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(dataset_ids, rotation=45, ha="right")
    ax.set_ylabel("Event count (million)")
    ax.set_title("Event counts across 12 with_abs datasets")
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURE_DIR, "event_counts.png"), dpi=200)
    plt.close(fig)


def plot_response_rates(core_metric_rows: Sequence[Dict]) -> None:
    plt = _import_plotting()
    rows = [row for row in core_metric_rows if row["field"] == "response_detected" and row["mean"] is not None]
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(range(len(rows)), [row["mean"] for row in rows], color="#577590")
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels([row["dataset_id"] for row in rows], rotation=45, ha="right")
    ax.set_ylabel("Sample mean of response_detected")
    ax.set_title("Estimated response detection rate by dataset")
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURE_DIR, "response_detected_mean.png"), dpi=200)
    plt.close(fig)


def plot_field_presence_heatmap(field_presence_rows: Sequence[Dict], dataset_ids: Sequence[str]) -> None:
    plt = _import_plotting()
    top_rows = list(field_presence_rows[:40])
    matrix = np.array([[row.get(dataset_id, 0) for dataset_id in dataset_ids] for row in top_rows], dtype=float)
    fig, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(matrix, aspect="auto", cmap="YlGn")
    ax.set_xticks(range(len(dataset_ids)))
    ax.set_xticklabels(dataset_ids, rotation=45, ha="right")
    ax.set_yticks(range(len(top_rows)))
    ax.set_yticklabels([row["field"] for row in top_rows])
    ax.set_title("Field presence matrix (top 40 fields)")
    fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURE_DIR, "field_presence_heatmap.png"), dpi=200)
    plt.close(fig)


def plot_core_metric_heatmap(core_metric_rows: Sequence[Dict]) -> None:
    plt = _import_plotting()
    focus_metrics = [
        "response_detected",
        "t_min",
        "t_response",
        "t_recover",
        "recovery_rate",
        "baseline_abs",
        "drop_abs",
        "change_to_peak_abs",
        "recovery_rate_abs",
    ]
    dataset_ids = sorted({row["dataset_id"] for row in core_metric_rows})
    matrix = np.full((len(focus_metrics), len(dataset_ids)), np.nan, dtype=float)
    for i, field in enumerate(focus_metrics):
        for j, dataset_id in enumerate(dataset_ids):
            matches = [row for row in core_metric_rows if row["dataset_id"] == dataset_id and row["normalized_field"] == field]
            if matches and matches[0]["mean"] is not None:
                matrix[i, j] = matches[0]["mean"]
    z_matrix = matrix.copy()
    for i in range(z_matrix.shape[0]):
        row = z_matrix[i]
        valid = np.isfinite(row)
        if np.count_nonzero(valid) >= 2:
            mean = np.nanmean(row[valid])
            std = np.nanstd(row[valid])
            if std > 0:
                row[valid] = (row[valid] - mean) / std
    fig, ax = plt.subplots(figsize=(13, 6))
    im = ax.imshow(z_matrix, aspect="auto", cmap="RdBu_r", vmin=-2.5, vmax=2.5)
    ax.set_xticks(range(len(dataset_ids)))
    ax.set_xticklabels(dataset_ids, rotation=45, ha="right")
    ax.set_yticks(range(len(focus_metrics)))
    ax.set_yticklabels(focus_metrics)
    ax.set_title("Within-metric z-score of sampled means")
    fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURE_DIR, "core_metric_mean_heatmap_zscore.png"), dpi=200)
    plt.close(fig)


def write_literature_table() -> None:
    headers = ["topic", "source", "year", "claim", "link_to_analysis"]
    write_csv(os.path.join(OUTPUT_DIR, "literature_evidence_table.csv"), LITERATURE_EVIDENCE, headers)


def build_report(
    file_rows: Sequence[Dict],
    field_presence_rows: Sequence[Dict],
    core_metric_rows: Sequence[Dict],
    pairwise_rows: Sequence[Dict],
) -> str:
    common_all = [row["field"] for row in field_presence_rows if row["present_count"] == len(file_rows)]
    flash_common = []
    nonflash_common = []
    flash_ids = {row["dataset_id"] for row in file_rows if row["drought_type"] == "flash"}
    nonflash_ids = {row["dataset_id"] for row in file_rows if row["drought_type"] == "nonflash"}
    for row in field_presence_rows:
        if all(row.get(dataset_id, 0) == 1 for dataset_id in flash_ids):
            flash_common.append(row["field"])
        if all(row.get(dataset_id, 0) == 1 for dataset_id in nonflash_ids):
            nonflash_common.append(row["field"])

    max_events = max(file_rows, key=lambda row: row["event_count"])
    min_events = min(file_rows, key=lambda row: row["event_count"])

    response_rows = [row for row in core_metric_rows if row["field"] == "response_detected" and row["mean"] is not None]
    response_lookup = {row["dataset_id"]: row["mean"] for row in response_rows}

    flash_nonflash_lines = []
    for variable in ("GPP", "NEE", "RECO"):
        for soil_layer in ("SMrz", "SMs"):
            flash_id = f"{variable}_flash_{soil_layer}"
            nonflash_id = f"{variable}_nonflash_{soil_layer}"
            if flash_id in response_lookup and nonflash_id in response_lookup:
                delta = response_lookup[nonflash_id] - response_lookup[flash_id]
                flash_nonflash_lines.append(
                    f"- {variable} ({soil_layer}): flash={response_lookup[flash_id]:.3f}, nonflash={response_lookup[nonflash_id]:.3f}, delta={delta:+.3f}"
                )

    variable_abs_fields = {}
    for variable in ("gpp", "nee", "reco"):
        variable_abs_fields[variable.upper()] = [
            row["field"]
            for row in field_presence_rows
            if row["field"].startswith(f"{variable}_") and row["field"].endswith("_abs")
        ]

    pairwise_focus = [
        row
        for row in pairwise_rows
        if row["field"] in {"t_response", "t_recover", "drop_abs", "change_to_peak_abs", "recovery_rate_abs", "baseline_abs"}
    ]
    pairwise_focus = sorted(pairwise_focus, key=lambda row: (-abs(row["delta_right_minus_left"]), row["comparison_type"], row["variable"], row["field"]))

    lines = []
    lines.append("# 12个 v11_with_abs 文件对比分析报告")
    lines.append("")
    lines.append("## 1. 数据范围")
    lines.append(f"- 文件数量：{len(file_rows)}")
    lines.append("- 组合结构：GPP / NEE / RECO × flash / nonflash × SMrz / SMs")
    lines.append(f"- 最大事件数：{max_events['dataset_id']} = {max_events['event_count']:,}")
    lines.append(f"- 最小事件数：{min_events['dataset_id']} = {min_events['event_count']:,}")
    lines.append(f"- 数值字段统计默认采用事件维前 {SAMPLE_SIZE:,} 个等步长样本或全量数组。")
    lines.append("")
    lines.append("## 2. 字段结构")
    lines.append(f"- 全部 12 文件共同字段数：{len(common_all)}")
    lines.append(f"- 全体共同字段：{', '.join(common_all)}")
    lines.append(f"- flash 共同字段：{', '.join(flash_common)}")
    lines.append(f"- nonflash 共同字段：{', '.join(nonflash_common)}")
    lines.append(f"- GPP 的 with_abs 字段：{', '.join(variable_abs_fields['GPP'])}")
    lines.append(f"- NEE 的 with_abs 字段：{', '.join(variable_abs_fields['NEE'])}")
    lines.append(f"- RECO 的 with_abs 字段：{', '.join(variable_abs_fields['RECO'])}")
    lines.append("")
    lines.append("## 3. 核心对比")
    lines.append("### 3.1 响应检测率")
    lines.extend(flash_nonflash_lines or ["- 未能计算 response_detected 对比。"])
    lines.append("")
    lines.append("### 3.2 核心指标差异较大的组合")
    for row in pairwise_focus[:12]:
        lines.append(
            f"- {row['comparison_type']} | {row['variable']} | {row['field']} ({row['left_field']} vs {row['right_field']}) | {row['left_dataset']}={row['left_mean']:.3f}, {row['right_dataset']}={row['right_mean']:.3f}, delta={row['delta_right_minus_left']:+.3f}"
        )
    lines.append("")
    lines.append("## 4. 文献结合解释")
    for item in LITERATURE_EVIDENCE:
        lines.append(f"- {item['source']} ({item['year']}): {item['claim']} {item['link_to_analysis']}")
    lines.append("")
    lines.append("## 5. 产出文件")
    lines.append("- `file_inventory.csv`：文件级清单")
    lines.append("- `field_presence_matrix.csv`：字段存在矩阵")
    lines.append("- `variable_summary.csv`：字段级统计摘要")
    lines.append("- `core_metric_comparison.csv`：核心指标摘要")
    lines.append("- `paired_metric_deltas.csv`：flash/nonflash 与 SMrz/SMs 的均值差")
    lines.append("- `literature_evidence_table.csv`：文献证据表")
    lines.append("- `figures/*.png`：事件数、响应率、字段覆盖与核心指标热图")
    lines.append("")
    lines.append("## 6. 解释边界")
    lines.append("- 本报告的字段统计重点是跨文件可比性与数量级差异，不替代逐区域、逐生物群系的精细空间分析。")
    lines.append("- 连续型变量采用样本统计以控制运行成本；事件数和字段结构来自文件全量元数据。")
    return "\n".join(lines) + "\n"


def plot_group_response_heatmap(rows: Sequence[Dict], group_type: str, out_png: str) -> None:
    plt = _import_plotting()
    dataset_ids = sorted({row["dataset_id"] for row in rows if row["group_type"] == group_type})
    group_labels = sorted({row["group_label"] for row in rows if row["group_type"] == group_type})
    matrix = np.full((len(group_labels), len(dataset_ids)), np.nan, dtype=float)
    row_lookup = {(row["dataset_id"], row["group_label"]): row for row in rows if row["group_type"] == group_type}
    for i, group_label in enumerate(group_labels):
        for j, dataset_id in enumerate(dataset_ids):
            row = row_lookup.get((dataset_id, group_label))
            if row and row["response_rate"] is not None:
                matrix[i, j] = row["response_rate"]
    fig, ax = plt.subplots(figsize=(14, max(4, 0.5 * max(len(group_labels), 1))))
    im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd", vmin=0.0, vmax=1.0)
    ax.set_xticks(range(len(dataset_ids)))
    ax.set_xticklabels(dataset_ids, rotation=45, ha="right")
    ax.set_yticks(range(len(group_labels)))
    ax.set_yticklabels(group_labels)
    ax.set_title(f"{group_type} response-rate heatmap")
    fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    fig.tight_layout()
    fig.savefig(out_png, dpi=200)
    plt.close(fig)


def plot_yearly_response_lines(rows: Sequence[Dict], out_png: str) -> None:
    plt = _import_plotting()
    fig, ax = plt.subplots(figsize=(14, 5))
    dataset_ids = sorted({row["dataset_id"] for row in rows if row["group_type"] == "year"})
    for dataset_id in dataset_ids:
        subset = [row for row in rows if row["group_type"] == "year" and row["dataset_id"] == dataset_id and row["group_label"].isdigit()]
        subset.sort(key=lambda row: int(row["group_label"]))
        ax.plot([int(row["group_label"]) for row in subset], [row["response_rate"] for row in subset], linewidth=1.1, label=dataset_id)
    ax.set_xlabel("Year")
    ax.set_ylabel("Response rate")
    ax.set_title("Yearly response-rate trajectories")
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_png, dpi=200)
    plt.close(fig)


def build_stratified_report(rows: Sequence[Dict], pair_rows: Sequence[Dict], group_type: str, title: str, note: Optional[str] = None) -> str:
    group_labels = sorted({row["group_label"] for row in rows if row["group_type"] == group_type})
    focus = [row for row in pair_rows if row["group_type"] == group_type and row["metric"] in {"response_rate", "baseline_abs_mean", "drop_abs_mean", "change_to_peak_abs_mean", "recovery_rate_abs_mean"}]
    focus = sorted(focus, key=lambda row: (-abs(row["delta_right_minus_left"]), row["variable"], row["metric"], row["group_label"]))
    lines = [f"# {title}", ""]
    lines.append(f"- 分组数：{len(group_labels)}")
    lines.append(f"- 分组标签：{', '.join(group_labels)}")
    if note:
        lines.append(f"- 说明：{note}")
    lines.append("")
    lines.append("## 差异最显著的组合")
    for row in focus[:20]:
        lines.append(
            f"- {row['comparison_type']} | {row['variable']} | {row['group_label']} | {row['metric']} | {row['left_dataset']}={row['left_value']:.3f}, {row['right_dataset']}={row['right_value']:.3f}, delta={row['delta_right_minus_left']:+.3f}"
        )
    return "\n".join(lines) + "\n"


def write_stratified_outputs(dataset_specs: Sequence[DatasetSpec]) -> None:
    for folder in (CONTINENT_DIR, YEAR_DIR, RECOVERY_DIR, CLIMATE_VEG_DIR):
        os.makedirs(folder, exist_ok=True)

    grouped = aggregate_stratified_rows(dataset_specs)
    pairwise = {group_type: build_group_pairwise_rows(rows, group_type) for group_type, rows in grouped.items()}

    summary_headers = [
        "dataset_id",
        "variable",
        "drought_type",
        "soil_layer",
        "group_type",
        "group_label",
        "event_count",
        "response_rate",
    ] + [f"{metric}_mean" for metric in STRATIFIED_METRICS if metric != "response_detected"]
    pair_headers = [
        "comparison_type",
        "group_type",
        "group_label",
        "variable",
        "soil_layer",
        "metric",
        "left_dataset",
        "right_dataset",
        "left_value",
        "right_value",
        "delta_right_minus_left",
    ]

    write_csv(os.path.join(CONTINENT_DIR, "continent_summary.csv"), grouped["continent"], summary_headers)
    write_csv(os.path.join(CONTINENT_DIR, "continent_pairwise_deltas.csv"), pairwise["continent"], pair_headers)
    plot_group_response_heatmap(grouped["continent"], "continent", os.path.join(CONTINENT_DIR, "continent_response_rate_heatmap.png"))
    write_text(os.path.join(CONTINENT_DIR, "continent_report.md"), build_stratified_report(grouped["continent"], pairwise["continent"], "continent", "大洲分层分析报告"))

    write_csv(os.path.join(YEAR_DIR, "yearly_summary.csv"), grouped["year"], summary_headers)
    write_csv(os.path.join(YEAR_DIR, "year_period_summary.csv"), grouped["year_period"], summary_headers)
    write_csv(os.path.join(YEAR_DIR, "year_period_pairwise_deltas.csv"), pairwise["year_period"], pair_headers)
    plot_yearly_response_lines(grouped["year"], os.path.join(YEAR_DIR, "yearly_response_rate_lines.png"))
    plot_group_response_heatmap(grouped["year_period"], "year_period", os.path.join(YEAR_DIR, "year_period_response_rate_heatmap.png"))
    write_text(os.path.join(YEAR_DIR, "year_group_report.md"), build_stratified_report(grouped["year_period"], pairwise["year_period"], "year_period", "年份分组分析报告"))

    write_csv(os.path.join(RECOVERY_DIR, "recovery_bin_summary.csv"), grouped["recovery_bin"], summary_headers)
    write_csv(os.path.join(RECOVERY_DIR, "recovery_bin_pairwise_deltas.csv"), pairwise["recovery_bin"], pair_headers)
    plot_group_response_heatmap(grouped["recovery_bin"], "recovery_bin", os.path.join(RECOVERY_DIR, "recovery_bin_response_rate_heatmap.png"))
    write_text(os.path.join(RECOVERY_DIR, "recovery_bin_report.md"), build_stratified_report(grouped["recovery_bin"], pairwise["recovery_bin"], "recovery_bin", "恢复时长分组分析报告"))

    climate_note = "本地未定位到可直接复用的植被类型分类栅格，本目录先提供基于纬度的气候带代理分层；植被类型精确拆分需补充独立分类数据源。"
    write_csv(os.path.join(CLIMATE_VEG_DIR, "climate_zone_summary.csv"), grouped["climate_zone"], summary_headers)
    write_csv(os.path.join(CLIMATE_VEG_DIR, "climate_zone_pairwise_deltas.csv"), pairwise["climate_zone"], pair_headers)
    plot_group_response_heatmap(grouped["climate_zone"], "climate_zone", os.path.join(CLIMATE_VEG_DIR, "climate_zone_response_rate_heatmap.png"))
    write_text(os.path.join(CLIMATE_VEG_DIR, "climate_zone_report.md"), build_stratified_report(grouped["climate_zone"], pairwise["climate_zone"], "climate_zone", "气候带分层分析报告", note=climate_note))
    write_text(os.path.join(CLIMATE_VEG_DIR, "vegetation_type_status.md"), climate_note + "\n")


def main() -> None:
    os.makedirs(FIGURE_DIR, exist_ok=True)
    dataset_specs = load_dataset_specs()
    inventories = [inventory_dataset(spec, sample_size=SAMPLE_SIZE) for spec in dataset_specs]
    file_rows = build_file_inventory_rows(inventories)
    variable_rows = [row for inv in inventories for row in inv["variable_rows"]]
    field_presence_rows = build_field_presence_rows(inventories)
    core_metric_rows = build_core_metric_rows(variable_rows)
    pairwise_rows = build_pairwise_delta_rows(core_metric_rows)

    file_headers = [
        "dataset_id",
        "variable",
        "drought_type",
        "soil_layer",
        "code_label",
        "event_count",
        "variable_count",
        "field_count",
        "title",
        "dims",
        "file_path",
    ]
    write_csv(os.path.join(OUTPUT_DIR, "file_inventory.csv"), file_rows, file_headers)

    variable_headers = [
        "dataset_id",
        "variable",
        "drought_type",
        "soil_layer",
        "code_label",
        "field",
        "dtype",
        "dimensions",
        "units",
        "long_name",
        "sample_size",
        "size",
        "finite_count",
        "nan_count",
        "finite_ratio",
        "min",
        "max",
        "mean",
        "median",
        "std",
        "p05",
        "p25",
        "p75",
        "p95",
        "file_path",
    ]
    write_csv(os.path.join(OUTPUT_DIR, "variable_summary.csv"), variable_rows, variable_headers)

    field_headers = ["field", "present_count"] + [row["dataset_id"] for row in file_rows]
    write_csv(os.path.join(OUTPUT_DIR, "field_presence_matrix.csv"), field_presence_rows, field_headers)

    core_headers = [
        "dataset_id",
        "variable",
        "drought_type",
        "soil_layer",
        "code_label",
        "normalized_field",
        "field",
        "dtype",
        "dimensions",
        "units",
        "sample_size",
        "finite_ratio",
        "mean",
        "median",
        "std",
        "p05",
        "p25",
        "p75",
        "p95",
    ]
    write_csv(os.path.join(OUTPUT_DIR, "core_metric_comparison.csv"), core_metric_rows, core_headers)

    pair_headers = [
        "comparison_type",
        "variable",
        "soil_layer",
        "field",
        "left_field",
        "right_field",
        "left_dataset",
        "right_dataset",
        "left_mean",
        "right_mean",
        "delta_right_minus_left",
    ]
    write_csv(os.path.join(OUTPUT_DIR, "paired_metric_deltas.csv"), pairwise_rows, pair_headers)
    write_literature_table()

    plot_event_counts(file_rows)
    plot_response_rates(core_metric_rows)
    plot_field_presence_heatmap(field_presence_rows, [row["dataset_id"] for row in file_rows])
    plot_core_metric_heatmap(core_metric_rows)
    write_stratified_outputs(dataset_specs)

    report = build_report(file_rows, field_presence_rows, core_metric_rows, pairwise_rows)
    write_text(os.path.join(OUTPUT_DIR, "compare_analysis_report.md"), report)
    print(f"Wrote outputs to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
