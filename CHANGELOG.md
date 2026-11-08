# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
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
