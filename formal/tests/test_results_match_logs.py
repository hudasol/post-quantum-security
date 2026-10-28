"""The ProVerif results table agrees with the committed ProVerif logs (review round 6, R6B17).

Continuous integration does not install ProVerif, so the models are not rerun there. This test needs no
ProVerif: for every model it counts the verdicts that ProVerif printed in the committed log
(formal/results/logs/<model>.txt, lines 'RESULT ... is true.', '... is false.' and '... cannot be proved.') and
compares them with the rows of formal/results/proverif_results.csv. Lines that start with 'RESULT (' report the
weaker form of a failed injective query (column weaker_form) and are not counted. A query that reached the time
limit has no RESULT line and is excluded from the count.
"""
import collections
import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "formal" / "results" / "proverif_results.csv"
LOGS = ROOT / "formal" / "results" / "logs"


def verdicts(log):
    c = collections.Counter()
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.startswith("RESULT ") or line.startswith("RESULT ("):
            continue
        if line.endswith(" is true."):
            c["proved"] += 1
        elif line.endswith(" is false."):
            c["counterexample"] += 1
        elif line.endswith(" cannot be proved."):
            c["cannot be proved"] += 1
        else:
            c["unrecognised"] += 1
    return c


class TestResultsMatchLogs(unittest.TestCase):
    def test_every_model_has_a_log_with_the_same_verdicts(self):
        rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
        by_model = collections.defaultdict(collections.Counter)
        for r in rows:
            if r["result"].startswith("cannot be proved (timeout"):
                continue
            by_model[r["model"]][r["result"]] += 1
        self.assertTrue(by_model)
        for model in sorted({r["model"] for r in rows}):
            log = LOGS / f"{model}.txt"
            self.assertTrue(log.exists(), f"no committed log for {model}")
            self.assertEqual(verdicts(log), by_model[model], model)


if __name__ == "__main__":
    unittest.main()
