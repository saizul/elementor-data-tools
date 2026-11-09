# elementor-data-tools

[![CI](https://github.com/saizul/elementor-data-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/saizul/elementor-data-tools/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

`eltools` is a command line tool and zero-dependency Python library for working with the
JSON that Elementor stores in WordPress (`_elementor_data`). Use it to read, validate,
bulk-edit and compare page designs from a terminal or a script, then write the result back
with WP-CLI safely.

```text
$ eltools widgets examples/landing-page.json
heading      5
text-editor  4
image        3
html         2
accordion    1
button       1
-----------  --
total        16
```

## What `_elementor_data` looks like

Every Elementor page keeps its design in the post meta key `_elementor_data`: one JSON
string holding a **list of top-level elements**. Each element is an object with the same
few keys:

| Key | Meaning |
| --- | --- |
| `id` | 7-character hex id, unique within the page |
| `elType` | `section`, `column`, `container` (flexbox layout) or `widget` |
| `widgetType` | only for widgets: `heading`, `text-editor`, `button`, `html`, `image`, ... |
| `settings` | the options chosen in the editor (text, colours, padding, links, ...) |
| `elements` | child elements |
| `isInner` | `true` for inner sections / containers nested inside another element |

The nesting rules:

```text
Legacy layout                          Flexbox layout (Elementor 3.6+)

section                                container
 └─ column                              ├─ widget
     ├─ widget                          └─ container (isInner: true)
     └─ section (isInner: true)             └─ widget
         └─ column
             └─ widget
```

A trimmed example (`examples/landing-page.json` has complete ones):

```json
[
  {
    "id": "4f1a9c2",
    "elType": "section",
    "settings": { "background_color": "#f6efe6" },
    "elements": [
      {
        "id": "7be03d1",
        "elType": "column",
        "settings": { "_column_size": 100 },
        "elements": [
          {
            "id": "1a7f3e9",
            "elType": "widget",
            "widgetType": "heading",
            "settings": { "title": "Coffee roasted for slow mornings", "header_size": "h1" },
            "elements": []
          }
        ]
      }
    ]
  }
]
```

Things worth knowing:

- **Three shapes of input.** The raw meta value (a JSON array); a *template export*
  from Elementor (`{"version": "0.4", "title": ..., "type": "page", "content": [...],
  "page_settings": {...}}`); and a JSON *string* that contains JSON (what you get when the
  value was double-encoded). `eltools` reads all three and writes back the same shape.
- **WordPress writes compact, escaped JSON.** `wp_json_encode` produces a single line where
  every `/` is `\/` and non-ASCII characters are `\uXXXX`. That is the `wp` output style
  here, and the files in `examples/` named `*-meta.json` use it.
- **Empty settings are `[]`, not `{}`.** PHP serializes an empty array as a list. Both are
  accepted by the validator and treated as equal by `diff`.
- **Repeater fields** (accordion, tabs, toggle, icon list) store a list of objects under
  `settings`, for example `settings.tabs[1].tab_content`.

## Install

```bash
pip install .            # Python 3.10+, no runtime dependencies
pip install -e ".[dev]"  # development: pytest + ruff
```

## Workflows

All commands accept a file path or `-` for stdin, so you can pipe straight from WP-CLI:

```bash
wp post meta get 123 _elementor_data | eltools validate -
```

### Inspect and validate

```bash
eltools pretty page.json                 # readable, indented (use --compact for one line)
eltools validate page.json               # exit 1 on structural errors; --strict fails on warnings
eltools tree page.json --max-depth 2     # paths, nesting and ids
eltools widgets page.json                # counts per widgetType
eltools widgets page.json --type html    # where every html widget lives
eltools find page.json --type button --setting 'link.url~/shop/'   # buttons linking to /shop/
eltools find page.json --setting header_size=h1 --json            # every element whose setting equals h1
```

`find` filters by `--type` and/or `--setting` (repeat `--setting`; all must match). A test is `PATH`
(set and non-empty), `PATH=VALUE` (exact, case-sensitive) or `PATH~TEXT` (contains, case-insensitive).
Paths are dotted and may index repeater lists, e.g. `link.url` or `tabs.0.tab_title`. It prints the index
path, id and values (or `--json` with JSON pointers) and exits 1 when nothing matches.

### Audit image alt text

```bash
eltools images page.json                 # every image: location, URL and alt text
eltools images page.json --missing-alt   # only images without alt text (exit 1 if any)
eltools images page.json --json          # machine readable, includes JSON pointers
```

`images` looks at Elementor media controls (image widget, image box, carousels, galleries, video
overlays ...), background images, and `<img>` tags inside any HTML text field. Background images are
decorative and never flagged. An `<img>` with `alt=""` is treated as intentionally decorative, while a
missing `alt` attribute is flagged. For media controls an empty stored alt is flagged; Elementor may
still use the alt text of the media library item at render time, which an export cannot show.

Validation catches: invalid or missing `elType`, widgets without `widgetType`, missing or
duplicate ids, wrong nesting (a widget directly in a section, a column in a column, a
top-level column), non-list `elements`, bad `settings`. Odd ids and a missing `elements`
list are warnings. Example (`examples/broken.json`):

```text
ERROR   E012 /0/elements/0/elements/0: widget is missing widgetType
ERROR   E015 /0/elements/0/elements/1: duplicate id 'ccccccc' (first used at /0/elements/0/elements/0)
ERROR   E022 /0/elements/1: a section can only contain columns (got widget)
ERROR   E021 /1: column cannot be a top-level element
4 error(s), 0 warning(s), 6 elements
```

Locations are JSON pointers into the content list (`/0/elements/1/elements/2` is the third
child of the second child of the first top-level element).

### Edit HTML widgets as real files

```bash
eltools extract page.json -d html/                    # html widgets -> html/<id>--html.html
$EDITOR html/c2d9a40--html.html
eltools insert page.json -d html/ -o page.edited.json # put them back
```

`extract` also takes `--types heading,text-editor,accordion` and `--field` for custom
paths; run `eltools fields` to see the text fields known for each widget type. Files are
written as UTF-8 with no newline translation, so an extract followed by an insert without
edits reproduces the original file byte for byte. An index (`eltools-extract.json`) records
each file's element id, JSON pointer and the hash of the original text. On `insert`, a
file is applied only if the export still has the text that was extracted, so someone
else's change is reported as a `CONFLICT` instead of being overwritten (`--force` to
override). `--dry-run` previews.

### Safe find/replace

```bash
eltools replace page.json --find "Shop the roastery" --replace "Shop now" \
    --types button --dry-run
```

```text
--- a/button#e84a0b7 text
+++ b/button#e84a0b7 text
@@ -1 +1 @@
-Shop the roastery
+Shop now

1 replacement(s) in 1 field(s) (dry run, nothing written)
```

The search only looks at the **text fields of the widget types you list** (`--types` is
required). Ids, keys, URLs, colours, dimensions and any other widget are never touched,
which is exactly what a global database search-replace cannot promise. Literal matching is
the default; add `--regex` (back-references work) and `-i` for case-insensitive. Write the
result with `-o FILE` or `--in-place` (which keeps `FILE.bak`).

### Compare two exports

```bash
eltools diff before.json after.json          # exit code 1 when they differ
eltools diff before.json after.json --json
eltools diff a.json b.json --ignore settings.custom_css
```

```text
+ added    button #fa05c13 at /1/elements/1/elements/3
+ added    section #d6a8e03 at /4 (+3 descendants)
- removed  heading #1bd7c05 at /1/elements/2/elements/1
~ changed  section #4f1a9c2 at /0
    ~ settings.padding.bottom: "120" -> "100"
    ~ settings.padding.top: "120" -> "100"
~ changed  heading #1a7f3e9 at /0/elements/0/elements/1
    ~ settings.title: "Coffee roasted for slow mornings" -> "Coffee roasted for slower mornings"
...
2 added, 1 removed, 4 changed, 0 moved
```

Elements are matched by `id`, not position, so inserting a widget does not make every
sibling look changed. The report lists added and removed subtrees once (with a descendant
count), setting-level changes with dotted paths (`settings.tabs.1.tab_content`), elements
that moved to a different parent, and parents whose children were reordered.

### Write back with WP-CLI

```bash
eltools wp-meta page.json --post-id 123 -o elementor_data.wp.json
```

This writes single-line, ASCII-only JSON with `\/` slashes and no trailing newline (the
same form WordPress stores; template exports are unwrapped to just the element list) and
prints a command recipe to stderr:

```bash
# 1. Back up the current value
wp post meta get 123 _elementor_data > elementor_data.backup.json

# 2. Write the new value (read from STDIN: no shell argument size limit)
wp post meta update 123 _elementor_data < elementor_data.wp.json

# 3. Regenerate Elementor CSS and flush caches
wp elementor flush-css
wp cache flush

# 4. Verify the stored value is valid and matches
wp post meta get 123 _elementor_data | eltools validate -
```

`wp-meta` refuses to emit data that fails validation unless you pass `--force`, and checks
that the encoded text parses back to identical data. Use `--wp-path` / `--url` to add
`--path=` / `--url=`. Try changes on a staging copy first and keep the backup from step 1.

## Library use

```python
from eltools import load, validate, widget_counts, replace_text, diff_documents, to_wp_meta

doc = load("page.json")
assert not [i for i in validate(doc.elements) if i.level == "error"]
print(widget_counts(doc.elements).most_common(3))

changes = replace_text(doc.elements, "2023", "2024", ("heading", "text-editor"))
doc_json = to_wp_meta(doc)  # ready for wp post meta update
```

## Examples

| File | Shape |
| --- | --- |
| `examples/landing-page.json` | template export, section/column layout, accordion repeater, 2 HTML widgets |
| `examples/landing-page-v2.json` | edited copy of the above for trying `diff` |
| `examples/container-meta.json` | raw `_elementor_data` in WordPress style, flexbox containers, unicode |
| `examples/broken.json` | deliberately invalid, for `validate` |

All sample content is synthetic (a made-up coffee roaster on `example.com`).

## Development

```bash
pip install -e ".[dev]"
ruff check . && pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md).

## Disclaimer

Not affiliated with Elementor Ltd. The format described here is based on observed exports
and may change between Elementor versions; always validate and keep backups.

## License

MIT. Copyright (c) 2026 Saizul Amin - [saizul.com](https://saizul.com)
