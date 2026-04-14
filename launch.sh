#!/usr/bin/env bash
# Launches the Claude Limits widget in the background.
# Run this from anywhere; it resolves its own path.
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$DIR/.venv/bin/python3"
[[ -x "$PYTHON" ]] || PYTHON=python3   # fallback if venv missing
exec "$PYTHON" "$DIR/widget.py" &
