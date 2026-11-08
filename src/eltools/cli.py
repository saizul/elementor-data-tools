"""``eltools`` command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from eltools import __version__
from eltools.diff import DiffResult, diff_documents
from eltools.document import STYLES, Document, ElementorDataError, dumps, loads
from eltools.extract import extract_fields, insert_fields
from eltools.fields import TEXT_FIELDS
from eltools.find import find_elements, parse_condition
from eltools.replace import replace_text
from eltools.tree import element_counts, max_depth, walk, widget_counts
from eltools.validate import errors_only, validate
from eltools.wpmeta import command_template, to_wp_meta


def _read_doc(arg: str) -> Document:
    if arg == "-":
        return loads(sys.stdin.read(), source="<stdin>")
    path = Path(arg)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ElementorDataError(f"cannot read {path}: {exc.strerror}") from exc
    except UnicodeDecodeError as exc:
        raise ElementorDataError(f"{path}: not valid UTF-8") from exc
    return loads(text, source=str(path))


def _write_file(path: str | Path, text: str) -> None:
    """Write UTF-8 without newline translation (identical bytes on every platform)."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _write_text(text: str, dest: str | None, newline: bool = True) -> None:
    if newline and not text.endswith("\n"):
        text += "\n"
    if dest in (None, "-"):
        sys.stdout.write(text)
    else:
        _write_file(dest, text)


def _csv(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(",") if v.strip())


def _save(doc: Document, args: argparse.Namespace) -> None:
    """Write an edited document to -o / --in-place (with a .bak copy)."""
    style = None if args.format == "auto" else args.format
    text = doc.dumps(style)
    keep_newline = (style or doc.style) != "wp"
    if args.in_place:
        src = Path(args.input)
        if args.input == "-":
            raise ElementorDataError("--in-place needs a file, not stdin")
        if not args.no_backup:
            Path(str(src) + ".bak").write_bytes(src.read_bytes())
        _write_text(text, str(src), keep_newline)
    else:
        _write_text(text, args.output, keep_newline)


def _add_output_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("-o", "--output", help="write result here (default: stdout)")
    p.add_argument("--in-place", action="store_true", help="overwrite INPUT (keeps INPUT.bak)")
    p.add_argument("--no-backup", action="store_true", help="with --in-place, skip the .bak copy")
    p.add_argument("--format", choices=["auto", *STYLES], default="auto", help="output style")


def cmd_pretty(args: argparse.Namespace) -> int:
    doc = _read_doc(args.input)
    if args.compact:
        text = dumps(doc.to_data(), "compact")
    else:
        text = dumps(doc.to_data(), "pretty", indent=args.indent)
    _write_text(text, args.output)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    doc = _read_doc(args.input)
    issues = validate(doc.elements)
    for issue in issues:
        print(issue)
    errs = errors_only(issues)
    warns = len(issues) - len(errs)
    print(
        f"{len(errs)} error(s), {warns} warning(s), {sum(1 for _ in walk(doc.elements))} elements"
    )
    return 1 if errs or (args.strict and warns) else 0


def cmd_tree(args: argparse.Namespace) -> int:
    doc = _read_doc(args.input)
    rows: list[dict[str, Any]] = []
    for node in walk(doc.elements):
        if args.max_depth is not None and node.depth > args.max_depth:
            continue
        rows.append(
            {
                "path": node.path_str,
                "pointer": node.pointer,
                "depth": node.depth,
                "elType": node.el_type,
                "kind": node.kind,
                "id": node.id,
            }
        )
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    for row in rows:
        indent = "  " * row["depth"]
        label = row["kind"] if row["elType"] == "widget" else row["elType"]
        print(f"{row['path']:<12} {indent}{label} #{row['id']}")
    return 0


def cmd_widgets(args: argparse.Namespace) -> int:
    doc = _read_doc(args.input)
    if args.type:
        nodes = [
            n for n in walk(doc.elements) if n.el_type == "widget" and n.widget_type == args.type
        ]
        if args.json:
            print(
                json.dumps(
                    [{"id": n.id, "pointer": n.pointer, "trail": n.trail} for n in nodes], indent=2
                )
            )
        else:
            for n in nodes:
                print(f"{n.path_str:<12} #{n.id}  {n.trail}")
        return 0 if nodes else 1
    counts = widget_counts(doc.elements)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if args.json:
        print(
            json.dumps(
                {
                    "elements": dict(element_counts(doc.elements)),
                    "widgets": dict(ranked),
                    "max_depth": max_depth(doc.elements),
                },
                indent=2,
            )
        )
        return 0
    width = max((len(k) for k, _ in ranked), default=6)
    for name, count in ranked:
        print(f"{name:<{width}}  {count}")
    print(f"{'-' * width}  --")
    print(f"{'total':<{width}}  {sum(counts.values())}")
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    doc = _read_doc(args.input)
    conditions = [parse_condition(spec) for spec in args.setting]
    if not args.type and not conditions:
        raise ElementorDataError("give --type and/or at least one --setting")
    hits = find_elements(doc.elements, args.type, conditions)
    if args.json:
        rows = [
            {
                "path": h.node.path_str,
                "pointer": h.node.pointer,
                "id": h.node.id,
                "kind": h.node.kind,
                "trail": h.node.trail,
                "settings": h.values,
            }
            for h in hits
        ]
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        for h in hits:
            shown = "  ".join(f"{k}={_short(v, 50)}" for k, v in h.values.items())
            print(f"{h.node.path_str:<12} {h.node.kind} #{h.node.id}  {shown}".rstrip())
        print(f"{len(hits)} match(es)", file=sys.stderr)
    return 0 if hits else 1


