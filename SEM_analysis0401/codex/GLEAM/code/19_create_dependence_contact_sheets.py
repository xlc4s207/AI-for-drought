#!/usr/bin/env python
"""Create 3x3 contact sheets for biome dependence plots."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-root", required=True)
    parser.add_argument(
        "--biomes",
        nargs="+",
        default=["Forest", "Grassland", "Savanna", "Cropland", "Shrubland", "Wetland"],
    )
    parser.add_argument("--thumb-width", type=int, default=480)
    parser.add_argument("--margin", type=int, default=24)
    parser.add_argument("--gutter", type=int, default=18)
    parser.add_argument("--header-height", type=int, default=78)
    return parser.parse_args()


def load_font(size: int):
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def feature_title_from_name(path: Path) -> str:
    stem = path.stem
    if stem.endswith("_dependence"):
        stem = stem[: -len("_dependence")]
    if stem[:3].isdigit() and stem[2] == "_":
        stem = stem[3:]
    return stem


def build_contact_sheet(
    biome: str,
    image_paths: list[Path],
    output_path: Path,
    thumb_width: int,
    margin: int,
    gutter: int,
    header_height: int,
) -> None:
    if not image_paths:
        return

    images = [Image.open(path).convert("RGB") for path in image_paths]
    thumb_height = int(round(images[0].height * (thumb_width / images[0].width)))
    thumbs = [img.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS) for img in images]

    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    sheet_width = margin * 2 + cols * thumb_width + (cols - 1) * gutter
    sheet_height = margin * 2 + header_height + rows * thumb_height + (rows - 1) * gutter

    sheet = Image.new("RGB", (sheet_width, sheet_height), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(30)
    subtitle_font = load_font(17)

    draw.text((margin, margin - 2), f"{biome} dependence plots", fill="black", font=title_font)
    draw.text(
        (margin, margin + 38),
        "9-feature SHAP dependence overview",
        fill="#555555",
        font=subtitle_font,
    )

    y0 = margin + header_height
    for idx, (thumb, src_path) in enumerate(zip(thumbs, image_paths)):
        row = idx // cols
        col = idx % cols
        x = margin + col * (thumb_width + gutter)
        y = y0 + row * (thumb_height + gutter)
        sheet.paste(thumb, (x, y))

        label = feature_title_from_name(src_path)
        label_bg_h = 30
        draw.rectangle((x, y, x + thumb_width, y + label_bg_h), fill=(255, 255, 255))
        draw.text((x + 10, y + 6), label, fill="#222222", font=subtitle_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=95)


def main() -> None:
    args = parse_args()
    result_root = Path(args.result_root)

    for biome in args.biomes:
        dep_dir = result_root / biome / "dependence_plots"
        if not dep_dir.exists():
            continue
        image_paths = sorted(dep_dir.glob("[0-9][0-9]_*.png"))
        if not image_paths:
            continue
        build_contact_sheet(
            biome=biome,
            image_paths=image_paths,
            output_path=dep_dir / "dependence_plots_overview.png",
            thumb_width=args.thumb_width,
            margin=args.margin,
            gutter=args.gutter,
            header_height=args.header_height,
        )
        print(f"[DONE] {biome} -> {dep_dir / 'dependence_plots_overview.png'}")


if __name__ == "__main__":
    main()
