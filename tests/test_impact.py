import tempfile
import unittest
from pathlib import Path

from roottrace.impact import impacted_files, likely_tests


class ImpactTests(unittest.TestCase):
    def test_python_reverse_dependency_impact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "core.py").write_text("def calc(): return 1\n")
            (root / "service.py").write_text("import core\ndef run(): return core.calc()\n")
            (root / "test_service.py").write_text("import service\ndef test_run(): assert service.run() == 1\n")
            impact = impacted_files(root, ["core.py"], max_depth=3)
            self.assertEqual(impact["core.py"], 0)
            self.assertEqual(impact["service.py"], 1)
            self.assertEqual(impact["test_service.py"], 2)
            self.assertIn(("test_service.py", 2), likely_tests(impact))
