from __future__ import annotations

import pytest

from eltools.fields import fields_for, get_path, iter_string_fields, set_path


def test_simple_field():
    s = {"title": "Hi", "size": 3}
    assert [p for p, _, _ in iter_string_fields(s, "title")] == ["title"]


def test_non_string_values_are_ignored():
    assert list(iter_string_fields({"title": 5}, "title")) == []
    assert list(iter_string_fields({"title": None}, "title")) == []


def test_missing_key():
    assert list(iter_string_fields({}, "title")) == []


def test_empty_list_settings():
    assert list(iter_string_fields([], "title")) == []


def test_repeater_wildcard():
    s = {"tabs": [{"tab_title": "A"}, {"tab_title": "B"}, {"other": "x"}]}
    found = [(p, c[k]) for p, c, k in iter_string_fields(s, "tabs.*.tab_title")]
    assert found == [("tabs.0.tab_title", "A"), ("tabs.1.tab_title", "B")]


def test_get_and_set_path():
    s = {"tabs": [{"tab_title": "A"}]}
    set_path(s, "tabs.0.tab_title", "Z")
    assert get_path(s, "tabs.0.tab_title") == "Z"


def test_container_assignment_writes_through():
    s = {"tabs": [{"tab_title": "A"}]}
    for _, container, key in iter_string_fields(s, "tabs.*.tab_title"):
        container[key] = "changed"
    assert s["tabs"][0]["tab_title"] == "changed"


def test_fields_for_known_and_override():
    assert fields_for("heading") == ["title"]
    assert fields_for("whatever", ["a.b"]) == ["a.b"]


def test_fields_for_unknown_raises():
    with pytest.raises(ValueError, match="no known text fields"):
        fields_for("google-maps")
