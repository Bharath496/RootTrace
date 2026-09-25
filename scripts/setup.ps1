$ErrorActionPreference = "Stop"
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install -e .
Write-Host "RootTrace installed. Run: roottrace doctor"
