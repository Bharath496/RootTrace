from __future__ import annotations

import ast
import re
from collections import defaultdict, deque
from pathlib import Path

_JS_IMPORT = re.compile(r"(?:import\s+.*?\s+from\s+|require\s*\()?[\"'](?P<path>\.{1,2}/[^\"']+)[\"']")
_JAVA_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?(?P<path>[\w.]+);", re.MULTILINE)


def _source_files(project: Path, extensions: set[str]) -> list[Path]:
    ignored = {".git", ".roottrace", ".venv", "venv", "node_modules", "dist", "build", "target", "__pycache__"}
    files: list[Path] = []
    for p in project.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in extensions:
            continue
        if any(part in ignored for part in p.parts):
            continue
        files.append(p)
    return files


def _resolve_python(module: str, current: Path, project: Path) -> Path | None:
    parts = module.split(".")
    candidates = [project.joinpath(*parts).with_suffix(".py"), project.joinpath(*parts, "__init__.py")]
    for c in candidates:
        if c.exists():
            return c
    return None


def _python_deps(path: Path, project: Path) -> list[Path]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return []
    result: list[Path] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = _resolve_python(alias.name, path, project)
                if resolved:
                    result.append(resolved)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.level:
                base = path.parent
                for _ in range(max(0, node.level - 1)):
                    base = base.parent
                candidate = base.joinpath(*node.module.split(".")).with_suffix(".py")
                if candidate.exists():
                    result.append(candidate)
            else:
                resolved = _resolve_python(node.module, path, project)
                if resolved:
                    result.append(resolved)
    return result


def _js_deps(path: Path) -> list[Path]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    result: list[Path] = []
    for match in _JS_IMPORT.finditer(text):
        raw = match.group("path")
        base = (path.parent / raw).resolve()
        candidates = [base, *[base.with_suffix(ext) for ext in (".js", ".jsx", ".ts", ".tsx")], *[(base / "index").with_suffix(ext) for ext in (".js", ".jsx", ".ts", ".tsx")]]
        for c in candidates:
            if c.exists() and c.is_file():
                result.append(c)
                break
    return result


def _java_deps(path: Path, project: Path, java_index: dict[str, Path]) -> list[Path]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    result: list[Path] = []
    for m in _JAVA_IMPORT.finditer(text):
        class_name = m.group("path").split(".")[-1]
        if class_name in java_index:
            result.append(java_index[class_name])
    return result


def build_dependency_graph(project: Path, extensions: set[str] | None = None) -> dict[str, set[str]]:
    extensions = extensions or {".py", ".js", ".jsx", ".ts", ".tsx", ".java"}
    project = project.resolve()
    files = _source_files(project, extensions)
    java_index = {p.stem: p for p in files if p.suffix == ".java"}
    graph: dict[str, set[str]] = defaultdict(set)
    for path in files:
        if path.suffix == ".py":
            deps = _python_deps(path, project)
        elif path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
            deps = _js_deps(path)
        elif path.suffix == ".java":
            deps = _java_deps(path, project, java_index)
        else:
            deps = []
        src = path.relative_to(project).as_posix()
        for dep in deps:
            try:
                dst = dep.resolve().relative_to(project).as_posix()
            except ValueError:
                continue
            graph[src].add(dst)
    return dict(graph)


def impacted_files(project: Path, changed: list[str], max_depth: int = 3) -> dict[str, int]:
    graph = build_dependency_graph(project)
    reverse: dict[str, set[str]] = defaultdict(set)
    for src, deps in graph.items():
        for dep in deps:
            reverse[dep].add(src)
    normalized = [c.replace("\\", "/").lstrip("./") for c in changed]
    distances: dict[str, int] = {c: 0 for c in normalized}
    queue: deque[tuple[str, int]] = deque((c, 0) for c in normalized)
    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for dependent in reverse.get(node, set()):
            nd = depth + 1
            if dependent not in distances or nd < distances[dependent]:
                distances[dependent] = nd
                queue.append((dependent, nd))
    return dict(sorted(distances.items(), key=lambda item: (item[1], item[0])))


def likely_tests(impacted: dict[str, int]) -> list[tuple[str, int]]:
    tests = []
    for file, distance in impacted.items():
        low = file.lower()
        if "/test" in low or low.startswith("test") or "/__tests__/" in low or low.endswith(("test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts")):
            tests.append((file, distance))
    return sorted(tests, key=lambda x: (x[1], x[0]))
