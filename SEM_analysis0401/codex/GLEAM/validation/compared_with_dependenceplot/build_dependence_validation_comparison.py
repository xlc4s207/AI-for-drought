#!/usr/bin/env python3
"""Combine SHAP dependence plots with ALE/ICE/PDP validation trajectories."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/home/xulc/flash_drought")
GLEAM = ROOT / "process/SEM_analysis0401/codex/GLEAM"
DEP_ROOT = GLEAM / "plots2/prepeak_shap_summary_20260502/dependence_compare_gpp_vs_reco"
COMBINED_ROOT = DEP_ROOT / "combined_by_biome_no_lai_with_intensity"
VALID = GLEAM / "validation"
OUT = VALID / "compared_with_dependenceplot"

BIOMES = ["Cropland", "Forest", "Grassland", "Savanna", "Shrubland"]
FEATURES = ["SSRD", "EVA", "TMP", "VPD", "SMrz", "PRE", "STRD", "WIND", "Duration", "Intensity"]
METRICS = ["GPP", "RECO"]
METHODS = {
    "ALE": {
        "root": VALID / "01_ALE/results",
        "suffix": "_ale_curve.png",
    },
    "ICE": {
        "root": VALID / "02_ICE/results",
        "suffix": "_ice_curves.png",
    },
    "PDP": {
        "root": VALID / "03_PDP/results",
        "suffix": "_pdp_curve.png",
    },
}

VALIDATION_LABELS = {
    "EVA": "|EVA|",
    "WIND": "WIND",
    "PRE": "PRE",
    "SSRD": "SSRD",
    "STRD": "STRD",
    "TMP": "TMP",
    "VPD": "VPD",
    "SMrz": "SMrz",
    "Duration": "Duration",
    "Intensity": "Intensity",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


FONT_TITLE = font(24, bold=True)
FONT_SUBTITLE = font(18, bold=True)
FONT_NORMAL = font(15)
FONT_SMALL = font(12)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def make_placeholder(size: tuple[int, int], title: str, reason: str = "not available") -> Image.Image:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline="#bdbdbd", width=2)
    tw, th = text_size(draw, title, FONT_SUBTITLE)
    draw.text(((size[0] - tw) / 2, size[1] * 0.38), title, fill="#4d4d4d", font=FONT_SUBTITLE)
    rw, rh = text_size(draw, reason, FONT_NORMAL)
    draw.text(((size[0] - rw) / 2, size[1] * 0.52), reason, fill="#7f7f7f", font=FONT_NORMAL)
    return img


def fit_image(path: Path | None, size: tuple[int, int], title: str | None = None) -> Image.Image:
    if path is None or not path.exists():
        return make_placeholder(size, title or "missing")
    src = Image.open(path).convert("RGB")
    if title:
        title_h = 34
        canvas = Image.new("RGB", (src.width, src.height + title_h), "white")
        d = ImageDraw.Draw(canvas)
        d.rectangle((0, 0, src.width, title_h), fill="#f2f2f2")
        d.text((8, 7), title, fill="#1f1f1f", font=FONT_SMALL)
        canvas.paste(src, (0, title_h))
        src = canvas
    src.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    x = (size[0] - src.width) // 2
    y = (size[1] - src.height) // 2
    canvas.paste(src, (x, y))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline="#d0d0d0", width=1)
    return canvas


def dependence_path(biome: str, feature: str) -> Path:
    return DEP_ROOT / biome / f"{feature}_gpp_vs_reco.png"


def combined_dependence_path(biome: str) -> Path:
    return COMBINED_ROOT / f"{biome}_no_lai_with_intensity_gpp_vs_reco.png"


def validation_path(method: str, metric: str, biome: str, feature: str) -> Path:
    label = VALIDATION_LABELS[feature]
    spec = METHODS[method]
    return spec["root"] / metric / biome / f"{label}{spec['suffix']}"


def validation_cell(method: str, biome: str, feature: str, size: tuple[int, int]) -> tuple[Image.Image, dict[str, object]]:
    pad = 8
    header_h = 28
    sub_h = (size[1] - header_h - pad * 3) // 2
    sub_w = size[0] - pad * 2
    canvas = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline="#d0d0d0", width=1)
    draw.rectangle((0, 0, size[0], header_h), fill="#f2f2f2")
    draw.text((8, 6), method, fill="#1f1f1f", font=FONT_SMALL)

    rec: dict[str, object] = {"method": method}
    y = header_h + pad
    for metric in METRICS:
        p = validation_path(method, metric, biome, feature)
        rec[f"{metric.lower()}_png"] = str(p) if p.exists() else ""
        sub = fit_image(p if p.exists() else None, (sub_w, sub_h), title=f"{metric} {feature}")
        canvas.paste(sub, (pad, y))
        y += sub_h + pad
    return canvas, rec


def make_feature_comparison(biome: str, feature: str, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    dep_size = (580, 430)
    method_size = (330, 430)
    gap = 14
    margin = 18
    title_h = 54
    width = margin * 2 + dep_size[0] + gap + len(METHODS) * method_size[0] + (len(METHODS) - 1) * gap
    height = margin * 2 + title_h + dep_size[1]
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    title = f"{biome} | {feature}: SHAP dependence vs ALE / ICE / PDP"
    draw.text((margin, 16), title, fill="#111111", font=FONT_TITLE)
    draw.line((margin, title_h, width - margin, title_h), fill="#bdbdbd", width=1)

    x = margin
    y = margin + title_h
    dep = fit_image(dependence_path(biome, feature), dep_size, title="Dependence plot (GPP vs RECO)")
    canvas.paste(dep, (x, y))
    record = {
        "biome": biome,
        "feature": feature,
        "output_png": str(out_dir / f"{feature}_dependence_ALE_ICE_PDP.png"),
        "dependence_png": str(dependence_path(biome, feature)) if dependence_path(biome, feature).exists() else "",
    }
    x += dep_size[0] + gap
    for method in METHODS:
        cell, rec = validation_cell(method, biome, feature, method_size)
        canvas.paste(cell, (x, y))
        for k, v in rec.items():
            if k != "method":
                record[f"{method.lower()}_{k}"] = v
        x += method_size[0] + gap
    out_path = Path(record["output_png"])
    canvas.save(out_path, dpi=(240, 240))
    return record


def make_biome_overview(biome: str, feature_records: list[dict[str, object]], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    cell_dep = (420, 300)
    cell_method = (270, 300)
    label_w = 110
    gap = 10
    margin = 16
    title_h = 54
    header_h = 34
    row_h = 310
    width = margin * 2 + label_w + gap + cell_dep[0] + gap + 3 * cell_method[0] + 2 * gap
    height = margin * 2 + title_h + header_h + len(FEATURES) * row_h
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 14), f"{biome}: dependence plots compared with ALE / ICE / PDP", fill="#111111", font=FONT_TITLE)
    draw.line((margin, title_h, width - margin, title_h), fill="#bdbdbd", width=1)

    x0 = margin
    y0 = margin + title_h
    headers = [("Feature", label_w), ("Dependence", cell_dep[0]), ("ALE", cell_method[0]), ("ICE", cell_method[0]), ("PDP", cell_method[0])]
    x = x0
    for h, w in headers:
        draw.rectangle((x, y0, x + w, y0 + header_h), fill="#f2f2f2", outline="#d0d0d0")
        draw.text((x + 6, y0 + 9), h, fill="#111111", font=FONT_SMALL)
        x += w + gap
    y = y0 + header_h + gap
    for feature in FEATURES:
        x = x0
        draw.rectangle((x, y, x + label_w, y + cell_dep[1]), fill="#fafafa", outline="#d0d0d0")
        draw.text((x + 8, y + 18), feature, fill="#111111", font=FONT_SUBTITLE)
        x += label_w + gap
        canvas.paste(fit_image(dependence_path(biome, feature), cell_dep), (x, y))
        x += cell_dep[0] + gap
        for method in METHODS:
            cell, _ = validation_cell(method, biome, feature, cell_method)
            canvas.paste(cell, (x, y))
            x += cell_method[0] + gap
        y += row_h
    out_path = out_dir / f"{biome}_dependence_ALE_ICE_PDP_overview.png"
    canvas.save(out_path, dpi=(220, 220))
    return out_path


def make_combined_biome_sheet(biome: str, overview_path: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    top_size = (1500, 1100)
    overview_size = (1500, 2200)
    margin = 18
    title_h = 54
    width = 2 * margin + top_size[0]
    height = 2 * margin + title_h + top_size[1] + 20 + overview_size[1]
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 14), f"{biome}: original combined dependence + validation trajectories", fill="#111111", font=FONT_TITLE)
    y = margin + title_h
    canvas.paste(fit_image(combined_dependence_path(biome), top_size, title="Original combined dependence plot"), (margin, y))
    y += top_size[1] + 20
    canvas.paste(fit_image(overview_path, overview_size, title="Feature-wise comparison sheet"), (margin, y))
    out_path = out_dir / f"{biome}_combined_dependence_with_ALE_ICE_PDP.png"
    canvas.save(out_path, dpi=(220, 220))
    return out_path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    by_feature = OUT / "by_feature"
    by_biome = OUT / "by_biome"
    combined = OUT / "combined_with_original"
    records: list[dict[str, object]] = []
    biome_records: list[dict[str, object]] = []

    for biome in BIOMES:
        feature_records = []
        for feature in FEATURES:
            rec = make_feature_comparison(biome, feature, by_feature / biome)
            records.append(rec)
            feature_records.append(rec)
        overview = make_biome_overview(biome, feature_records, by_biome)
        combined_path = make_combined_biome_sheet(biome, overview, combined)
        biome_records.append(
            {
                "biome": biome,
                "overview_png": str(overview),
                "combined_with_original_png": str(combined_path),
                "original_combined_dependence_png": str(combined_dependence_path(biome)),
            }
        )

    pd.DataFrame(records).to_csv(OUT / "feature_comparison_index.csv", index=False)
    pd.DataFrame(biome_records).to_csv(OUT / "biome_overview_index.csv", index=False)
    readme = [
        "# Dependence plot compared with ALE / ICE / PDP",
        "",
        "This folder combines existing GPP-vs-RECO SHAP dependence plots with validation trajectories from ALE, ICE, and PDP.",
        "",
        "- `by_feature/{biome}/`: one comparison figure per feature.",
        "- `by_biome/`: one compact overview sheet per biome.",
        "- `combined_with_original/`: original all-feature dependence plot plus the validation overview sheet.",
        "",
        "Missing ALE/ICE/PDP panels are shown as `not available`, because the validation workflow only generated trajectories for selected high-importance features.",
    ]
    (OUT / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print(f"Wrote outputs under {OUT}")
    print(f"Feature comparison figures: {len(records)}")
    print(f"Biome overview figures: {len(biome_records)}")


if __name__ == "__main__":
    main()
