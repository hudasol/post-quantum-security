"""Tests for the paper layout (six page main part, supplementary section) and its figures."""
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PaperLayout(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "docs" / "PAPER.md").read_text(encoding="utf-8")

    def test_sections_in_order(self):
        heads = ["## Abstract", "## 1. Introduction", "## 2. Related work", "## 3. Method", "## 4. Results",
                 "## 5. Threats to validity", "## 6. Conclusion", "## References", "## Supplementary material"]
        pos = [self.text.index(h) for h in heads]
        self.assertEqual(pos, sorted(pos))

    def test_one_answer_per_research_question(self):
        for i in range(1, 7):
            m = re.search(rf"### 4\.{i} RQ{i}: [^\n]+\n\nAnswer", self.text)
            self.assertIsNotNone(m, f"RQ{i} has no short answer")

    def test_main_part_within_page_budget(self):
        bp = _load("build_paper")
        n = bp.main_word_count(self.text)
        # six pages at the stated words per page, figures included in that estimate
        self.assertLessEqual(n, 6 * bp.WORDS_PER_PAGE)

    def test_at_most_four_figures_in_main_part(self):
        main = self.text[self.text.index("## Abstract"):self.text.index("## References")]
        figs = re.findall(r"!\[[^\]]*\]\((figures/paper/[^)]+)\)", main)
        self.assertLessEqual(len(figs), 4)
        for f in figs:
            self.assertTrue((ROOT / "docs" / f).exists(), f)

    def test_captions_name_source_files(self):
        for cap in re.findall(r"!\[([^\]]*)\]\(figures/paper/", self.text):
            self.assertIn("Source: `", cap)

    def test_placeholder_has_no_number(self):
        m = re.search(r"### 4\.7 Software in the loop \(placeholder\)\n\n([^\n]+)", self.text)
        self.assertIsNotNone(m)
        self.assertIsNone(re.search(r"\d", m.group(1)))


class PaperFigures(unittest.TestCase):
    def test_sources_exist(self):
        mf = _load("make_paper_figures")
        for fig, sources in mf.FIGURES.items():
            for s in sources:
                self.assertTrue((ROOT / s).exists(), s)
            self.assertTrue((ROOT / "docs" / "figures" / "paper" / fig).exists(), fig)


if __name__ == "__main__":
    unittest.main()
