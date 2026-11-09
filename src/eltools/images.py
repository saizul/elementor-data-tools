"""List every image in an export with its alt text (for accessibility and SEO audits)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from eltools.tree import Node, walk

KIND_IMAGE = "image"  # an Elementor media control (image widget, image-box, carousel, ...)
KIND_BACKGROUND = "background"  # decorative background image, alt text does not apply
KIND_HTML = "html"  # an <img> tag inside HTML (html, text-editor, tab content, ...)

# Keys that make a {"url": ...} mapping a media control value rather than a link control.
_MEDIA_KEYS = ("id", "alt", "source", "size")


@dataclass
class ImageRef:
    node: Node
    field: str
    kind: str
    url: str
    alt: str | None
    attachment_id: Any = None

    @property
    def missing_alt(self) -> bool:
        """No alt text is stored in the export.

        Backgrounds are decorative. For an ``<img>`` tag an explicit ``alt=""`` is the
        correct way to mark a decorative image, so only a missing attribute counts.
        Media controls store an empty alt when none was typed (Elementor may still fall
        back to the media library's alt text, which an export cannot show).
        """
        if self.kind == KIND_BACKGROUND:
            return False
        if self.kind == KIND_HTML:
            return self.alt is None
        return not (self.alt or "").strip()


class _ImgTags(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            self.tags.append(dict(attrs))

    handle_startendtag = handle_starttag  # <img ... />


def html_images(markup: str) -> list[tuple[str, str | None]]:
    """``(src, alt)`` for each ``<img>`` in ``markup``; ``alt`` is ``None`` when absent."""
    if "<img" not in markup.lower():
        return []
    parser = _ImgTags()
    parser.feed(markup)
    parser.close()
    return [(tag.get("src") or "", tag.get("alt")) for tag in parser.tags]


def _is_media(value: dict[str, Any]) -> bool:
    return (
        isinstance(value.get("url"), str)
        and value["url"] != ""
        and any(key in value for key in _MEDIA_KEYS)
    )


def _scan(value: Any, trail: list[str]) -> Iterator[tuple[str, str, Any]]:
    """Yield ``(path, kind, payload)``: a media dict, or an HTML string containing <img."""
    if isinstance(value, dict):
        if _is_media(value):
            leaf = trail[-1] if trail else ""
            kind = KIND_BACKGROUND if "background" in leaf or leaf.startswith("bg_") else KIND_IMAGE
            yield ".".join(trail), kind, value
            return
        for key, item in value.items():
            yield from _scan(item, trail + [str(key)])
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _scan(item, trail + [str(index)])
    elif isinstance(value, str) and "<img" in value.lower():
        yield ".".join(trail), KIND_HTML, value


def find_images(elements: Any) -> list[ImageRef]:
    """Every image reference in document order."""
    refs: list[ImageRef] = []
    for node in walk(elements):
        settings = node.element.get("settings")
        if not isinstance(settings, dict):
            continue
        for path, kind, payload in _scan(settings, []):
            if kind == KIND_HTML:
                for src, alt in html_images(payload):
                    refs.append(ImageRef(node, path, kind, src, alt))
            else:
                alt = payload.get("alt")
                refs.append(
                    ImageRef(
                        node,
                        path,
                        kind,
                        payload["url"],
                        alt if isinstance(alt, str) else None,
                        payload.get("id"),
                    )
                )
    return refs
