from __future__ import annotations

import re

from roottrace.models import Failure, ParseResult
from roottrace.parsers.base import LogParser

_RULES = [
    ("dependency", "missing_dependency", re.compile(r"(?:module not found|no module named|cannot find module|could not resolve dependency|dependency resolution failed)", re.I)),
    ("build", "compilation", re.compile(r"(?:compilation failed|compile error|syntaxerror|cannot compile|cannot find symbol)", re.I)),
    ("ci", "permission", re.compile(r"(?:permission denied|access denied|403 forbidden|resource not accessible by integration)", re.I)),
    ("ci", "missing_secret", re.compile(r"(?:secret.*(?:missing|not set)|missing.*secret|environment variable .* not set|undefined secret)", re.I)),
    ("ci", "configuration", re.compile(r"(?:invalid workflow|yaml.*error|unknown key|configuration error|workflow.*invalid)", re.I)),
    ("infrastructure", "dns", re.compile(r"(?:temporary failure in name resolution|name or service not known|could not resolve host|dns)", re.I)),
    ("infrastructure", "network", re.compile(r"(?:connection reset|connection refused|network is unreachable|socket hang up|econnreset|econnrefused)", re.I)),
    ("infrastructure", "timeout", re.compile(r"(?:timed out|timeout|deadline exceeded|etimedout)", re.I)),
    ("infrastructure", "memory", re.compile(r"(?:out of memory|oomkilled|java heap space|memoryerror)", re.I)),
    ("application", "database", re.compile(r"(?:database.*(?:failed|error|unavailable)|sqlstate|operationalerror|connection.*database|deadlock detected)", re.I)),
    ("application", "authentication", re.compile(r"(?:unauthorized|jwt.*expired|token.*expired|authentication failed|invalid token|401 unauthorized)", re.I)),
    ("application", "authorization", re.compile(r"(?:forbidden|permission.*application|403)", re.I)),
    ("application", "validation", re.compile(r"(?:validationerror|invalid payload|unprocessable entity|422)", re.I)),
    ("test", "assertion", re.compile(r"(?:assertionerror|expected .* (?:but|to) .*|assert .* failed)", re.I)),
]

_EXCEPTION = re.compile(r"\b([A-Za-z_][\w.]*?(?:Error|Exception|Failure))\b")
_FILE_LINE = re.compile(r"(?P<file>(?:[A-Za-z]:)?[\w./\\-]+\.(?:py|js|ts|tsx|jsx|java|go|cs|rb|php))(?::(?P<line>\d+))?")


class GenericParser(LogParser):
    name = "generic"

    def score(self, text: str, source: str = "") -> int:
        return 1

    def parse(self, text: str, source: str = "") -> ParseResult:
        failures: list[Failure] = []
        seen: set[tuple[str, str, str]] = set()
        lines = text.splitlines()
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            for category, subtype, rule in _RULES:
                if rule.search(stripped):
                    file_match = _FILE_LINE.search(stripped)
                    exc_match = _EXCEPTION.search(stripped)
                    key = (category, subtype, stripped[:160])
                    if key in seen:
                        break
                    seen.add(key)
                    failures.append(
                        Failure(
                            category=category,
                            subtype=subtype,
                            message=stripped[:500],
                            framework="generic",
                            file=file_match.group("file").replace("\\", "/") if file_match else None,
                            line=int(file_match.group("line")) if file_match and file_match.group("line") else None,
                            exception=exc_match.group(1) if exc_match else None,
                        )
                    )
                    break
            if len(failures) >= 200:
                break
        if not failures:
            suspicious = next((l.strip() for l in reversed(lines) if any(k in l.lower() for k in ("error", "failed", "fatal", "exception"))), None)
            if suspicious:
                failures.append(Failure("unknown", "unclassified", suspicious[:500], "generic"))
        return ParseResult(self.name, failures)
