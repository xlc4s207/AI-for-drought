#!/usr/bin/env python3
"""Build Chinese markdown and xlsx comparison reports for GPP SMrz version outputs."""

import argparse
import datetime as dt
import math
import os
import zipfile
from xml.sax.saxutils import escape
from typing import Dict, Iterable, List, Optional

import netCDF4 as nc
import numpy as np


DEFAULT_FILES = [
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120.nc",
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100.nc",
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5.nc",
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260324_latfix_relm03_abspeak_absrec_c10_w420.nc",
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260323_rel_m02.nc",
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260323_latfix_relm05_rec_m02_c10_w360.nc",
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260323_latfix_rec_m02.nc",
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260322_lu_025deg.nc",
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260322_025deg.nc",
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v20260316.nc",
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/gpp_response_SMrz_events_global_v11_with_abs.nc",
]

DEFAULT_OUTPUT = (
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/"
    "gpp_smrz_version_comparison_20260324.md"
)
DEFAULT_XLSX_OUTPUT = (
    "/home/xulc/flash_drought/process/GPP-draught-analysis/code1/results/"
    "gpp_smrz_version_comparison_20260324.xlsx"
)

REQUIRED_FIELDS = [
    "lat",
    "lon",
    "response_detected",
    "t_response_onset_start",
    "t_response",
    "t_response_drought_start",
    "t_response_after_threshold",
    "t_recover_to_baseline",
    "t_recover",
    "t_recover_drought_start",
]


def to_numpy(var):
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        arr = arr.filled(np.nan)
    arr = np.asarray(arr)
    if np.issubdtype(arr.dtype, np.integer):
        arr = arr.astype(np.float64)
    fill_value = getattr(var, "_FillValue", None)
    if fill_value is not None:
        if np.issubdtype(arr.dtype, np.floating):
            arr[np.isclose(arr, float(fill_value), equal_nan=False)] = np.nan
        else:
            arr[arr == fill_value] = np.nan
    return arr


def clean_time(values):
    arr = np.asarray(values, dtype=np.float64)
    arr[arr < 0] = np.nan
    return arr


def finite_mean(values):
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return math.nan
    return float(np.nanmean(arr))


def finite_median(values):
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return math.nan
    return float(np.nanmedian(arr))


def format_num(value, decimals=2):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "-"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    return f"{float(value):,.{decimals}f}"


def format_text(value, decimals=2):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "-"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{decimals}f}"
    return str(value)


def pick_metric_alias(data: Dict[str, Iterable], aliases: List[str]):
    for name in aliases:
        if name in data:
            return data[name]
    return None


def _unique_pixel_count(lat, lon, mask):
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    if lat.size == 0 or lon.size == 0:
        return 0
    if lat.shape != mask.shape or lon.shape != mask.shape:
        return 0
    valid = mask & np.isfinite(lat) & np.isfinite(lon)
    if not np.any(valid):
        return 0
    pairs = np.column_stack((np.round(lat[valid], 6), np.round(lon[valid], 6)))
    return int(np.unique(pairs, axis=0).shape[0])


