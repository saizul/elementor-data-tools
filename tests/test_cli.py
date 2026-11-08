from __future__ import annotations

import json

import pytest

from eltools import __version__
from eltools.cli import main


def run(capsys, *argv):
    code = main([str(a) for a in argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0 and __version__ in capsys.readouterr().out


def test_pretty_from_compact(capsys, examples_dir):
    code, out, _ = run(capsys, "pretty", examples_dir / "container-meta.json")
    assert code == 0 and out.count("\n") > 20 and "Café menu" in out


def test_pretty_compact_flag(capsys, examples_dir):
    _, out, _ = run(capsys, "pretty", examples_dir / "landing-page.json", "--compact")
    assert out.count("\n") == 1 and json.loads(out)["type"] == "page"


def test_pretty_from_stdin(capsys, monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO('[{"id":"a"}]'))
    _, out, _ = run(capsys, "pretty", "-")
    assert '"id": "a"' in out


def test_validate_ok(capsys, examples_dir):
    code, out, _ = run(capsys, "validate", examples_dir / "landing-page.json")
    assert code == 0 and "0 error(s)" in out


def test_validate_fails_on_broken(capsys, examples_dir):
    code, out, _ = run(capsys, "validate", examples_dir / "broken.json")
    assert code == 1 and "E012" in out


def test_validate_strict_fails_on_warnings(capsys, tmp_path):
    p = tmp_path / "w.json"
    p.write_text('[{"id":"XYZ","elType":"container","settings":{},"elements":[]}]')
    assert run(capsys, "validate", p)[0] == 0
    assert run(capsys, "validate", p, "--strict")[0] == 1


def test_invalid_json_exit_2(capsys, tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{")
    code, _, err = run(capsys, "validate", p)
    assert code == 2 and "invalid JSON" in err


def test_tree_output(capsys, examples_dir):
    _, out, _ = run(capsys, "tree", examples_dir / "container-meta.json")
    assert "0/1/0" in out and "icon-box #4d6f8b0" in out


def test_tree_max_depth_and_json(capsys, examples_dir):
    _, out, _ = run(
        capsys, "tree", examples_dir / "landing-page.json", "--max-depth", "0", "--json"
    )
    rows = json.loads(out)
    assert len(rows) == 4 and all(r["depth"] == 0 for r in rows)


def test_widgets_counts(capsys, examples_dir):
    _, out, _ = run(capsys, "widgets", examples_dir / "landing-page.json")
    lines = out.splitlines()
    assert lines[0].split() == ["heading", "5"] and lines[-1].split() == ["total", "16"]


def test_widgets_json(capsys, examples_dir):
    _, out, _ = run(capsys, "widgets", examples_dir / "landing-page.json", "--json")
    data = json.loads(out)
    assert data["widgets"]["html"] == 2 and data["elements"]["section"] == 4


def test_widgets_type_listing(capsys, examples_dir):
    code, out, _ = run(capsys, "widgets", examples_dir / "landing-page.json", "--type", "html")
    assert code == 0 and "c2d9a40" in out and "b7d40e2" in out


def test_widgets_type_none_found(capsys, examples_dir):
    assert run(capsys, "widgets", examples_dir / "landing-page.json", "--type", "video")[0] == 1


def test_extract_then_insert_cli(capsys, examples_dir, tmp_path):
    out_dir, result = tmp_path / "html", tmp_path / "out.json"
    code, out, _ = run(capsys, "extract", examples_dir / "landing-page.json", "-d", out_dir)
    assert code == 0 and "c2d9a40--html.html" in out
    f = out_dir / "c2d9a40--html.html"
    f.write_text(f.read_text().replace("2016", "2017"), encoding="utf-8")
    code, out, _ = run(
        capsys, "insert", examples_dir / "landing-page.json", "-d", out_dir, "-o", result
    )
    assert code == 0 and "updated  c2d9a40--html.html" in out
    assert "est. 2017" in result.read_text()
    assert json.loads(result.read_text())["type"] == "page"


def test_insert_no_edit_writes_identical_file(capsys, examples_dir, tmp_path):
    out_dir, result = tmp_path / "h", tmp_path / "o.json"
    run(capsys, "extract", examples_dir / "landing-page.json", "-d", out_dir)
    run(capsys, "insert", examples_dir / "landing-page.json", "-d", out_dir, "-o", result)
    assert result.read_text() == (examples_dir / "landing-page.json").read_text()


def test_insert_dry_run(capsys, examples_dir, tmp_path):
    out_dir = tmp_path / "h"
    run(capsys, "extract", examples_dir / "landing-page.json", "-d", out_dir)
    (out_dir / "c2d9a40--html.html").write_text("x", encoding="utf-8")
    code, out, _ = run(capsys, "insert", examples_dir / "landing-page.json", "-d", out_dir, "-n")
    assert code == 0 and "would update" in out


def test_replace_dry_run_shows_diff(capsys, examples_dir):
    code, out, _ = run(
        capsys,
        "replace",
        examples_dir / "landing-page.json",
        "--find",
        "roastery",
        "--replace",
        "roastery & cafe",
        "--types",
        "heading,button",
        "--dry-run",
    )
    assert code == 0 and "+Shop the roastery & cafe" in out and "dry run" in out


def test_replace_requires_destination(capsys, examples_dir):
    code, _, err = run(
        capsys,
        "replace",
        examples_dir / "landing-page.json",
        "--find",
        "a",
        "--replace",
        "b",
        "--types",
        "heading",
    )
    assert code == 2 and "--dry-run" in err


def test_replace_to_file(capsys, examples_dir, tmp_path):
    dest = tmp_path / "r.json"
    code, _, _ = run(
        capsys,
        "replace",
        examples_dir / "landing-page.json",
        "--find",
        "Ethiopia",
        "--replace",
        "Kenya",
        "--types",
        "heading",
        "-o",
        dest,
    )
    text = dest.read_text()
    assert code == 0 and "Kenya Guji" in text and "Ethiopia Guji beans" in text


def test_replace_in_place_makes_backup(capsys, examples_dir, tmp_path):
    work = tmp_path / "p.json"
    work.write_text((examples_dir / "landing-page.json").read_text())
    run(
        capsys,
        "replace",
        work,
        "--find",
        "Ethiopia",
        "--replace",
        "Kenya",
        "--types",
        "heading",
        "--in-place",
    )
    assert "Kenya" in work.read_text()
    assert "Ethiopia Guji" in (tmp_path / "p.json.bak").read_text()


def test_replace_in_place_no_backup(capsys, examples_dir, tmp_path):
    work = tmp_path / "p.json"
    work.write_text((examples_dir / "landing-page.json").read_text())
    run(
        capsys,
        "replace",
        work,
        "--find",
        "Ethiopia",
        "--replace",
        "Kenya",
        "--types",
        "heading",
        "--in-place",
        "--no-backup",
    )
    assert not (tmp_path / "p.json.bak").exists()


def test_replace_preserves_wp_style(capsys, examples_dir, tmp_path):
    dest = tmp_path / "w.json"
    run(
        capsys,
        "replace",
        examples_dir / "container-meta.json",
        "--find",
        "Pastries",
        "--replace",
        "Bakes",
        "--types",
        "icon-box",
        "-o",
        dest,
    )
    text = dest.read_text()
    assert "\n" not in text and "Bakes" in text and "\\/" in text and text.isascii()


def test_replace_unknown_type(capsys, examples_dir):
    code, _, err = run(
        capsys,
        "replace",
        examples_dir / "landing-page.json",
        "--find",
        "a",
        "--replace",
        "b",
        "--types",
        "nonsense",
        "--dry-run",
    )
    assert code == 2 and "no known text fields" in err


def test_diff_exit_codes(capsys, examples_dir):
    a, b = examples_dir / "landing-page.json", examples_dir / "landing-page-v2.json"
    code, out, _ = run(capsys, "diff", a, b)
    assert code == 1 and "2 added, 1 removed, 4 changed" in out
    assert run(capsys, "diff", a, a)[0] == 0


def test_diff_json(capsys, examples_dir):
    code, out, _ = run(
        capsys,
        "diff",
        examples_dir / "landing-page.json",
        examples_dir / "landing-page-v2.json",
        "--json",
    )
    assert code == 1 and len(json.loads(out)["added"]) == 2


def test_diff_ignore(capsys, examples_dir):
    _, out, _ = run(
        capsys,
        "diff",
        examples_dir / "landing-page.json",
        examples_dir / "landing-page-v2.json",
        "--ignore",
        "settings.padding",
    )
    assert "padding" not in out


def test_wp_meta_to_file_and_template(capsys, examples_dir, tmp_path):
    dest = tmp_path / "meta.json"
    code, out, err = run(
        capsys, "wp-meta", examples_dir / "landing-page.json", "--post-id", "42", "-o", dest
    )
    assert code == 0 and out == ""
    assert f"wp post meta update 42 _elementor_data < {dest}" in err
    assert dest.read_text().isascii() and "\\/" in dest.read_text()


def test_wp_meta_stdout_is_clean_json(capsys, examples_dir):
    code, out, err = run(capsys, "wp-meta", examples_dir / "container-meta.json", "--post-id", "9")
    assert code == 0 and json.loads(out)[0]["id"] == "9a1c3e5" and "wp post meta" in err


def test_wp_meta_refuses_invalid(capsys, examples_dir):
    code, out, err = run(capsys, "wp-meta", examples_dir / "broken.json", "--post-id", "1")
    assert code == 1 and out == "" and "refusing" in err


def test_wp_meta_force(capsys, examples_dir):
    assert run(capsys, "wp-meta", examples_dir / "broken.json", "--post-id", "1", "--force")[0] == 0


def test_fields_listing(capsys):
    _, out, _ = run(capsys, "fields")
    assert "heading" in out and "tabs.*.tab_title" in out


def test_missing_subcommand():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
