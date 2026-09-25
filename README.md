# RootTrace

**Local-first CI failure intelligence for engineering teams.**

RootTrace ingests CI/test artifacts, normalizes failures, fingerprints recurring problems, tracks test history, estimates flaky behavior, correlates failures with Git changes, builds a lightweight dependency-impact graph, ranks probable root-cause candidates, and produces terminal, JSON, Markdown, HTML, and SARIF reports.

It is designed to work without a hosted RootTrace service, paid API, cloud database, or external AI provider. By default, RootTrace makes **no network calls**.

## Why

A failed pipeline usually tells an engineer *that* something failed, then leaves the expensive part to a human: decide whether it is an application regression, test problem, dependency issue, CI configuration problem, infrastructure failure, or recurring flaky behavior. RootTrace collects the evidence into one local investigation layer.

## Current V1 capabilities

- Parsers: pytest, JUnit XML, Jest, Maven/Gradle, generic CI/application logs
- Normalized failure taxonomy and stable fingerprints
- SQLite-backed local run/failure/test history
- Flaky-test scoring based on observed pass/fail history and transitions
- Git commit/branch/change correlation
- Best-effort static dependency graph for Python, JavaScript/TypeScript, and Java
- Change-impact traversal and candidate-test discovery
- Ranked root-cause candidates with human-readable evidence
- Framework-specific reproduction commands where possible
- Terminal, JSON, Markdown, HTML, and SARIF outputs
- Local history dashboard
- GitHub Actions, GitLab CI, and Jenkins integration examples
- Parser plugin entry point (`roottrace.parsers`)
- Optional local-only Ollama explanation layer; never required for core analysis
- Local benchmark harness

## Zero-budget architecture

RootTrace's core uses the Python standard library. It stores state under `.roottrace/`:

```text
.roottrace/
├── config.json
├── history.db
├── cache/
└── reports/
    ├── run-1.json
    ├── run-1.md
    ├── run-1.html
    ├── run-1.sarif
    └── history.html
```

No server is required.

## Install from this repository

Requires Python 3.10+ and Git for Git-aware features.

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install:

```bash
python -m pip install -e .
```

Initialize inside a repository:

```bash
roottrace init
```

Check the environment:

```bash
roottrace doctor
```

## Analyze failures

```bash
roottrace analyze path/to/pytest.log
roottrace analyze path/to/junit.xml
roottrace analyze path/to/log-directory/
cat build.log | roottrace analyze -
```

RootTrace exits `0` by default even when the artifact contains a failure. This is deliberate: an analysis step should not accidentally replace the original CI failure. To make detected failures produce exit code `1`:

```bash
roottrace analyze build.log --fail-on-detected
```

Example output:

```text
ROOTTRACE ANALYSIS
==============================================================================
Source: pytest.log
Parser: pytest
Failures found: 1

[1] TEST / test_failure
Fingerprint: 11F5AAAC7F46
Confidence: 78%
Framework: pytest
Test: test_refresh_token
Location: tests/auth/test_token.py:72
Exception: JWTExpiredError

Probable causes:
   80% Changed file [src/auth/token.py]
       - The file appears in the observed stack trace.

Evidence:
  + Observed exception: JWTExpiredError
  + Parsed by the pytest adapter

Reproduce: python -m pytest tests/auth/test_token.py::test_refresh_token -vv
```

## Historical analysis

```bash
roottrace history
roottrace explain 11F5AAAC7F46
roottrace flaky
roottrace report
```

`roottrace report` creates a local HTML history dashboard. No web server is required; open the generated file directly in a browser. For a localhost-only viewer, run `roottrace serve` and open `http://127.0.0.1:8765/history.html`.

## Change-impact analysis

Analyze the current change:

```bash
roottrace impact
```

Compare Git refs:

```bash
roottrace compare main feature/auth-refactor
```

The impact engine builds a best-effort local import graph and walks reverse dependencies to identify code and test files that may be affected by changed files. This is **decision support**, not permission to skip tests blindly.

## Benchmark

A small smoke benchmark is included:

```bash
roottrace benchmark benchmarks/manifest.json
```

The manifest format is intentionally simple so teams can replace the bundled examples with historical CI artifacts and expected classifications.

## Optional local AI

Core RootTrace does not use AI. If Ollama is already installed locally, a recorded fingerprint can optionally be explained by a local model:

```bash
roottrace explain 11F5AAAC7F46 --ollama qwen2.5-coder:7b
```

The deterministic evidence remains the source of truth. The local model is only an explanation layer.

## CI integrations

Examples are in `integrations/`:

- `github-actions-example.yml`
- `gitlab-ci.yml`
- `Jenkinsfile`

RootTrace works best when the test command saves machine-readable artifacts (especially JUnit XML) plus raw console logs.

## Parser plugins

Third-party packages can register parsers through the Python entry-point group `roottrace.parsers`. A plugin should expose a `LogParser` instance or class.

## Development

Run tests without installing:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Run the bundled benchmark:

```bash
PYTHONPATH=src python -m roottrace.cli benchmark benchmarks/manifest.json
```

## Important limitations

RootTrace V1 is usable, but it does not claim causal certainty. Static dependency analysis is best-effort and cannot fully resolve dynamic imports, reflection, generated code, monorepo build systems, remote services, or every language ecosystem. Root-cause scores are evidence rankings, not proofs. Treat them as a way to reduce investigation time, then verify the hypothesis.

See `docs/ARCHITECTURE.md`, `docs/ALGORITHMS.md`, `docs/PRIVACY.md`, and `docs/VALIDATION.md`.