def summarize_version(file_path: str, data: Dict[str, Iterable], attrs: Optional[Dict[str, str]] = None):
    response_flag = np.asarray(data.get("response_detected", []), dtype=np.float64) == 1
    total_events = int(len(response_flag))
    lat = np.asarray(data.get("lat", []), dtype=np.float64)
    lon = np.asarray(data.get("lon", []), dtype=np.float64)

    response_onset = clean_time(pick_metric_alias(data, ["t_response_onset_start", "t_response"]))
    response_drought = clean_time(pick_metric_alias(data, ["t_response_drought_start", "t_response_after_threshold"]))
    recover_peak = clean_time(pick_metric_alias(data, ["t_recover_to_baseline", "t_recover"]))
    recover_drought = clean_time(pick_metric_alias(data, ["t_recover_drought_start"]))

    response_count = int(np.sum(response_flag))
    recovery_mask = np.isfinite(recover_peak)
    recovery_count = int(np.sum(recovery_mask))

    row = {
        "file_name": os.path.basename(file_path),
        "file_path": file_path,
        "version": os.path.basename(file_path).replace("gpp_response_SMrz_events_global_", "").replace(".nc", ""),
        "event_total": total_events,
        "response_count": response_count,
        "response_pct": (100.0 * response_count / total_events) if total_events > 0 else math.nan,
        "response_pixel_count": _unique_pixel_count(lat, lon, response_flag),
        "recovery_count": recovery_count,
        "recovery_pct_total": (100.0 * recovery_count / total_events) if total_events > 0 else math.nan,
        "recovery_pct_response": (100.0 * recovery_count / response_count) if response_count > 0 else math.nan,
        "recovery_pixel_count": _unique_pixel_count(lat, lon, recovery_mask),
        "response_onset_mean": finite_mean(response_onset),
        "response_onset_median": finite_median(response_onset),
        "response_drought_mean": finite_mean(response_drought),
        "response_drought_median": finite_median(response_drought),
        "recover_peak_mean": finite_mean(recover_peak),
        "recover_peak_median": finite_median(recover_peak),
        "recover_drought_mean": finite_mean(recover_drought),
        "recover_drought_median": finite_median(recover_drought),
        "title": (attrs or {}).get("title", ""),
        "description": (attrs or {}).get("description", ""),
        "source_events": (attrs or {}).get("source_event_file") or (attrs or {}).get("source_events", ""),
        "source_data": (attrs or {}).get("source_data_file") or (attrs or {}).get("source_gpp", ""),
    }
    if "v11_with_abs" in row["version"]:
        row["notes"] = (
            "旧版字段；响应时间主要对应 `t_response`，恢复时间主要对应 "
            "`t_recover_to_baseline/t_recover`，缺少明确的 drought 起算恢复字段。"
        )
    elif "v20260316" in row["version"]:
        row["notes"] = (
            "过渡版字段；可同时统计 `t_response_onset_start` 与 "
            "`t_response_drought_start/t_response_after_threshold`，但恢复仍以单一恢复字段为主。"
        )
    else:
        row["notes"] = (
            "新版紧凑字段；`response_detected==1` 记为响应，"
            "`t_response_onset_start`/`t_response_drought_start` 分别表示 onset 与 drought 起算响应时间，"
            "`t_recover_to_baseline`/`t_recover_drought_start` 表示峰值后与 drought 起算恢复时间。"
        )
    return row


def load_file_summary(file_path: str):
    with nc.Dataset(file_path, "r") as ds:
        data = {name: to_numpy(ds.variables[name]) for name in REQUIRED_FIELDS if name in ds.variables}
        attrs = {name: getattr(ds, name) for name in ds.ncattrs()}
    return summarize_version(file_path, data, attrs)


def _find_row(rows, suffix):
    for row in rows:
        if row["version"] == suffix:
            return row
    return None


def build_count_table(rows: List[Dict[str, object]]):
    header = [
        "版本",
        "输出事件数",
        "响应事件数",
        "响应比例(%)",
        "响应像元数",
        "恢复事件数",
        "恢复/输出(%)",
        "恢复/响应(%)",
        "恢复像元数",
    ]
    table = [header]
    for row in rows:
        table.append(
            [
                row["version"],
                row["event_total"],
                row["response_count"],
                round(row["response_pct"], 2) if math.isfinite(row["response_pct"]) else None,
                row["response_pixel_count"],
                row["recovery_count"],
                round(row["recovery_pct_total"], 2) if math.isfinite(row["recovery_pct_total"]) else None,
                round(row["recovery_pct_response"], 2) if math.isfinite(row["recovery_pct_response"]) else None,
                row["recovery_pixel_count"],
            ]
        )
    return table


