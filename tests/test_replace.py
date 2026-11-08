from __future__ import annotations

import pytest

from eltools.replace import replace_text
from eltools.tree import find_by_id, walk


def test_replace_only_chosen_widget_types(tree):
    changes = replace_text(tree, "Hello", "Hi", ("heading",))
    assert [c.id for c in changes] == ["ccccccc"]
    assert find_by_id(tree, "ccccccc").element["settings"]["title"] == "Hi World"
    assert find_by_id(tree, "ddddddd").element["settings"]["editor"] == "<p>Hello <b>there</b></p>"
    assert find_by_id(tree, "eeeeeee").element["settings"]["text"] == "Hello"


def test_multiple_types(tree):
    changes = replace_text(tree, "Hello", "Hi", ("heading", "text-editor", "button"))
    assert len(changes) == 3


def test_url_fields_are_never_touched(tree):
    replace_text(tree, "hello", "bye", ("button",))
    assert find_by_id(tree, "eeeeeee").element["settings"]["link"]["url"] == "https://x.test/hello"


def test_case_sensitive_by_default(tree):
    assert replace_text(tree, "hello", "x", ("heading",)) == []


def test_ignore_case(tree):
    changes = replace_text(tree, "hello", "Howdy", ("heading",), ignore_case=True)
    assert changes[0].after == "Howdy World"


def test_regex_with_groups(tree):
    changes = replace_text(tree, r"(\w+) World", r"World, \1", ("heading",), regex=True)
    assert changes[0].after == "World, Hello"


def test_literal_replacement_is_not_regex(tree):
    replace_text(tree, "Hello", r"\1 $1", ("heading",))
    assert find_by_id(tree, "ccccccc").element["settings"]["title"] == r"\1 $1 World"


def test_literal_find_with_special_chars(tree):
    tree[0]["elements"][0]["elements"][0]["settings"]["title"] = "Price (50%) [new]"
    changes = replace_text(tree, "(50%)", "(40%)", ("heading",))
    assert changes[0].after == "Price (40%) [new]"


def test_count_multiple_occurrences(tree):
    tree[0]["elements"][0]["elements"][0]["settings"]["title"] = "a a a"
    assert replace_text(tree, "a", "b", ("heading",))[0].count == 3


def test_dry_run_leaves_tree_untouched(tree):
    import copy

    before = copy.deepcopy(tree)
    changes = replace_text(tree, "Hello", "Hi", ("heading", "text-editor"), apply=False)
    assert len(changes) == 2 and tree == before


def test_html_content_replaced_inside_markup(tree):
    replace_text(tree, "<b>there</b>", "<i>you</i>", ("text-editor",))
    assert find_by_id(tree, "ddddddd").element["settings"]["editor"] == "<p>Hello <i>you</i></p>"


def test_repeater_fields(landing):
    changes = replace_text(landing.elements, "Skip", "Pause", ("accordion",))
    assert changes and changes[0].field == "tabs.1.tab_content"


def test_custom_field_override(landing):
    changes = replace_text(landing.elements, "Shop", "Buy", ("button",), fields=["text"])
    assert [c.after for c in changes] == ["Buy the roastery"]


def test_empty_find_rejected(tree):
    with pytest.raises(ValueError):
        replace_text(tree, "", "x", ("heading",))


def test_no_types_rejected(tree):
    with pytest.raises(ValueError):
        replace_text(tree, "a", "b", ())


def test_unknown_widget_type_rejected_before_any_change(tree):
    with pytest.raises(ValueError):
        replace_text(tree, "Hello", "Hi", ("heading", "mystery-widget"))
    assert find_by_id(tree, "ccccccc").element["settings"]["title"] == "Hello World"


def test_diff_text_is_unified(tree):
    change = replace_text(tree, "Hello", "Hi", ("heading",), apply=False)[0]
    text = change.diff()
    assert text.startswith("--- a/heading#ccccccc title")
    assert "-Hello World" in text and "+Hi World" in text


def test_multiline_diff(tree):
    tree[0]["elements"][0]["elements"][1]["settings"]["editor"] = "<p>one</p>\n<p>two</p>"
    change = replace_text(tree, "two", "2", ("text-editor",), apply=False)[0]
    assert "-<p>two</p>" in change.diff() and "+<p>2</p>" in change.diff()


def test_structure_and_ids_unchanged(landing):
    before = [(n.id, n.kind, n.path) for n in walk(landing.elements)]
    replace_text(landing.elements, "e", "E", ("heading", "text-editor", "button"))
    assert before == [(n.id, n.kind, n.path) for n in walk(landing.elements)]


def test_changes_report_pointer(tree):
    assert replace_text(tree, "Hello", "Hi", ("heading",))[0].pointer == "/0/elements/0/elements/0"
