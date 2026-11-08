from __future__ import annotations

import copy

from conftest import widget
from eltools.validate import errors_only, validate


def codes(issues):
    return sorted(i.code for i in issues)


def test_examples_are_valid(landing, container_doc):
    assert validate(landing.elements) == []
    assert validate(container_doc.elements) == []


def test_simple_tree_valid(tree):
    assert validate(tree) == []


def test_root_not_a_list():
    assert codes(validate({"a": 1})) == ["E001"]


def test_non_object_element():
    assert "E010" in codes(validate([5]))


def test_bad_eltype(tree):
    tree[0]["elType"] = "banana"
    assert "E011" in codes(validate(tree))


def test_missing_id(tree):
    del tree[0]["id"]
    assert "E013" in codes(validate(tree))


def test_odd_id_is_warning_only(tree):
    tree[0]["id"] = "XYZ"
    issues = validate(tree)
    assert codes(issues) == ["W014"] and not errors_only(issues)


def test_duplicate_id(tree):
    tree[0]["elements"][0]["elements"][1]["id"] = "ccccccc"
    issues = validate(tree)
    assert "E015" in codes(issues)
    assert "/0/elements/0/elements/0" in str([i for i in issues if i.code == "E015"][0])


def test_widget_without_widget_type(tree):
    del tree[0]["elements"][0]["elements"][0]["widgetType"]
    assert "E012" in codes(validate(tree))


def test_settings_wrong_type(tree):
    tree[0]["settings"] = "nope"
    assert "E017" in codes(validate(tree))


def test_php_empty_array_settings_is_fine(tree):
    tree[0]["settings"] = []
    assert validate(tree) == []


def test_elements_wrong_type(tree):
    tree[0]["elements"] = {}
    assert "E016" in codes(validate(tree))


def test_missing_elements_warns(tree):
    del tree[0]["elements"][0]["elements"][0]["elements"]
    assert "W016" in codes(validate(tree))


def test_column_at_top_level():
    assert "E021" in codes(validate([{"id": "aaaaaaa", "elType": "column", "elements": []}]))


def test_widget_at_top_level():
    assert "E021" in codes(validate([widget("aaaaaaa")]))


def test_section_must_contain_columns(tree):
    tree[0]["elements"].append(widget("fffffff"))
    assert "E022" in codes(validate(tree))


def test_column_in_column(tree):
    tree[0]["elements"][0]["elements"].append(
        {"id": "1111111", "elType": "column", "settings": {}, "elements": []}
    )
    assert "E023" in codes(validate(tree))


def test_inner_section_needs_flag(tree):
    inner = {"id": "2222222", "elType": "section", "settings": {}, "elements": []}
    tree[0]["elements"][0]["elements"].append(inner)
    assert "W024" in codes(validate(tree))
    inner["isInner"] = True
    assert "W024" not in codes(validate(tree))


def test_container_cannot_hold_column():
    data = [
        {
            "id": "aaaaaaa",
            "elType": "container",
            "settings": {},
            "elements": [{"id": "bbbbbbb", "elType": "column", "settings": {}, "elements": []}],
        }
    ]
    assert "E025" in codes(validate(data))


def test_widget_with_children_warns(tree):
    tree[0]["elements"][0]["elements"][0]["elements"] = [widget("9999999")]
    got = codes(validate(tree))
    assert "W020" in got and "E026" in got


def test_broken_example_reports_known_errors(broken):
    got = codes(validate(broken.elements))
    assert got == ["E012", "E015", "E021", "E022"]


def test_validation_does_not_mutate(landing):
    before = copy.deepcopy(landing.elements)
    validate(landing.elements)
    assert landing.elements == before