def build_full_table(rows: List[Dict[str, object]]):
    header = [
        "版本",
        "输出事件数",
        "响应事件数",
        "响应比例(%)",
        "响应像元数",
        "恢复事件数",
        "恢复/输出(%)",
        "恢复/响应(%)",
        "恢复像元数",
        "平均响应时间_onset天",
        "中位响应时间_onset天",
        "平均响应时间_drought天",
        "中位响应时间_drought天",
        "平均恢复时间_peak_to_recover天",
        "中位恢复时间_peak_to_recover天",
        "平均恢复时间_drought_to_recover天",
        "中位恢复时间_drought_to_recover天",
        "事件源",
        "数据源",
        "字段口径说明",
    ]
    table = [header]
    for row in rows:
        table.append(
            [
                row["version"],
                row["event_total"],
                row["response_count"],
                round(row["response_pct"], 2) if math.isfinite(row["response_pct"]) else None,
                row["response_pixel_count"],
                row["recovery_count"],
                round(row["recovery_pct_total"], 2) if math.isfinite(row["recovery_pct_total"]) else None,
                round(row["recovery_pct_response"], 2) if math.isfinite(row["recovery_pct_response"]) else None,
                row["recovery_pixel_count"],
                round(row["response_onset_mean"], 2) if math.isfinite(row["response_onset_mean"]) else None,
                round(row["response_onset_median"], 2) if math.isfinite(row["response_onset_median"]) else None,
                round(row["response_drought_mean"], 2) if math.isfinite(row["response_drought_mean"]) else None,
                round(row["response_drought_median"], 2) if math.isfinite(row["response_drought_median"]) else None,
                round(row["recover_peak_mean"], 2) if math.isfinite(row["recover_peak_mean"]) else None,
                round(row["recover_peak_median"], 2) if math.isfinite(row["recover_peak_median"]) else None,
                round(row["recover_drought_mean"], 2) if math.isfinite(row["recover_drought_mean"]) else None,
                round(row["recover_drought_median"], 2) if math.isfinite(row["recover_drought_median"]) else None,
                row["source_events"] or "-",
                row["source_data"] or "-",
                row["notes"],
            ]
        )
    return table


def build_timing_table(rows: List[Dict[str, object]]):
    header = [
        "版本",
        "平均响应时间_onset天",
        "中位响应时间_onset天",
        "平均响应时间_drought天",
        "中位响应时间_drought天",
        "平均恢复时间_peak_to_recover天",
        "中位恢复时间_peak_to_recover天",
        "平均恢复时间_drought_to_recover天",
        "中位恢复时间_drought_to_recover天",
    ]
    table = [header]
    for row in rows:
        table.append(
            [
                row["version"],
                round(row["response_onset_mean"], 2) if math.isfinite(row["response_onset_mean"]) else None,
                round(row["response_onset_median"], 2) if math.isfinite(row["response_onset_median"]) else None,
                round(row["response_drought_mean"], 2) if math.isfinite(row["response_drought_mean"]) else None,
                round(row["response_drought_median"], 2) if math.isfinite(row["response_drought_median"]) else None,
                round(row["recover_peak_mean"], 2) if math.isfinite(row["recover_peak_mean"]) else None,
                round(row["recover_peak_median"], 2) if math.isfinite(row["recover_peak_median"]) else None,
                round(row["recover_drought_mean"], 2) if math.isfinite(row["recover_drought_mean"]) else None,
                round(row["recover_drought_median"], 2) if math.isfinite(row["recover_drought_median"]) else None,
            ]
        )
    return table


def build_source_table(rows: List[Dict[str, object]]):
    header = ["版本", "事件源", "数据源", "字段口径说明"]
    table = [header]
    for row in rows:
        table.append([row["version"], row["source_events"] or "-", row["source_data"] or "-", row["notes"]])
    return table


