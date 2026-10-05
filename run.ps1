$ErrorActionPreference = "Stop"
Write-Host "Building env..."
cd env
if (-not (Test-Path build)) { mkdir build }
cd build
cmake ..
cmake --build . --config Release
cd ../..
Write-Host "Running RL task..."
python scripts/run_all.py
Write-Host "Analyzing..."
python scripts/analyze.py
Write-Host "Done!"
