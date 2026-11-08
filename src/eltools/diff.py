"""Element-level diff between two Elementor exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from eltools.tree import Node, walk


@dataclass
class SettingChange:
    path: str
    op: str  # added | removed | changed
    old: Any = None
    new: Any = None


@dataclass
class ElementRef:
    id: str
    kind: str
    pointer: str
    parent_id: str | None
    descendants: int = 0


@dataclass
class ElementChange:
    id: str
    kind: str
    pointer_a: str
    pointer_b: str
    changes: list[SettingChange] = field(default_factory=list)


@dataclass
class Move:
    id: str
    kind: str
    old_parent: str | None
    new_parent: str | None


@dataclass
class DiffResult:
    added: list[ElementRef] = field(default_factory=list)
    removed: list[ElementRef] = field(default_factory=list)
    changed: list[ElementChange] = field(default_factory=list)
    moved: list[Move] = field(default_factory=list)
    reordered: list[str] = field(default_factory=list)  # parent ids whose child order differs

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changed or self.moved or self.reordered)

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return {
            "added": [asdict(x) for x in self.added],
            "removed": [asdict(x) for x in self.removed],
            "changed": [asdict(x) for x in self.changed],
            "moved": [asdict(x) for x in self.moved],
            "reordered": self.reordered,
        }


def _key(node: Node) -> str:
    return node.id or f"@{node.pointer}"


def _index(elements: Any) -> dict[str, Node]:
    out: dict[str, Node] = {}
    for node in walk(elements):
        out.setdefault(_key(node), node)  # duplicate ids: the first wins
    return out


def _descendants(node: Node) -> int:
    return sum(1 for _ in walk(node.children)) if node.children else 0


def _equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return a == b


def diff_values(a: Any, b: Any, path: str = "") -> list[SettingChange]:
    """Recursive diff of two JSON values; PHP's empty ``[]`` equals an empty object."""
    if a in ([], {}) and b in ([], {}):
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[SettingChange] = []
        for key in sorted(set(a) | set(b), key=str):
            sub = f"{path}.{key}" if path else str(key)
            if key not in a:
                out.append(SettingChange(sub, "added", None, b[key]))
            elif key not in b:
                out.append(SettingChange(sub, "removed", a[key], None))
            else:
                out.extend(diff_values(a[key], b[key], sub))
        return out
    if isinstance(a, list) and isinstance(b, list):
        out = []
        for i in range(max(len(a), len(b))):
            sub = f"{path}.{i}" if path else str(i)
            if i >= len(a):
                out.append(SettingChange(sub, "added", None, b[i]))
            elif i >= len(b):
                out.append(SettingChange(sub, "removed", a[i], None))
            else:
                out.extend(diff_values(a[i], b[i], sub))
        return out
    if _equal(a, b):
        return []
    return [SettingChange(path or ".", "changed", a, b)]


def _own_properties(element: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in element.items() if k not in ("elements", "id")}


def _parent_id(node: Node) -> str | None:
    return _key(node.parent) if node.parent else None


def diff_documents(a: list[Any], b: list[Any], ignore_keys: tuple[str, ...] = ()) -> DiffResult:
    """Compare two element trees by element id.

    ``ignore_keys`` are dotted paths (or prefixes) inside an element to skip, such as
    ``settings._element_id`` or ``settings.custom_css``.
    """
    ia, ib = _index(a), _index(b)
    result = DiffResult()

    def ref(node: Node) -> ElementRef:
        return ElementRef(_key(node), node.kind, node.pointer, _parent_id(node), _descendants(node))

    added_keys = [k for k in ib if k not in ia]
    removed_keys = [k for k in ia if k not in ib]
    added_set, removed_set = set(added_keys), set(removed_keys)
    # Report only the roots of added/removed subtrees; descendants are counted in them.
    result.added = [ref(ib[k]) for k in added_keys if _parent_id(ib[k]) not in added_set]
    result.removed = [ref(ia[k]) for k in removed_keys if _parent_id(ia[k]) not in removed_set]

    for key, na in ia.items():
        nb = ib.get(key)
        if nb is None:
            continue
        changes = [
            c
            for c in diff_values(_own_properties(na.element), _own_properties(nb.element))
            if not any(c.path == k or c.path.startswith(k + ".") for k in ignore_keys)
        ]
        if changes:
            result.changed.append(ElementChange(key, nb.kind, na.pointer, nb.pointer, changes))
        pa, pb = _parent_id(na), _parent_id(nb)
        if pa != pb:
            result.moved.append(Move(key, nb.kind, pa, pb))

    def children_order(index: dict[str, Node], common: set[str]) -> dict[str | None, list[str]]:
        order: dict[str | None, list[str]] = {}
        for k, n in index.items():
            if k in common:
                order.setdefault(_parent_id(n), []).append(k)
        return order

    common = set(ia) & set(ib)
    oa, ob = children_order(ia, common), children_order(ib, common)
    for parent, kids in oa.items():
        kept = [k for k in kids if _parent_id(ib[k]) == parent]
        kept_set = set(kept)
        in_b = [k for k in ob.get(parent, []) if k in kept_set]
        if kept != in_b:
            result.reordered.append(parent or "(top level)")
    return result
