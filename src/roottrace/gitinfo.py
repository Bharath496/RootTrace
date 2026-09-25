from __future__ import annotations

import subprocess
from pathlib import Path


def _git(project_dir: Path, *args: str, timeout: int = 8) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(project_dir), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip()


def is_repository(project_dir: Path) -> bool:
    return _git(project_dir, "rev-parse", "--is-inside-work-tree") == "true"


def current_commit(project_dir: Path) -> str | None:
    return _git(project_dir, "rev-parse", "HEAD")


def current_branch(project_dir: Path) -> str | None:
    branch = _git(project_dir, "rev-parse", "--abbrev-ref", "HEAD")
    return branch if branch and branch != "HEAD" else None


def changed_files(project_dir: Path, base: str | None = None, head: str = "HEAD") -> list[str]:
    if base:
        output = _git(project_dir, "diff", "--name-only", f"{base}..{head}")
    else:
        output = _git(project_dir, "diff", "--name-only", "HEAD~1", head)
        if output is None:
            output = _git(project_dir, "diff", "--name-only", head)
    if not output:
        # Include uncommitted changes in local use.
        output = _git(project_dir, "status", "--porcelain")
        if not output:
            return []
        return [line[3:].strip().replace("\\", "/") for line in output.splitlines() if len(line) > 3]
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def changed_files_between(project_dir: Path, base: str, head: str) -> list[str]:
    output = _git(project_dir, "diff", "--name-only", f"{base}..{head}")
    if not output:
        return []
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def recent_commits_for_file(project_dir: Path, file: str, limit: int = 5) -> list[dict[str, str]]:
    output = _git(project_dir, "log", f"-{limit}", "--format=%H%x09%ad%x09%s", "--date=iso-strict", "--", file)
    if not output:
        return []
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            rows.append({"commit": parts[0], "date": parts[1], "subject": parts[2]})
    return rows


def show_file_at(project_dir: Path, commit: str, file: str) -> str | None:
    return _git(project_dir, "show", f"{commit}:{file}", timeout=15)
