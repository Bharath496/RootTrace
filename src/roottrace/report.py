from __future__ import annotations

import html
import json
from pathlib import Path

from roottrace.db import HistoryDB
from roottrace.models import AnalysisRun


def render_terminal(run: AnalysisRun, db: HistoryDB | None = None) -> str:
    lines = [
        "ROOTTRACE ANALYSIS", "=" * 78,
        f"Source: {run.source}", f"Parser: {run.parser}", f"Commit: {run.commit or 'unknown'}",
        f"Branch: {run.branch or 'unknown'}", f"Changed files: {len(run.changed_files)}",
        f"Tests observed: {len(run.tests)}", f"Failures found: {len(run.failures)}",
    ]
    if not run.failures:
        lines += ["", "No recognized failures were found in this input."]
        return "\n".join(lines)
    for i, f in enumerate(run.failures, 1):
        lines += ["", f"[{i}] {f.category.upper()} / {f.subtype}", f"Fingerprint: {f.fingerprint}", f"Confidence: {int(f.confidence * 100)}%", f"Framework: {f.framework}"]
        if f.occurrence_count:
            lines.append(f"History: seen {f.occurrence_count} time(s)" + (f", flaky score {f.flaky_score:.2f}" if f.flaky_score is not None else ""))
        if f.test: lines.append(f"Test: {f.test}")
        if f.file: lines.append(f"Location: {f.file}" + (f":{f.line}" if f.line else ""))
        if f.exception: lines.append(f"Exception: {f.exception}")
        lines.append(f"Message: {f.message}")
        if f.candidates:
            lines.append("Probable causes:")
            for c in f.candidates[:3]:
                loc = f" [{c.file}]" if c.file else ""
                lines.append(f"  {int(c.score * 100):>3}% {c.label}{loc}")
                for reason in c.rationale[:2]: lines.append(f"      - {reason}")
        if f.evidence:
            lines.append("Evidence:")
            for ev in f.evidence:
                lines.append(f"  {'+' if ev.weight >= 0 else '-'} {ev.message}")
        if f.reproduction:
            lines.append(f"Reproduce: {f.reproduction}")
    return "\n".join(lines)


def _markdown(run: AnalysisRun) -> str:
    lines = ["# RootTrace Analysis", "", f"- **Source:** `{run.source}`", f"- **Parser:** `{run.parser}`", f"- **Commit:** `{run.commit or 'unknown'}`", f"- **Branch:** `{run.branch or 'unknown'}`", f"- **Failures:** {len(run.failures)}", f"- **Tests observed:** {len(run.tests)}", ""]
    for i, f in enumerate(run.failures, 1):
        lines += [f"## {i}. {f.category} / {f.subtype}", "", f"**Fingerprint:** `{f.fingerprint}`  ", f"**Confidence:** {int(f.confidence*100)}%  "]
        if f.test: lines.append(f"**Test:** `{f.test}`  ")
        if f.file: lines.append(f"**Location:** `{f.file}{':' + str(f.line) if f.line else ''}`  ")
        if f.exception: lines.append(f"**Exception:** `{f.exception}`  ")
        lines += ["", f.message, "", "### Probable causes"]
        for c in f.candidates:
            lines.append(f"- **{int(c.score*100)}%** {c.label}" + (f" (`{c.file}`)" if c.file else ""))
            for r in c.rationale[:2]: lines.append(f"  - {r}")
        lines += ["", "### Evidence"]
        for ev in f.evidence: lines.append(f"- {ev.message}")
        if f.reproduction:
            lines += ["", "### Reproduction", "```bash", f.reproduction, "```"]
        lines.append("")
    return "\n".join(lines) + "\n"


