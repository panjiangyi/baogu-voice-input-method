#!/usr/bin/env python3
"""Compare saved evaluation TSVs with one scoring implementation.

Every TSV keeps the reference and the produced text, so the comparison can be
recomputed instead of trusting the numbers each run printed.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SUITE = {"__file__": str(ROOT / "scripts/08-offline-suite.py")}
exec(compile((ROOT / "scripts/08-offline-suite.py").read_text(),
             str(ROOT / "scripts/08-offline-suite.py"), "exec"), SUITE)
cer = SUITE["cer"]
mixed_error = SUITE["mixed_error"]
normalize = SUITE["normalize"]


def score(path: Path) -> dict:
    rows = list(csv.DictReader(path.open(), delimiter="\t"))
    if not rows:
        return {}
    edits = refs = mixed_edits = mixed_refs = 0
    exact = 0
    english_errors = english_refs = 0
    waits = []
    for row in rows:
        expected, final = row["expected"], row["final"]
        distance, rate = cer(expected, final)
        edits += distance
        refs += max(len(normalize(expected)), 1)
        mixed_distance, mixed_length = mixed_error(expected, final)
        mixed_edits += mixed_distance
        mixed_refs += mixed_length
        exact += int(normalize(expected) == normalize(final))
        english_errors += int(row["english_errors"])
        english_refs += int(row["english_reference"])
        if row.get("final_wait_sec"):
            waits.append(float(row["final_wait_sec"]))
    return {
        "cases": len(rows),
        "exact": f"{exact}/{len(rows)}",
        "cer": edits / max(refs, 1),
        "mixed": mixed_edits / max(mixed_refs, 1),
        "english_errors": english_errors,
        "english_refs": english_refs,
        "waits": waits,
    }


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def main() -> int:
    targets = [Path(arg) for arg in sys.argv[1:]]
    if not targets:
        targets = sorted((ROOT / "docs/evaluation").glob("*.tsv"))
    header = (f"{'file':<44}{'cases':>7}{'exact':>9}{'CER':>10}{'mixed':>10}"
              f"{'EN err':>10}{'wait p50':>10}{'wait p95':>10}")
    print(header)
    print("-" * len(header))
    for path in targets:
        if not path.exists():
            print(f"{path.name:<44}missing")
            continue
        try:
            result = score(path)
        except Exception as ex:
            print(f"{path.name:<44}unreadable: {ex}")
            continue
        if not result:
            print(f"{path.name:<44}empty")
            continue
        waits = result["waits"]
        print(f"{path.name:<44}{result['cases']:>7}{result['exact']:>9}"
              f"{result['cer']:>9.2%} {result['mixed']:>9.2%}"
              f"{str(result['english_errors']) + '/' + str(result['english_refs']):>10}"
              f"{percentile(waits, 0.5):>9.2f}s{percentile(waits, 0.95):>9.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