def cmd_extract(args: argparse.Namespace) -> int:
    doc = _read_doc(args.input)
    entries = extract_fields(
        doc.elements, Path(args.dir), _csv(args.types), list(_csv(args.field)) or None
    )
    for e in entries:
        print(f"{e.file}  ({e.widget_type} {e.field})")
    print(f"extracted {len(entries)} field(s) to {args.dir}", file=sys.stderr)
    return 0 if entries else 1


def cmd_insert(args: argparse.Namespace) -> int:
    doc = _read_doc(args.input)
    report = insert_fields(doc.elements, Path(args.dir), force=args.force, dry_run=args.dry_run)
    for name in report.updated:
        print(f"{'would update' if args.dry_run else 'updated'}  {name}")
    for name in report.unchanged:
        print(f"unchanged  {name}", file=sys.stderr)
    for msg in report.missing:
        print(f"MISSING    {msg}", file=sys.stderr)
    for msg in report.conflicts:
        print(f"CONFLICT   {msg}", file=sys.stderr)
    if not report.ok:
        return 1
    if not args.dry_run and report.updated:
        _save(doc, args)
    elif not args.dry_run and not args.in_place and args.output:
        _save(doc, args)  # still honour -o when nothing changed
    return 0


def cmd_replace(args: argparse.Namespace) -> int:
    doc = _read_doc(args.input)
    types = _csv(args.types)
    changes = replace_text(
        doc.elements,
        args.find,
        args.replace,
        types,
        fields=list(_csv(args.field)) or None,
        regex=args.regex,
        ignore_case=args.ignore_case,
        apply=not args.dry_run,
    )
    if args.dry_run:
        for c in changes:
            print(c.diff())
            print()
        total = sum(c.count for c in changes)
        print(f"{total} replacement(s) in {len(changes)} field(s) (dry run, nothing written)")
        return 0
    if not (args.output or args.in_place):
        raise ElementorDataError("choose --dry-run, -o FILE or --in-place")
    _save(doc, args)
    print(
        f"{sum(c.count for c in changes)} replacement(s) in {len(changes)} field(s)",
        file=sys.stderr,
    )
    return 0


def _short(value: Any, limit: int = 70) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def format_diff(result: DiffResult) -> str:
    lines: list[str] = []
    for r in result.added:
        extra = f" (+{r.descendants} descendants)" if r.descendants else ""
        lines.append(f"+ added    {r.kind} #{r.id} at {r.pointer}{extra}")
    for r in result.removed:
        extra = f" (+{r.descendants} descendants)" if r.descendants else ""
        lines.append(f"- removed  {r.kind} #{r.id} at {r.pointer}{extra}")
    for c in result.changed:
        lines.append(f"~ changed  {c.kind} #{c.id} at {c.pointer_b}")
        for s in c.changes:
            if s.op == "added":
                lines.append(f"    + {s.path}: {_short(s.new)}")
            elif s.op == "removed":
                lines.append(f"    - {s.path}: {_short(s.old)}")
            else:
                lines.append(f"    ~ {s.path}: {_short(s.old)} -> {_short(s.new)}")
    for m in result.moved:
        lines.append(f"> moved    {m.kind} #{m.id}: parent {m.old_parent} -> {m.new_parent}")
    for p in result.reordered:
        lines.append(f"= reordered children of {p}")
    if not lines:
        lines.append("no differences")
    else:
        lines.append(
            f"{len(result.added)} added, {len(result.removed)} removed, "
            f"{len(result.changed)} changed, {len(result.moved)} moved"
        )
    return "\n".join(lines)


def cmd_diff(args: argparse.Namespace) -> int:
    a, b = _read_doc(args.a), _read_doc(args.b)
    result = diff_documents(a.elements, b.elements, ignore_keys=tuple(args.ignore or ()))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(format_diff(result))
    return 0 if result.empty else 1


