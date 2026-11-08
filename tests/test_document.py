from __future__ import annotations

import json

import pytest

from eltools.document import ElementorDataError, detect_style, dumps, load, loads


def test_loads_plain_list():
    doc = loads('[{"id":"a","elType":"section","elements":[]}]')
    assert doc.wrapper is None and len(doc.elements) == 1


def test_loads_template_export_keeps_wrapper(landing):
    assert landing.wrapper["type"] == "page"
    assert landing.wrapper["version"] == "0.4"
    assert isinstance(landing.elements, list)


def test_to_data_reattaches_content(landing):
    data = landing.to_data()
    assert data["content"] is landing.elements
    assert data["page_settings"]["template"] == "elementor_canvas"


def test_string_encoded_json_is_unwrapped():
    inner = '[{"id":"a1b2c3d","elType":"container","elements":[]}]'
    doc = loads(json.dumps(inner))
    assert doc.string_encoded and doc.elements[0]["id"] == "a1b2c3d"


def test_string_encoded_roundtrip_stays_encoded():
    inner = '[{"id":"a1b2c3d","elType":"container","elements":[]}]'
    doc = loads(json.dumps(inner))
    assert loads(doc.dumps("compact")).string_encoded


@pytest.mark.parametrize("text", ["", "{", "[1,", "not json", "nul"])
def test_invalid_json_raises(text):
    with pytest.raises(ElementorDataError):
        loads(text)


def test_error_mentions_line_and_column():
    with pytest.raises(ElementorDataError, match="line 2"):
        loads('[\n  {"a": }]')


@pytest.mark.parametrize("text", ['{"foo": 1}', "42", "true", '{"content": "no"}'])
def test_wrong_shape_raises(text):
    with pytest.raises(ElementorDataError):
        loads(text)


def test_bom_is_ignored():
    assert loads("﻿[]").elements == []


def test_load_missing_file(tmp_path):
    with pytest.raises(ElementorDataError, match="cannot read"):
        load(tmp_path / "nope.json")


def test_load_invalid_utf8(tmp_path):
    p = tmp_path / "bad.json"
    p.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(ElementorDataError):
        load(p)


def test_detect_style():
    assert detect_style("[\n  1\n]") == "pretty"
    assert detect_style('["a\\/b"]') == "wp"
    assert detect_style('["caf\\u00e9"]') == "wp"
    assert detect_style('["plain"]') == "compact"


def test_wp_style_escapes_slashes_and_unicode():
    out = dumps({"u": "https://a.test/x", "t": "Café — ok"}, "wp")
    assert "\\/" in out and "https://" not in out
    assert "\\u00e9" in out and "\\u2014" in out
    assert out.isascii() and "\n" not in out
    assert json.loads(out) == {"u": "https://a.test/x", "t": "Café — ok"}


def test_wp_style_emoji_uses_surrogate_pairs():
    assert "\\ud83d\\ude00" in dumps("😀", "wp")


def test_compact_has_no_spaces():
    assert dumps({"a": [1, 2]}, "compact") == '{"a":[1,2]}'


def test_pretty_keeps_unicode_and_slashes():
    out = dumps({"a": "é/"}, "pretty")
    assert "é/" in out and "\n" in out


def test_unknown_style():
    with pytest.raises(ValueError):
        dumps([], "fancy")


def test_wp_roundtrip_is_byte_identical(container_doc, examples_dir):
    original = (examples_dir / "container-meta.json").read_text(encoding="utf-8")
    assert container_doc.style == "wp"
    assert container_doc.dumps() == original


def test_pretty_roundtrip_is_byte_identical(landing, examples_dir):
    original = (examples_dir / "landing-page.json").read_text(encoding="utf-8")
    assert landing.dumps() + "\n" == original


def test_key_order_preserved(landing):
    again = loads(landing.dumps())
    assert list(again.elements[0].keys()) == list(landing.elements[0].keys())


def test_copy_is_deep(landing):
    clone = landing.copy()
    clone.elements[0]["id"] = "zzzzzzz"
    assert landing.elements[0]["id"] != "zzzzzzz"
