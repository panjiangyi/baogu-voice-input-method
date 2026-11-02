#!/usr/bin/env python3
"""Score accent-sensitive terms per case, independent of the reference text.

The natural-accent set contains two free-speech cases whose reference was
transcribed from one model's output (S-007, S-008). Any character-level
score on those cases rewards that model and punishes the others, so this
script scores the *terms* instead: a list of strings that must appear in the
recognised text of a case (docs/evaluation/accent-expected-terms.tsv).

Usage:
  python3 scripts/28-term-hits.py \\
      --set accent-spontaneous \\
      docs/evaluation/accent-spontaneous-*-20261102.tsv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMS = ROOT / "docs" / "evaluation" / "accent-expected-terms.tsv"


def load_terms(path: Path, wanted_set: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) < 3 or row[0].lstrip().startswith("#"):
                continue
            if row[0] != wanted_set:
                continue
            out.setdefault(row[1], []).append(row[2])
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--set", required=True)
    parser.add_argument("--terms", type=Path, default=TERMS)
    parser.add_argument("--show-misses", action="store_true")
    args = parser.parse_args()

    wanted = load_terms(args.terms, args.set)
    total = sum(len(v) for v in wanted.values())

    print(f"{'results file':<58}{'hits':>8}{'terms':>8}   rate")
    print("-" * 92)
    for path in args.results:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        hits = 0
        misses: list[str] = []
        for row in rows:
            case = row.get("case", "")
            text = (row.get("final") or "").casefold()
            for term in wanted.get(case, []):
                if term.casefold() in text:
                    hits += 1
                else:
                    misses.append(f"{case}:{term}")
        name = path.name
        if len(name) > 57:
            name = name[:54] + "..."
        print(f"{name:<58}{hits:>5}/{total:<3}{hits / max(total, 1):>7.1%}")
        if args.show_misses and misses:
            print(f"    missed: {', '.join(misses)}")


if __name__ == "__main__":
    raise SystemExit(main())
