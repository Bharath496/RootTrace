from __future__ import annotations

import xml.etree.ElementTree as ET

from roottrace.models import Failure, ParseResult, TestOutcome
from roottrace.parsers.base import LogParser


class JUnitParser(LogParser):
    name = "junit"

    def score(self, text: str, source: str = "") -> int:
        score = 0
        stripped = text.lstrip()
        if stripped.startswith("<?xml") or stripped.startswith("<testsuite") or stripped.startswith("<testsuites"):
            score += 8
        if "<testcase" in text and ("<failure" in text or "<error" in text):
            score += 10
        if source.lower().endswith(".xml"):
            score += 3
        return score

    def parse(self, text: str, source: str = "") -> ParseResult:
        failures: list[Failure] = []
        tests: list[TestOutcome] = []
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return ParseResult(self.name)
        for case in root.iter("testcase"):
            classname = case.attrib.get("classname", "")
            name = case.attrib.get("name", "unknown")
            full = f"{classname}::{name}" if classname else name
            file = case.attrib.get("file")
            duration = None
            try:
                duration = float(case.attrib.get("time", ""))
            except ValueError:
                pass
            failure_node = case.find("failure")
            error_node = case.find("error")
            skipped_node = case.find("skipped")
            node = failure_node if failure_node is not None else error_node
            if node is not None:
                status = "failed" if failure_node is not None else "error"
                message = node.attrib.get("message") or (node.text or "JUnit test failure").strip().splitlines()[0][:500]
                exc = node.attrib.get("type")
                failures.append(Failure("test","test_failure" if status == "failed" else "test_error",message,"junit",test=full,file=file,exception=exc))
                tests.append(TestOutcome("junit", full, status, duration, file, message))
            elif skipped_node is not None:
                tests.append(TestOutcome("junit", full, "skipped", duration, file))
            else:
                tests.append(TestOutcome("junit", full, "passed", duration, file))
        return ParseResult(self.name, failures, tests, {"test_count": len(tests)})
