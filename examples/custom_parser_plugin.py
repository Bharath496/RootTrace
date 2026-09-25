"""Minimal parser-plugin example. Package this in another Python distribution and
register it under the `roottrace.parsers` entry-point group.
"""
from roottrace.models import Failure, ParseResult
from roottrace.parsers.base import LogParser


class ExampleParser(LogParser):
    name = "example-ci"

    def score(self, text: str, source: str = "") -> int:
        return 50 if "EXAMPLE_CI_FAILURE" in text else 0

    def parse(self, text: str, source: str = "") -> ParseResult:
        if "EXAMPLE_CI_FAILURE" not in text:
            return ParseResult(self.name)
        return ParseResult(self.name, [Failure("ci", "example", "Example CI failure", self.name)])
