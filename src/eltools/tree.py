"""Walking the Elementor element tree."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

EL_SECTION = "section"
EL_COLUMN = "column"
EL_CONTAINER = "container"
EL_WIDGET = "widget"
EL_TYPES = (EL_SECTION, EL_COLUMN, EL_CONTAINER, EL_WIDGET)


@dataclass
class Node:
    """One element plus where it lives."""

    element: dict[str, Any]
    path: tuple[int, ...]
    parent: Node | None = None

    @property
    def id(self) -> str | None:
        value = self.element.get("id")
        return value if isinstance(value, str) else None

    @property
    def el_type(self) -> str | None:
        value = self.element.get("elType")
        return value if isinstance(value, str) else None

    @property
    def widget_type(self) -> str | None:
        value = self.element.get("widgetType")
        return value if isinstance(value, str) else None

    @property
    def kind(self) -> str:
        """``widgetType`` for widgets, ``elType`` otherwise."""
        if self.el_type == EL_WIDGET and self.widget_type:
            return self.widget_type
        return self.el_type or "?"

    @property
    def depth(self) -> int:
        return len(self.path) - 1

    @property
    def path_str(self) -> str:
        """Index path such as ``0/1/2`` (top-level element 0, its child 1, ...)."""
        return "/".join(str(i) for i in self.path)

    @property
    def pointer(self) -> str:
        """JSON pointer into the content list, e.g. ``/0/elements/1/elements/2``."""
        parts = [str(self.path[0])]
        for idx in self.path[1:]:
            parts += ["elements", str(idx)]
        return "/" + "/".join(parts)

    @property
    def trail(self) -> str:
        chain: list[str] = []
        node: Node | None = self
        while node is not None:
            chain.append(f"{node.kind}#{node.id or '?'}")
            node = node.parent
        return " > ".join(reversed(chain))

    @property
    def children(self) -> list[Any]:
        kids = self.element.get("elements")
        return kids if isinstance(kids, list) else []


def walk(
    elements: Any, _parent: Node | None = None, _prefix: tuple[int, ...] = ()
) -> Iterator[Node]:
    """Depth-first, document-order traversal. Malformed entries are skipped, not fatal."""
    if not isinstance(elements, list):
        return
    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            continue
        node = Node(element=element, path=_prefix + (index,), parent=_parent)
        yield node
        yield from walk(element.get("elements"), node, node.path)


def find_by_id(elements: Any, element_id: str) -> Node | None:
    for node in walk(elements):
        if node.id == element_id:
            return node
    return None


def resolve_pointer(elements: list[Any], pointer: str) -> dict[str, Any] | None:
    """Return the element at a pointer produced by :attr:`Node.pointer`, or ``None``."""
    parts = [p for p in pointer.split("/") if p != ""]
    current: Any = elements
    try:
        for part in parts:
            current = current[int(part)] if isinstance(current, list) else current[part]
    except (IndexError, KeyError, ValueError, TypeError):
        return None
    return current if isinstance(current, dict) else None


def widget_counts(elements: Any) -> Counter[str]:
    counts: Counter[str] = Counter()
    for node in walk(elements):
        if node.el_type == EL_WIDGET:
            counts[node.widget_type or "?"] += 1
    return counts


def element_counts(elements: Any) -> Counter[str]:
    counts: Counter[str] = Counter()
    for node in walk(elements):
        counts[node.el_type or "?"] += 1
    return counts


def max_depth(elements: Any) -> int:
    return max((n.depth for n in walk(elements)), default=-1)
