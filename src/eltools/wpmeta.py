"""Produce ``_elementor_data`` JSON in the exact shape WordPress stores it."""

from __future__ import annotations

import json
import shlex
from typing import Any

from eltools.document import STYLE_WP, Document, dumps


def to_wp_meta(source: Document | list[Any]) -> str:
    """ASCII-only, single-line JSON with ``/`` escaped as ``\\/`` and no trailing newline.

    Template exports are unwrapped: the post meta holds only the element list.
    The result is parsed back and compared before it is returned.
    """
    elements = source.elements if isinstance(source, Document) else source
    text = dumps(elements, STYLE_WP)
    if json.loads(text) != elements:  # defensive: never emit data that does not round-trip
        raise ValueError("serialization did not round-trip")
    return text


def command_template(
    post_id: int | str,
    data_file: str,
    *,
    wp_path: str | None = None,
    url: str | None = None,
    meta_key: str = "_elementor_data",
) -> list[str]:
    """Lines of a shell recipe for applying ``data_file`` with WP-CLI."""
    flags = ""
    if wp_path:
        flags += f" --path={shlex.quote(wp_path)}"
    if url:
        flags += f" --url={shlex.quote(url)}"
    pid = shlex.quote(str(post_id))
    data = shlex.quote(data_file)
    return [
        "# 1. Back up the current value",
        f"wp post meta get {pid} {meta_key}{flags} > elementor_data.backup.json",
        "",
        "# 2. Write the new value (read from STDIN: no shell argument size limit)",
        f"wp post meta update {pid} {meta_key}{flags} < {data}",
        "",
        "# 3. Regenerate Elementor CSS and flush caches",
        f"wp elementor flush-css{flags}",
        f"wp cache flush{flags}",
        "",
        "# 4. Verify the stored value is valid and matches",
        f"wp post meta get {pid} {meta_key}{flags} | eltools validate -",
    ]
