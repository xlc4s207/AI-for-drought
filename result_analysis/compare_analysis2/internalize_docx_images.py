#!/home/xulc/.local/share/mamba/envs/Flash_dra/bin/python
"""Convert externally linked images in a DOCX into embedded media files."""

from __future__ import annotations

import argparse
import posixpath
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

ET.register_namespace("", PKG_REL_NS)
ET.register_namespace("", CONTENT_TYPES_NS)


def local_path_from_target(target: str) -> Path:
    parsed = urlparse(target)
    if parsed.scheme != "file":
        raise ValueError(f"Unsupported external image target: {target}")
    return Path(unquote(parsed.path))


def ensure_content_type_default(content_types_xml: bytes, extension: str) -> bytes:
    root = ET.fromstring(content_types_xml)
    qname = f"{{{CONTENT_TYPES_NS}}}Default"
    existing = {
        elem.attrib.get("Extension", "").lower(): elem
        for elem in root.findall(qname)
    }
    if extension.lower() not in existing:
        mime = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "bmp": "image/bmp",
            "tif": "image/tiff",
            "tiff": "image/tiff",
        }.get(extension.lower(), f"image/{extension.lower()}")
        ET.SubElement(root, qname, {"Extension": extension.lower(), "ContentType": mime})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def internalize_docx(docx_path: Path) -> int:
    with ZipFile(docx_path, "r") as zin:
        files = {name: zin.read(name) for name in zin.namelist()}

    rels_name = "word/_rels/document.xml.rels"
    if rels_name not in files:
        raise FileNotFoundError(f"{rels_name} not found in {docx_path}")

    root = ET.fromstring(files[rels_name])
    rel_tag = f"{{{PKG_REL_NS}}}Relationship"
    used_media_names = {name for name in files if name.startswith("word/media/")}
    new_media = {}
    replaced = 0

    for rel in root.findall(rel_tag):
        if rel.attrib.get("Type") != IMAGE_REL_TYPE:
            continue
        if rel.attrib.get("TargetMode") != "External":
            continue
        target = rel.attrib.get("Target", "")
        image_path = local_path_from_target(target)
        if not image_path.exists():
            raise FileNotFoundError(f"External image not found for {docx_path}: {image_path}")
        ext = image_path.suffix.lower().lstrip(".") or "png"
        base = image_path.stem or "image"
        media_name = f"word/media/{base}.{ext}"
        counter = 1
        while media_name in used_media_names or media_name in new_media:
            media_name = f"word/media/{base}_{counter}.{ext}"
            counter += 1
        new_media[media_name] = image_path.read_bytes()
        used_media_names.add(media_name)
        rel.attrib["Target"] = posixpath.join("media", Path(media_name).name)
        rel.attrib.pop("TargetMode", None)
        files["[Content_Types].xml"] = ensure_content_type_default(files["[Content_Types].xml"], ext)
        replaced += 1

    if replaced == 0:
        return 0

    files[rels_name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    files.update(new_media)

    tmp_path = docx_path.with_suffix(docx_path.suffix + ".tmp")
    with ZipFile(tmp_path, "w", compression=ZIP_DEFLATED) as zout:
        for name, data in files.items():
            zout.writestr(name, data)
    tmp_path.replace(docx_path)
    return replaced


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", nargs="+", help="DOCX file(s) to fix")
    args = parser.parse_args()
    for item in args.docx:
        path = Path(item)
        count = internalize_docx(path)
        print(f"{path}: internalized {count} image(s)")


if __name__ == "__main__":
    main()
