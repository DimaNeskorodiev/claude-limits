#!/usr/bin/env bash
# Claude Limits Widget – one-time setup
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "▶ Creating virtualenv and installing Python dependencies..."
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/python3" -m pip install -r "$DIR/requirements.txt" --quiet

echo "▶ Making scripts executable..."
chmod +x "$DIR/widget.py"
chmod +x "$DIR/launch.sh"

echo ""
echo "✓ Setup complete."
echo ""
echo "Run the widget:"
echo "   ./launch.sh"
echo ""
echo "Or open the widget right now:"
echo "   python3 widget.py"
