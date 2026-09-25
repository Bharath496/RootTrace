#!/usr/bin/env sh
set -eu
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
echo "RootTrace installed. Run: roottrace doctor"
