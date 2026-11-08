from __future__ import annotations

import json

import pytest

from eltools.document import loads
from eltools.extract import INDEX_NAME, extract_fields, insert_fields, sha256
from eltools.tree import walk


def html_values(doc):
    return {
        n.id: n.element["settings"]["html"] for n in walk(doc.elements) if n.widget_type == "html"
    }


def test_extract_html_widgets(landing, tmp_path):
    entries = extract_fields(landing.elements, tmp_path)
    assert sorted(e.id for e in entries) == ["b7d40e2", "c2d9a40"]
    for e in entries:
        assert (tmp_path / e.file).is_file() and e.file.endswith(".html")
    assert (tmp_path / INDEX_NAME).is_file()


def test_extracted_content_matches_exactly(landing, tmp_path):
    extract_fields(landing.elements, tmp_path)
    for wid, value in html_values(landing).items():
        assert (tmp_path / f"{wid}--html.html").read_bytes() == value.encode("utf-8")


def test_roundtrip_without_edits_changes_nothing(landing, tmp_path):
    before = landing.dumps()
    extract_fields(landing.elements, tmp_path)
    report = insert_fields(landing.elements, tmp_path)
    assert report.ok and report.updated == []
    assert len(report.unchanged) == 2
    assert landing.dumps() == before


def test_edit_and_insert(landing, tmp_path):
    extract_fields(landing.elements, tmp_path)
    target = tmp_path / "b7d40e2--html.html"
    target.write_text(target.read_text().replace("Subscribe", "Join"), encoding="utf-8")
    report = insert_fields(landing.elements, tmp_path)
    assert report.updated == ["b7d40e2--html.html"] and report.ok
    assert "Join</button>" in html_values(landing)["b7d40e2"]


def test_other_content_untouched_after_insert(landing, tmp_path):
    original = landing.copy()
    extract_fields(landing.elements, tmp_path)
    (tmp_path / "c2d9a40--html.html").write_text("<p>new</p>", encoding="utf-8")
    insert_fields(landing.elements, tmp_path)
    after = loads(landing.dumps())
    assert html_values(after)["b7d40e2"] == html_values(original)["b7d40e2"]
    assert after.elements[1:] == original.elements[1:]


def test_crlf_and_trailing_whitespace_survive(tmp_path):
    value = "<p>line1</p>\r\n<p>line2</p>\r\n\r\n  "
    data = [
        {
            "id": "aaaaaaa",
            "elType": "container",
            "settings": {},
            "elements": [
                {
                    "id": "bbbbbbb",
                    "elType": "widget",
                    "widgetType": "html",
                    "settings": {"html": value},
                    "elements": [],
                }
            ],
        }
    ]
    extract_fields(data, tmp_path)
    assert (tmp_path / "bbbbbbb--html.html").read_bytes() == value.encode()
    assert insert_fields(data, tmp_path).unchanged == ["bbbbbbb--html.html"]
    assert data[0]["elements"][0]["settings"]["html"] == value


def test_unicode_roundtrip(container_doc, tmp_path):
    extract_fields(container_doc.elements, tmp_path, ("heading",))
    f = tmp_path / "2b4d6f8--title.txt"
    assert f.read_text(encoding="utf-8") == "Café menu — spring 2024"
    f.write_text("Café menu — summer 2024", encoding="utf-8")
    insert_fields(container_doc.elements, tmp_path)
    assert "summer" in container_doc.dumps() and "\\u00e9" in container_doc.dumps()


def test_extract_repeater_fields(landing, tmp_path):
    entries = extract_fields(landing.elements, tmp_path, ("accordion",))
    assert len(entries) == 6
    assert (tmp_path / "4c1e7a9--tabs-1-tab_content.html").is_file()
    assert (tmp_path / "4c1e7a9--tabs-1-tab_title.txt").is_file()


def test_insert_repeater_edit(landing, tmp_path):
    extract_fields(landing.elements, tmp_path, ("accordion",))
    (tmp_path / "4c1e7a9--tabs-0-tab_title.txt").write_text("Is it fresh?", encoding="utf-8")
    insert_fields(landing.elements, tmp_path)
    acc = [n for n in walk(landing.elements) if n.widget_type == "accordion"][0]
    assert acc.element["settings"]["tabs"][0]["tab_title"] == "Is it fresh?"


def test_dry_run_does_not_modify(landing, tmp_path):
    extract_fields(landing.elements, tmp_path)
    (tmp_path / "c2d9a40--html.html").write_text("changed", encoding="utf-8")
    before = landing.dumps()
    report = insert_fields(landing.elements, tmp_path, dry_run=True)
    assert report.updated == ["c2d9a40--html.html"]
    assert landing.dumps() == before


def test_conflict_when_export_changed_since_extract(landing, tmp_path):
    extract_fields(landing.elements, tmp_path)
    (tmp_path / "c2d9a40--html.html").write_text("my edit", encoding="utf-8")
    landing.elements[0]["elements"][0]["elements"][0]["settings"]["html"] = "someone else's edit"
    report = insert_fields(landing.elements, tmp_path)
    assert report.conflicts and not report.ok
    assert html_values(landing)["c2d9a40"] == "someone else's edit"


def test_force_overrides_conflict(landing, tmp_path):
    extract_fields(landing.elements, tmp_path)
    (tmp_path / "c2d9a40--html.html").write_text("my edit", encoding="utf-8")
    landing.elements[0]["elements"][0]["elements"][0]["settings"]["html"] = "other"
    report = insert_fields(landing.elements, tmp_path, force=True)
    assert report.ok and html_values(landing)["c2d9a40"] == "my edit"


def test_missing_element_reported(landing, tmp_path):
    extract_fields(landing.elements, tmp_path)
    del landing.elements[3]
    report = insert_fields(landing.elements, tmp_path)
    assert any("b7d40e2" in m for m in report.missing) and not report.ok


def test_missing_file_reported(landing, tmp_path):
    extract_fields(landing.elements, tmp_path)
    (tmp_path / "c2d9a40--html.html").unlink()
    assert any("file not found" in m for m in insert_fields(landing.elements, tmp_path).missing)


def test_missing_index(tmp_path):
    with pytest.raises(ValueError, match="extract index"):
        insert_fields([], tmp_path)


def test_index_contents(landing, tmp_path):
    extract_fields(landing.elements, tmp_path)
    index = json.loads((tmp_path / INDEX_NAME).read_text())
    entry = [f for f in index["files"] if f["id"] == "c2d9a40"][0]
    assert entry["sha256"] == sha256(html_values(landing)["c2d9a40"])
    assert entry["pointer"] == "/0/elements/0/elements/0"


def test_extract_creates_directory(landing, tmp_path):
    out = tmp_path / "a" / "b"
    extract_fields(landing.elements, out)
    assert out.is_dir()


def test_widget_type_without_known_fields_raises(landing, tmp_path):
    # a type that exists in the page but has no registered text fields
    landing.elements[0]["elements"][0]["elements"].append(
        {
            "id": "9f9f9f9",
            "elType": "widget",
            "widgetType": "google_maps",
            "settings": {},
            "elements": [],
        }
    )
    with pytest.raises(ValueError):
        extract_fields(landing.elements, tmp_path, ("google_maps",))


def test_widget_types_not_present_extract_nothing(landing, tmp_path):
    assert extract_fields(landing.elements, tmp_path, ("alert",)) == []
