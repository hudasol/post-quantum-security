"""Checks for the context fact table and its Markdown builder. Author: Huda Mueen."""
import unittest

from scripts import build_context_entities as b


def row(**kw):
    r = {"organisation": "EDGE Group", "fact_id": "X-01", "paraphrase": "A short paraphrase.",
         "url": "https://example.org/page", "retrieval_date": b.RETRIEVAL_DATE, "page_section": "Body",
         "relevance": "context"}
    r.update(kw)
    return r


class TestContextEntities(unittest.TestCase):
    def test_current_table_is_valid(self):
        rows = b.load()
        self.assertEqual(b.validate(rows), [])
        for o, n in b.counts(rows).items():
            self.assertGreaterEqual(n, 4, o)

    def test_validate_flags_problems(self):
        self.assertEqual(b.validate([row()]), [])
        self.assertTrue(b.validate([row(retrieval_date="2026-01-01")]))
        self.assertTrue(b.validate([row(url="http://example.org")]))
        self.assertTrue(b.validate([row(organisation="Other")]))
        self.assertTrue(b.validate([row(), row()]))
        self.assertTrue(b.validate([row(page_section="")]))
        self.assertTrue(b.validate([row(paraphrase="word " * 80)]))

    def test_counts_and_cell(self):
        self.assertEqual(b.counts([row(), row(organisation="ADEO")])["EDGE Group"], 1)
        self.assertEqual(b.cell("a|b\nc"), "a\\|b c")

    def test_render_contains_disclaimer_and_rows(self):
        md = b.render([row()])
        self.assertIn("no endorsement", md)
        self.assertIn(b.RETRIEVAL_DATE, md)
        self.assertIn("X-01", md)
        self.assertNotIn(chr(0x2014), md)


if __name__ == "__main__":
    unittest.main()
