from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Evidence:
    kind: str
    message: str
    weight: float = 0.0


@dataclass(slots=True)
class RootCauseCandidate:
    label: str
    score: float
    rationale: list[str] = field(default_factory=list)
    file: str | None = None
    line: int | None = None


@dataclass(slots=True)
class Failure:
    category: str
    subtype: str
    message: str
    framework: str = "unknown"
    test: str | None = None
    file: str | None = None
    line: int | None = None
    exception: str | None = None
    stack_files: list[str] = field(default_factory=list)
    fingerprint: str = ""
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
    candidates: list[RootCauseCandidate] = field(default_factory=list)
    reproduction: str | None = None
    occurrence_count: int = 0
    first_seen: str | None = None
    last_seen: str | None = None
    flaky_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TestOutcome:
    framework: str
    test: str
    status: str  # passed | failed | skipped | error
    duration: float | None = None
    file: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ParseResult:
    parser: str
    failures: list[Failure] = field(default_factory=list)
    tests: list[TestOutcome] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisRun:
    source: str
    parser: str
    commit: str | None
    branch: str | None
    changed_files: list[str]
    failures: list[Failure]
    tests: list[TestOutcome] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    run_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
