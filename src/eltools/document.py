"""Loading and serializing Elementor data in the shapes WordPress produces."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STYLE_PRETTY = "pretty"
STYLE_COMPACT = "compact"
STYLE_WP = "wp"
STYLES = (STYLE_PRETTY, STYLE_COMPACT, STYLE_WP)


class ElementorDataError(ValueError):
    """The input is not usable Elementor data."""


@dataclass
class Document:
    """Parsed Elementor data.

    ``elements`` is the list stored in the ``_elementor_data`` post meta. A template
    export (Elementor's "Export Template") wraps that list in an object under
    ``content``; the wrapper is kept (its ``content`` slot is filled from
    ``elements`` on output) so it can be written back unchanged.
    """

    elements: list[dict[str, Any]]
    wrapper: dict[str, Any] | None = None
    style: str = STYLE_PRETTY
    string_encoded: bool = False
    source: str = field(default="<memory>", compare=False)

    def copy(self) -> Document:
        return copy.deepcopy(self)

    def to_data(self) -> Any:
        """The Python object that should be serialized (wrapper re-attached)."""
        if self.wrapper is None:
            return self.elements
        # rebuild in the original key order so a no-op edit is byte-identical
        return {k: (self.elements if k == "content" else v) for k, v in self.wrapper.items()}

    def dumps(self, style: str | None = None) -> str:
        return dumps(self.to_data(), style or self.style, string_encoded=self.string_encoded)


def detect_style(text: str) -> str:
    body = text.strip()
    if "\n" in body:
        return STYLE_PRETTY
    if "\\/" in body or "\\u" in body:
        return STYLE_WP
    return STYLE_COMPACT


def loads(text: str, source: str = "<string>") -> Document:
    """Parse text from a file, ``wp post meta get`` output, or a template export."""
    text = text.lstrip("﻿")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ElementorDataError(
            f"{source}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    string_encoded = False
    if isinstance(value, str):  # JSON that was stored as a JSON string
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ElementorDataError(
                f"{source}: JSON string does not contain JSON: {exc.msg}"
            ) from exc
        string_encoded = True
    wrapper = None
    if isinstance(value, dict) and isinstance(value.get("content"), list):
        wrapper = dict(value)
        elements = value["content"]
    elif isinstance(value, list):
        elements = value
    else:
        raise ElementorDataError(
            f"{source}: expected a list of elements or a template export with a 'content' list"
        )
    return Document(
        elements=elements,
        wrapper=wrapper,
        style=detect_style(text),
        string_encoded=string_encoded,
        source=source,
    )


def load(path: str | Path) -> Document:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ElementorDataError(f"cannot read {path}: {exc.strerror}") from exc
    except UnicodeDecodeError as exc:
        raise ElementorDataError(f"{path}: not valid UTF-8") from exc
    return loads(text, source=str(path))


def dumps(
    data: Any, style: str = STYLE_PRETTY, *, string_encoded: bool = False, indent: int = 2
) -> str:
    """Serialize ``data``.

    * ``pretty``  - indented, readable, unicode kept as-is
    * ``compact`` - single line, unicode kept as-is
    * ``wp``      - single line, ASCII only (``\\uXXXX``) and ``/`` written as ``\\/``,
      exactly how WordPress (``wp_json_encode``) stores ``_elementor_data``
    """
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r}; choose from {', '.join(STYLES)}")
    if style == STYLE_PRETTY:
        return json.dumps(data, indent=indent, ensure_ascii=False)
    ascii_only = style == STYLE_WP
    out = json.dumps(data, separators=(",", ":"), ensure_ascii=ascii_only)
    if ascii_only:
        out = out.replace("/", "\\/")
    if string_encoded:
        out = json.dumps(out, ensure_ascii=ascii_only)
        if ascii_only:
            out = out.replace("/", "\\/")
    return out
