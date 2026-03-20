#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Claude Limits Widget — one-command installer
#
# Usage (pipe-install from GitHub):
#   curl -fsSL https://raw.githubusercontent.com/GITHUB_USER/claude-limits/main/install.sh | bash
#
# Or clone and run locally:
#   bash install.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Styling ──────────────────────────────────────────────────────────────────
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
RESET='\033[0m'

info()    { echo -e "${CYAN}▶${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET} $*"; }
error()   { echo -e "${RED}✗${RESET} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

# ── Config ────────────────────────────────────────────────────────────────────
RAW_BASE="https://raw.githubusercontent.com/DimaNeskorodiev/claude-limits/main"
INSTALL_DIR="$HOME/Library/Application Support/ClaudeLimits"
PLIST_LABEL="com.claude.limits.widget"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
MIN_PYTHON_MINOR=9    # requires Python 3.9+

# ── Banner ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║       Claude Limits Widget Installer     ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ── 1. macOS check ────────────────────────────────────────────────────────────
header "Checking system requirements…"

if [[ "$(uname)" != "Darwin" ]]; then
    error "This widget requires macOS. Exiting."
    exit 1
fi
success "macOS detected: $(sw_vers -productVersion)"

# ── 2. Python 3 check ────────────────────────────────────────────────────────
# IMPORTANT: /usr/bin/python3 on macOS is a stub — calling it without a real
# Python installed triggers the "No developer tools were found" Xcode dialog.
# We deliberately skip that stub and only use real Python installations.
PYTHON=""

# Ordered list of real Python paths (Homebrew M1, Homebrew Intel, python.org,
# pyenv, version-specific binaries). /usr/bin/python3 is intentionally absent.
CANDIDATES=(
    /opt/homebrew/bin/python3
    /opt/homebrew/bin/python3.13
    /opt/homebrew/bin/python3.12
    /opt/homebrew/bin/python3.11
    /opt/homebrew/bin/python3.10
    /opt/homebrew/bin/python3.9
    /usr/local/bin/python3
    /usr/local/bin/python3.13
    /usr/local/bin/python3.12
    /usr/local/bin/python3.11
    /usr/local/bin/python3.10
    /usr/local/bin/python3.9
    "$HOME/.pyenv/shims/python3"
)

for candidate in "${CANDIDATES[@]}"; do
    if [[ -x "$candidate" ]]; then
        ver=$("$candidate" -c "import sys; print(sys.version_info.minor)" 2>/dev/null) || continue
        if [[ "$ver" -ge "$MIN_PYTHON_MINOR" ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    error "Python 3.${MIN_PYTHON_MINOR}+ not found."
    echo ""
    echo "  ⚠️  Do NOT use the macOS built-in python3 — it requires Xcode."
    echo ""
    echo "  Install a real Python (no Xcode needed) via one of:"
    echo ""
    echo "    Option 1 — python.org installer (recommended, easiest):"
    echo "      https://www.python.org/downloads/"
    echo ""
    echo "    Option 2 — Homebrew:"
    echo "      /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "      brew install python"
    echo ""
    echo "  After installing Python, re-run this installer."
    exit 1
fi
success "Python found: $PYTHON ($($PYTHON --version))"

# ── 3. pip check ─────────────────────────────────────────────────────────────
if ! "$PYTHON" -m pip --version &>/dev/null; then
    error "pip is not available for $PYTHON."
    echo "  Try:  $PYTHON -m ensurepip --upgrade"
    exit 1
fi
success "pip available"

# ── 4. Download / update app files ───────────────────────────────────────────
header "Installing app files…"

mkdir -p "$INSTALL_DIR"

# Files to fetch from GitHub (curl is built into every macOS — no git needed)
FILES=(widget.py requirements.txt uninstall.sh launch.sh)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/widget.py" && "$SCRIPT_DIR" != "$INSTALL_DIR" ]]; then
    # Running from a local checkout — copy files directly
    info "Copying files from local source: $SCRIPT_DIR"
    for f in "${FILES[@]}"; do
        [[ -f "$SCRIPT_DIR/$f" ]] && cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/"
    done
    cp "$SCRIPT_DIR/install.sh" "$INSTALL_DIR/"
else
    # Fresh install or update — download each file via curl (no git required)
    if [[ -f "$INSTALL_DIR/widget.py" ]]; then
        info "Updating to latest version…"
    else
        info "Downloading app files from GitHub…"
    fi
    for f in "${FILES[@]}"; do
        curl -fsSL "$RAW_BASE/$f" -o "$INSTALL_DIR/$f"
    done
    # Always refresh the installer itself too
    curl -fsSL "$RAW_BASE/install.sh" -o "$INSTALL_DIR/install.sh"
    chmod +x "$INSTALL_DIR/install.sh" "$INSTALL_DIR/uninstall.sh" "$INSTALL_DIR/launch.sh"
fi
success "App files ready in: $INSTALL_DIR"

# ── 5. Install Python dependencies ───────────────────────────────────────────
header "Installing Python dependencies…"
info "This may take a minute on first run…"
"$PYTHON" -m pip install -r "$INSTALL_DIR/requirements.txt" --quiet --upgrade
success "Dependencies installed"

# ── 6. Remove quarantine attribute (macOS Gatekeeper) ────────────────────────
xattr -rd com.apple.quarantine "$INSTALL_DIR" 2>/dev/null || true

# ── 7. LaunchAgent (auto-start at login) ─────────────────────────────────────
header "Configuring auto-start at login…"

# Stop any existing instance first
if launchctl list | grep -q "$PLIST_LABEL" 2>/dev/null; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

LOG_DIR="$HOME/Library/Logs/ClaudeLimits"
mkdir -p "$LOG_DIR"

cat > "$PLIST_PATH" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>${INSTALL_DIR}/widget.py</string>
  </array>
  <key>RunAtLoad</key>
  <false/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/stderr.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
PLIST_EOF

launchctl load "$PLIST_PATH" 2>/dev/null || true
success "Auto-start agent installed (starts at next login)"

# ── 8. Launch widget now ──────────────────────────────────────────────────────
header "Launching widget…"

# Kill any stale instance
pkill -f "widget.py" 2>/dev/null || true
sleep 0.5

# Start in background
"$PYTHON" "$INSTALL_DIR/widget.py" &>/dev/null &
sleep 1

success "Widget is running!"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  Claude Limits Widget installed! 🎉     ${RESET}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
echo ""
echo "  Look for the icon in your menu bar (top-right of screen)."
echo "  Click it to see your Claude usage, or click the gear to"
echo "  connect your Claude session."
echo ""
echo "  Logs:       $LOG_DIR/"
echo "  App files:  $INSTALL_DIR/"
echo ""
echo "  To uninstall:"
echo "    bash \"$INSTALL_DIR/uninstall.sh\""
echo ""
