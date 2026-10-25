#!/usr/bin/env bash
# Assemble a self-contained deployment folder (dist/) for AgentCore: entrypoint + shared agent code.
set -euo pipefail
cd "$(dirname "$0")"
rm -rf dist && mkdir -p dist
cp agentcore_app.py requirements.txt dist/
cp -R ../api/app dist/app
find dist -name "__pycache__" -prune -exec rm -rf {} +
echo "dist/ ready. See docs/aws-setup.md (Mode C) for deploy steps."
