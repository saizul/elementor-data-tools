from __future__ import annotations

import copy

from eltools.cli import format_diff
from eltools.diff import diff_documents, diff_values
from eltools.tree import find_by_id


def test_identical_documents_have_no_diff(landing):
    assert diff_documents(landing.elements, copy.deepcopy(landing.elements)).empty


def test_example_diff_summary(landing, landing_v2):
    r = diff_documents(landing.elements, landing_v2.elements)
    assert sorted(a.id for a in r.added) == ["d6a8e03", "fa05c13"]
    assert [x.id for x in r.removed] == ["1bd7c05"]
    assert sorted(c.id for c in r.changed) == ["1a7f3e9", "4c1e7a9", "4f1a9c2", "e84a0b7"]
    assert r.moved == [] and r.reordered == []


def test_added_subtree_reported_once_with_descendants(landing, landing_v2):
    r = diff_documents(landing.elements, landing_v2.elements)
    section = [a for a in r.added if a.id == "d6a8e03"][0]
    assert section.descendants == 3 and section.kind == "section"


def test_setting_change_details(landing, landing_v2):
    r = diff_documents(landing.elements, landing_v2.elements)
    btn = [c for c in r.changed if c.id == "e84a0b7"][0]
    paths = {s.path: (s.old, s.new) for s in btn.changes}
    assert paths["settings.text"] == ("Shop the roastery", "Shop the roastery now")
    assert "settings.link.url" in paths


def test_repeater_item_change_path(landing, landing_v2):
    r = diff_documents(landing.elements, landing_v2.elements)
    acc = [c for c in r.changed if c.id == "4c1e7a9"][0]
    assert [s.path for s in acc.changes] == ["settings.tabs.1.tab_content"]


def test_added_and_removed_setting_keys(tree):
    other = copy.deepcopy(tree)
    other[0]["elements"][0]["elements"][0]["settings"]["align"] = "left"
    del other[0]["elements"][0]["elements"][0]["settings"]["title"]
    r = diff_documents(tree, other)
    ops = {s.path: s.op for s in r.changed[0].changes}
    assert ops == {"settings.align": "added", "settings.title": "removed"}


def test_widget_type_change_detected(tree):
    other = copy.deepcopy(tree)
    other[0]["elements"][0]["elements"][0]["widgetType"] = "text-editor"
    r = diff_documents(tree, other)
    assert r.changed[0].changes[0].path == "widgetType"


def test_moved_between_columns():
    def col(cid, kids):
        return {"id": cid, "elType": "column", "settings": {}, "elements": kids}

    w = {
        "id": "wwwwwww",
        "elType": "widget",
        "widgetType": "heading",
        "settings": {},
        "elements": [],
    }
    a = [
        {
            "id": "sssssss",
            "elType": "section",
            "settings": {},
            "elements": [col("c111111", [w]), col("c222222", [])],
        }
    ]
    b = [
        {
            "id": "sssssss",
            "elType": "section",
            "settings": {},
            "elements": [col("c111111", []), col("c222222", [copy.deepcopy(w)])],
        }
    ]
    r = diff_documents(a, b)
    assert len(r.moved) == 1
    assert (r.moved[0].old_parent, r.moved[0].new_parent) == ("c111111", "c222222")
    assert r.added == [] and r.removed == []


def test_reorder_detected(tree):
    other = copy.deepcopy(tree)
    kids = other[0]["elements"][0]["elements"]
    kids[0], kids[1] = kids[1], kids[0]
    r = diff_documents(tree, other)
    assert r.reordered == ["bbbbbbb"] and not r.changed and not r.moved


def test_removing_sibling_is_not_a_reorder(tree):
    other = copy.deepcopy(tree)
    del other[0]["elements"][0]["elements"][0]
    r = diff_documents(tree, other)
    assert r.reordered == [] and [x.id for x in r.removed] == ["ccccccc"]


def test_ignore_keys(landing, landing_v2):
    r = diff_documents(landing.elements, landing_v2.elements, ignore_keys=("settings.padding",))
    assert "4f1a9c2" not in [c.id for c in r.changed]


def test_php_empty_array_equals_empty_object(tree):
    a = copy.deepcopy(tree)
    b = copy.deepcopy(tree)
    a[0]["settings"] = []
    b[0]["settings"] = {}
    assert diff_documents(a, b).empty


def test_bool_vs_int_is_a_change():
    assert diff_values({"a": True}, {"a": 1})[0].op == "changed"


def test_int_vs_float_equal():
    assert diff_values({"a": 10}, {"a": 10.0}) == []


def test_list_length_changes():
    ops = [(c.path, c.op) for c in diff_values({"l": [1, 2]}, {"l": [1, 2, 3]})]
    assert ops == [("l.2", "added")]


def test_diff_is_symmetric_for_add_remove(landing, landing_v2):
    fwd = diff_documents(landing.elements, landing_v2.elements)
    back = diff_documents(landing_v2.elements, landing.elements)
    assert sorted(a.id for a in fwd.added) == sorted(r.id for r in back.removed)
    assert sorted(a.id for a in back.added) == sorted(r.id for r in fwd.removed)


def test_diff_does_not_mutate(landing, landing_v2):
    a, b = copy.deepcopy(landing.elements), copy.deepcopy(landing_v2.elements)
    diff_documents(landing.elements, landing_v2.elements)
    assert a == landing.elements and b == landing_v2.elements


def test_to_dict_is_json_serializable(landing, landing_v2):
    import json

    json.dumps(diff_documents(landing.elements, landing_v2.elements).to_dict())


def test_format_diff_text(landing, landing_v2):
    out = format_diff(diff_documents(landing.elements, landing_v2.elements))
    assert "+ added    section #d6a8e03" in out and "(+3 descendants)" in out
    assert "- removed  heading #1bd7c05" in out
    assert out.splitlines()[-1] == "2 added, 1 removed, 4 changed, 0 moved"


def test_format_diff_empty():
    assert format_diff(diff_documents([], [])) == "no differences"


def test_find_sanity(landing_v2):
    assert find_by_id(landing_v2.elements, "fa05c13").widget_type == "button"
