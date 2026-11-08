from __future__ import annotations

import json

import pytest

from eltools.cli import main
from eltools.document import ElementorDataError
from eltools.find import Condition, find_elements, lookup, matches, parse_condition


def test_parse_condition_forms():
    assert parse_condition("link.url") == Condition("link.url", "exists")
    assert parse_condition("title=Hello World") == Condition("title", "=", "Hello World")
    assert parse_condition("link.url~example.com") == Condition("link.url", "~", "example.com")
    # the first operator wins, the rest belongs to the value
    assert parse_condition("text=a~b") == Condition("text", "=", "a~b")
    assert parse_condition("text~a=b") == Condition("text", "~", "a=b")


@pytest.mark.parametrize("spec", ["", "=x", "a..b=1", ".a", "a."])
def test_parse_condition_rejects_bad_paths(spec):
    with pytest.raises(ElementorDataError):
        parse_condition(spec)


def test_lookup_handles_dicts_lists_and_missing():
    settings = {"tabs": [{"tab_title": "A"}, {"tab_title": "B"}], "link": {"url": "x"}}
    assert lookup(settings, "tabs.1.tab_title") == "B"
    assert lookup(settings, "link.url") == "x"
    assert lookup(settings, "tabs.5.tab_title") is not lookup(settings, "tabs.1.tab_title")
    assert matches(settings, Condition("tabs.5", "exists")) is False
    assert matches(settings, Condition("link.nope", "=", "x")) is False


def test_matches_operators():
    settings = {
        "title": "Coffee",
        "flag": True,
        "size": 12,
        "empty": "",
        "link": {"url": "https://A.com/x"},
    }
    assert matches(settings, Condition("title", "=", "Coffee"))
    assert not matches(settings, Condition("title", "=", "coffee"))  # exact is case-sensitive
    assert matches(settings, Condition("title", "~", "COFF"))  # contains is not
    assert matches(settings, Condition("flag", "=", "true"))
    assert matches(settings, Condition("size", "=", "12"))
    assert matches(settings, Condition("link.url", "~", "a.com"))
    assert matches(settings, Condition("link", "exists"))
    assert not matches(settings, Condition("empty", "exists"))


def test_find_by_type_and_setting(landing):
    hits = find_elements(landing.elements, "heading", [parse_condition("header_size=h3")])
    assert [h.values["header_size"] for h in hits] == ["h3", "h3", "h3"]
    assert all(h.node.kind == "heading" for h in hits)


def test_find_nested_repeater_and_and_semantics(landing):
    hits = find_elements(landing.elements, None, [parse_condition("tabs.0.tab_title~fresh")])
    assert len(hits) == 1 and hits[0].node.kind == "accordion"
    none = find_elements(
        landing.elements,
        "heading",
        [parse_condition("header_size=h3"), parse_condition("title~nothing")],
    )
    assert none == []


def test_find_link_urls_across_widget_types(landing):
    hits = find_elements(landing.elements, None, [parse_condition("link.url~/shop/")])
    assert [h.node.kind for h in hits] == ["button"]


def test_cli_find_text_and_json(capsys, examples_dir):
    path = str(examples_dir / "landing-page.json")
    assert main(["find", path, "--type", "image", "--setting", "image.alt~colombia"]) == 0
    out = capsys.readouterr()
    assert "image #" in out.out and "1 match(es)" in out.err
    assert main(["find", path, "--setting", "header_size=h3", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 3 and rows[0]["settings"] == {"header_size": "h3"}
    assert rows[0]["pointer"].startswith("/")


def test_cli_find_no_match_exits_1(capsys, examples_dir):
    path = str(examples_dir / "landing-page.json")
    assert main(["find", path, "--type", "heading", "--setting", "title=No such title"]) == 1
    assert "0 match(es)" in capsys.readouterr().err


def test_cli_find_requires_a_filter(capsys, examples_dir):
    assert main(["find", str(examples_dir / "landing-page.json")]) == 2
    assert "--type" in capsys.readouterr().err
