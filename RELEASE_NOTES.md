# RootTrace 1.0.0

This release turns the V0.1 proof of concept into a complete local-first product boundary.

## Shipped

- Multi-framework parsing: pytest, JUnit XML, Jest, Maven/Gradle, generic CI logs
- Failure taxonomy and normalized fingerprints
- SQLite historical database
- Test-outcome history and flaky scoring
- Git correlation and recent-file commit evidence
- Static change-impact graph for Python, JS/TS, and Java
- Ranked root-cause candidates and reproduction commands
- JSON, Markdown, HTML, SARIF reports
- Local history dashboard and localhost viewer
- Parser plugin mechanism
- GitHub Actions, GitLab CI, Jenkins examples
- Optional local Ollama explanation
- Built-in benchmark harness
- Unit tests, validation docs, privacy/security docs

## Verified for this release

- Python source compiles successfully.
- Automated suite: 10 tests passing.
- Bundled benchmark: 5/5 expected classifications.
- Wheel builds successfully without runtime dependencies.
- Fresh-venv installation was tested.
- End-to-end Git repository test correlated a changed auth source file with a failing auth stack and discovered the impacted test.
- Repeated alternating JUnit outcomes were detected as potentially flaky.

RootTrace scores are investigation aids, not proof of causality. Real-world benchmark expansion remains an ongoing product/research activity.
