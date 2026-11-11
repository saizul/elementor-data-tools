from __future__ import annotations

import json

import pytest

from conftest import widget
from eltools import LinkRef, find_links
from eltools.cli import main
from eltools.links import (
    classify,
    host_counts,
    host_matches,
    html_links,
    link_issues,
    normalize_host,
    url_host,
)
from eltools.tree import Node


def run(capsys, *argv):
    code = main([str(a) for a in argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def link(url, external="", nofollow=""):
    return {"url": url, "is_external": external, "nofollow": nofollow, "custom_attributes": ""}


def _page():
    html = (
        '<p><a href="https://shop.test/about/">About <b>us</b></a> and '
        '<a href="http://partner.example.org/" target="_blank" rel="noopener nofollow">partner</a> '
        '<a href="#">soon</a> <a name="top">no href</a> '
        '<a href="mailto:hello@shop.test">mail</a></p>'
    )
    return [
        {
            "id": "sec0001",
            "elType": "section",
            "settings": {
                "background_image": {"url": "https://shop.test/bg.jpg", "id": 9},
                "link": link(""),
            },
            "elements": [
                {
                    "id": "col0001",
                    "elType": "column",
                    "settings": [],
                    "elements": [
                        widget(
                            "btn0001", "button", text="Shop", link=link("https://shop.test/shop/")
                        ),
                        widget("btn0002", "button", text="Later", link=link("")),
                        widget(
                            "btn0003",
                            "button",
                            link=link("https://staging.shop.test/cart/", "on", "on"),
                        ),
                        widget("hed0001", "heading", title="Hi", link=link("")),
                        widget(
                            "img0001",
                            "image",
                            image={"url": "https://shop.test/a.jpg", "id": 1, "alt": "A"},
                            link=link("#pricing"),
                        ),
                        widget("txt0001", "text-editor", editor=html),
                        widget(
                            "ico0001",
                            "icon-list",
                            icon_list=[
                                {"text": "Call", "link": link("tel:+10000000000")},
                                {"text": "Docs", "link": link("/docs/")},
                                {"text": "None", "link": link("")},
                                {"text": "Bad", "link": link("www.shop.test/x")},
                            ],
                        ),
                    ],
                }
            ],
        },
        "junk",
    ]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://WWW.Example.com/x?y=1", "example.com"),
        ("Example.com:8443", "example.com"),
        ("www.example.com/path//deep", "example.com"),
        ("//cdn.example.com/a.js", "cdn.example.com"),
        ("https://user@example.com/", "example.com"),
        ("  ", ""),
    ],
)
def test_normalize_host(value, expected):
    assert normalize_host(value) == expected


def test_url_host():
    assert url_host(" HTTPS://Shop.Test:8443/a ") == "shop.test"
    assert url_host("//cdn.shop.test/x") == "cdn.shop.test"
    assert url_host("/relative/") == "" and url_host("mailto:a@shop.test") == ""
    assert url_host("https://[broken") == ""


def test_host_matches_exact_and_subdomains():
    assert host_matches("staging.shop.test", "shop.test")
    assert host_matches("www.shop.test", "https://shop.test/")
    assert host_matches("shop.test", "www.shop.test")
    assert not host_matches("notshop.test", "shop.test")
    assert not host_matches("shop.test", "staging.shop.test")
    assert not host_matches("", "shop.test") and not host_matches("shop.test", "")


@pytest.mark.parametrize(
    "url,site,expected",
    [
        ("", None, "other"),
        ("#", None, "other"),
        ("javascript:void(0)", None, "other"),
        ("#pricing", None, "anchor"),
        ("mailto:hello@shop.test", None, "mailto"),
        ("TEL:+10000000000", None, "tel"),
        ("https://shop.test/a", None, "absolute"),
        ("https://www.shop.test/a", "shop.test", "internal"),
        ("//shop.test/a", "https://www.shop.test", "internal"),
        ("https://blog.shop.test/a", "shop.test", "external"),
        ("http://other.test/", "shop.test", "external"),
        ("/shop/", "shop.test", "relative"),
        ("shop/item?x=a:b", None, "relative"),
        ("www.shop.test/x", None, "relative"),
        ("sms:+10000000000", None, "other"),
        ("  /padded/ ", None, "relative"),
    ],
)
def test_classify(url, site, expected):
    assert classify(url, site) == expected


def _ref(url, kind="control"):
    return LinkRef(Node({"id": "x"}, (0,)), "link", kind, url)


