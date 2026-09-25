import unittest
from pathlib import Path

from roottrace.parsers.jest_parser import JestParser
from roottrace.parsers.junit_parser import JUnitParser
from roottrace.parsers.pytest_parser import PytestParser
from roottrace.parsers.build_parser import MavenGradleParser
from roottrace.parsers.generic import GenericParser

FIX = Path(__file__).parent / "fixtures"


class ParserTests(unittest.TestCase):
    def test_pytest(self):
        result = PytestParser().parse((FIX / "pytest_failure.log").read_text(), "pytest.log")
        self.assertEqual(len(result.failures), 1); self.assertEqual(result.failures[0].exception, "JWTExpiredError"); self.assertEqual(result.failures[0].test, "test_refresh_token"); self.assertGreaterEqual(len(result.tests), 2)
    def test_junit(self):
        result = JUnitParser().parse((FIX / "junit.xml").read_text(), "junit.xml")
        self.assertEqual(len(result.tests), 3); self.assertEqual(len(result.failures), 1); self.assertEqual(result.failures[0].exception, "AssertionError")
    def test_jest(self):
        result = JestParser().parse((FIX / "jest_failure.log").read_text(), "jest.log")
        self.assertEqual(len(result.failures), 1); self.assertEqual(result.failures[0].exception, "JWTExpiredError"); self.assertEqual(result.failures[0].file, "src/auth/token.test.ts")
    def test_gradle(self):
        result = MavenGradleParser().parse((FIX / "gradle_failure.log").read_text(), "gradle.log")
        self.assertEqual(result.failures[0].category, "build"); self.assertEqual(result.failures[0].subtype, "compilation")
    def test_generic_network(self):
        result = GenericParser().parse((FIX / "generic_ci_failure.log").read_text(), "generic.log")
        self.assertEqual(result.failures[0].category, "infrastructure"); self.assertEqual(result.failures[0].subtype, "network")
