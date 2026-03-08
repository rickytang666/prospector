#!/bin/bash
set -e

echo "Clearing __pycache__..."
find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} +

echo "Waiting 3 seconds..."
sleep 3

echo "Starting app..."
.venv/bin/uvicorn main:app
