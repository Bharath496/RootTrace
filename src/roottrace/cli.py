from __future__ import annotations

import argparse
import json
import os
import functools
import http.server
import platform
import shutil
import sys
from pathlib import Path

from roottrace import __version__
from roottrace.analyzer import analyze_text, decorate_with_history
from roottrace.benchmark import run_benchmark
from roottrace.config import DB_FILE, REPORTS_DIR, initialize, load_config
from roottrace.db import HistoryDB
from roottrace.gitinfo import changed_files, changed_files_between, current_branch, current_commit, is_repository
from roottrace.impact import impacted_files, likely_tests
from roottrace.local_ai import explain_with_ollama
from roottrace.models import Failure
from roottrace.parsers import parser_names
from roottrace.report import render_terminal, write_history_dashboard, write_reports


def _project_dir(raw: str | None) -> Path:
    return Path(raw or ".").resolve()


def _db(project: Path) -> HistoryDB:
    rt = initialize(project)
    return HistoryDB(rt / DB_FILE)


def _read_sources(inputs: list[str]) -> list[tuple[str, str]]:
    if inputs == ["-"]:
        return [("stdin", sys.stdin.read())]
    sources: list[tuple[str, str]] = []
    for raw in inputs:
        path = Path(raw).resolve()
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in {".log", ".txt", ".xml", ".out"}:
                    sources.append((str(child), child.read_text(encoding="utf-8", errors="replace")))
        elif path.is_file():
            sources.append((str(path), path.read_text(encoding="utf-8", errors="replace")))
        else:
            raise FileNotFoundError(raw)
    return sources


def cmd_init(args: argparse.Namespace) -> int:
    project = _project_dir(args.project)
    rt = initialize(project)
    with HistoryDB(rt / DB_FILE): pass
    print(f"RootTrace {__version__} initialized at {rt}")
    print("Privacy default: no network calls. Analysis and history remain local.")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    project = _project_dir(args.project)
    rt = initialize(project)
    detected = 0
    try: sources = _read_sources(args.inputs)
    except (OSError, FileNotFoundError) as exc:
        print(f"roottrace: cannot read input: {exc}", file=sys.stderr); return 2
    if not sources:
        print("roottrace: no supported log/XML files found", file=sys.stderr); return 2
    with HistoryDB(rt / DB_FILE) as db:
        for index, (source, text) in enumerate(sources, 1):
            run = analyze_text(text, source, project, args.parser, args.commit)
            db.save_run(run); decorate_with_history(run, db)
            paths = write_reports(run, rt / REPORTS_DIR, db)
            detected += len(run.failures)
            if len(sources) > 1: print(f"\n### INPUT {index}/{len(sources)} ###")
            print(render_terminal(run, db)); print("\nReports:")
            for kind, path in paths.items(): print(f"  {kind.upper():5} {path}")
    return 1 if args.fail_on_detected and detected else 0


def cmd_history(args: argparse.Namespace) -> int:
    project = _project_dir(args.project)
    with _db(project) as db:
        rows = db.recent_runs(args.limit)
        if not rows:
            print("No RootTrace runs recorded yet."); return 0
        print("ID   FAIL  PARSER         COMMIT       BRANCH         SOURCE"); print("-" * 110)
        for row in rows:
            commit = (row["commit_hash"] or "unknown")[:10]; branch = (row["branch"] or "unknown")[:14]
            print(f"{row['id']:<4} {row['failure_count']:<5} {row['parser']:<14} {commit:<12} {branch:<14} {row['source']}")
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    project = _project_dir(args.project)
    with _db(project) as db:
        rows = db.failure_by_fingerprint(args.fingerprint)
        if not rows:
            print(f"No recorded failure with fingerprint {args.fingerprint.upper()}"); return 2
        first = rows[0]
        print(f"Fingerprint: {first['fingerprint']}"); print(f"Occurrences: {len(rows)}")
        print(f"Category: {first['category']} / {first['subtype']}"); print(f"Framework: {first['framework']}")
        print(f"Exception: {first['exception'] or 'unknown'}"); print(f"Latest message: {first['message']}")
        if first["reproduction"]: print(f"Reproduce: {first['reproduction']}")
        candidates = json.loads(first["candidates_json"] or "[]")
        if candidates:
            print("\nProbable causes:")
            for c in candidates[:5]: print(f"  {int(float(c['score'])*100):>3}% {c['label']}" + (f" [{c['file']}]" if c.get("file") else ""))
        print("\nHistory:")
        for row in rows[:30]: print(f"  run={row['run_id']} commit={(row['commit_hash'] or 'unknown')[:10]} branch={row['branch'] or 'unknown'} source={row['source']}")
        if args.ollama:
            failure = Failure(first["category"], first["subtype"], first["message"], first["framework"], first["test_name"], first["file_path"], first["line_number"], first["exception"], fingerprint=first["fingerprint"], confidence=float(first["confidence"]))
            print("\nLOCAL MODEL EXPLANATION\n" + "-" * 78)
            try: print(explain_with_ollama(failure, args.ollama))
            except RuntimeError as exc:
                print(f"Local AI unavailable: {exc}", file=sys.stderr); return 3
    return 0


