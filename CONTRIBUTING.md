# Contributing

Thanks for helping improve elementor-data-tools. Bug reports, new widget field mappings and
focused pull requests are welcome.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Before opening a pull request

```bash
ruff check .
ruff format --check .
pytest
```

CI runs the same checks on Python 3.10, 3.11, 3.12 and 3.13.

## Guidelines

- The runtime must stay dependency free (standard library only).
- Anything that edits data must be reversible: support a dry run or write to a new file,
  and never change ids, keys or settings outside the fields the user selected.
- A no-op edit (extract then insert, load then dump in the same style) must be byte-identical.
- Adding a widget to `eltools/fields.py`: list only keys that hold human text, use
  `tabs.*.field` for repeaters, and add a test.
- Sample data in `examples/` must be synthetic. Never commit exports from a real site.
- Update `CHANGELOG.md` under an "Unreleased" heading.

## Reporting bugs

Include the Python version, the command, and a minimal anonymised snippet of the JSON that
triggers the problem.
