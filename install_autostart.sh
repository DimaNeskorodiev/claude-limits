#!/usr/bin/env bash
# Installs a launchd agent so the widget starts automatically at login.
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.claude.limits.widget.plist"
PYTHON="$(which python3)"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.claude.limits.widget</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$DIR/widget.py</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>$HOME/.claude_widget_stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$HOME/.claude_widget_stderr.log</string>
</dict>
</plist>
EOF

launchctl load "$PLIST" 2>/dev/null || true
echo "✓ Auto-start installed. Widget will launch at next login."
echo "  To start it now:  launchctl start com.claude.limits.widget"
echo "  To remove:        launchctl unload \"$PLIST\" && rm \"$PLIST\""
