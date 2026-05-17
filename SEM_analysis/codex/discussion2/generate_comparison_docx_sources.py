#!/usr/bin/env python3
"""Generate HTML sources for comparison-scope discussion documents."""

from __future__ import annotations

from html import escape
from pathlib import Path


ROOT = Path("/home/xulc/flash_drought/process/SEM_analysis/codex/discussion2")

GPP_PREPEAK_OVERVIEW = "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/prepeak_event_sem_path_diagrams_overview.png"
GPP_RECOVERY_OVERVIEW = "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/sem_process_recoverywin_precipEmean_usertrim/sem_process_recoverywin_precipEmean_usertrim_sem_path_diagrams_overview.png"
RECO_PREPEAK_OVERVIEW = "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_prepeak_event_mechanism_20260421/sem_prepeak_event_mechanism_sem_path_diagrams_overview.png"
RECO_RECOVERY_OVERVIEW = "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260415/process_recoverywin_sem_path_diagrams_overview.png"

GPP_COMPARE_DIR = "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_compare_prepeak_vs_recoverywin_20260420"
RECO_COMPARE_DIR = "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_compare_prepeak_vs_recoverywin_20260421"

DOCS = [
    {
        "md": ROOT / "02_within_metric_scope_comparison/gpp_prepeak_vs_recoverywin_analysis_cn.md",
        "html": ROOT / "02_within_metric_scope_comparison/gpp_prepeak_vs_recoverywin_analysis_docx_source.html",
        "blocks": [
            {
                "after": 0,
                "figures": [
                    (f"{GPP_COMPARE_DIR}/all_biomes_prepeak_vs_recoverywin_beeswarm.png", "GPP compare beeswarm", "图 1. GPP 在前置预测口径与过程解释口径下的全 biome beeswarm 对比图。该图用于展示特征排序如何从峰值前记忆转向恢复期近端控制。"),
                    (GPP_PREPEAK_OVERVIEW, "GPP prepeak overview", "图 2. GPP 前置预测口径的 SEM 路径图总览。该图代表恢复记忆框架的整体结构。"),
                ],
            },
            {
                "after": 1,
                "figures": [
                    (GPP_RECOVERY_OVERVIEW, "GPP recovery overview", "图 3. GPP 过程解释口径的 SEM 路径图总览。该图展示恢复期即时环境控制结构。"),
                    (f"{GPP_COMPARE_DIR}/Forest_prepeak_vs_recoverywin_dependence.png", "GPP Forest compare", "图 4. Forest 中前置预测与过程解释口径的 dependence 对比。该图用于显示森林恢复记忆与恢复期即时控制的差异。"),
                ],
            },
            {
                "after": 2,
                "figures": [
                    (f"{GPP_COMPARE_DIR}/Grassland_prepeak_vs_recoverywin_dependence.png", "GPP Grassland compare", "图 5. Grassland 中前置预测与过程解释口径的 dependence 对比。"),
                    (f"{GPP_COMPARE_DIR}/Savanna_prepeak_vs_recoverywin_dependence.png", "GPP Savanna compare", "图 6. Savanna 中前置预测与过程解释口径的 dependence 对比。"),
                ],
            },
            {
                "after": 3,
                "figures": [
                    (f"{GPP_COMPARE_DIR}/Cropland_prepeak_vs_recoverywin_dependence.png", "GPP Cropland compare", "图 7. Cropland 中前置预测与过程解释口径的 dependence 对比。"),
                    (f"{GPP_COMPARE_DIR}/Shrubland_prepeak_vs_recoverywin_dependence.png", "GPP Shrubland compare", "图 8. Shrubland 中前置预测与过程解释口径的 dependence 对比。"),
                ],
            },
        ],
    },
    {
        "md": ROOT / "02_within_metric_scope_comparison/reco_prepeak_vs_recoverywin_analysis_cn.md",
        "html": ROOT / "02_within_metric_scope_comparison/reco_prepeak_vs_recoverywin_analysis_docx_source.html",
        "blocks": [
            {
                "after": 0,
                "figures": [
                    (f"{RECO_COMPARE_DIR}/all_biomes_prepeak_vs_recoverywin_beeswarm.png", "RECO compare beeswarm", "图 1. RECO 在前置预测口径与过程解释口径下的全 biome beeswarm 对比图。"),
                    (RECO_PREPEAK_OVERVIEW, "RECO prepeak overview", "图 2. RECO 前置预测口径的 SEM 路径图总览。"),
                ],
            },
            {
                "after": 1,
                "figures": [
                    (RECO_RECOVERY_OVERVIEW, "RECO recovery overview", "图 3. RECO 过程解释口径的 SEM 路径图总览。"),
                    (f"{RECO_COMPARE_DIR}/Forest_prepeak_vs_recoverywin_dependence.png", "RECO Forest compare", "图 4. Forest 中前置预测与过程解释口径的 dependence 对比。"),
                ],
            },
            {
                "after": 2,
                "figures": [
                    (f"{RECO_COMPARE_DIR}/Grassland_prepeak_vs_recoverywin_dependence.png", "RECO Grassland compare", "图 5. Grassland 中前置预测与过程解释口径的 dependence 对比。"),
                    (f"{RECO_COMPARE_DIR}/Savanna_prepeak_vs_recoverywin_dependence.png", "RECO Savanna compare", "图 6. Savanna 中前置预测与过程解释口径的 dependence 对比。"),
                ],
            },
            {
                "after": 3,
                "figures": [
                    (f"{RECO_COMPARE_DIR}/Cropland_prepeak_vs_recoverywin_dependence.png", "RECO Cropland compare", "图 7. Cropland 中前置预测与过程解释口径的 dependence 对比。"),
                    (f"{RECO_COMPARE_DIR}/Shrubland_prepeak_vs_recoverywin_dependence.png", "RECO Shrubland compare", "图 8. Shrubland 中前置预测与过程解释口径的 dependence 对比。"),
                ],
            },
            {
                "after": 4,
                "figures": [
                    (f"{RECO_COMPARE_DIR}/Wetland_prepeak_vs_recoverywin_dependence.png", "RECO Wetland compare", "图 9. Wetland 中前置预测与过程解释口径的 dependence 对比。湿地在 RECO 双口径比较中是重要的边界案例。"),
                ],
            },
        ],
    },
    {
        "md": ROOT / "03_gpp_vs_reco_cross_metric_comparison/gpp_vs_reco_overall_synthesis_cn.md",
        "html": ROOT / "03_gpp_vs_reco_cross_metric_comparison/gpp_vs_reco_overall_synthesis_docx_source.html",
        "blocks": [
            {
                "after": 0,
                "figures": [
                    (GPP_PREPEAK_OVERVIEW, "GPP prepeak overview", "图 1. GPP 前置预测口径的 SEM 路径图总览。"),
                    (RECO_PREPEAK_OVERVIEW, "RECO prepeak overview", "图 2. RECO 前置预测口径的 SEM 路径图总览。"),
                ],
            },
            {
                "after": 1,
                "figures": [
                    (GPP_RECOVERY_OVERVIEW, "GPP recovery overview", "图 3. GPP 过程解释口径的 SEM 路径图总览。"),
                    (RECO_RECOVERY_OVERVIEW, "RECO recovery overview", "图 4. RECO 过程解释口径的 SEM 路径图总览。"),
                ],
            },
            {
                "after": 2,
                "figures": [
                    (f"{GPP_COMPARE_DIR}/all_biomes_prepeak_vs_recoverywin_beeswarm.png", "GPP compare beeswarm", "图 5. GPP 双口径比较的全 biome beeswarm 图。"),
                    (f"{RECO_COMPARE_DIR}/all_biomes_prepeak_vs_recoverywin_beeswarm.png", "RECO compare beeswarm", "图 6. RECO 双口径比较的全 biome beeswarm 图。"),
                ],
            },
        ],
    },
    {
        "md": ROOT / "03_gpp_vs_reco_cross_metric_comparison/gpp_vs_reco_prepeak_analysis_cn.md",
        "html": ROOT / "03_gpp_vs_reco_cross_metric_comparison/gpp_vs_reco_prepeak_analysis_docx_source.html",
        "blocks": [
            {
                "after": 0,
                "figures": [
                    (GPP_PREPEAK_OVERVIEW, "GPP prepeak overview", "图 1. GPP 前置预测口径的 SEM 路径图总览。"),
                    (RECO_PREPEAK_OVERVIEW, "RECO prepeak overview", "图 2. RECO 前置预测口径的 SEM 路径图总览。"),
                ],
            },
            {
                "after": 1,
                "figures": [
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Forest/feature_importance_beeswarm.png", "GPP Forest prepeak beeswarm", "图 3. GPP 在 Forest 中的前置预测 beeswarm 图。"),
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Forest/feature_importance_beeswarm.png", "RECO Forest prepeak beeswarm", "图 4. RECO 在 Forest 中的前置预测 beeswarm 图。"),
                ],
            },
            {
                "after": 2,
                "figures": [
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/sem_by_biome/GPP_code1_Grassland_flash_SMrz_path_diagram.png", "GPP Grassland prepeak sem", "图 5. GPP 在 Grassland 中的前置预测路径图。"),
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_prepeak_event_mechanism_20260421/by_biome/RECO_code1_Grassland_flash_SMrz_path_diagram.png", "RECO Grassland prepeak sem", "图 6. RECO 在 Grassland 中的前置预测路径图。"),
                ],
            },
            {
                "after": 3,
                "figures": [
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/sem_by_biome/GPP_code1_Cropland_flash_SMrz_path_diagram.png", "GPP Cropland prepeak sem", "图 7. GPP 在 Cropland 中的前置预测路径图。"),
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_prepeak_event_mechanism_20260421/by_biome/RECO_code1_Cropland_flash_SMrz_path_diagram.png", "RECO Cropland prepeak sem", "图 8. RECO 在 Cropland 中的前置预测路径图。"),
                ],
            },
        ],
    },
    {
        "md": ROOT / "03_gpp_vs_reco_cross_metric_comparison/gpp_vs_reco_recoverywin_analysis_cn.md",
        "html": ROOT / "03_gpp_vs_reco_cross_metric_comparison/gpp_vs_reco_recoverywin_analysis_docx_source.html",
        "blocks": [
            {
                "after": 0,
                "figures": [
                    (GPP_RECOVERY_OVERVIEW, "GPP recovery overview", "图 1. GPP 过程解释口径的 SEM 路径图总览。"),
                    (RECO_RECOVERY_OVERVIEW, "RECO recovery overview", "图 2. RECO 过程解释口径的 SEM 路径图总览。"),
                ],
            },
            {
                "after": 1,
                "figures": [
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Forest/feature_importance_beeswarm.png", "GPP Forest recovery beeswarm", "图 3. GPP 在 Forest 中的过程解释 beeswarm 图。"),
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Forest/feature_importance_beeswarm.png", "RECO Forest recovery beeswarm", "图 4. RECO 在 Forest 中的过程解释 beeswarm 图。"),
                ],
            },
            {
                "after": 2,
                "figures": [
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/sem_process_recoverywin_precipEmean_usertrim/by_biome/GPP_code1_Grassland_flash_SMrz_path_diagram.png", "GPP Grassland recovery sem", "图 5. GPP 在 Grassland 中的过程解释路径图。"),
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260415/by_biome/RECO_code1_Grassland_flash_SMrz_path_diagram.png", "RECO Grassland recovery sem", "图 6. RECO 在 Grassland 中的过程解释路径图。"),
                ],
            },
            {
                "after": 3,
                "figures": [
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_rechunk_py_clean/sem_process_recoverywin_precipEmean_usertrim/by_biome/GPP_code1_Cropland_flash_SMrz_path_diagram.png", "GPP Cropland recovery sem", "图 7. GPP 在 Cropland 中的过程解释路径图。"),
                    ("/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260415/by_biome/RECO_code1_Cropland_flash_SMrz_path_diagram.png", "RECO Cropland recovery sem", "图 8. RECO 在 Cropland 中的过程解释路径图。"),
                ],
            },
        ],
    },
]


