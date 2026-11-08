"""Find elements by widget type and/or setting values."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from eltools.document import ElementorDataError
from eltools.tree import Node, walk

_MISSING = object()


@dataclass(frozen=True)
class Condition:
    """One ``--setting`` test: ``path`` (non-empty), ``path=value`` (exact) or ``path~text``."""

    path: str
    op: str  # "exists", "=" or "~"
    value: str = ""

    def __str__(self) -> str:
        return self.path if self.op == "exists" else f"{self.path}{self.op}{self.value}"


def parse_condition(spec: str) -> Condition:
    positions = [(spec.find(op), op) for op in ("=", "~") if op in spec]
    if not positions:
        path, op, value = spec, "exists", ""
    else:
        index, op = min(positions)
        path, value = spec[:index], spec[index + 1 :]
    path = path.strip()
    if not path or any(not part for part in path.split(".")):
        raise ElementorDataError(
            f"invalid --setting {spec!r}: expected PATH, PATH=VALUE or PATH~TEXT"
        )
    return Condition(path, op, value)


def lookup(settings: Any, path: str) -> Any:
    """Follow a dotted path through dicts and lists (``tabs.0.tab_title``)."""
    current = settings
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return _MISSING
    return current


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value, ensure_ascii=False)


def matches(settings: Any, cond: Condition) -> bool:
    value = lookup(settings, cond.path)
    if value is _MISSING:
        return False
    if cond.op == "exists":
        return value not in ("", None, [], {})
    text = _as_text(value)
    if cond.op == "=":
        return text == cond.value
    return cond.value.lower() in text.lower()


@dataclass
class Hit:
    node: Node
    values: dict[str, Any]


def find_elements(
    elements: Any, widget_type: str | None = None, conditions: list[Condition] | None = None
) -> list[Hit]:
    """Elements of ``widget_type`` (any if None) whose settings satisfy every condition."""
    conditions = conditions or []
    hits: list[Hit] = []
    for node in walk(elements):
        if widget_type and not (node.el_type == "widget" and node.widget_type == widget_type):
            continue
        settings = node.element.get("settings")
        if conditions and not isinstance(settings, dict):
            continue
        if all(matches(settings, c) for c in conditions):
            values = {c.path: lookup(settings, c.path) for c in conditions}
            hits.append(Hit(node, values))
    return hits
