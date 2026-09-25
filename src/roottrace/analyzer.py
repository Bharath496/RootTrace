from __future__ import annotations

import re
from pathlib import Path

from roottrace.db import HistoryDB
from roottrace.fingerprint import make_fingerprint
from roottrace.gitinfo import changed_files as git_changed_files, current_branch, current_commit, recent_commits_for_file
from roottrace.models import AnalysisRun, Evidence, Failure, RootCauseCandidate
from roottrace.parsers import select_parser


def _norm(path: str | None) -> str:
    return (path or "").replace("\\", "/").lstrip("./")


def _path_related(a: str | None, b: str) -> bool:
    left, right = _norm(a), _norm(b)
    return bool(left and right and (left == right or left.endswith(right) or right.endswith(left)))


def _tokens(path: str | None) -> set[str]:
    if not path:
        return set()
    return {t for t in re.split(r"[^a-zA-Z0-9]+", path.lower()) if len(t) >= 3 and t not in {"test", "tests", "src", "main"}}


def _reproduction(f: Failure) -> str | None:
    if f.framework == "pytest" and f.file:
        node = f"::{f.test}" if f.test else ""
        return f"python -m pytest {f.file}{node} -vv"
    if f.framework == "jest":
        if f.file and f.test:
            safe = f.test.replace('"', '\\"')
            return f'npx jest {f.file} -t "{safe}" --runInBand'
        if f.file:
            return f"npx jest {f.file} --runInBand"
    if f.framework == "maven-gradle":
        return "./gradlew test  # or: mvn -DskipTests=false test"
    return None


def _root_cause_candidates(failure: Failure, changed: list[str], project_dir: Path) -> list[RootCauseCandidate]:
    candidates: list[RootCauseCandidate] = []
    failure_tokens = _tokens(failure.file) | _tokens(failure.test) | _tokens(failure.message)
    for file in changed:
        reasons: list[str] = []
        score = 0.08
        if _path_related(failure.file, file):
            score += 0.72
            reasons.append("The failure location is directly changed in this revision.")
        if any(_path_related(stack, file) for stack in failure.stack_files):
            score += 0.45
            reasons.append("The file appears in the observed stack trace.")
        overlap = failure_tokens & _tokens(file)
        if overlap:
            score += min(0.25, 0.07 * len(overlap))
            reasons.append("Name/module tokens overlap with the failing test or error.")
        low = file.lower()
        if failure.category == "test" and not any(k in low for k in ("test", "spec")):
            score += 0.05
        if reasons or score >= 0.12:
            recent = recent_commits_for_file(project_dir, file, 1)
            if recent:
                reasons.append(f"Most recent file commit: {recent[0]['commit'][:10]} {recent[0]['subject']}")
            candidates.append(RootCauseCandidate("Changed file", round(min(score, 0.98), 2), reasons, file=file))

    category_hypotheses = {
        ("dependency", "missing_dependency"): "Dependency installation or lockfile mismatch",
        ("dependency", "resolution"): "Dependency resolution or version conflict",
        ("ci", "missing_secret"): "Missing CI secret or environment configuration",
        ("ci", "permission"): "CI token/runner permission problem",
        ("ci", "configuration"): "CI workflow configuration problem",
        ("infrastructure", "dns"): "DNS or service discovery problem",
        ("infrastructure", "network"): "Network/service availability problem",
        ("infrastructure", "timeout"): "Timeout caused by slowness or unavailable dependency",
        ("infrastructure", "memory"): "Runner/process memory exhaustion",
        ("application", "database"): "Database connectivity, migration, or query failure",
        ("application", "authentication"): "Authentication/token lifecycle regression",
        ("application", "authorization"): "Authorization/permission logic problem",
        ("application", "validation"): "Input schema or validation regression",
        ("build", "compilation"): "Compilation or source compatibility regression",
    }
    label = category_hypotheses.get((failure.category, failure.subtype))
    if label:
        candidates.append(RootCauseCandidate(label, 0.68, ["The normalized failure signature matches this failure family."]))

    if failure.category == "test" and not candidates:
        candidates.append(RootCauseCandidate("Test or application regression", 0.5, ["The test framework reported a deterministic test failure, but no changed file was strongly correlated."]))
    if not candidates:
        candidates.append(RootCauseCandidate("Unclassified failure", 0.2, ["RootTrace has evidence of failure but insufficient evidence for a stronger causal candidate."]))
    return sorted(candidates, key=lambda c: c.score, reverse=True)[:5]


def _score_failure(failure: Failure, changed: list[str], project_dir: Path) -> None:
    evidence: list[Evidence] = []
    score = 0.38
    if failure.exception:
        evidence.append(Evidence("exception", f"Observed exception: {failure.exception}", 0.10)); score += 0.10
    if failure.file:
        loc = failure.file + (f":{failure.line}" if failure.line else "")
        evidence.append(Evidence("location", f"Failure points to {loc}", 0.10)); score += 0.10
    direct = [c for c in changed if _path_related(failure.file, c)]
    if direct:
        evidence.append(Evidence("git", f"Failure location is changed in the current revision: {direct[0]}", 0.22)); score += 0.22
    stack_changed = [c for c in changed if any(_path_related(s, c) for s in failure.stack_files)]
    if stack_changed and not direct:
        evidence.append(Evidence("git", f"A changed file appears in the stack trace: {stack_changed[0]}", 0.16)); score += 0.16
    if changed and not direct and not stack_changed:
        evidence.append(Evidence("git", f"Current revision changes {len(changed)} file(s), but no direct stack/path match was found", -0.03)); score -= 0.03
    if failure.framework not in {"generic", "unknown"}:
        evidence.append(Evidence("parser", f"Parsed by the {failure.framework} adapter", 0.08)); score += 0.08
    if failure.subtype == "unclassified":
        score -= 0.18
    failure.evidence = evidence
    failure.confidence = round(max(0.05, min(score, 0.98)), 2)
    failure.fingerprint = make_fingerprint(failure.category, failure.subtype, failure.exception, failure.file, failure.test, failure.message)
    failure.candidates = _root_cause_candidates(failure, changed, project_dir)
    failure.reproduction = _reproduction(failure)


def analyze_text(text: str, source: str, project_dir: Path, parser_name: str | None = None, commit: str | None = None) -> AnalysisRun:
    parser = select_parser(text, parser_name, source)
    parsed = parser.parse(text, source)
    changed = git_changed_files(project_dir)
    for failure in parsed.failures:
        _score_failure(failure, changed, project_dir)
    return AnalysisRun(
        source=source,
        parser=parser.name,
        commit=commit or current_commit(project_dir),
        branch=current_branch(project_dir),
        changed_files=changed,
        failures=parsed.failures,
        tests=parsed.tests,
        metadata=parsed.metadata,
    )


def decorate_with_history(run: AnalysisRun, db: HistoryDB) -> None:
    for failure in run.failures:
        stats = db.fingerprint_stats(failure.fingerprint)
        failure.occurrence_count = int(stats["count"])
        failure.first_seen = stats["first_seen"] if isinstance(stats["first_seen"], str) else None
        failure.last_seen = stats["last_seen"] if isinstance(stats["last_seen"], str) else None
        if failure.test:
            test_stats = db.test_stats(failure.framework, failure.test, 100)
            failure.flaky_score = float(test_stats["flaky_score"])
            if int(test_stats["passed"]) > 0 and int(test_stats["failed"]) > 0:
                failure.evidence.append(Evidence("history", f"This test has both pass and fail outcomes across {test_stats['total']} recorded runs (flaky score {failure.flaky_score:.2f})", 0.08))
