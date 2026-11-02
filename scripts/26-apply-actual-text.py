#!/usr/bin/env python3
"""Write confirmed transcripts into a session manifest.

The manifest holds the prompted text in `target_text` and what the speaker
actually said in `actual_text`. The actual text is the reference: a recording
of free speech has no prompt to fall back on, so the reference has to come
from a human, typed out.

Usage:
  python3 scripts/26-apply-actual-text.py \\
      --manifest samples/accent-spontaneous/manifest.tsv \\
      --transcripts samples/accent-spontaneous/actual_text.draft.tsv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_transcripts(path: Path) -> dict[str, str]:
    """Read `id<TAB>text` lines; `#` comments and blank lines are ignored."""
    result: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                parts = line.split(None, 1)
            if len(parts) != 2 or not parts[1].strip():
                raise SystemExit(f"{path}:{number}: expected 'id<TAB>text'")
            result[parts[0].strip()] = parts[1].strip()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--transcripts", type=Path, required=True)
    args = parser.parse_args()

    transcripts = read_transcripts(args.transcripts)
    with args.manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise SystemExit(f"{args.manifest}: no rows")

    updated = 0
    for row in rows:
        text = transcripts.get(row["id"])
        if text is None:
            continue
        if row.get("actual_text") != text:
            updated += 1
        row["actual_text"] = text

    with args.manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{args.manifest}: {updated} row(s) updated, {len(rows)} total")


if __name__ == "__main__":
    main()
