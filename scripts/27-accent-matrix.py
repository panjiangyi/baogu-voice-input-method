#!/usr/bin/env python3
"""Compare backends on the accent acceptance set.

Prints one row per results TSV: content CER, mixed error rate, exact
sentences, English token errors, the wait percentiles and how many accent
target words were missed. The target list is the same file used by
`25-evaluate-accent.py`, so a word that came out as the accented spelling
counts as a miss, not as a hit.

Usage:
  python3 scripts/27-accent-matrix.py \\
      --manifest samples/accent-nl-nasal/manifest.tsv \\
      --targets docs/evaluation/accent-targets.txt \\
      docs/evaluation/accent-nl-nasal-*-production-20261102.tsv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE: dict = {"__file__": str(ROOT / "scripts/08-offline-suite.py")}
exec(compile((ROOT / "scripts/08-offline-suite.py").read_text(),
             str(ROOT / "scripts/08-offline-suite.py"), "exec"), SUITE)
cer = SUITE["cer"]
mixed_error = SUITE["mixed_error"]
normalize = SUITE["normalize"]


def load_manifest(path: Path) -> dict[str, str]:
    references: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            text = (row.get("actual_text") or row.get("target_text") or "").strip()
            if text:
                references[row["id"]] = text
    return references


def load_targets(path: Path) -> list[tuple[str, list[str]]]:
    targets = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        alternatives = [part.strip() for part in line.split("|") if part.strip()]
        if alternatives:
            targets.append((alternatives[0], alternatives))
    return targets


def hits(text: str, alternatives: list[str]) -> int:
    return sum(1 for alt in alternatives if alt and alt in text)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    args = parser.parse_args()

    references = load_manifest(args.manifest)
    targets = load_targets(args.targets)

    print(f"{'results file':<58}{'CER':>8}{'mixed':>9}{'exact':>8}"
          f"{'EN err':>9}{'p95':>8}{'target miss':>12}")
    print("-" * 112)
    for path in args.results:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        if not rows:
            continue
        edits = refs = mixed_edits = mixed_refs = 0
        exact = 0
        english_errors = english_refs = 0
        waits = []
        missed_targets = 0
        for row in rows:
            reference = references.get(row.get("case", ""), row["expected"])
            hypothesis = row.get("final", "")
            distance, _ = cer(reference, hypothesis)
            edits += distance
            refs += max(len(normalize(reference)), 1)
            mixed_distance, mixed_length = mixed_error(reference, hypothesis)
            mixed_edits += mixed_distance
            mixed_refs += mixed_length
            exact += int(normalize(reference) == normalize(hypothesis))
            english_errors += int(row.get("english_errors") or 0)
            english_refs += int(row.get("english_reference") or 0)
            if row.get("final_wait_sec"):
                waits.append(float(row["final_wait_sec"]))
            for _label, alternatives in targets:
                want = hits(reference, alternatives)
                if want and hits(hypothesis, alternatives) < want:
                    missed_targets += 1
        name = path.name
        if len(name) > 57:
            name = name[:54] + "..."
        print(f"{name:<58}{edits / max(refs, 1):>7.2%}{mixed_edits / max(mixed_refs, 1):>9.2%}"
              f"{exact:>5}/{len(rows)}{english_errors:>6}/{english_refs}"
              f"{percentile(waits, 0.95):>7.2f}s{missed_targets:>12}")


if __name__ == "__main__":
    raise SystemExit(main())
