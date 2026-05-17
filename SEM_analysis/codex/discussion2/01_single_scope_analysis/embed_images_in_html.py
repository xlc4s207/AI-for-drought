#!/usr/bin/env python3
"""Embed local image paths in HTML as data URIs for portable docx conversion."""

from __future__ import annotations

import argparse
import base64
import mimetypes
import re
from pathlib import Path


IMG_PATTERN = re.compile(r'(<img\s+[^>]*src=")([^"]+)(")', re.IGNORECASE)


def embed_image(src: str) -> str:
    path = Path(src)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {src}")
    mime, _ = mimetypes.guess_type(path.name)
    if mime is None:
        mime = "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    text = input_path.read_text(encoding="utf-8")

    def replacer(match: re.Match[str]) -> str:
        prefix, src, suffix = match.groups()
        if src.startswith("data:"):
            return match.group(0)
        return f"{prefix}{embed_image(src)}{suffix}"

    embedded = IMG_PATTERN.sub(replacer, text)
    output_path.write_text(embedded, encoding="utf-8")


if __name__ == "__main__":
    main()
