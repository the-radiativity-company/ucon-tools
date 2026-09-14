# © 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0
# See the LICENSE file for details.

"""Changelog release helpers.

Two commands, both operating on ``CHANGELOG.md`` in Keep a Changelog form:

``promote <version> [--date YYYY-MM-DD]``
    Insert a dated ``## [<version>]`` heading directly below
    ``## [Unreleased]``, so the accumulated Unreleased entries become
    that version's section and Unreleased is left empty for the next
    cycle. Refuses when Unreleased is empty (nothing to release) or the
    version heading already exists.

``check <version>``
    Exit non-zero when ``## [<version>]`` is absent or its section is
    empty. The publish workflow runs this before extracting release
    notes, so a tag whose section was never promoted fails loudly
    instead of publishing an empty GitHub Release.
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
UNRELEASED = "## [Unreleased]"
HEADING = re.compile(r"^## \[([^\]]+)\]")


def _sections(lines: list[str]) -> dict[str, list[str]]:
    """Map heading version → its body lines (headings excluded)."""
    out: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        match = HEADING.match(line)
        if match:
            current = match.group(1)
            out[current] = []
            continue
        if current is not None:
            out[current].append(line)
    return out


def promote(version: str, date: str | None) -> int:
    lines = CHANGELOG.read_text().splitlines()
    sections = _sections(lines)

    if version in sections:
        print(f"error: CHANGELOG already has a [{version}] heading", file=sys.stderr)
        return 1
    if "Unreleased" not in sections:
        print(f"error: CHANGELOG has no {UNRELEASED} heading", file=sys.stderr)
        return 1
    if not any(line.strip() for line in sections["Unreleased"]):
        print(
            "error: [Unreleased] is empty — nothing to release. Record the "
            "changes before tagging.",
            file=sys.stderr,
        )
        return 1

    stamp = date or datetime.date.today().isoformat()
    index = lines.index(UNRELEASED)
    lines[index + 1 : index + 1] = ["", f"## [{version}] - {stamp}"]
    CHANGELOG.write_text("\n".join(lines) + "\n")
    print(f"CHANGELOG: [Unreleased] promoted to [{version}] - {stamp}")
    return 0


def check(version: str) -> int:
    sections = _sections(CHANGELOG.read_text().splitlines())
    if version not in sections:
        print(
            f"error: CHANGELOG has no [{version}] heading — the release notes "
            f"would be empty. Run `make release VERSION={version}`, land that "
            "commit on main, then re-tag.",
            file=sys.stderr,
        )
        return 1
    if not any(line.strip() for line in sections[version]):
        print(f"error: CHANGELOG section [{version}] is empty", file=sys.stderr)
        return 1
    print(f"CHANGELOG: [{version}] section present and non-empty")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    promote_parser = sub.add_parser("promote", help="date and name the Unreleased section")
    promote_parser.add_argument("version")
    promote_parser.add_argument("--date", default=None, help="defaults to today (UTC-naive)")

    check_parser = sub.add_parser("check", help="verify a version section exists and is non-empty")
    check_parser.add_argument("version")

    args = parser.parse_args(argv)
    if args.command == "promote":
        return promote(args.version, args.date)
    return check(args.version)


if __name__ == "__main__":
    raise SystemExit(main())
