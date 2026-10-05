#!/bin/bash
# Thin wrapper: all the work happens in scripts/run_all.py
set -e
cd "$(dirname "$0")"
python3 scripts/run_all.py "$@"
