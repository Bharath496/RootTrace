import tempfile
import unittest
from pathlib import Path

from roottrace.analyzer import analyze_text, decorate_with_history
from roottrace.db import HistoryDB
from roottrace.report import write_reports

FIX = Path(__file__).parent / "fixtures"


class AnalysisReportTests(unittest.TestCase):
    def test_analysis_writes_all_report_formats(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            text = (FIX / "pytest_failure.log").read_text()
            run = analyze_text(text, "pytest.log", root, "pytest")
            db = HistoryDB(root / "history.db")
            try:
                db.save_run(run)
                decorate_with_history(run, db)
                paths = write_reports(run, root / "reports", db)
                self.assertEqual(set(paths), {"json", "md", "html", "sarif"})
                for p in paths.values(): self.assertTrue(p.exists())
                self.assertTrue(run.failures[0].reproduction.startswith("python -m pytest"))
                self.assertEqual(run.failures[0].occurrence_count, 1)
            finally: db.close()
