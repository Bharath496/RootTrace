import tempfile
import unittest
from pathlib import Path

from roottrace.db import HistoryDB
from roottrace.models import AnalysisRun, TestOutcome


class DBFlakyTests(unittest.TestCase):
    def test_flaky_score_detects_alternating_outcomes(self):
        with tempfile.TemporaryDirectory() as td:
            db = HistoryDB(Path(td) / "history.db")
            try:
                for status in ["passed", "failed", "passed", "failed", "passed"]:
                    db.save_run(AnalysisRun("x", "pytest", None, None, [], [], [TestOutcome("pytest", "test_x", status)]))
                stats = db.test_stats("pytest", "test_x")
                self.assertEqual(stats["total"], 5)
                self.assertGreater(stats["flaky_score"], 0.25)
                rows = db.flaky_tests(min_runs=3, threshold=0.25)
                self.assertEqual(rows[0]["test"], "test_x")
            finally: db.close()
