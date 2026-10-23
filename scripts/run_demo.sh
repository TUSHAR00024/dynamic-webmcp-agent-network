#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "============================================================="
echo "   Launching Dynamic WebMCP Agent Network (Fetch-A-Thon 3.0) "
echo "============================================================="
echo "Starting backend and WebMCP bridge server at http://127.0.0.1:8000"
echo "Open your browser to http://127.0.0.1:8000 to interact with the demo store."
echo "Press Ctrl+C to stop."
echo "============================================================="

python3 backend/app.py