@pytest.mark.parametrize(
    "url,kind,expected",
    [
        ("https://shop.test/", "control", []),
        ("/shop/", "control", []),
        ("#pricing", "control", []),
        ("mailto:hello@shop.test?subject=Hi there", "html", []),
        ("", "control", ["empty"]),
        ("  ", "html", ["placeholder"]),
        ("#", "html", ["placeholder"]),
        ("JavaScript:void(0);", "control", ["placeholder"]),
        ("http://shop.test/", "control", ["insecure"]),
        ("www.shop.test/x", "control", ["no-scheme"]),
        ("www", "control", []),
        (" https://shop.test/ ", "control", ["whitespace"]),
        ("https://shop.test/a b", "control", ["whitespace"]),
        ("http://old.test/ x", "control", ["forbidden-host", "insecure", "whitespace"]),
        ("https://sub.old.test/", "control", ["forbidden-host"]),
        ("https://bold.test/", "control", []),
    ],
)
def test_link_issues(url, kind, expected):
    assert link_issues(_ref(url, kind), ["old.test"]) == expected


def test_html_links_attributes_and_text():
    links = html_links(
        '<A HREF="/a" TARGET="_BLANK" REL="NoFollow sponsored">One\n  <em>two</em></A>'
        '<a href="/img"><img src="x.png" alt="Logo"/></a>'
        "<a>plain</a><a href>empty</a><a href='/open'>never closed"
    )
    assert links == [
        {"href": "/a", "text": "One two", "new_tab": True, "nofollow": True},
        {"href": "/img", "text": "Logo", "new_tab": False, "nofollow": False},
        {"href": "", "text": "empty", "new_tab": False, "nofollow": False},
        {"href": "/open", "text": "never closed", "new_tab": False, "nofollow": False},
    ]
    assert html_links("<p>no links, just an <abbr>abbr</abbr> and <article>x</article></p>") == []
    assert html_links("plain text") == []


def test_html_links_nested_anchor_starts_a_new_link():
    links = html_links('<a href="/one">one <a href="/two">two</a>')
    assert [(link_["href"], link_["text"]) for link_ in links] == [("/one", "one"), ("/two", "two")]


def test_find_links_document_order_and_fields():
    refs = find_links(_page(), site="shop.test", forbid_hosts=["staging.shop.test"])
    assert [(r.node.id, r.field, r.url) for r in refs] == [
        ("btn0001", "link", "https://shop.test/shop/"),
        ("btn0002", "link", ""),
        ("btn0003", "link", "https://staging.shop.test/cart/"),
        ("img0001", "link", "#pricing"),
        ("txt0001", "editor", "https://shop.test/about/"),
        ("txt0001", "editor", "http://partner.example.org/"),
        ("txt0001", "editor", "#"),
        ("txt0001", "editor", "mailto:hello@shop.test"),
        ("ico0001", "icon_list.0.link", "tel:+10000000000"),
        ("ico0001", "icon_list.1.link", "/docs/"),
        ("ico0001", "icon_list.3.link", "www.shop.test/x"),
    ]
    by_url = {r.url: r for r in refs}
    assert by_url["https://shop.test/shop/"].type == "internal"
    assert by_url["https://shop.test/shop/"].issues == []
    assert by_url[""].issues == ["empty"] and by_url[""].type == "other"
    staging = by_url["https://staging.shop.test/cart/"]
    assert staging.type == "external" and staging.issues == ["forbidden-host"]
    assert staging.new_tab and staging.nofollow and staging.host == "staging.shop.test"
    partner = by_url["http://partner.example.org/"]
    assert partner.kind == "html" and partner.text == "partner"
    assert partner.new_tab and partner.nofollow and partner.issues == ["insecure"]
    assert by_url["https://shop.test/about/"].text == "About us"
    assert by_url["#"].issues == ["placeholder"]
    assert by_url["#pricing"].type == "anchor" and by_url["#pricing"].kind == "control"
    assert by_url["www.shop.test/x"].issues == ["no-scheme"]
    assert by_url["/docs/"].type == "relative" and by_url["/docs/"].text is None


def test_find_links_skips_media_and_optional_empty_controls():
    urls = [r.url for r in find_links(_page())]
    assert "https://shop.test/bg.jpg" not in urls and "https://shop.test/a.jpg" not in urls
    ids = [r.node.id for r in find_links(_page())]
    assert "hed0001" not in ids and "sec0001" not in ids  # empty optional link controls


def test_find_links_without_site_uses_absolute_type():
    refs = find_links(_page())
    assert {r.type for r in refs if r.host} == {"absolute"}
    assert all("forbidden-host" not in r.issues for r in refs)


def test_dynamic_link_is_not_reported_as_empty():
    button = widget("btn0009", "button", link=link(""))
    button["settings"]["__dynamic__"] = {"link": '[elementor-tag id="1" name="post-url"]'}
    other = widget("btn0010", "button", link=link(""))
    other["settings"]["__dynamic__"] = {"text": '[elementor-tag id="2" name="post-title"]'}
    refs = find_links([button, other])
    assert [(r.node.id, r.issues) for r in refs] == [("btn0010", ["empty"])]


def test_dynamic_definitions_are_not_scanned_for_html():
    w = widget("txt0009", "text-editor", editor="<p>x</p>")
    w["settings"]["__dynamic__"] = {"editor": '<a href="/from-tag">tag</a>'}
    assert find_links([w]) == []


