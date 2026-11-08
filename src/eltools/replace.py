"""Find/replace restricted to text fields of selected widget types."""

from __future__ import annotations

import copy
import difflib
import re
from dataclasses import dataclass
from typing import Any

from eltools.fields import fields_for, iter_string_fields
from eltools.tree import EL_WIDGET, walk


@dataclass
class Change:
    id: str
    widget_type: str
    pointer: str
    field: str
    before: str
    after: str
    count: int

    def diff(self) -> str:
        label = f"{self.widget_type}#{self.id} {self.field}"
        lines = difflib.unified_diff(
            self.before.splitlines(keepends=True),
            self.after.splitlines(keepends=True),
            fromfile=f"a/{label}",
            tofile=f"b/{label}",
            lineterm="",
        )
        return "\n".join(line.rstrip("\n") for line in lines)


def replace_text(
    elements: list[Any],
    find: str,
    replacement: str,
    widget_types: tuple[str, ...],
    *,
    fields: list[str] | None = None,
    regex: bool = False,
    ignore_case: bool = False,
    apply: bool = True,
) -> list[Change]:
    """Replace ``find`` in the text fields of ``widget_types`` only.

    Keys, ids, URLs in non-text settings and the structure are never touched.
    With ``apply=False`` the tree is left unmodified and the changes are just reported.
    """
    if not find:
        raise ValueError("find must not be empty")
    if not widget_types:
        raise ValueError("choose at least one widget type")
    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(find if regex else re.escape(find), flags)
    repl: Any = replacement if regex else (lambda _m: replacement)
    wanted = set(widget_types)
    for wt in wanted:
        fields_for(wt, fields)  # validate early, before touching anything
    target = elements if apply else copy.deepcopy(elements)
    changes: list[Change] = []
    for node in walk(target):
        if node.el_type != EL_WIDGET or node.widget_type not in wanted:
            continue
        settings = node.element.get("settings")
        for spec in fields_for(node.widget_type or "", fields):
            for path, container, key in iter_string_fields(settings, spec):
                before = container[key]
                after, count = pattern.subn(repl, before)
                if count and after != before:
                    container[key] = after
                    changes.append(
                        Change(
                            node.id or "?",
                            node.widget_type or "?",
                            node.pointer,
                            path,
                            before,
                            after,
                            count,
                        )
                    )
    return changes
