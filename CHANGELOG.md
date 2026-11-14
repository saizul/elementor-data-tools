# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `reid` command: give fresh, unique 7-hex-digit ids to duplicated (later copies only), missing and malformed element ids, to ids also used in `--avoid FILE` exports, or to every element with `--all`. `elementor-element-<id>` references in settings are rewritten to match (whole document for unique ids, only inside the renamed copy for duplicates; `--no-references` to skip). `--dry-run`/`--check` (exit 1 when changes are needed) preview the plan, `--map FILE` saves the old/new list, `--seed` makes output reproducible. Also available as `reassign_ids()` in the library.
- `links` command: list every link (Elementor link controls and `<a href>` tags inside HTML) with its type, new-tab/nofollow flags and anchor text; flags buttons without a link, `#` placeholders, `http://` URLs, URLs missing a scheme, stray whitespace and hosts given with `--forbid-host` (staging or old domains). `--check` shows only flagged links and exits 1 when there are any; `--site` separates internal from external links; `--hosts` prints a per-host count.
- `images` command: list every image (media controls, background images and `<img>` tags inside HTML) with URL and alt text; `--missing-alt` shows only images without alt text and exits 1 when there are any, for audits and CI.
- `find` command: locate elements by `--type` and `--setting` tests (`PATH`, `PATH=VALUE`, `PATH~TEXT`, dotted paths into repeaters).

## [1.0.0] - 2026-11-08

### Added
- Loading of raw `_elementor_data`, Elementor template exports and double-encoded JSON strings,
  with output in `pretty`, `compact` or WordPress (`wp`) style.
- `pretty`, `validate`, `tree` and `widgets` commands with JSON pointers and widget counts.
- `extract` / `insert` for text fields of chosen widgets, with hash-based conflict detection.
- `replace`: find/replace limited to text fields of selected widget types, with dry-run diff.
- `diff`: element-level comparison by id (added, removed, changed settings, moved, reordered).
- `wp-meta`: ASCII-escaped, slash-escaped JSON and a WP-CLI command template.
- Synthetic example exports in `examples/`.
