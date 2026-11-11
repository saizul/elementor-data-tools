"""List every link in an export and flag the ones that usually need fixing.

Covers Elementor link controls (button, heading, image, icon list, ... anything stored as
``{"url": ..., "is_external": ..., "nofollow": ...}``) and ``<a href>`` tags inside HTML
text fields. Nothing is fetched: this is a static audit of what the export contains.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from eltools.tree import Node, walk

KIND_CONTROL = "control"  # an Elementor link control
KIND_HTML = "html"  # an <a href> tag inside HTML (html, text-editor, tab content, ...)

TYPE_ANCHOR = "anchor"  # "#pricing": jumps within the page
TYPE_RELATIVE = "relative"  # "/shop/" or "shop/"
TYPE_MAIL = "mailto"
TYPE_TEL = "tel"
TYPE_ABSOLUTE = "absolute"  # http(s) URL, no --site given to compare with
TYPE_INTERNAL = "internal"  # http(s) URL on the site
TYPE_EXTERNAL = "external"  # http(s) URL on another host
TYPE_OTHER = "other"  # empty, "#", javascript:, sms:, ...
LINK_TYPES = (
    TYPE_INTERNAL,
    TYPE_EXTERNAL,
    TYPE_ABSOLUTE,
    TYPE_RELATIVE,
    TYPE_ANCHOR,
    TYPE_MAIL,
    TYPE_TEL,
    TYPE_OTHER,
)

ISSUE_EMPTY = "empty"  # a button with no link at all
ISSUE_PLACEHOLDER = "placeholder"  # "#", "javascript:void(0)": left over from a template
ISSUE_INSECURE = "insecure"  # http:// link
ISSUE_NO_SCHEME = "no-scheme"  # "www.example.com/x" is treated as a relative path by browsers
ISSUE_WHITESPACE = "whitespace"  # stray spaces around or inside the URL
ISSUE_FORBIDDEN = "forbidden-host"  # host given with --forbid-host (staging, old domain)

# Keys that make a {"url": ...} mapping a media control value rather than a link control.
_MEDIA_KEYS = ("id", "alt", "source", "size")
# Widgets whose whole purpose is the link: an empty link control there is a mistake.
_LINK_REQUIRED = ("button",)
_PLACEHOLDERS = ("#", "#!", "javascript:;", "javascript:void(0)", "javascript:void(0);")


@dataclass
class LinkRef:
    node: Node
    field: str
    kind: str
    url: str
    text: str | None = None  # anchor text, HTML links only
    new_tab: bool = False
    nofollow: bool = False
    type: str = TYPE_OTHER
    issues: list[str] = field(default_factory=list)

    @property
    def host(self) -> str:
        """Lowercase host of an http(s) or protocol-relative URL, else ``""``."""
        return url_host(self.url)


def normalize_host(value: str) -> str:
    """``https://WWW.Example.com/x`` or ``Example.com:443`` -> ``example.com``."""
    value = value.strip().lower()
    if "://" in value or value.startswith("//"):
        value = urlsplit(value).netloc
    value = value.split("/")[0].split("@")[-1].split(":")[0]
    return value[4:] if value.startswith("www.") else value


def url_host(url: str) -> str:
    url = url.strip()
    if not url.lower().startswith(("http://", "https://", "//")):
        return ""
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def host_matches(host: str, pattern: str) -> bool:
    """True when ``host`` is ``pattern`` or one of its subdomains (``www.`` is ignored)."""
    host, pattern = normalize_host(host), normalize_host(pattern)
    return bool(host and pattern) and (host == pattern or host.endswith("." + pattern))


def classify(url: str, site: str | None = None) -> str:
    """One of :data:`LINK_TYPES` for a URL as written in the export."""
    stripped = url.strip()
    lowered = stripped.lower()
    if not stripped or lowered in _PLACEHOLDERS:
        return TYPE_OTHER
    if stripped.startswith("#"):
        return TYPE_ANCHOR
    if lowered.startswith("mailto:"):
        return TYPE_MAIL
    if lowered.startswith("tel:"):
        return TYPE_TEL
    if lowered.startswith(("http://", "https://", "//")):
        if not site:
            return TYPE_ABSOLUTE
        return (
            TYPE_INTERNAL
            if normalize_host(url_host(stripped)) == normalize_host(site)
            else (TYPE_EXTERNAL)
        )
    head = lowered.split("/")[0].split("?")[0]
    if ":" in head:  # some other scheme: javascript:, sms:, whatsapp:, ...
        return TYPE_OTHER
    return TYPE_RELATIVE


