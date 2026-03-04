#!/usr/bin/env bash
# Launches the Claude Limits widget in the background.
# Run this from anywhere; it resolves its own path.
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/widget.py" &
