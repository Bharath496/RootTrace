from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

ROOTTRACE_DIR = ".roottrace"
CONFIG_FILE = "config.json"
DB_FILE = "history.db"
REPORTS_DIR = "reports"
CACHE_DIR = "cache"

DEFAULT_CONFIG = {
    "version": 1,
    "privacy": {"network_access": False},
    "analysis": {
        "max_failures": 200,
        "include_git_evidence": True,
        "history_window": 100,
        "flaky_min_runs": 3,
        "flaky_threshold": 0.25,
    },
    "impact": {
        "max_depth": 3,
        "extensions": [".py", ".js", ".jsx", ".ts", ".tsx", ".java"],
    },
}


def state_dir(project_dir: Path) -> Path:
    return project_dir / ROOTTRACE_DIR


def initialize(project_dir: Path) -> Path:
    rt_dir = state_dir(project_dir)
    rt_dir.mkdir(parents=True, exist_ok=True)
    (rt_dir / REPORTS_DIR).mkdir(exist_ok=True)
    (rt_dir / CACHE_DIR).mkdir(exist_ok=True)
    config_path = rt_dir / CONFIG_FILE
    if not config_path.exists():
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    return rt_dir


def load_config(project_dir: Path) -> dict:
    config_path = state_dir(project_dir) / CONFIG_FILE
    if not config_path.exists():
        return deepcopy(DEFAULT_CONFIG)
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return deepcopy(DEFAULT_CONFIG)
    cfg = deepcopy(DEFAULT_CONFIG)
    for section, value in loaded.items():
        if isinstance(value, dict) and isinstance(cfg.get(section), dict):
            cfg[section].update(value)
        else:
            cfg[section] = value
    return cfg
