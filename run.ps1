# Thin wrapper: all the work happens in scripts/run_all.py
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python scripts/run_all.py @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
