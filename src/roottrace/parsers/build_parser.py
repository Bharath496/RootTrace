from __future__ import annotations

import re

from roottrace.models import Failure, ParseResult
from roottrace.parsers.base import LogParser

_JAVA_FILE = re.compile(r"(?P<file>[\w./\\-]+\.java):\[(?P<line>\d+),(?P<col>\d+)\]")
_GRADLE_TASK = re.compile(r"Execution failed for task '(?P<task>[^']+)'", re.I)


class MavenGradleParser(LogParser):
    name = "maven-gradle"

    def score(self, text: str, source: str = "") -> int:
        low = text.lower()
        score = 0
        if "[error]" in low and ("maven" in low or "mvn" in low or "mojo" in low):
            score += 8
        if "build failure" in low:
            score += 5
        if "gradle" in low or "execution failed for task" in low:
            score += 8
        return score

    def parse(self, text: str, source: str = "") -> ParseResult:
        failures: list[Failure] = []
        java = _JAVA_FILE.search(text)
        task = _GRADLE_TASK.search(text)
        low = text.lower()
        if "could not resolve" in low or "dependency" in low and "failed" in low:
            category, subtype = "dependency", "resolution"
        elif "compilation failure" in low or "compilation failed" in low or "cannot find symbol" in low:
            category, subtype = "build", "compilation"
        elif task:
            category, subtype = "build", "task_failure"
        else:
            category, subtype = "build", "build_failure"
        message = "Build failed"
        for line in text.splitlines():
            stripped = line.strip()
            if "[ERROR]" in stripped or "FAILURE:" in stripped or "Execution failed" in stripped:
                message = stripped[:500]
                break
        failures.append(
            Failure(
                category=category,
                subtype=subtype,
                message=message,
                framework="maven-gradle",
                file=java.group("file").replace("\\", "/") if java else None,
                line=int(java.group("line")) if java else None,
            )
        )
        return ParseResult(self.name, failures)
