from __future__ import annotations

from eltools.tree import (
    element_counts,
    find_by_id,
    max_depth,
    resolve_pointer,
    walk,
    widget_counts,
)


def test_walk_is_document_order(tree):
    ids = [n.id for n in walk(tree)]
    assert ids == ["aaaaaaa", "bbbbbbb", "ccccccc", "ddddddd", "eeeeeee"]


def test_paths_and_depth(tree):
    nodes = {n.id: n for n in walk(tree)}
    assert nodes["aaaaaaa"].path == (0,) and nodes["aaaaaaa"].depth == 0
    assert nodes["eeeeeee"].path == (0, 0, 2) and nodes["eeeeeee"].depth == 2
    assert nodes["eeeeeee"].path_str == "0/0/2"


def test_pointer_format(tree):
    node = find_by_id(tree, "eeeeeee")
    assert node.pointer == "/0/elements/0/elements/2"


def test_resolve_pointer_roundtrip(tree):
    for node in walk(tree):
        assert resolve_pointer(tree, node.pointer) is node.element


def test_resolve_pointer_missing(tree):
    assert resolve_pointer(tree, "/5/elements/1") is None
    assert resolve_pointer(tree, "/0/nope/1") is None


def test_trail_and_parent(tree):
    node = find_by_id(tree, "ccccccc")
    assert node.parent.id == "bbbbbbb"
    assert node.trail == "section#aaaaaaa > column#bbbbbbb > heading#ccccccc"


def test_kind_uses_widget_type(tree):
    kinds = {n.id: n.kind for n in walk(tree)}
    assert kinds["aaaaaaa"] == "section" and kinds["ddddddd"] == "text-editor"


def test_find_by_id_missing(tree):
    assert find_by_id(tree, "nothere") is None


def test_widget_counts(tree):
    assert dict(widget_counts(tree)) == {"heading": 1, "text-editor": 1, "button": 1}


def test_element_counts(tree):
    assert dict(element_counts(tree)) == {"section": 1, "column": 1, "widget": 3}


def test_max_depth(tree):
    assert max_depth(tree) == 2
    assert max_depth([]) == -1


def test_walk_tolerates_garbage():
    data = [1, None, {"id": "a", "elType": "section", "elements": "oops"}, {"elements": [3]}]
    assert [n.id for n in walk(data)] == ["a", None]


def test_walk_non_list():
    assert list(walk({"a": 1})) == []


def test_example_landing_counts(landing):
    counts = widget_counts(landing.elements)
    assert counts["heading"] == 5 and counts["html"] == 2 and counts["accordion"] == 1
    assert sum(counts.values()) == 16


def test_inner_container_depth(container_doc):
    nodes = {n.id: n for n in walk(container_doc.elements)}
    assert nodes["4d6f8b0"].depth == 2
    assert nodes["4d6f8b0"].trail.startswith("container#9a1c3e5 > container#3c5e7a9")
