from __future__ import annotations

import re

from roottrace.models import Failure, ParseResult, TestOutcome
from roottrace.parsers.base import LogParser

_FAILED = re.compile(r"^FAILED\s+(?P<node>[^\s]+?)(?:\s+-\s+(?P<message>.*))?$", re.MULTILINE)
_VERBOSE = re.compile(r"^(?P<node>[^\s]+\.py(?:::[^\s]+)+)\s+(?P<status>PASSED|FAILED|SKIPPED|ERROR)(?:\s+\[[^\]]+\])?", re.MULTILINE)
_EXCEPTION = re.compile(r"^(?:E\s+)?(?P<exc>[A-Za-z_][\w.]*?(?:Error|Exception|Failure)):\s*(?P<msg>.+)$", re.MULTILINE)
_TRACE_FILE = re.compile(r"(?P<file>[\w./\\-]+\.py):(?P<line>\d+):")


def _split_node(node: str) -> tuple[str | None, str | None]:
    parts = node.split("::")
    return (parts[0].replace("\\", "/") if parts else None, "::".join(parts[1:]) if len(parts) > 1 else None)


class PytestParser(LogParser):
    name = "pytest"

    def score(self, text: str, source: str = "") -> int:
        score = 0
        low = text.lower()
        if "pytest" in low: score += 3
        if "short test summary info" in low: score += 6
        if _FAILED.search(text): score += 10
        if _VERBOSE.search(text): score += 5
        if source.endswith(".xml"): score -= 5
        return score

    def parse(self, text: str, source: str = "") -> ParseResult:
        failures: list[Failure] = []
        tests: list[TestOutcome] = []
        seen_tests: set[str] = set()
        for m in _VERBOSE.finditer(text):
            file, test = _split_node(m.group("node"))
            name = test or m.group("node")
            status = m.group("status").lower()
            status = "failed" if status == "failed" else "passed" if status == "passed" else status
            tests.append(TestOutcome("pytest", name, status, file=file))
            seen_tests.add(name)
        exception_matches = list(_EXCEPTION.finditer(text))
        trace_files = [(m.group("file").replace("\\", "/"), int(m.group("line"))) for m in _TRACE_FILE.finditer(text)]
        for m in _FAILED.finditer(text):
            file, test = _split_node(m.group("node"))
            raw = (m.group("message") or "pytest test failure").strip()
            exc = None
            exc_message = raw
            if ":" in raw:
                prefix = raw.split(":", 1)[0].strip()
                if prefix.endswith(("Error", "Exception", "Failure")): exc = prefix
            if not exc and exception_matches:
                exc = exception_matches[-1].group("exc")
                if raw == "pytest test failure": exc_message = exception_matches[-1].group("msg").strip()
            line = None
            if file:
                matching = [ln for f, ln in trace_files if f.endswith(file) or file.endswith(f)]
                line = matching[-1] if matching else None
            stack_files = list(dict.fromkeys(f for f, _ in trace_files[-20:]))
            failures.append(Failure("test","test_failure",exc_message,"pytest",test=test,file=file,line=line,exception=exc,stack_files=stack_files))
            if test and test not in seen_tests:
                tests.append(TestOutcome("pytest", test, "failed", file=file, message=exc_message)); seen_tests.add(test)
        if not failures and exception_matches:
            for exc_match in exception_matches[-20:]:
                failures.append(Failure("application","exception",exc_match.group("msg").strip(),"pytest",file=trace_files[-1][0] if trace_files else None,line=trace_files[-1][1] if trace_files else None,exception=exc_match.group("exc"),stack_files=list(dict.fromkeys(f for f, _ in trace_files[-20:]))))
        return ParseResult(self.name, failures, tests)
