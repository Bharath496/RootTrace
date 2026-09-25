from __future__ import annotations

import json
import shutil
import subprocess

from roottrace.models import Failure


def explain_with_ollama(failure: Failure, model: str) -> str:
    """Optional, local-only explanation. RootTrace never requires this path."""
    if not shutil.which("ollama"):
        raise RuntimeError("Ollama is not installed or not available on PATH.")
    payload = {
        "failure": failure.to_dict(),
        "instruction": "Explain the evidence conservatively. Do not invent facts. Separate observed evidence from hypotheses and give local debugging steps.",
    }
    prompt = json.dumps(payload, indent=2)
    proc = subprocess.run(["ollama", "run", model, prompt], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "Local model execution failed")
    return proc.stdout.strip()
