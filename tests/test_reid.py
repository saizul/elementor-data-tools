from __future__ import annotations

import copy
import json

from conftest import simple_tree, widget
from eltools.cli import main
from eltools.reid import (
    REASON_ALL,
    REASON_DUPLICATE,
    REASON_MALFORMED,
    REASON_MISSING,
    REASON_TAKEN,
    IdGenerator,
    collect_ids,
    reassign_ids,
)
from eltools.tree import walk
from eltools.validate import ID_RE, errors_only, validate


def run(capsys, *argv):
    code = main([str(a) for a in argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def _ids(elements):
    return [n.id for n in walk(elements)]


def _pasted_twice():
    """A section copied into the same page: every id appears twice."""
    first = simple_tree()[0]
    first["settings"]["custom_css"] = "selector .elementor-element-ccccccc { color: red; }"
    return [first, copy.deepcopy(first)]


def test_generator_is_unique_hex_and_seeded():
    gen = IdGenerator(taken={"aaaaaaa"}, seed=42)
    ids = [gen() for _ in range(500)]
    assert len(set(ids)) == 500
    assert all(ID_RE.match(i) and not i.isdigit() for i in ids)
    assert "aaaaaaa" not in ids
    assert IdGenerator(seed=42)() == IdGenerator(seed=42)()


def test_clean_tree_needs_no_changes(tree):
    before = copy.deepcopy(tree)
    assert reassign_ids(tree) == []
    assert tree == before


def test_duplicates_keep_first_and_fix_the_copy():
    elements = _pasted_twice()
    changes = reassign_ids(elements, seed=1)
    assert len(changes) == 5
    assert {c.reason for c in changes} == {REASON_DUPLICATE}
    assert all(c.pointer.startswith("/1") for c in changes)
    ids = _ids(elements)
    assert len(ids) == len(set(ids))
    assert ids[:5] == ["aaaaaaa", "bbbbbbb", "ccccccc", "ddddddd", "eeeeeee"]
    assert not errors_only(validate(elements))


def test_duplicate_references_are_rewritten_only_in_the_copy():
    elements = _pasted_twice()
    changes = reassign_ids(elements, seed=1)
    new_heading = next(c.new for c in changes if c.old == "ccccccc")
    assert "elementor-element-ccccccc" in elements[0]["settings"]["custom_css"]
    assert elements[1]["settings"]["custom_css"] == (
        f"selector .elementor-element-{new_heading} {{ color: red; }}"
    )
    assert next(c for c in changes if c.old == "ccccccc").references == 1


def test_missing_and_malformed_ids():
    elements = [
        {"elType": "container", "settings": {}, "elements": [widget("XYZ"), widget("")]},
    ]
    changes = reassign_ids(elements, seed=3)
    assert [(c.pointer, c.old, c.reason) for c in changes] == [
        ("/0", None, REASON_MISSING),
        ("/0/elements/0", "XYZ", REASON_MALFORMED),
        ("/0/elements/1", "", REASON_MISSING),
    ]
    assert all(ID_RE.match(i) for i in _ids(elements))


def test_avoid_ids_from_another_page_and_rewrite_globally(tree):
    tree[0]["elements"][0]["elements"][0]["settings"]["custom_css"] = (
        ".elementor-element-ddddddd p { margin: 0 }"
    )
    tree[0]["elements"][0]["elements"][1]["settings"]["editor"] = (
        '<div class="elementor-element-ddddddd elementor-element-ddddddd2">x</div>'
    )
    changes = reassign_ids(tree, avoid={"ddddddd", "zzzzzzz"}, seed=5)
    assert [(c.old, c.reason) for c in changes] == [("ddddddd", REASON_TAKEN)]
    new = changes[0].new
    css = tree[0]["elements"][0]["elements"][0]["settings"]["custom_css"]
    html = tree[0]["elements"][0]["elements"][1]["settings"]["editor"]
    assert css == f".elementor-element-{new} p {{ margin: 0 }}"
    # a longer class name that merely starts with the id is left alone
    assert html == f'<div class="elementor-element-{new} elementor-element-ddddddd2">x</div>'
    assert changes[0].references == 2


def test_regenerate_all_never_reuses_old_ids(tree):
    old = set(_ids(tree))
    changes = reassign_ids(tree, regenerate_all=True, seed=9)
    assert len(changes) == 5 and {c.reason for c in changes} == {REASON_ALL}
    assert not old & set(_ids(tree))


def test_no_references_and_dry_run():
    elements = _pasted_twice()
    snapshot = copy.deepcopy(elements)
    planned = reassign_ids(elements, seed=1, apply=False)
    assert elements == snapshot
    assert next(c for c in planned if c.old == "ccccccc").references == 1
    applied = reassign_ids(elements, seed=1, update_references=False)
    assert [c.new for c in applied] == [c.new for c in planned]
    assert all(c.references == 0 for c in applied)
    assert elements[1]["settings"]["custom_css"] == snapshot[1]["settings"]["custom_css"]


def test_references_in_nested_settings_lists():
    elements = [widget("aaaaaaa", "accordion", tabs=[{"tab_content": "#elementor-element-x"}])]
    elements[0]["settings"]["tabs"].append({"tab_content": "a .elementor-element-aaaaaaa b"})
    changes = reassign_ids(elements, regenerate_all=True, seed=2)
    assert elements[0]["settings"]["tabs"][1]["tab_content"] == (
        f"a .elementor-element-{changes[0].new} b"
    )


def test_collect_ids_skips_non_strings():
    assert collect_ids([{"id": 5, "elements": [{"id": "abcdef0"}]}, "junk"]) == {"abcdef0"}


def test_cli_check_and_dry_run(capsys, tmp_path):
    p = tmp_path / "page.json"
    p.write_text(json.dumps(_pasted_twice()))
    code, out, err = run(capsys, "reid", p, "--check", "--seed", "1")
    assert code == 1
    assert "section #aaaaaaa -> #" in out and "(duplicate)" in out
    assert "5 id(s) to change, 1 reference(s) (nothing written)" in err
    code, out, _ = run(capsys, "reid", p, "--dry-run", "--json", "--seed", "1")
    assert code == 0 and len(json.loads(out)) == 5
    assert json.loads(p.read_text()) == _pasted_twice()


def test_cli_check_passes_on_clean_example(capsys, examples_dir):
    code, out, _ = run(capsys, "reid", examples_dir / "landing-page.json", "--check")
    assert code == 0 and out == ""


def test_cli_writes_output_and_map(capsys, tmp_path):
    p = tmp_path / "page.json"
    p.write_text(json.dumps(_pasted_twice()))
    out_file, map_file = tmp_path / "fixed.json", tmp_path / "map.json"
    code, _, err = run(capsys, "reid", p, "-o", out_file, "--map", map_file, "--seed", "1")
    assert code == 0 and "5 id(s) changed" in err
    fixed = json.loads(out_file.read_text())
    assert len(set(_ids(fixed))) == 10
    mapping = json.loads(map_file.read_text())
    assert {m["old"] for m in mapping} == {"aaaaaaa", "bbbbbbb", "ccccccc", "ddddddd", "eeeeeee"}
    assert [m["new"] for m in mapping] == _ids(fixed)[5:]


def test_cli_in_place_keeps_template_wrapper_and_backup(capsys, tmp_path, examples_dir):
    p = tmp_path / "landing.json"
    p.write_bytes((examples_dir / "landing-page.json").read_bytes())
    code, _, _ = run(capsys, "reid", p, "--all", "--in-place", "--seed", "4")
    assert code == 0
    data = json.loads(p.read_text())
    original = json.loads((examples_dir / "landing-page.json").read_text())
    assert data["type"] == original["type"] and data["title"] == original["title"]
    assert not set(_ids(data["content"])) & set(_ids(original["content"]))
    assert (tmp_path / "landing.json.bak").read_bytes() == (
        examples_dir / "landing-page.json"
    ).read_bytes()


def test_cli_avoid_other_export(capsys, tmp_path, examples_dir):
    code, out, err = run(
        capsys,
        "reid",
        examples_dir / "landing-page.json",
        "--avoid",
        examples_dir / "landing-page-v2.json",
        "--check",
    )
    assert code == 1 and "(taken)" in out


def test_cli_needs_an_output_mode(capsys, examples_dir):
    code, _, err = run(capsys, "reid", examples_dir / "landing-page.json")
    assert code == 2 and "choose --dry-run, --check" in err