def cmd_flaky(args: argparse.Namespace) -> int:
    project = _project_dir(args.project); cfg = load_config(project)
    min_runs = args.min_runs or int(cfg["analysis"]["flaky_min_runs"])
    threshold = args.threshold if args.threshold is not None else float(cfg["analysis"]["flaky_threshold"])
    with _db(project) as db: rows = db.flaky_tests(min_runs, threshold, args.limit)
    if not rows:
        print(f"No tests meet flaky threshold {threshold:.2f} with at least {min_runs} recorded outcomes."); return 0
    print("SCORE  RUNS  PASS  FAIL  FRAMEWORK  TEST"); print("-" * 100)
    for row in rows: print(f"{float(row['flaky_score']):.2f}   {row['total']:<5} {row['passed']:<5} {row['failed']:<5} {row['framework']:<10} {row['test']}")
    return 0


def _render_impact(project: Path, changed: list[str], depth: int) -> int:
    if not changed:
        print("No changed files found for the requested revision range."); return 0
    impact = impacted_files(project, changed, depth)
    print("CHANGE IMPACT"); print("=" * 78); print("Changed:")
    for file in changed: print(f"  [0] {file}")
    indirect = [(f, d) for f, d in impact.items() if d > 0]
    print("\nPotentially impacted:")
    if indirect:
        for file, distance in indirect: print(f"  [{distance}] {file}")
    else: print("  No local dependents discovered by the static graph.")
    tests = likely_tests(impact); print("\nCandidate tests:")
    if tests:
        for file, distance in tests: print(f"  [{distance}] {file}")
    else: print("  No test files discovered in the impact graph.")
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    project = _project_dir(args.project)
    if not is_repository(project): print("RootTrace impact analysis requires a Git repository.", file=sys.stderr); return 2
    changed = changed_files_between(project, args.base, args.head) if args.base else changed_files(project)
    return _render_impact(project, changed, args.depth)


def cmd_compare(args: argparse.Namespace) -> int:
    project = _project_dir(args.project)
    if not is_repository(project): print("RootTrace compare requires a Git repository.", file=sys.stderr); return 2
    changed = changed_files_between(project, args.base, args.head)
    print(f"Comparing {args.base}..{args.head}\n")
    return _render_impact(project, changed, args.depth)


