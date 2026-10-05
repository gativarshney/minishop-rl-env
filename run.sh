#!/bin/bash
set -e
echo "Building env..."
cd env
mkdir -p build
cd build
cmake ..
cmake --build . --config Release
cd ../..
echo "Running RL task..."
python3 scripts/run_all.py
echo "Analyzing..."
python3 scripts/analyze.py
echo "Done!"