def link_issues(ref: LinkRef, forbid_hosts: Iterable[str] = ()) -> list[str]:
    """Problems with one link, most important first (empty list when it looks fine)."""
    url = ref.url
    stripped = url.strip()
    lowered = stripped.lower()
    if not stripped:
        return [ISSUE_EMPTY if ref.kind == KIND_CONTROL else ISSUE_PLACEHOLDER]
    if lowered in _PLACEHOLDERS:
        return [ISSUE_PLACEHOLDER]
    issues: list[str] = []
    host = url_host(stripped)
    if any(host_matches(host, pattern) for pattern in forbid_hosts):
        issues.append(ISSUE_FORBIDDEN)
    if lowered.startswith("http://"):
        issues.append(ISSUE_INSECURE)
    if lowered.startswith("www.") and "." in lowered[4:]:
        issues.append(ISSUE_NO_SCHEME)
    if stripped != url or any(ch.isspace() for ch in stripped):
        if not lowered.startswith(("mailto:", "tel:", "javascript:")):
            issues.append(ISSUE_WHITESPACE)
    return issues


class _Anchors(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, Any]] = []
        self._open: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._close()
            found = dict(attrs)
            if "href" in found:
                self._open = {"attrs": found, "text": []}
        elif tag == "img" and self._open is not None:
            alt = dict(attrs).get("alt")
            if alt:
                self._open["text"].append(alt)  # an image link is named by its alt text

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._close()

    def handle_data(self, data: str) -> None:
        if self._open is not None:
            self._open["text"].append(data)

    def _close(self) -> None:
        if self._open is not None:
            self._open["text"] = " ".join("".join(self._open["text"]).split())
            self.links.append(self._open)
            self._open = None

    def close(self) -> None:
        super().close()
        self._close()  # unterminated <a>


def html_links(markup: str) -> list[dict[str, Any]]:
    """``{"href", "text", "new_tab", "nofollow"}`` for each ``<a href>`` in ``markup``."""
    if "<a" not in markup.lower():
        return []
    parser = _Anchors()
    parser.feed(markup)
    parser.close()
    out = []
    for link in parser.links:
        attrs = link["attrs"]
        rel = (attrs.get("rel") or "").lower().split()
        out.append(
            {
                "href": attrs.get("href") or "",
                "text": link["text"],
                "new_tab": (attrs.get("target") or "").lower() == "_blank",
                "nofollow": "nofollow" in rel,
            }
        )
    return out


def _is_link_control(value: dict[str, Any]) -> bool:
    return isinstance(value.get("url"), str) and not any(key in value for key in _MEDIA_KEYS)


def _scan(value: Any, trail: list[str]) -> Iterator[tuple[str, str, Any]]:
    """Yield ``(path, kind, payload)``: a link control dict, or an HTML string with <a."""
    if isinstance(value, dict):
        if _is_link_control(value):
            yield ".".join(trail), KIND_CONTROL, value
            return
        for key, item in value.items():
            if key == "__dynamic__":  # dynamic tag definitions, not content
                continue
            yield from _scan(item, trail + [str(key)])
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _scan(item, trail + [str(index)])
    elif isinstance(value, str) and "<a" in value.lower():
        yield ".".join(trail), KIND_HTML, value


def _on(value: Any) -> bool:
    return value in ("on", "yes", True, 1, "1", "true")


def _is_dynamic(settings: dict[str, Any], path: str) -> bool:
    """The control is filled by a dynamic tag (post URL, ACF field, ...) at render time."""
    dynamic = settings.get("__dynamic__")
    return isinstance(dynamic, dict) and path.split(".")[0] in dynamic


def find_links(
    elements: Any, site: str | None = None, forbid_hosts: Iterable[str] = ()
) -> list[LinkRef]:
    """Every link in document order, classified and checked.

    Link controls left empty are skipped (most widgets have an optional link), except on
    widgets that exist to be clicked (buttons), where an empty link is reported as an issue.
    Controls filled by a dynamic tag are skipped: their URL is only known at render time.
    """
    forbid = tuple(forbid_hosts)
    refs: list[LinkRef] = []
    for node in walk(elements):
        settings = node.element.get("settings")
        if not isinstance(settings, dict):
            continue
        for path, kind, payload in _scan(settings, []):
            found: list[LinkRef] = []
            if kind == KIND_HTML:
                for link in html_links(payload):
                    found.append(
                        LinkRef(
                            node,
                            path,
                            kind,
                            link["href"],
                            link["text"],
                            link["new_tab"],
                            link["nofollow"],
                        )
                    )
            else:
                url = payload["url"]
                if _is_dynamic(settings, path):
                    continue
                if not url.strip() and not (node.kind in _LINK_REQUIRED and path == "link"):
                    continue
                found.append(
                    LinkRef(
                        node,
                        path,
                        kind,
                        url,
                        None,
                        _on(payload.get("is_external")),
                        _on(payload.get("nofollow")),
                    )
                )
            for ref in found:
                ref.type = classify(ref.url, site)
                ref.issues = link_issues(ref, forbid)
            refs.extend(found)
    return refs


def host_counts(refs: Iterable[LinkRef]) -> Counter[str]:
    """How many links point at each host (links without a host are not counted)."""
    return Counter(ref.host for ref in refs if ref.host)
