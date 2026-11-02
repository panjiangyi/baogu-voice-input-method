#!/usr/bin/env python3
"""Pool the natural-accent results and apply the acceptance rule.

One row per configuration (a backend, optionally with a vocabulary prompt):
the read set and the free-speech set are scored with the same metric
implementation and pooled, so the acceptance rule from the plan (mixed error
rate at least 20% below the Paraformer baseline, no regression in Chinese,
English or numbers, p95 wait within 3s) can be read off one table.

Usage:
  python3 scripts/29-accent-verdict.py \\
      --free-manifest samples/accent-spontaneous/manifest.reconstructed.tsv \\
      --config "Paraformer (default)=docs/evaluation/accent-nl-nasal-paraformer-production-20261102.tsv,docs/evaluation/accent-spontaneous-paraformer-production-20261102.tsv" \\
      --config "Qwen3 + vocabulary=docs/evaluation/accent-nl-nasal-qwen3-hotwords-20261102.tsv,docs/evaluation/accent-spontaneous-qwen3-hotwords-20261102.tsv"
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


def load_terms(path: Path) -> dict[tuple[str, str], list[str]]:
    out: dict[tuple[str, str], list[str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) < 3 or row[0].lstrip().startswith("#"):
                continue
            out.setdefault((row[0], row[1]), []).append(row[2])
    return out


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def score(results: Path, references: dict[str, str], set_name: str,
          terms: dict[tuple[str, str], list[str]]):
    with results.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    mixed_edits = mixed_refs = edits = refs = 0
    exact = 0
    term_hits = term_total = 0
    waits: list[float] = []
    timeouts = 0
    for row in rows:
        case = row.get("case", "")
        reference = references.get(case, row.get("expected", ""))
        hypothesis = row.get("final", "")
        distance, _ = cer(reference, hypothesis)
        edits += distance
        refs += max(len(normalize(reference)), 1)
        mixed_distance, mixed_length = mixed_error(reference, hypothesis)
        mixed_edits += mixed_distance
        mixed_refs += mixed_length
        exact += int(normalize(reference) == normalize(hypothesis))
        if row.get("final_wait_sec"):
            waits.append(float(row["final_wait_sec"]))
        if (row.get("final_reason") or "") == "timeout":
            timeouts += 1
        text = hypothesis.casefold()
        for term in terms.get((set_name, case), []):
            term_total += 1
            term_hits += int(term.casefold() in text)
    return {
        "rows": len(rows),
        "mixed_edits": mixed_edits,
        "mixed_refs": mixed_refs,
        "edits": edits,
        "refs": refs,
        "exact": exact,
        "waits": waits,
        "timeouts": timeouts,
        "term_hits": term_hits,
        "term_total": term_total,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-manifest", type=Path,
                        default=ROOT / "samples/accent-nl-nasal/manifest.tsv")
    parser.add_argument("--free-manifest", type=Path,
                        default=ROOT / "samples/accent-spontaneous/manifest.tsv")
    parser.add_argument("--terms", type=Path,
                        default=ROOT / "docs/evaluation/accent-expected-terms.tsv")
    parser.add_argument("--config", action="append", required=True,
                        help="LABEL=read-results.tsv,free-results.tsv")
    args = parser.parse_args()

    read_refs = load_manifest(args.read_manifest)
    free_refs = load_manifest(args.free_manifest)
    terms = load_terms(args.terms)

    configs = []
    for spec in args.config:
        label, _, files = spec.partition("=")
        read_file, _, free_file = files.partition(",")
        configs.append((label, Path(read_file), Path(free_file)))

    baseline = None
    print(f"{'configuration':<34}{'mixed (pooled)':>16}{'vs baseline':>13}"
          f"{'exact':>9}{'terms':>9}{'p95 wait':>11}{'timeouts':>10}")
    print("-" * 102)
    for label, read_file, free_file in configs:
        read = score(read_file, read_refs, "accent-nl-nasal", terms)
        free = score(free_file, free_refs, "accent-spontaneous", terms)
        mixed = (read["mixed_edits"] + free["mixed_edits"]) / max(
            read["mixed_refs"] + free["mixed_refs"], 1)
        exact = read["exact"] + free["exact"]
        cases = read["rows"] + free["rows"]
        hits = read["term_hits"] + free["term_hits"]
        total = read["term_total"] + free["term_total"]
        waits = read["waits"] + free["waits"]
        p95 = percentile(waits, 0.95)
        timeouts = read["timeouts"] + free["timeouts"]
        if baseline is None:
            baseline = mixed
        delta = (mixed - baseline) / baseline if baseline else 0.0
        print(f"{label:<34}{mixed:>15.2%}{delta:>12.1%}"
              f"{exact:>6}/{cases:<3}{hits:>5}/{total:<3}{p95:>9.2f}s{timeouts:>10}")


if __name__ == "__main__":
    raise SystemExit(main())
