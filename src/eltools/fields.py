"""Which settings keys hold human-editable text for each widget type."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

# Paths are dotted; ``*`` walks every item of a repeater list.
TEXT_FIELDS: dict[str, list[str]] = {
    "heading": ["title"],
    "text-editor": ["editor"],
    "button": ["text"],
    "html": ["html"],
    "shortcode": ["shortcode"],
    "image": ["caption"],
    "icon-box": ["title_text", "description_text"],
    "image-box": ["title_text", "description_text"],
    "testimonial": ["testimonial_content", "testimonial_name", "testimonial_job"],
    "alert": ["alert_title", "alert_description"],
    "counter": ["title", "prefix", "suffix"],
    "call-to-action": ["title", "description", "button"],
    "accordion": ["tabs.*.tab_title", "tabs.*.tab_content"],
    "toggle": ["tabs.*.tab_title", "tabs.*.tab_content"],
    "tabs": ["tabs.*.tab_title", "tabs.*.tab_content"],
    "icon-list": ["icon_list.*.text"],
}

# Fields whose value is HTML; everything else is written as .txt when extracted.
HTML_FIELD_NAMES = {"html", "editor", "tab_content", "testimonial_content", "description"}


def iter_string_fields(settings: Any, spec: str) -> Iterator[tuple[str, Any, Any]]:
    """Yield ``(concrete_path, container, key)`` for each string value matched by ``spec``.

    ``container[key]`` is the string, so callers can read or assign it.
    """
    if not isinstance(settings, dict):
        return
    parts = spec.split(".")

    def rec(obj: Any, idx: int, trail: list[str]) -> Iterator[tuple[str, Any, Any]]:
        part = parts[idx]
        last = idx == len(parts) - 1
        if part == "*":
            if isinstance(obj, list):
                for i in range(len(obj)):
                    if last:
                        if isinstance(obj[i], str):
                            yield ".".join(trail + [str(i)]), obj, i
                    else:
                        yield from rec(obj[i], idx + 1, trail + [str(i)])
            return
        if isinstance(obj, dict) and part in obj:
            if last:
                if isinstance(obj[part], str):
                    yield ".".join(trail + [part]), obj, part
            else:
                yield from rec(obj[part], idx + 1, trail + [part])
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            if last:
                if isinstance(obj[int(part)], str):
                    yield ".".join(trail + [part]), obj, int(part)
            else:
                yield from rec(obj[int(part)], idx + 1, trail + [part])

    yield from rec(settings, 0, [])


def get_path(settings: Any, path: str) -> Any:
    """Read a concrete dotted path (as produced by :func:`iter_string_fields`)."""
    current = settings
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current


def set_path(settings: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    current = settings
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    last = parts[-1]
    if isinstance(current, list):
        current[int(last)] = value
    else:
        current[last] = value


def fields_for(widget_type: str, override: list[str] | None = None) -> list[str]:
    if override:
        return list(override)
    try:
        return TEXT_FIELDS[widget_type]
    except KeyError:
        raise ValueError(
            f"no known text fields for widget type {widget_type!r}; pass fields explicitly"
        ) from None