def test_empty_secondary_link_on_button_is_ignored():
    w = widget("btn0011", "button", link=link("/go/"), other_link=link(""))
    assert [r.field for r in find_links([w])] == ["link"]


def test_malformed_settings_are_ignored():
    assert find_links([{"id": "a", "elType": "widget", "settings": []}, "junk"]) == []
    assert find_links(None) == []
    odd = widget("odd0001", "button", link={"url": 5}, text=None)
    assert find_links([odd]) == []


def test_host_counts():
    counts = host_counts(find_links(_page()))
    assert counts == {"shop.test": 2, "staging.shop.test": 1, "partner.example.org": 1}
    assert counts.most_common(1)[0] == ("shop.test", 2)


def test_examples_have_clean_links(landing, container_doc):
    refs = find_links(landing.elements, site="demo.example.com")
    assert [r.url for r in refs] == [
        "https://demo.example.com/shop/",
        "https://demo.example.com/shipping/",
    ]
    assert all(r.type == "internal" and not r.issues for r in refs)
    assert all(not r.issues for r in find_links(container_doc.elements))


def _write(tmp_path):
    path = tmp_path / "page.json"
    path.write_text(json.dumps(_page()), encoding="utf-8")
    return path


def test_cli_lists_links(capsys, tmp_path):
    code, out, err = run(capsys, "links", _write(tmp_path), "--site", "shop.test")
    assert code == 0
    lines = out.splitlines()
    assert len(lines) == 11
    assert lines[0].split() == [
        "0/0/0",
        "button",
        "#btn0001",
        "link",
        "https://shop.test/shop/",
        "[internal]",
    ]
    assert "(no url)  [other]  EMPTY" in lines[1]
    assert "[external new-tab nofollow]  INSECURE" in out
    assert "[anchor]" in out and "[mailto]" in out and "[tel]" in out
    assert "www.shop.test/x  [relative]  NO-SCHEME" in out
    assert "11 link(s), 4 with issues" in err


def test_cli_check_exit_code_and_json(capsys, tmp_path):
    code, out, err = run(
        capsys, "links", _write(tmp_path), "--check", "--json", "--forbid-host", "staging.shop.test"
    )
    rows = json.loads(out)
    assert code == 1
    assert [(r["id"], r["issues"]) for r in rows] == [
        ("btn0002", ["empty"]),
        ("btn0003", ["forbidden-host"]),
        ("txt0001", ["insecure"]),
        ("txt0001", ["placeholder"]),
        ("ico0001", ["no-scheme"]),
    ]
    first = rows[1]
    assert first["pointer"] == "/0/elements/0/elements/2" and first["path"] == "0/0/2"
    assert first["widget"] == "button" and first["kind"] == "control" and first["text"] is None
    assert first["host"] == "staging.shop.test" and first["type"] == "absolute"
    assert first["new_tab"] is True and first["nofollow"] is True
    assert rows[2]["text"] == "partner" and rows[2]["kind"] == "html"
    assert "11 link(s), 5 with issues" in err


def test_cli_check_clean_page_exits_zero(capsys, examples_dir):
    code, out, err = run(capsys, "links", examples_dir / "landing-page.json", "--check")
    assert code == 0 and out == ""
    assert "2 link(s), 0 with issues" in err


def test_cli_forbid_host_makes_clean_page_fail(capsys, examples_dir):
    code, out, _ = run(
        capsys,
        "links",
        examples_dir / "landing-page.json",
        "--check",
        "--forbid-host",
        "example.com",
    )
    assert code == 1 and out.count("FORBIDDEN-HOST") == 2


def test_cli_type_filter(capsys, tmp_path):
    path = _write(tmp_path)
    code, out, _ = run(capsys, "links", path, "--site", "www.shop.test", "--type", "external")
    assert code == 0
    assert [line.split()[4] for line in out.splitlines()] == [
        "https://staging.shop.test/cart/",
        "http://partner.example.org/",
    ]
    code, out, _ = run(capsys, "links", path, "--type", "anchor", "--json")
    assert [r["url"] for r in json.loads(out)] == ["#pricing"]


def test_cli_type_internal_requires_site(capsys, tmp_path):
    code, out, err = run(capsys, "links", _write(tmp_path), "--type", "internal")
    assert code == 2 and out == "" and "--site" in err


def test_cli_hosts_summary(capsys, tmp_path):
    path = _write(tmp_path)
    code, out, err = run(capsys, "links", path, "--hosts")
    assert code == 0
    assert [line.split() for line in out.splitlines()] == [
        ["shop.test", "2"],
        ["staging.shop.test", "1"],
        ["partner.example.org", "1"],
    ]
    code, out, _ = run(capsys, "links", path, "--hosts", "--json", "--check")
    assert code == 1 and json.loads(out) == {"partner.example.org": 1}


def test_cli_reads_stdin(capsys, monkeypatch, tmp_path):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_page())))
    code, out, _ = run(capsys, "links", "-", "--type", "tel")
    assert code == 0 and "tel:+10000000000" in out