def cmd_wp_meta(args: argparse.Namespace) -> int:
    doc = _read_doc(args.input)
    problems = errors_only(validate(doc.elements))
    if problems and not args.force:
        for p in problems:
            print(p, file=sys.stderr)
        print("refusing to emit invalid data (use --force to override)", file=sys.stderr)
        return 1
    text = to_wp_meta(doc)
    data_file = args.output or "elementor_data.wp.json"
    if args.output and args.output != "-":
        _write_file(args.output, text)
    else:
        sys.stdout.write(text)
    print("", file=sys.stderr)
    for line in command_template(args.post_id, data_file, wp_path=args.wp_path, url=args.url):
        print(line, file=sys.stderr)
    return 0


def cmd_fields(_args: argparse.Namespace) -> int:
    for wt, paths in sorted(TEXT_FIELDS.items()):
        print(f"{wt:<16} {', '.join(paths)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="eltools", description="Tools for Elementor _elementor_data JSON."
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("pretty", help="pretty-print (or --compact) an export")
    s.add_argument("input", help="file, or - for stdin")
    s.add_argument("-o", "--output")
    s.add_argument("--indent", type=int, default=2)
    s.add_argument("--compact", action="store_true")
    s.set_defaults(func=cmd_pretty)

    s = sub.add_parser("validate", help="check structure; exit 1 on errors")
    s.add_argument("input")
    s.add_argument("--strict", action="store_true", help="treat warnings as failures")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("tree", help="print the element tree with paths")
    s.add_argument("input")
    s.add_argument("--max-depth", type=int)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_tree)

    s = sub.add_parser("widgets", help="count widgets by type, or list one type")
    s.add_argument("input")
    s.add_argument("--type", help="list instances of this widgetType")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_widgets)

    s = sub.add_parser(
        "find", help="find elements by widget type and setting values (exit 1 if none)"
    )
    s.add_argument("input")
    s.add_argument("--type", help="only this widgetType")
    s.add_argument(
        "--setting",
        action="append",
        default=[],
        metavar="TEST",
        help="PATH (set and non-empty), PATH=VALUE (exact) or PATH~TEXT (contains, "
        "case-insensitive); dotted paths such as link.url or tabs.0.tab_title; repeatable (AND)",
    )
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_find)

    s = sub.add_parser("extract", help="write widget text fields to files")
    s.add_argument("input")
    s.add_argument("-d", "--dir", required=True, help="output directory")
    s.add_argument("--types", default="html", help="comma separated widget types (html)")
    s.add_argument("--field", default="", help="override field paths, comma separated")
    s.set_defaults(func=cmd_extract)

    s = sub.add_parser("insert", help="put edited files from extract back into the export")
    s.add_argument("input")
    s.add_argument("-d", "--dir", required=True)
    s.add_argument("--force", action="store_true", help="overwrite even if the export changed")
    s.add_argument("-n", "--dry-run", action="store_true")
    _add_output_args(s)
    s.set_defaults(func=cmd_insert)

    s = sub.add_parser("replace", help="find/replace in text fields of chosen widget types")
    s.add_argument("input")
    s.add_argument("--find", required=True)
    s.add_argument("--replace", required=True)
    s.add_argument(
        "--types", required=True, help="comma separated widget types, e.g. heading,text-editor"
    )
    s.add_argument("--field", default="", help="override field paths, comma separated")
    s.add_argument("--regex", action="store_true")
    s.add_argument("-i", "--ignore-case", action="store_true")
    s.add_argument("-n", "--dry-run", action="store_true", help="show a diff, write nothing")
    _add_output_args(s)
    s.set_defaults(func=cmd_replace)

    s = sub.add_parser("diff", help="element-level diff of two exports (exit 1 if different)")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--json", action="store_true")
    s.add_argument(
        "--ignore",
        action="append",
        metavar="PATH",
        help="dotted path to ignore, e.g. settings.custom_css",
    )
    s.set_defaults(func=cmd_diff)

    s = sub.add_parser("wp-meta", help="emit WP-CLI safe JSON and a command template")
    s.add_argument("input")
    s.add_argument("--post-id", required=True)
    s.add_argument("-o", "--output", help="write JSON to this file (default: stdout)")
    s.add_argument("--wp-path", help="value for wp --path=")
    s.add_argument("--url", help="value for wp --url= (multisite)")
    s.add_argument("--force", action="store_true", help="emit even if validation fails")
    s.set_defaults(func=cmd_wp_meta)

    s = sub.add_parser("fields", help="list the text fields known for each widget type")
    s.set_defaults(func=cmd_fields)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ElementorDataError, ValueError) as exc:
        print(f"eltools: error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:  # pragma: no cover
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
