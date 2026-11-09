from __future__ import annotations

import json

from conftest import widget
from eltools.cli import main
from eltools.images import find_images, html_images


def run(capsys, *argv):
    code = main([str(a) for a in argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def _page():
    return [
        {
            "id": "sec0001",
            "elType": "section",
            "settings": {
                "background_image": {"url": "https://x.test/bg.jpg", "id": 9, "source": "library"}
            },
            "elements": [
                {
                    "id": "col0001",
                    "elType": "column",
                    "settings": {},
                    "elements": [
                        widget(
                            "img0001",
                            "image",
                            image={"url": "https://x.test/a.jpg", "id": 1, "alt": "Beans"},
                        ),
                        widget(
                            "img0002",
                            "image",
                            image={"url": "https://x.test/b.jpg", "id": 2, "alt": ""},
                        ),
                        widget(
                            "car0001",
                            "image-carousel",
                            carousel=[
                                {"id": 3, "url": "https://x.test/c.jpg"},
                                {"id": 4, "url": "https://x.test/d.jpg"},
                            ],
                        ),
                        widget(
                            "txt0001",
                            "text-editor",
                            editor='<p>Hi</p><img src="/e.jpg" alt="Roaster"><img src="/f.jpg">'
                            '<IMG SRC="/g.jpg" ALT="" />',
                        ),
                        widget(
                            "btn0001",
                            "button",
                            text="Shop",
                            link={"url": "https://x.test/shop/", "is_external": ""},
                        ),
                    ],
                }
            ],
        }
    ]


def test_html_images_reports_missing_and_empty_alt():
    found = html_images('<img src="a.png" alt="A"><img src="b.png"><img src="c.png" alt="">')
    assert found == [("a.png", "A"), ("b.png", None), ("c.png", "")]
    assert html_images("<p>no pictures</p>") == []


def test_find_images_collects_all_sources_in_document_order():
    refs = find_images(_page())
    summary = [(r.node.id, r.field, r.kind, r.url) for r in refs]
    assert summary == [
        ("sec0001", "background_image", "background", "https://x.test/bg.jpg"),
        ("img0001", "image", "image", "https://x.test/a.jpg"),
        ("img0002", "image", "image", "https://x.test/b.jpg"),
        ("car0001", "carousel.0", "image", "https://x.test/c.jpg"),
        ("car0001", "carousel.1", "image", "https://x.test/d.jpg"),
        ("txt0001", "editor", "html", "/e.jpg"),
        ("txt0001", "editor", "html", "/f.jpg"),
        ("txt0001", "editor", "html", "/g.jpg"),
    ]


def test_link_controls_are_not_images():
    assert all(r.node.id != "btn0001" for r in find_images(_page()))


def test_missing_alt_rules():
    missing = {(r.node.id, r.url) for r in find_images(_page()) if r.missing_alt}
    assert missing == {
        ("img0002", "https://x.test/b.jpg"),  # control with empty alt
        ("car0001", "https://x.test/c.jpg"),  # control without alt
        ("car0001", "https://x.test/d.jpg"),
        ("txt0001", "/f.jpg"),  # <img> without alt attribute
    }  # background and explicit alt="" on <img> are fine


def test_malformed_settings_are_ignored():
    assert find_images([{"id": "a", "elType": "widget", "settings": []}, "junk"]) == []


def test_cli_lists_images(capsys, examples_dir):
    code, out, err = run(capsys, "images", examples_dir / "landing-page.json")
    assert code == 0
    assert out.count("\n") == 3 and 'alt="Ethiopia Guji beans"' in out
    assert "3 image(s), 0 without alt text" in err


def test_cli_missing_alt_exit_code_and_json(capsys, tmp_path):
    path = tmp_path / "page.json"
    path.write_text(json.dumps(_page()), encoding="utf-8")
    code, out, err = run(capsys, "images", path, "--missing-alt", "--json")
    rows = json.loads(out)
    assert code == 1
    assert [r["url"] for r in rows] == [
        "https://x.test/b.jpg",
        "https://x.test/c.jpg",
        "https://x.test/d.jpg",
        "/f.jpg",
    ]
    assert rows[0]["missing_alt"] is True and rows[0]["attachment_id"] == 2
    assert rows[3]["alt"] is None and rows[3]["kind"] == "html"


def test_cli_missing_alt_clean_page_exits_zero(capsys, examples_dir):
    code, out, _ = run(capsys, "images", examples_dir / "landing-page.json", "--missing-alt")
    assert code == 0 and out == ""


def test_cli_text_output_flags_missing_and_background(capsys, tmp_path):
    path = tmp_path / "page.json"
    path.write_text(json.dumps(_page()), encoding="utf-8")
    code, out, err = run(capsys, "images", path)
    assert code == 0
    assert "(background)" in out and "alt=MISSING" in out
    assert "8 image(s), 4 without alt text" in err
