#!/usr/bin/env python3
"""Learn which hotwords the recognizer keeps mishearing.

After an accepted LLM correction the raw ASR text and the corrected text are
diffed. Every span the LLM replaced with a hotword ("p二" -> "PR") is counted
in a TSV next to the personal glossary. The counted pairs go back into the
next correction prompt as known misrecognitions, so a mistake fixed once is
easier to fix again.

Only replacements whose corrected side is a hotword are learned: filler
removal, punctuation, case-only changes and ordinary rewording are ignored.
"""
from __future__ import annotations

import difflib
import os
import re
import tempfile
import time
from pathlib import Path

# A token is one CJK character or one ASCII word; spacing and punctuation are
# cosmetic and never part of a learned pair.
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+/-]*|[㐀-䶿一-鿿豈-﫿]")
MAX_SPAN_TOKENS = 8
HEADER = "# misheard\tcorrect\tcount\tlast_seen\n"


def learned_mistakes_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "baogu" / "learned-mistakes.tsv"


def _tokens(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in TOKEN_RE.finditer(text)]


def _key(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def find_mistakes(original: str, corrected: str, terms: list[str]) -> list[tuple[str, str]]:
    """(misheard, hotword) pairs for every span the correction turned into a hotword."""
    vocabulary = {_key(term): term for term in terms if term.strip()}
    before, after = _tokens(original), _tokens(corrected)
    a = [t[0].casefold() for t in before]
    b = [t[0].casefold() for t in after]
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    pairs: list[tuple[str, str]] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op != "replace" or i2 - i1 > MAX_SPAN_TOKENS or j2 - j1 > MAX_SPAN_TOKENS:
            continue
        # The diff may keep part of a hotword as unchanged ("get help actions"
        # -> "GitHub Actions" only replaces "get help"), so grow the span over
        # neighbouring unchanged tokens until it spells a whole hotword.
        for left in range(4):
            for right in range(4):
                lo_a, hi_a, lo_b, hi_b = i1 - left, i2 + right, j1 - left, j2 + right
                if lo_a < 0 or lo_b < 0 or hi_a > len(a) or hi_b > len(b):
                    continue
                if a[lo_a:i1] != b[lo_b:j1] or a[i2:hi_a] != b[j2:hi_b]:
                    continue
                fixed = corrected[after[lo_b][1]:after[hi_b - 1][2]]
                term = vocabulary.get(_key(fixed))
                if term is None:
                    continue
                misheard = original[before[lo_a][1]:before[hi_a - 1][2]].strip()
                if _key(misheard) != _key(term):
                    pairs.append((misheard, term))
                break
            else:
                continue
            break
    return pairs


def _read_table(path: Path) -> dict[tuple[str, str], list]:
    """{(misheard, correct): [count, last_seen]}"""
    table: dict[tuple[str, str], list] = {}
    if not path.is_file():
        return table
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        try:
            count = int(parts[2])
            seen = float(parts[3]) if len(parts) > 3 else 0.0
        except ValueError:
            continue
        table[(parts[0], parts[1])] = [count, seen]
    return table


def _ranked(table: dict[tuple[str, str], list]) -> list:
    return sorted(table.items(), key=lambda item: (item[1][0], item[1][1]), reverse=True)


def load_learned_mistakes(path: Path | None = None) -> list[tuple[str, str, int]]:
    """Learned (misheard, correct, count), most frequent first."""
    table = _read_table(path or learned_mistakes_path())
    return [(misheard, correct, count) for (misheard, correct), (count, _) in _ranked(table)]


def record_mistakes(pairs: list[tuple[str, str]], path: Path | None = None) -> None:
    if not pairs:
        return
    path = path or learned_mistakes_path()
    now = time.time()
    table = _read_table(path)
    for pair in pairs:
        entry = table.setdefault(pair, [0, 0.0])
        entry[0] += 1
        entry[1] = now
    rows = _ranked(table)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write a sibling temp file and rename so a crash never truncates the table.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".learned-", suffix=".tsv")
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(HEADER)
        for (misheard, correct), (count, seen) in rows:
            out.write(f"{misheard}\t{correct}\t{count}\t{seen:.0f}\n")
    os.replace(tmp, path)


if __name__ == "__main__":
    for misheard, correct, count in load_learned_mistakes():
        print(f"{count}\t{misheard} -> {correct}")
