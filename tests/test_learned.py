import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baogu_learned import find_mistakes, load_learned_mistakes, record_mistakes  # noqa: E402

TERMS = ["PR", "GitHub Actions", "CI", "main"]


class FindMistakesTest(unittest.TestCase):
    def test_homophone_replaced_by_hotword_is_learned(self):
        self.assertEqual(
            find_mistakes("我刚提了一个p二", "我刚提了一个 PR。", TERMS),
            [("p二", "PR")])
        self.assertEqual(
            find_mistakes("这个分支的p 二还没过CI", "这个分支的 PR 还没过 CI。", TERMS),
            [("p 二", "PR")])

    def test_multi_word_hotword(self):
        self.assertEqual(
            find_mistakes("看一下 get help actions 的结果",
                          "看一下 GitHub Actions 的结果。", TERMS),
            [("get help actions", "GitHub Actions")])

    def test_cosmetic_and_non_hotword_edits_are_ignored(self):
        # Punctuation, spacing and case are not mishearings.
        self.assertEqual(find_mistakes("PR提好了", "PR 提好了。", TERMS), [])
        self.assertEqual(find_mistakes("合并到 Main", "合并到 main", TERMS), [])
        # Filler removal and rewording to a non-hotword teach nothing.
        self.assertEqual(find_mistakes("嗯明天三点开会", "明天三点开会。", TERMS), [])
        self.assertEqual(find_mistakes("今天气像很好", "今天气象很好", TERMS), [])


class RecordMistakesTest(unittest.TestCase):
    def test_counts_accumulate_and_rank(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baogu" / "learned-mistakes.tsv"
            record_mistakes([("p二", "PR")], path)
            record_mistakes([("批二", "PR"), ("p二", "PR")], path)
            self.assertEqual(load_learned_mistakes(path),
                             [("p二", "PR", 2), ("批二", "PR", 1)])
            record_mistakes([], path)
            self.assertEqual(len(load_learned_mistakes(path)), 2)

    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_learned_mistakes(Path(tmp) / "none.tsv"), [])


if __name__ == "__main__":
    unittest.main()