def build_markdown(rows: List[Dict[str, object]]):
    lines = [
        "# GPP根系土壤湿度骤旱版本对比报告",
        "",
        "## 概述",
        "",
        "本报告对 `code1` 下 11 个 GPP-SMrz 结果文件进行统一统计对比。",
        "除特别说明为唯一像元数外，表中计数均为事件级统计。",
        "",
        "## 综合总表",
        "",
        "| 版本 | 输出事件数 | 响应事件数 | 响应比例(%) | 响应像元数 | 恢复事件数 | 恢复/输出(%) | 恢复/响应(%) | 恢复像元数 | 平均响应时间_onset(天) | 中位响应时间_onset(天) | 平均响应时间_drought(天) | 中位响应时间_drought(天) | 平均恢复时间_peak_to_recover(天) | 中位恢复时间_peak_to_recover(天) | 平均恢复时间_drought_to_recover(天) | 中位恢复时间_drought_to_recover(天) | 事件源 | 数据源 | 字段口径说明 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {version} | {event_total} | {response_count} | {response_pct} | {response_pixel_count} | "
            "{recovery_count} | {recovery_pct_total} | {recovery_pct_response} | {recovery_pixel_count} | "
            "{response_onset_mean} | {response_onset_median} | {response_drought_mean} | {response_drought_median} | "
            "{recover_peak_mean} | {recover_peak_median} | {recover_drought_mean} | {recover_drought_median} | "
            "{source_events} | {source_data} | {notes} |".format(
                version=row["version"],
                event_total=format_num(row["event_total"], 0),
                response_count=format_num(row["response_count"], 0),
                response_pct=format_num(row["response_pct"]),
                response_pixel_count=format_num(row["response_pixel_count"], 0),
                recovery_count=format_num(row["recovery_count"], 0),
                recovery_pct_total=format_num(row["recovery_pct_total"]),
                recovery_pct_response=format_num(row["recovery_pct_response"]),
                recovery_pixel_count=format_num(row["recovery_pixel_count"], 0),
                response_onset_mean=format_num(row["response_onset_mean"]),
                response_onset_median=format_num(row["response_onset_median"]),
                response_drought_mean=format_num(row["response_drought_mean"]),
                response_drought_median=format_num(row["response_drought_median"]),
                recover_peak_mean=format_num(row["recover_peak_mean"]),
                recover_peak_median=format_num(row["recover_peak_median"]),
                recover_drought_mean=format_num(row["recover_drought_mean"]),
                recover_drought_median=format_num(row["recover_drought_median"]),
                source_events=row["source_events"] or "-",
                source_data=row["source_data"] or "-",
                notes=row["notes"],
            )
        )

    rec120 = _find_row(rows, "v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec120")
    rec100 = _find_row(rows, "v20260324_latfix_relm03_abspeak_absrec_c30x095_w420_decline30_d5_rec100")
    c30 = _find_row(rows, "v20260324_latfix_relm03_abspeak_absrec_c30_w420_decline30_d5")
    c10 = _find_row(rows, "v20260324_latfix_relm03_abspeak_absrec_c10_w420")
    lu = _find_row(rows, "v20260322_lu_025deg")

    lines.extend(["", "## 主要结论", ""])
    if c10 and c30:
        lines.append(
            "- 从 `c10_w420` 到 `c30_w420_decline30_d5`，响应事件数从 "
            f"{format_num(c10['response_count'], 0)} 降到 {format_num(c30['response_count'], 0)}，"
            "说明“干旱开始后30天内持续下降”的门槛明显筛掉了一批弱响应或噪声事件。"
        )
    if c30 and rec120:
        lines.append(
            "- 加入 `0.95×干旱前30天均值` 基线并设置 `rec120` 后，响应事件数保持不变 "
            f"({format_num(rec120['response_count'], 0)})，但有效恢复事件降到 "
            f"{format_num(rec120['recovery_count'], 0)}，峰值到恢复的平均时间降到 "
            f"{format_num(rec120['recover_peak_mean'])} 天。"
        )
    if rec120 and rec100:
        lines.append(
            "- 将最大有效恢复时间从 120 天进一步收紧到 100 天后，有效恢复事件从 "
            f"{format_num(rec120['recovery_count'], 0)} 进一步降到 {format_num(rec100['recovery_count'], 0)}，"
            f"峰值到恢复的平均时间也从 {format_num(rec120['recover_peak_mean'])} 天降到 "
            f"{format_num(rec100['recover_peak_mean'])} 天。"
        )
    if lu:
        lines.append(
            "- `v20260322_lu_025deg` 相比更早的 `v20260316` 和 `v11_with_abs` 明显更严格，"
            f"其输出事件数只有 {format_num(lu['event_total'], 0)}，因此这三代结果不应直接等同对比。"
        )

    lines.append("")
    return "\n".join(lines)


