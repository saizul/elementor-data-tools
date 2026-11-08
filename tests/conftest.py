from __future__ import annotations

import copy
from pathlib import Path

import pytest

from eltools.document import Document, load

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def landing() -> Document:
    return load(EXAMPLES / "landing-page.json")


@pytest.fixture
def landing_v2() -> Document:
    return load(EXAMPLES / "landing-page-v2.json")


@pytest.fixture
def container_doc() -> Document:
    return load(EXAMPLES / "container-meta.json")


@pytest.fixture
def broken() -> Document:
    return load(EXAMPLES / "broken.json")


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


def widget(wid: str, wtype: str = "heading", **settings):
    return {
        "id": wid,
        "elType": "widget",
        "widgetType": wtype,
        "settings": settings,
        "elements": [],
    }


def simple_tree():
    return [
        {
            "id": "aaaaaaa",
            "elType": "section",
            "settings": {},
            "elements": [
                {
                    "id": "bbbbbbb",
                    "elType": "column",
                    "settings": {"_column_size": 100},
                    "elements": [
                        widget("ccccccc", "heading", title="Hello World"),
                        widget("ddddddd", "text-editor", editor="<p>Hello <b>there</b></p>"),
                        widget(
                            "eeeeeee", "button", text="Hello", link={"url": "https://x.test/hello"}
                        ),
                    ],
                }
            ],
        }
    ]


@pytest.fixture
def tree():
    return copy.deepcopy(simple_tree())
