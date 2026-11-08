"""Structural validation of Elementor element trees."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from eltools.tree import EL_COLUMN, EL_CONTAINER, EL_SECTION, EL_TYPES, EL_WIDGET

ID_RE = re.compile(r"^[0-9a-f]{7}$")
ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    level: str
    code: str
    pointer: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.code} {self.pointer or '/'}: {self.message}"


def validate(elements: Any) -> list[Issue]:
    """Return all problems found. An empty list means the tree looks sound."""
    issues: list[Issue] = []
    if not isinstance(elements, list):
        return [Issue(ERROR, "E001", "", "root must be a list of elements")]
    seen: dict[str, str] = {}

    def check(items: list[Any], parent_type: str | None, prefix: str) -> None:
        for index, element in enumerate(items):
            pointer = f"{prefix}/{index}"
            if not isinstance(element, dict):
                issues.append(Issue(ERROR, "E010", pointer, "element is not an object"))
                continue
            el_type = element.get("elType")
            if el_type not in EL_TYPES:
                issues.append(
                    Issue(
                        ERROR,
                        "E011",
                        pointer,
                        f"elType must be one of {', '.join(EL_TYPES)} (got {el_type!r})",
                    )
                )
            ident = element.get("id")
            if not isinstance(ident, str) or not ident:
                issues.append(Issue(ERROR, "E013", pointer, "missing id"))
            else:
                if not ID_RE.match(ident):
                    issues.append(
                        Issue(WARNING, "W014", pointer, f"id {ident!r} is not 7 hex characters")
                    )
                if ident in seen:
                    issues.append(
                        Issue(
                            ERROR,
                            "E015",
                            pointer,
                            f"duplicate id {ident!r} (first used at {seen[ident]})",
                        )
                    )
                else:
                    seen[ident] = pointer
            if el_type == EL_WIDGET and not isinstance(element.get("widgetType"), str):
                issues.append(Issue(ERROR, "E012", pointer, "widget is missing widgetType"))
            settings = element.get("settings")
            # PHP serializes an empty settings array as [] rather than {}; both are fine.
            if settings is not None and not isinstance(settings, dict) and settings != []:
                issues.append(Issue(ERROR, "E017", pointer, "settings must be an object"))
            children = element.get("elements")
            if children is None:
                issues.append(Issue(WARNING, "W016", pointer, "missing 'elements' list"))
                children = []
            elif not isinstance(children, list):
                issues.append(Issue(ERROR, "E016", pointer, "'elements' must be a list"))
                children = []
            _check_parent(el_type, parent_type, element, pointer)
            if el_type == EL_WIDGET and children:
                issues.append(Issue(WARNING, "W020", pointer, "widget has child elements"))
            check(children, el_type if isinstance(el_type, str) else None, f"{pointer}/elements")

    def _check_parent(
        el_type: Any, parent_type: str | None, element: dict[str, Any], pointer: str
    ) -> None:
        if parent_type is None:
            if el_type in (EL_COLUMN, EL_WIDGET):
                issues.append(
                    Issue(ERROR, "E021", pointer, f"{el_type} cannot be a top-level element")
                )
            return
        if parent_type == EL_SECTION and el_type != EL_COLUMN:
            issues.append(
                Issue(ERROR, "E022", pointer, f"a section can only contain columns (got {el_type})")
            )
        elif parent_type == EL_COLUMN and el_type == EL_COLUMN:
            issues.append(Issue(ERROR, "E023", pointer, "a column cannot contain a column"))
        elif parent_type == EL_COLUMN and el_type == EL_SECTION and not element.get("isInner"):
            issues.append(
                Issue(
                    WARNING, "W024", pointer, "section nested in a column should set isInner=true"
                )
            )
        elif parent_type == EL_CONTAINER and el_type in (EL_SECTION, EL_COLUMN):
            issues.append(Issue(ERROR, "E025", pointer, f"a container cannot contain a {el_type}"))
        elif parent_type == EL_WIDGET:
            issues.append(Issue(ERROR, "E026", pointer, "a widget cannot contain elements"))

    check(elements, None, "")
    return issues


def errors_only(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == ERROR]