def _excel_col_name(idx):
    idx += 1
    chars = []
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        chars.append(chr(65 + rem))
    return "".join(reversed(chars))


def _xml_cell(row_idx, col_idx, value):
    ref = f"{_excel_col_name(col_idx)}{row_idx}"
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return f'<c r="{ref}" t="inlineStr"><is><t>-</t></is></c>'
    if isinstance(value, (int, np.integer)):
        return f'<c r="{ref}"><v>{int(value)}</v></c>'
    if isinstance(value, (float, np.floating)):
        return f'<c r="{ref}"><v>{float(value)}</v></c>'
    text = escape(str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def _sheet_xml(rows):
    xml_rows = []
    for r_idx, row in enumerate(rows, start=1):
        cells = "".join(_xml_cell(r_idx, c_idx, value) for c_idx, value in enumerate(row))
        xml_rows.append(f'<row r="{r_idx}">{cells}</row>')
    dimension = f"A1:{_excel_col_name(max(len(rows[0]) - 1, 0))}{max(len(rows), 1)}"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension}"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        '</worksheet>'
    )


def write_xlsx(output_path, sheets):
    created = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "docProps/core.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            "<dc:creator>Codex</dc:creator>"
            "<cp:lastModifiedBy>Codex</cp:lastModifiedBy>"
            "<dc:title>GPP SMrz版本对比</dc:title>"
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>'
            "</cp:coreProperties>",
        )
        zf.writestr(
            "docProps/app.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            "<Application>Codex</Application>"
            f"<TitlesOfParts><vt:vector size=\"{len(sheets)}\" baseType=\"lpstr\">"
            + "".join(f"<vt:lpstr>{escape(name)}</vt:lpstr>" for name, _rows in sheets)
            + "</vt:vector></TitlesOfParts>"
            f"<HeadingPairs><vt:vector size=\"2\" baseType=\"variant\"><vt:variant><vt:lpstr>工作表</vt:lpstr></vt:variant><vt:variant><vt:i4>{len(sheets)}</vt:i4></vt:variant></vt:vector></HeadingPairs>"
            "</Properties>",
        )
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<sheets>"
            + "".join(
                f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
                for i, (name, _rows) in enumerate(sheets, start=1)
            )
            + "</sheets></workbook>",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            + "</Relationships>",
        )
        zf.writestr(
            "xl/styles.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            '</styleSheet>',
        )
        for i, (_name, rows) in enumerate(sheets, start=1):
            zf.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(rows))


def build_excel_sheets(rows):
    return [
        ("综合总表", build_full_table(rows)),
        ("事件与像元统计", build_count_table(rows)),
        ("时间指标统计", build_timing_table(rows)),
        ("数据源说明", build_source_table(rows)),
    ]


def parse_args():
    parser = argparse.ArgumentParser(description="Build Chinese markdown and xlsx comparison reports for GPP SMrz versions.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="输出markdown路径。")
    parser.add_argument("--xlsx-output", default=DEFAULT_XLSX_OUTPUT, help="输出xlsx路径。")
    parser.add_argument("--files", nargs="*", default=DEFAULT_FILES, help="Result files to compare.")
    return parser.parse_args()


def main():
    args = parse_args()
    rows = [load_file_summary(path) for path in args.files]
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(build_markdown(rows))
    write_xlsx(args.xlsx_output, build_excel_sheets(rows))
    print(f"Markdown报告已写出: {args.output}")
    print(f"Excel表格已写出: {args.xlsx_output}")


if __name__ == "__main__":
    main()
