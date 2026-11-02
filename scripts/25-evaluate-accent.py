#!/usr/bin/env python3
"""Score a recorded session, optionally with focus on target words.

The general metrics come from the same implementation as the offline suite, so
the numbers stay comparable. The target-word pass exists for accent work: a
sentence can be recognised well overall while a single n/l or nasal-final word
is still wrong, and that word is exactly what the user cares about.

Usage:
  python3 scripts/25-evaluate-accent.py --manifest samples/<session>/manifest.tsv
  python3 scripts/25-evaluate-accent.py --manifest ... --targets docs/evaluation/accent-targets.txt
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE: dict = {"__file__": str(ROOT / "scripts/08-offline-suite.py")}
exec(compile((ROOT / "scripts/08-offline-suite.py").read_text(),
             str(ROOT / "scripts/08-offline-suite.py"), "exec"), SUITE)
cer = SUITE["cer"]
mixed_error = SUITE["mixed_error"]
normalize = SUITE["normalize"]


def load_manifest(path: Path) -> list[dict]:
    rows = []
    with path.open() as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            reference = (row.get("actual_text") or row.get("target_text") or "").strip()
            if reference:
                rows.append({"id": row["id"], "reference": reference})
    return rows


def load_targets(path: Path) -> list[tuple[str, list[str]]]:
    """Each line is one concept; alternatives are separated by '|'."""
    targets = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        alternatives = [part.strip() for part in line.split("|") if part.strip()]
        if alternatives:
            targets.append((alternatives[0], alternatives))
    return targets


def target_hits(text: str, alternatives: list[str]) -> int:
    return sum(1 for alt in alternatives if alt and alt in text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="session manifest.tsv with target_text/actual_text")
    parser.add_argument("--results", type=Path,
                        help="optional TSV produced by the offline suite, for the final text")
    parser.add_argument("--targets", type=Path,
                        help="file of target words, one concept per line, '|' separates alternatives")
    args = parser.parse_args()

    rows = load_manifest(args.manifest)
    if not rows:
        print("no rows in manifest", file=sys.stderr)
        return 1

    produced: dict[str, str] = {}
    if args.results:
        for row in csv.DictReader(args.results.open(), delimiter="\t"):
            produced[row.get("case", "")] = row.get("final", "")

    edits = refs = mixed_edits = mixed_refs = 0
    exact = 0
    scored = 0
    for row in rows:
        hypothesis = produced.get(row["id"])
        if hypothesis is None:
            continue
        scored += 1
        distance, _ = cer(row["reference"], hypothesis)
        edits += distance
        refs += max(len(normalize(row["reference"])), 1)
        mixed_distance, mixed_length = mixed_error(row["reference"], hypothesis)
        mixed_edits += mixed_distance
        mixed_refs += mixed_length
        exact += int(normalize(row["reference"]) == normalize(hypothesis))

    print(f"sentences scored: {scored}/{len(rows)}")
    print(f"content CER: {edits / max(refs, 1):.2%} ({edits}/{refs})")
    print(f"mixed error rate: {mixed_edits / max(mixed_refs, 1):.2%} "
          f"({mixed_edits}/{mixed_refs})")
    print(f"exact sentences: {exact}/{scored}")

    if args.targets:
        print()
        print(f"{'target':<16}{'ref hits':>9}{'out hits':>9}  missed")
        print("-" * 60)
        for label, alternatives in load_targets(args.targets):
            ref_hits = out_hits = 0
            missed = []
            for row in rows:
                hypothesis = produced.get(row["id"])
                if hypothesis is None:
                    continue
                want = target_hits(row["reference"], alternatives)
                if not want:
                    continue
                got = target_hits(hypothesis, alternatives)
                ref_hits += want
                out_hits += got
                if got < want:
                    missed.append(row["id"])
            if not ref_hits:
                continue
            status = "ok" if out_hits >= ref_hits else "MISSING"
            print(f"{label:<16}{ref_hits:>9}{out_hits:>9}  {status} {','.join(missed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
