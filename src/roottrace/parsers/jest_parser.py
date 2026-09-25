from __future__ import annotations

import re

from roottrace.models import Failure, ParseResult, TestOutcome
from roottrace.parsers.base import LogParser

_FAIL_SUITE = re.compile(r"^\s*FAIL\s+(?P<file>[^\s]+)", re.MULTILINE)
_TEST_LINE = re.compile(r"^\s*[✕×]\s+(?P<name>.+?)(?:\s+\(\d+\s*ms\))?$", re.MULTILINE)
_PASS_LINE = re.compile(r"^\s*[✓√]\s+(?P<name>.+?)(?:\s+\(\d+\s*ms\))?$", re.MULTILINE)
_ERROR = re.compile(r"^\s*(?P<exc>[A-Za-z_$][\w.$]*?(?:Error|Exception)):\s*(?P<msg>.+)$", re.MULTILINE)
_STACK = re.compile(r"(?:at .*? \()?((?:[A-Za-z]:)?[^\s():]+\.(?:js|jsx|ts|tsx)):(\d+):(\d+)\)?")


class JestParser(LogParser):
    name = "jest"

    def score(self, text: str, source: str = "") -> int:
        score = 0
        low = text.lower()
        if "test suites:" in low and "tests:" in low:
            score += 8
        if _FAIL_SUITE.search(text):
            score += 8
        if "jest" in low:
            score += 4
        return score

    def parse(self, text: str, source: str = "") -> ParseResult:
        failures: list[Failure] = []
        tests: list[TestOutcome] = []
        suite_match = _FAIL_SUITE.search(text)
        file = suite_match.group("file").replace("\\", "/") if suite_match else None
        err = _ERROR.search(text)
        exc = err.group("exc") if err else None
        err_msg = err.group("msg") if err else "Jest test failure"
        stack = [(m.group(1).replace("\\", "/"), int(m.group(2))) for m in _STACK.finditer(text)]
        stack_files = list(dict.fromkeys(f for f, _ in stack[-20:]))
        for m in _TEST_LINE.finditer(text):
            name = m.group("name").strip()
            failures.append(Failure("test","test_failure",err_msg,"jest",test=name,file=file or (stack[-1][0] if stack else None),line=stack[-1][1] if stack else None,exception=exc,stack_files=stack_files))
            tests.append(TestOutcome("jest", name, "failed", file=file, message=err_msg))
        for m in _PASS_LINE.finditer(text):
            tests.append(TestOutcome("jest", m.group("name").strip(), "passed", file=file))
        if not failures and suite_match:
            failures.append(Failure("test", "suite_failure", err_msg, "jest", file=file, exception=exc, stack_files=stack_files))
        return ParseResult(self.name, failures, tests)
