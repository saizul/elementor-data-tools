from __future__ import annotations

import json
import shlex

from eltools.document import loads
from eltools.wpmeta import command_template, to_wp_meta


def test_ascii_only_and_single_line(container_doc):
    out = to_wp_meta(container_doc)
    assert out.isascii() and "\n" not in out


def test_slashes_escaped(landing):
    out = to_wp_meta(landing)
    assert "https:\\/\\/demo.example.com" in out and "https://" not in out


def test_unicode_escaped(container_doc):
    out = to_wp_meta(container_doc)
    assert "Caf\\u00e9" in out and "\\u2014" in out


def test_no_trailing_newline(landing):
    assert not to_wp_meta(landing).endswith("\n")


def test_roundtrips_to_same_data(landing):
    assert json.loads(to_wp_meta(landing)) == landing.elements


def test_template_export_is_unwrapped(landing):
    data = json.loads(to_wp_meta(landing))
    assert isinstance(data, list) and data[0]["id"] == "4f1a9c2"


def test_accepts_plain_list(tree):
    assert json.loads(to_wp_meta(tree)) == tree


def test_matches_original_wp_file_exactly(container_doc, examples_dir):
    assert to_wp_meta(container_doc) == (examples_dir / "container-meta.json").read_text()


def test_idempotent_through_loads(container_doc):
    once = to_wp_meta(container_doc)
    assert to_wp_meta(loads(once)) == once


def test_double_quotes_and_backslashes_survive():
    data = [
        {
            "id": "aaaaaaa",
            "elType": "widget",
            "widgetType": "html",
            "settings": {"html": 'a "quote" \\ back\\slash\nnew\tline'},
            "elements": [],
        }
    ]
    assert json.loads(to_wp_meta(data)) == data


def test_command_template_basics():
    lines = command_template(42, "out.json")
    text = "\n".join(lines)
    assert "wp post meta update 42 _elementor_data < out.json" in text
    assert "wp post meta get 42 _elementor_data > elementor_data.backup.json" in text
    assert "wp elementor flush-css" in text


def test_command_template_options_quoted():
    lines = command_template("7", "my file.json", wp_path="/var/www/my site", url="https://a.test")
    update = [ln for ln in lines if ln.startswith("wp post meta update")][0]
    assert "< 'my file.json'" in update
    assert "--path='/var/www/my site'" in update and "--url=https://a.test" in update
    assert shlex.split(update)[:4] == ["wp", "post", "meta", "update"]


def test_post_id_is_quoted_against_injection():
    lines = command_template("1; rm -rf /", "f.json")
    update = [ln for ln in lines if ln.startswith("wp post meta update")][0]
    assert shlex.split(update)[4] == "1; rm -rf /"
