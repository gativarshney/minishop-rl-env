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
python scripts/run_all.py
echo "Analyzing..."
python scripts/analyze.py
echo "Done!"
