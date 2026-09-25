from __future__ import annotations

import json
from pathlib import Path

from roottrace.analyzer import analyze_text


def run_benchmark(manifest_path: Path, project_dir: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest.get("cases", [])
    results = []
    correct = 0
    for case in cases:
        artifact = (manifest_path.parent / case["file"]).resolve()
        text = artifact.read_text(encoding="utf-8", errors="replace")
        run = analyze_text(text, str(artifact), project_dir, case.get("force_parser"))
        first = run.failures[0] if run.failures else None
        actual = {
            "parser": run.parser,
            "category": first.category if first else None,
            "subtype": first.subtype if first else None,
        }
        expected = case["expected"]
        ok = all(actual.get(k) == v for k, v in expected.items())
        correct += int(ok)
        results.append({"name": case.get("name", case["file"]), "ok": ok, "expected": expected, "actual": actual})
    total = len(results)
    return {"total": total, "correct": correct, "accuracy": (correct / total if total else 0.0), "results": results}
