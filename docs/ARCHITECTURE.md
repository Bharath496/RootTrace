# Architecture

```text
CI/test artifact
      │
      ▼
Parser registry
(pytest/JUnit/Jest/build/generic/plugins)
      │
      ▼
Normalized ParseResult
  ├─ Failures
  └─ Test outcomes
      │
      ▼
Analysis engine
  ├─ stable fingerprint
  ├─ failure taxonomy
  ├─ Git change evidence
  ├─ stack/change correlation
  ├─ root-cause candidates
  └─ reproduction command
      │
      ├───────────────┐
      ▼               ▼
SQLite history    Dependency graph
  ├─ runs            ├─ Python AST
  ├─ failures        ├─ JS/TS imports
  └─ test outcomes   └─ Java imports
      │               │
      ▼               ▼
recurrence/flaky   impact traversal
      │               │
      └──────┬────────┘
             ▼
Reports
terminal / JSON / Markdown / HTML / SARIF
```

## Design principles

1. **Local first.** Analysis must remain useful with no RootTrace cloud service.
2. **Deterministic core.** Parsing, fingerprints, history, correlations, and scores do not require an LLM.
3. **Evidence before explanation.** The tool distinguishes observed signals from hypotheses.
4. **Adapters over conditionals.** Framework support lives behind parser interfaces and plugin entry points.
5. **Graceful uncertainty.** Unknown failures remain unknown rather than being forced into a confident category.
6. **Portable artifacts.** JSON and SARIF let other systems consume results without coupling to the CLI UI.

## Storage

SQLite is used because the state is relational, queryable, transactional, local, and needs no server. A run records its source, parser, commit, branch, changed files, failures, and test outcomes.

## Extensibility

The parser registry loads built-ins plus packages registered under `roottrace.parsers`. Future language-specific impact engines can follow the same adapter model.
