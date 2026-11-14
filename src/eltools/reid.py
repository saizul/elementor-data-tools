"""Regenerating element ids so content can be pasted into another page safely.

Elementor identifies every element by a 7-character hex ``id``. Its generated CSS
targets ``.elementor-element-<id>``, so two elements sharing an id on one page (a
section copied between exports, a template inserted twice) end up sharing styles,
and the editor can select or save the wrong one. :func:`reassign_ids` gives such
elements fresh, unique ids and updates ``elementor-element-<id>`` references in
their settings (custom CSS, HTML widgets) to match.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from eltools.tree import Node, walk
from eltools.validate import ID_RE

REASON_DUPLICATE = "duplicate"
REASON_MISSING = "missing"
REASON_MALFORMED = "malformed"
REASON_TAKEN = "taken"  # used by a document given with avoid=
REASON_ALL = "all"

_MAX_ATTEMPTS = 10_000


@dataclass(frozen=True)
class IdChange:
    pointer: str
    kind: str
    old: str | None
    new: str
    reason: str
    references: int = 0  # elementor-element-<old> strings rewritten

    def to_dict(self) -> dict[str, Any]:
        return {
            "pointer": self.pointer,
            "kind": self.kind,
            "old": self.old,
            "new": self.new,
            "reason": self.reason,
            "references": self.references,
        }


def collect_ids(elements: Any) -> set[str]:
    """All string ids used anywhere in an element list."""
    return {n.id for n in walk(elements) if n.id}


class IdGenerator:
    """Random 7-hex-digit ids that never repeat one in ``taken`` (which it updates)."""

    def __init__(self, taken: Iterable[str] = (), seed: int | None = None) -> None:
        self.taken = set(taken)
        self._random = random.Random(seed)

    def __call__(self) -> str:
        for _ in range(_MAX_ATTEMPTS):
            candidate = f"{self._random.getrandbits(28):07x}"
            # an all-digit id would round-trip through PHP as an integer key in some plugins
            if candidate not in self.taken and not candidate.isdigit():
                self.taken.add(candidate)
                return candidate
        raise RuntimeError("could not find a free element id")  # pragma: no cover


def _reason(node: Node, counts: Counter[str], first_seen: set[str], avoid: set[str]) -> str | None:
    ident = node.element.get("id")
    if not isinstance(ident, str) or not ident:
        return REASON_MISSING
    if not ID_RE.match(ident):
        return REASON_MALFORMED
    if ident in avoid:
        return REASON_TAKEN
    if counts[ident] > 1:
        if ident in first_seen:
            return REASON_DUPLICATE
        first_seen.add(ident)  # the first occurrence keeps its id
    return None


def _rewrite(value: Any, pattern: re.Pattern[str], replacement: str) -> tuple[Any, int]:
    """Replace ``pattern`` in every string inside ``value``; return (new value, count)."""
    if isinstance(value, str):
        new, count = pattern.subn(replacement, value)
        return new, count
    if isinstance(value, list):
        total = 0
        for index, item in enumerate(value):
            value[index], count = _rewrite(item, pattern, replacement)
            total += count
        return value, total
    if isinstance(value, dict):
        total = 0
        for key in list(value):
            value[key], count = _rewrite(value[key], pattern, replacement)
            total += count
        return value, total
    return value, 0


def _reference_pattern(old: str) -> re.Pattern[str]:
    """``elementor-element-<old>`` as a whole CSS class name."""
    return re.compile(rf"(?<![0-9A-Za-z_-])elementor-element-{re.escape(old)}(?![0-9A-Za-z_-])")


def _rewrite_settings(nodes: Iterable[Node], old: str, new: str) -> int:
    pattern = _reference_pattern(old)
    total = 0
    for node in nodes:
        settings = node.element.get("settings")
        if isinstance(settings, dict):
            _, count = _rewrite(settings, pattern, f"elementor-element-{new}")
            total += count
    return total


def _copy_root(node: Node, renamed: set[int]) -> Node:
    """The outermost renamed ancestor: the root of the pasted copy ``node`` belongs to."""
    root = node
    while root.parent is not None and id(root.parent.element) in renamed:
        root = root.parent
    return root


def _subtree(node: Node) -> list[Node]:
    return [node, *walk(node.children, node, node.path)]


def reassign_ids(
    elements: list[Any],
    *,
    regenerate_all: bool = False,
    avoid: Iterable[str] = (),
    seed: int | None = None,
    update_references: bool = True,
    apply: bool = True,
) -> list[IdChange]:
    """Give fresh ids to elements whose id is missing, malformed, duplicated or in ``avoid``.

    * The first element with a given id keeps it; later duplicates get new ids.
    * ``avoid`` are ids used elsewhere (e.g. on the page the content will be pasted into).
    * ``regenerate_all`` replaces every id, for a clean copy of a whole template.
    * With ``update_references``, ``elementor-element-<old>`` strings in settings are
      rewritten: across the whole document when the old id was unique, and only inside the
      renamed copy (the outermost renamed ancestor's subtree) when it was a duplicate, so
      the original keeps its references.
    * With ``apply=False`` nothing is modified; the planned changes are returned.

    Changes are returned in document order.
    """
    avoid_set = set(avoid)
    nodes = list(walk(elements))
    counts = Counter(n.id for n in nodes if n.id)
    # new ids never reuse an id that exists in either document, even one being replaced
    generate = IdGenerator(taken=set(counts) | avoid_set, seed=seed)

    plan: list[tuple[Node, str]] = []
    first_seen: set[str] = set()
    for node in nodes:
        reason = REASON_ALL if regenerate_all else _reason(node, counts, first_seen, avoid_set)
        if reason is not None:
            plan.append((node, reason))

    renamed = {id(node.element) for node, _ in plan}
    changes: list[IdChange] = []
    for node, reason in plan:
        old = node.id
        new = generate()
        references = 0
        if update_references and old and ID_RE.match(old):
            scope = _subtree(_copy_root(node, renamed)) if counts[old] > 1 else nodes
            if apply:
                references = _rewrite_settings(scope, old, new)
            else:
                references = _count_references(scope, old)
        if apply:
            node.element["id"] = new
        changes.append(IdChange(node.pointer, node.kind, old, new, reason, references))
    return changes


def _count_references(nodes: Iterable[Node], old: str) -> int:
    pattern = _reference_pattern(old)
    total = 0

    def count(value: Any) -> None:
        nonlocal total
        if isinstance(value, str):
            total += len(pattern.findall(value))
        elif isinstance(value, list):
            for item in value:
                count(item)
        elif isinstance(value, dict):
            for item in value.values():
                count(item)

    for node in nodes:
        settings = node.element.get("settings")
        if isinstance(settings, dict):
            count(settings)
    return total
