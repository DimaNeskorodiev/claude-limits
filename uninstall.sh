#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Claude Limits Widget — uninstaller
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

PLIST_LABEL="com.claude.limits.widget"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
INSTALL_DIR="$HOME/Library/Application Support/ClaudeLimits"
LOG_DIR="$HOME/Library/Logs/ClaudeLimits"
PREFS_FILE="$HOME/.claude_limits_config.json"

echo ""
echo -e "${BOLD}Claude Limits Widget — Uninstaller${RESET}"
echo ""

# Confirm
read -r -p "  Remove Claude Limits Widget and all its files? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "  Cancelled."
    exit 0
fi

echo ""

# Stop the running widget
echo -e "  Stopping widget process…"
pkill -f "widget.py" 2>/dev/null && echo -e "  ${GREEN}✓${RESET} Process stopped" || echo "  (no running process found)"

# Unload and remove LaunchAgent
if [[ -f "$PLIST_PATH" ]]; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    echo -e "  ${GREEN}✓${RESET} Auto-start agent removed"
fi

# Remove app files
if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
    echo -e "  ${GREEN}✓${RESET} App files removed: $INSTALL_DIR"
fi

# Remove logs
if [[ -d "$LOG_DIR" ]]; then
    rm -rf "$LOG_DIR"
    echo -e "  ${GREEN}✓${RESET} Logs removed: $LOG_DIR"
fi

# Offer to remove saved config / session key
if [[ -f "$PREFS_FILE" ]]; then
    read -r -p "  Remove saved session config ($PREFS_FILE)? [y/N] " del_prefs
    if [[ "$del_prefs" =~ ^[Yy]$ ]]; then
        rm -f "$PREFS_FILE"
        echo -e "  ${GREEN}✓${RESET} Config removed"
    else
        echo "  Config kept at $PREFS_FILE"
    fi
fi

echo ""
echo -e "${BOLD}${GREEN}  Claude Limits Widget uninstalled successfully.${RESET}"
echo ""
