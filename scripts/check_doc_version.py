#!/usr/bin/env python3
"""Verify / refresh the sha256 version marker embedded in documentation files.

Each documented file carries a self-referential marker of the form:

    <!-- doc-sha256: <hex> -->

The hash is computed over the file *with the marker line removed*, so the
marker is stable across refreshes.

Modes:
  * default (local):  rewrite the marker so it matches the current content.
                      Never fails -- meant to be run as part of normal work.
  * --strict / CI:    compare the marker against the computed hash and exit 1
                      on mismatch. Used by CI to catch drift.

This mirrors the "sha256 sync markers" convention used elsewhere, kept
effortless: locally the marker heals itself, CI only enforces it.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

MARKER_RE = re.compile(r"^<!--\s*doc-sha256:\s*[0-9a-f]{64}\s*-->\s*$", re.MULTILINE)
DEFAULT_FILES = ["README.md"]


def content_hash(text: str) -> str:
    stripped = MARKER_RE.sub("", text)
    return hashlib.sha256(stripped.encode("utf-8")).hexdigest()


def process(path: str, strict: bool) -> int:
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"ERROR: documentation file not found: {path}", file=sys.stderr)
        return 1

    current = content_hash(text)
    match = MARKER_RE.search(text)

    if match:
        embedded = re.search(r"[0-9a-f]{64}", match.group(0)).group(0)
        if embedded == current:
            print(f"OK   {path} ({current[:12]}…)")
            return 0
        if strict:
            print(
                f"ERROR: {path} doc-sha256 mismatch\n"
                f"  stored:    {embedded}\n"
                f"  computed:  {current}",
                file=sys.stderr,
            )
            return 1
        updated = MARKER_RE.sub(f"<!-- doc-sha256: {current} -->\n", text, count=1)
    else:
        if strict:
            print(f"ERROR: {path} has no doc-sha256 marker", file=sys.stderr)
            return 1
        # Append the marker on its own line without an extra blank line, so that
        # the content *without* the marker stays byte-identical to the original.
        updated = text if text.endswith("\n") else text + "\n"
        updated += f"<!-- doc-sha256: {current} -->\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"UPDATE {path} -> {current[:12]}…")
    return 0


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    files = [a for a in argv if not a.startswith("-")] or DEFAULT_FILES
    code = 0
    for path in files:
        code |= process(path, strict)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
