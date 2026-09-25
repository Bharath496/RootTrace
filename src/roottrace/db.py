from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from roottrace.models import AnalysisRun

_SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    parser TEXT NOT NULL,
    commit_hash TEXT,
    branch TEXT,
    changed_files_json TEXT NOT NULL,
    failure_count INTEGER NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    category TEXT NOT NULL,
    subtype TEXT NOT NULL,
    framework TEXT NOT NULL,
    test_name TEXT,
    file_path TEXT,
    line_number INTEGER,
    exception TEXT,
    message TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence_json TEXT NOT NULL,
    candidates_json TEXT NOT NULL DEFAULT '[]',
    reproduction TEXT,
    FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS test_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    framework TEXT NOT NULL,
    test_name TEXT NOT NULL,
    status TEXT NOT NULL,
    duration REAL,
    file_path TEXT,
    message TEXT,
    FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_failures_fingerprint ON failures(fingerprint);
CREATE INDEX IF NOT EXISTS idx_failures_run_id ON failures(run_id);
CREATE INDEX IF NOT EXISTS idx_tests_name ON test_outcomes(framework, test_name);
CREATE INDEX IF NOT EXISTS idx_tests_run ON test_outcomes(run_id);
"""


class HistoryDB:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self._migrate()

    def _columns(self, table: str) -> set[str]:
        return {str(r["name"]) for r in self.conn.execute(f"PRAGMA table_info({table})")}

    def _migrate(self) -> None:
        run_cols = self._columns("runs")
        if "branch" not in run_cols:
            self.conn.execute("ALTER TABLE runs ADD COLUMN branch TEXT")
        if "metadata_json" not in run_cols:
            self.conn.execute("ALTER TABLE runs ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
        fail_cols = self._columns("failures")
        if "candidates_json" not in fail_cols:
            self.conn.execute("ALTER TABLE failures ADD COLUMN candidates_json TEXT NOT NULL DEFAULT '[]'")
        if "reproduction" not in fail_cols:
            self.conn.execute("ALTER TABLE failures ADD COLUMN reproduction TEXT")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "HistoryDB":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def save_run(self, run: AnalysisRun) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs(created_at,source,parser,commit_hash,branch,changed_files_json,failure_count,metadata_json) VALUES(?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), run.source, run.parser, run.commit, run.branch, json.dumps(run.changed_files), len(run.failures), json.dumps(run.metadata)),
        )
        run_id = int(cur.lastrowid)
        for f in run.failures:
            self.conn.execute(
                """INSERT INTO failures(
                run_id,fingerprint,category,subtype,framework,test_name,file_path,line_number,exception,message,confidence,evidence_json,candidates_json,reproduction
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run_id, f.fingerprint, f.category, f.subtype, f.framework, f.test, f.file, f.line, f.exception, f.message, f.confidence,
                 json.dumps([{"kind": e.kind, "message": e.message, "weight": e.weight} for e in f.evidence]),
                 json.dumps([{"label": c.label, "score": c.score, "rationale": c.rationale, "file": c.file, "line": c.line} for c in f.candidates]),
                 f.reproduction),
            )
        for t in run.tests:
            self.conn.execute(
                "INSERT INTO test_outcomes(run_id,framework,test_name,status,duration,file_path,message) VALUES(?,?,?,?,?,?,?)",
                (run_id, t.framework, t.test, t.status, t.duration, t.file, t.message),
            )
        self.conn.commit()
        run.run_id = run_id
        return run_id

    def recent_runs(self, limit: int = 10) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)))

    def failure_by_fingerprint(self, fingerprint: str) -> list[sqlite3.Row]:
        return list(self.conn.execute(
            """SELECT f.*, r.created_at, r.source, r.commit_hash, r.branch
            FROM failures f JOIN runs r ON r.id=f.run_id
            WHERE f.fingerprint=? ORDER BY f.id DESC""", (fingerprint.upper(),)))

    def fingerprint_stats(self, fingerprint: str) -> dict[str, object]:
        row = self.conn.execute(
            """SELECT COUNT(*) n, MIN(r.created_at) first_seen, MAX(r.created_at) last_seen
            FROM failures f JOIN runs r ON r.id=f.run_id WHERE f.fingerprint=?""", (fingerprint.upper(),)).fetchone()
        return {"count": int(row["n"] or 0), "first_seen": row["first_seen"], "last_seen": row["last_seen"]}

    def fingerprint_count(self, fingerprint: str) -> int:
        return int(self.fingerprint_stats(fingerprint)["count"])

    def test_stats(self, framework: str, test_name: str, limit: int = 100) -> dict[str, float | int]:
        rows = list(self.conn.execute(
            """SELECT status FROM test_outcomes WHERE framework=? AND test_name=?
            ORDER BY id DESC LIMIT ?""", (framework, test_name, limit)))
        total = len(rows)
        passed = sum(1 for r in rows if r["status"] == "passed")
        failed = sum(1 for r in rows if r["status"] in {"failed", "error"})
        transitions = sum(1 for a, b in zip(rows, rows[1:]) if a["status"] != b["status"])
        if total == 0:
            score = 0.0
        else:
            balance = min(passed, failed) / max(1, total)
            transition_rate = transitions / max(1, total - 1)
            score = min(1.0, (balance * 1.4) + (transition_rate * 0.6))
        return {"total": total, "passed": passed, "failed": failed, "transitions": transitions, "flaky_score": round(score, 3)}

    def flaky_tests(self, min_runs: int = 3, threshold: float = 0.25, limit: int = 100) -> list[dict[str, object]]:
        names = list(self.conn.execute(
            """SELECT framework,test_name,COUNT(*) n FROM test_outcomes
            GROUP BY framework,test_name HAVING COUNT(*)>=? ORDER BY n DESC LIMIT ?""", (min_runs, limit)))
        results: list[dict[str, object]] = []
        for row in names:
            stats = self.test_stats(row["framework"], row["test_name"], limit=500)
            if float(stats["flaky_score"]) >= threshold and int(stats["passed"]) > 0 and int(stats["failed"]) > 0:
                results.append({"framework": row["framework"], "test": row["test_name"], **stats})
        return sorted(results, key=lambda x: (-float(x["flaky_score"]), -int(x["total"])))

    def summary(self) -> dict[str, object]:
        runs = int(self.conn.execute("SELECT COUNT(*) n FROM runs").fetchone()["n"])
        failures = int(self.conn.execute("SELECT COUNT(*) n FROM failures").fetchone()["n"])
        tests = int(self.conn.execute("SELECT COUNT(*) n FROM test_outcomes").fetchone()["n"])
        categories = [dict(r) for r in self.conn.execute("SELECT category,COUNT(*) count FROM failures GROUP BY category ORDER BY count DESC")]
        return {"runs": runs, "failures": failures, "test_outcomes": tests, "categories": categories}
