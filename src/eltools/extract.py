"""Extract widget text to files and put edited files back (round-trip safe)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eltools.fields import HTML_FIELD_NAMES, fields_for, get_path, iter_string_fields, set_path
from eltools.tree import EL_WIDGET, resolve_pointer, walk

INDEX_NAME = "eltools-extract.json"
INDEX_VERSION = 1


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slug(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "-", path).strip("-")


def _extension(widget_type: str, path: str) -> str:
    leaf = path.split(".")[-1]
    return "html" if widget_type == "html" or leaf in HTML_FIELD_NAMES else "txt"


@dataclass
class ExtractedFile:
    file: str
    id: str
    widget_type: str
    field: str
    pointer: str
    sha256: str


@dataclass
class InsertReport:
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.conflicts


def extract_fields(
    elements: list[Any],
    outdir: Path,
    widget_types: tuple[str, ...] = ("html",),
    fields: list[str] | None = None,
) -> list[ExtractedFile]:
    """Write each matching text field to ``outdir`` and an index describing them.

    Files are written byte-for-byte as UTF-8 with no newline translation so that
    inserting them back without edits changes nothing.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    wanted = set(widget_types)
    entries: list[ExtractedFile] = []
    for node in walk(elements):
        if node.el_type != EL_WIDGET or node.widget_type not in wanted or not node.id:
            continue
        settings = node.element.get("settings")
        for spec in fields_for(node.widget_type, fields):
            for path, container, key in iter_string_fields(settings, spec):
                value = container[key]
                name = f"{node.id}--{_slug(path)}.{_extension(node.widget_type, path)}"
                (outdir / name).write_bytes(value.encode("utf-8"))
                entries.append(
                    ExtractedFile(
                        name, node.id, node.widget_type, path, node.pointer, sha256(value)
                    )
                )
    index = {"version": INDEX_VERSION, "files": [e.__dict__ for e in entries]}
    (outdir / INDEX_NAME).write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return entries


def load_index(indir: Path) -> list[ExtractedFile]:
    path = Path(indir) / INDEX_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [ExtractedFile(**item) for item in data["files"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"cannot read extract index {path}: {exc}") from exc


def insert_fields(
    elements: list[Any], indir: Path, *, force: bool = False, dry_run: bool = False
) -> InsertReport:
    """Re-insert files written by :func:`extract_fields`.

    A file is applied only when the live value still matches what was extracted
    (so edits made elsewhere are not clobbered) unless ``force`` is set.
    """
    indir = Path(indir)
    report = InsertReport()
    for entry in load_index(indir):
        element = resolve_pointer(elements, entry.pointer)
        if element is None or element.get("id") != entry.id:
            report.missing.append(f"{entry.file}: element {entry.id} not at {entry.pointer}")
            continue
        file_path = indir / entry.file
        if not file_path.is_file():
            report.missing.append(f"{entry.file}: file not found")
            continue
        new_value = file_path.read_bytes().decode("utf-8")
        settings = element.get("settings")
        try:
            current = get_path(settings, entry.field)
        except (KeyError, IndexError, ValueError, TypeError):
            report.missing.append(f"{entry.file}: field {entry.field} no longer exists")
            continue
        if not isinstance(current, str):
            report.missing.append(f"{entry.file}: field {entry.field} is no longer text")
            continue
        if new_value == current:
            report.unchanged.append(entry.file)
            continue
        if sha256(current) != entry.sha256 and not force:
            report.conflicts.append(
                f"{entry.file}: the export changed since extraction (use force to overwrite)"
            )
            continue
        if not dry_run:
            set_path(settings, entry.field, new_value)
        report.updated.append(entry.file)
    return report