def _html(run: AnalysisRun) -> str:
    cards = []
    for f in run.failures:
        causes = "".join(f"<li><strong>{int(c.score*100)}%</strong> {html.escape(c.label)} {('<code>'+html.escape(c.file)+'</code>') if c.file else ''}</li>" for c in f.candidates[:5])
        evidence = "".join(f"<li>{html.escape(e.message)}</li>" for e in f.evidence)
        repro = f"<pre>{html.escape(f.reproduction)}</pre>" if f.reproduction else ""
        cards.append(f"""<section><h2>{html.escape(f.category)} / {html.escape(f.subtype)}</h2>
        <p><b>{html.escape(f.fingerprint)}</b> · confidence {int(f.confidence*100)}% · {html.escape(f.framework)}</p>
        <p>{html.escape(f.message)}</p><h3>Probable causes</h3><ul>{causes}</ul><h3>Evidence</h3><ul>{evidence}</ul>{repro}</section>""")
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>RootTrace report</title><style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;background:#111;color:#eee}}section{{border:1px solid #333;border-radius:12px;padding:20px;margin:18px 0;background:#171717}}code,pre{{background:#242424;padding:3px 6px;border-radius:5px}}pre{{overflow:auto;padding:12px}}.meta{{color:#bbb}}h1,h2{{margin-bottom:.3em}}</style></head><body>
<h1>RootTrace Analysis</h1><p class='meta'>Source: {html.escape(run.source)} · Parser: {html.escape(run.parser)} · Commit: {html.escape(run.commit or 'unknown')} · Failures: {len(run.failures)}</p>{''.join(cards) or '<section><h2>No recognized failures</h2></section>'}</body></html>"""


def _sarif(run: AnalysisRun) -> dict:
    rules: dict[str, dict] = {}
    results = []
    for f in run.failures:
        rule_id = f"roottrace/{f.category}/{f.subtype}"
        rules.setdefault(rule_id, {"id": rule_id, "name": f.subtype, "shortDescription": {"text": f"RootTrace {f.category} failure"}})
        result: dict = {"ruleId": rule_id, "level": "error", "message": {"text": f.message}, "properties": {"fingerprint": f.fingerprint, "confidence": f.confidence}}
        if f.file:
            region = {"startLine": max(1, f.line or 1)}
            result["locations"] = [{"physicalLocation": {"artifactLocation": {"uri": f.file}, "region": region}}]
        results.append(result)
    return {"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0", "runs": [{"tool": {"driver": {"name": "RootTrace", "version": "1.0.0", "rules": list(rules.values())}}, "results": results}]}


def write_reports(run: AnalysisRun, reports_dir: Path, db: HistoryDB | None = None) -> dict[str, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stem = f"run-{run.run_id or 'unsaved'}"
    paths = {ext: reports_dir / f"{stem}.{ext}" for ext in ("json", "md", "html", "sarif")}
    paths["json"].write_text(json.dumps(run.to_dict(), indent=2) + "\n", encoding="utf-8")
    paths["md"].write_text(_markdown(run), encoding="utf-8")
    paths["html"].write_text(_html(run), encoding="utf-8")
    paths["sarif"].write_text(json.dumps(_sarif(run), indent=2) + "\n", encoding="utf-8")
    return paths


def write_history_dashboard(db: HistoryDB, reports_dir: Path) -> Path:
    summary = db.summary()
    flaky = db.flaky_tests()
    recent = db.recent_runs(50)
    categories = "".join(f"<li>{html.escape(str(c['category']))}: {c['count']}</li>" for c in summary["categories"]) or "<li>No failures recorded.</li>"
    flaky_html = "".join(f"<li>{html.escape(str(t['framework']))} · {html.escape(str(t['test']))} · score {float(t['flaky_score']):.2f} · {t['passed']} pass / {t['failed']} fail</li>" for t in flaky) or "<li>No flaky tests meet the configured threshold yet.</li>"
    rows = []
    for r in recent:
        report = reports_dir / f"run-{r['id']}.html"
        source = html.escape(str(r['source']))
        link = f"<a href='run-{r['id']}.html'>run {r['id']}</a>" if report.exists() else f"run {r['id']}"
        rows.append(f"<tr><td>{link}</td><td>{r['failure_count']}</td><td>{html.escape(str(r['parser']))}</td><td>{html.escape((r['commit_hash'] or 'unknown')[:10])}</td><td>{html.escape(str(r['branch'] or 'unknown'))}</td><td>{source}</td></tr>")
    recent_html = "".join(rows) or "<tr><td colspan='6'>No runs recorded.</td></tr>"
    body = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>RootTrace history</title><style>body{{font-family:system-ui;max-width:1180px;margin:40px auto;padding:0 20px;background:#111;color:#eee}}a{{color:#8ab4f8}}.stats{{display:flex;gap:20px;flex-wrap:wrap}}.stat{{padding:18px;border:1px solid #333;background:#171717;border-radius:10px;min-width:150px}}table{{width:100%;border-collapse:collapse;background:#171717}}th,td{{padding:10px;border-bottom:1px solid #333;text-align:left;vertical-align:top}}th{{color:#bbb}}code{{background:#242424;padding:2px 5px;border-radius:4px}}</style></head><body><h1>RootTrace History</h1><div class='stats'><div class='stat'><b>{summary['runs']}</b><br>runs</div><div class='stat'><b>{summary['failures']}</b><br>failures</div><div class='stat'><b>{summary['test_outcomes']}</b><br>test outcomes</div></div><h2>Recent analyses</h2><table><thead><tr><th>Run</th><th>Failures</th><th>Parser</th><th>Commit</th><th>Branch</th><th>Source</th></tr></thead><tbody>{recent_html}</tbody></table><h2>Failure categories</h2><ul>{categories}</ul><h2>Potentially flaky tests</h2><ul>{flaky_html}</ul></body></html>"""
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "history.html"
    path.write_text(body, encoding="utf-8")
    return path