def cmd_report(args: argparse.Namespace) -> int:
    project = _project_dir(args.project); rt = initialize(project)
    with HistoryDB(rt / DB_FILE) as db:
        path = write_history_dashboard(db, rt / REPORTS_DIR); summary = db.summary()
    print(f"History report: {path}"); print(f"Runs: {summary['runs']}  Failures: {summary['failures']}  Test outcomes: {summary['test_outcomes']}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    project = _project_dir(args.project); cfg = load_config(project)
    checks = [("RootTrace",__version__),("Python",platform.python_version()),("Platform",platform.platform()),("Project",str(project)),("Git executable",shutil.which("git") or "NOT FOUND"),("Git repository","yes" if is_repository(project) else "no"),("Current commit",current_commit(project) or "unknown"),("Current branch",current_branch(project) or "unknown"),("Parsers",", ".join(parser_names())),("Network access",str(bool(cfg.get("privacy",{}).get("network_access",False))).lower()),("Ollama (optional)",shutil.which("ollama") or "not installed")]
    width = max(len(k) for k, _ in checks)
    for key, value in checks: print(f"{key:<{width}} : {value}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    project = _project_dir(args.project); rt = initialize(project)
    with HistoryDB(rt / DB_FILE) as db: write_history_dashboard(db, rt / REPORTS_DIR)
    directory = rt / REPORTS_DIR
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"RootTrace local UI: http://127.0.0.1:{args.port}/history.html"); print("Serving localhost only. Press Ctrl+C to stop.")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    project = _project_dir(args.project); manifest = Path(args.manifest).resolve()
    if not manifest.is_file(): print(f"Benchmark manifest not found: {manifest}", file=sys.stderr); return 2
    result = run_benchmark(manifest, project)
    print(f"Benchmark: {result['correct']}/{result['total']} correct ({float(result['accuracy'])*100:.1f}%)")
    for row in result["results"]:
        status = "PASS" if row["ok"] else "FAIL"; print(f"  {status:4} {row['name']}")
        if not row["ok"]: print(f"       expected={row['expected']} actual={row['actual']}")
    return 0 if result["correct"] == result["total"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="roottrace", description="Local-first CI failure and root-cause intelligence")
    p.add_argument("--project", help="Repository/project directory (default: current directory)")
    p.add_argument("--version", action="version", version=f"RootTrace {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    q=sub.add_parser("init",help="Initialize local RootTrace state"); q.set_defaults(func=cmd_init)
    q=sub.add_parser("analyze",help="Analyze one or more CI/test logs or a directory"); q.add_argument("inputs",nargs="+"); q.add_argument("--parser",choices=parser_names()); q.add_argument("--commit"); q.add_argument("--fail-on-detected",action="store_true"); q.set_defaults(func=cmd_analyze)
    q=sub.add_parser("history",help="Show recent analyses"); q.add_argument("--limit",type=int,default=20); q.set_defaults(func=cmd_history)
    q=sub.add_parser("explain",help="Explain a failure fingerprint and its history"); q.add_argument("fingerprint"); q.add_argument("--ollama",metavar="MODEL"); q.set_defaults(func=cmd_explain)
    q=sub.add_parser("flaky",help="Find tests with both pass and fail history"); q.add_argument("--min-runs",type=int); q.add_argument("--threshold",type=float); q.add_argument("--limit",type=int,default=100); q.set_defaults(func=cmd_flaky)
    q=sub.add_parser("impact",help="Analyze changed files and likely impacted dependents/tests"); q.add_argument("--base"); q.add_argument("--head",default="HEAD"); q.add_argument("--depth",type=int,default=3); q.set_defaults(func=cmd_impact)
    q=sub.add_parser("compare",help="Compare two Git refs and run change-impact analysis"); q.add_argument("base"); q.add_argument("head"); q.add_argument("--depth",type=int,default=3); q.set_defaults(func=cmd_compare)
    q=sub.add_parser("report",help="Build local HTML history/flakiness dashboard"); q.set_defaults(func=cmd_report)
    q=sub.add_parser("serve",help="Serve the local HTML reports on localhost only"); q.add_argument("--port",type=int,default=8765); q.set_defaults(func=cmd_serve)
    q=sub.add_parser("doctor",help="Check the local RootTrace environment"); q.set_defaults(func=cmd_doctor)
    q=sub.add_parser("benchmark",help="Evaluate RootTrace against a local benchmark manifest"); q.add_argument("manifest"); q.set_defaults(func=cmd_benchmark)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser(); args = parser.parse_args(argv)
    try: return int(args.func(args))
    except KeyboardInterrupt: return 130
    except Exception as exc:
        if os.environ.get("ROOTTRACE_DEBUG"): raise
        print(f"roottrace: {type(exc).__name__}: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