def split_paragraphs(lines: list[str]) -> list[str]:
    paragraphs = []
    current: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            if current:
                paragraphs.append(" ".join(part.strip() for part in current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(part.strip() for part in current))
    return paragraphs


def parse_markdown(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    title = ""
    intro: list[str] = []
    table: list[str] = []
    body: list[str] = []
    state = "title"
    for line in lines:
        if state == "title" and line.startswith("# "):
            title = line[2:].strip()
            state = "intro"
            continue
        if state == "intro":
            if line.lstrip().startswith("|"):
                state = "table"
                table.append(line)
            else:
                intro.append(line)
            continue
        if state == "table":
            if line.lstrip().startswith("|"):
                table.append(line)
            else:
                state = "body"
                body.append(line)
            continue
        body.append(line)

    intro_paragraphs = split_paragraphs(intro)
    body_paragraphs = split_paragraphs(body)
    table_parsed = parse_table(table) if table else None
    if table_parsed is None and body_paragraphs == []:
        body_paragraphs = intro_paragraphs
        intro_paragraphs = []

    return {
        "title": title,
        "intro": intro_paragraphs,
        "table": table_parsed,
        "body": body_paragraphs,
    }


def parse_table(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    header = [cell.strip() for cell in lines[0].strip().strip("|").split("|")]
    rows: list[list[str]] = []
    for line in lines[2:]:
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return header, rows


def render_table(table: tuple[list[str], list[list[str]]] | None) -> str:
    if table is None:
        return ""
    header, rows = table
    html = "<table><tr>" + "".join(f"<th>{escape(cell)}</th>" for cell in header) + "</tr>"
    for row in rows:
        html += "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
    html += "</table>"
    return html


def figure_grid(figures: list[tuple[str, str, str]]) -> str:
    rows = []
    for idx in range(0, len(figures), 2):
        cells = []
        for src, alt, caption in figures[idx: idx + 2]:
            cells.append(
                "<td>"
                f'<img src="{src}" alt="{escape(alt)}" />'
                f'<div class="caption">{escape(caption)}</div>'
                "</td>"
            )
        while len(cells) < 2:
            cells.append("<td></td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return '<table class="figure-grid">' + "".join(rows) + "</table>"


def render_doc(config: dict) -> str:
    parsed = parse_markdown(config["md"])
    body_parts = []
    blocks = {block["after"]: block for block in config["blocks"]}
    for idx, paragraph in enumerate(parsed["body"]):
        body_parts.append(f"<p>{escape(paragraph)}</p>")
        if idx in blocks:
            body_parts.append(figure_grid(blocks[idx]["figures"]))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>{escape(parsed["title"])}</title>
  <style>
    body {{
      font-family: "Arial", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
      font-size: 11pt;
      line-height: 1.55;
      color: #111;
      margin: 1cm;
    }}
    h1, h2 {{
      color: #111;
      page-break-after: avoid;
    }}
    h1 {{
      font-size: 20pt;
      text-align: center;
      margin-bottom: 0.4cm;
    }}
    h2 {{
      font-size: 15pt;
      margin-top: 0.8cm;
      margin-bottom: 0.25cm;
      border-bottom: 1px solid #bbb;
      padding-bottom: 0.08cm;
    }}
    p {{
      text-align: justify;
      margin: 0.18cm 0;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 0.35cm 0 0.45cm 0;
      font-size: 9.5pt;
    }}
    th, td {{
      border: 1px solid #999;
      padding: 0.14cm 0.16cm;
      vertical-align: top;
    }}
    th {{
      background: #e8eef6;
      text-align: center;
      font-weight: 700;
    }}
    .figure-grid td {{
      border: none;
      width: 50%;
      padding: 0.08cm;
      vertical-align: top;
      text-align: center;
    }}
    img {{
      max-width: 100%;
      height: auto;
      border: 1px solid #ccc;
    }}
    .caption {{
      font-size: 9pt;
      color: #333;
      margin-top: 0.1cm;
      text-align: left;
    }}
  </style>
</head>
<body>
  <h1>{escape(parsed["title"])}</h1>
  {''.join(f"<p>{escape(p)}</p>" for p in parsed["intro"])}
  {render_table(parsed["table"])}
  {''.join(body_parts)}
</body>
</html>
"""


def main() -> None:
    for config in DOCS:
        config["html"].write_text(render_doc(config), encoding="utf-8")
        print(f"Wrote {config['html']}")


if __name__ == "__main__":
    main()
