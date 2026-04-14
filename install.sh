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
FILES=(widget.py requirements.txt uninstall.sh launch.sh generate_icon.py)

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

# ── 5. Create virtualenv + install Python dependencies ───────────────────────
header "Installing Python dependencies…"
info "This may take a minute on first run…"

VENV_DIR="$INSTALL_DIR/.venv"
"$PYTHON" -m venv "$VENV_DIR"
VENV_PYTHON="$VENV_DIR/bin/python3"
"$VENV_PYTHON" -m pip install -r "$INSTALL_DIR/requirements.txt" --quiet --upgrade
success "Dependencies installed (virtualenv: $VENV_DIR)"

# ── 6. Remove quarantine attribute (macOS Gatekeeper) ────────────────────────
xattr -rd com.apple.quarantine "$INSTALL_DIR" 2>/dev/null || true

# ── 7. Create .app bundle in ~/Applications ───────────────────────────────────
header "Creating application bundle…"

APP_DIR="$HOME/Applications/Claude Limits.app"
APP_MACOS="$APP_DIR/Contents/MacOS"
APP_RES="$APP_DIR/Contents/Resources"

mkdir -p "$APP_MACOS" "$APP_RES"

# Launcher executable inside the bundle
cat > "$APP_MACOS/Claude Limits" <<LAUNCHER_EOF
#!/usr/bin/env bash
exec "${VENV_PYTHON}" "${INSTALL_DIR}/widget.py" &>/dev/null &
LAUNCHER_EOF
chmod +x "$APP_MACOS/Claude Limits"

# Generate app icon (runs in the venv which already has pyobjc)
[[ -f "$INSTALL_DIR/generate_icon.py" ]] || \
    curl -fsSL "$RAW_BASE/generate_icon.py" -o "$INSTALL_DIR/generate_icon.py"

if "$VENV_PYTHON" "$INSTALL_DIR/generate_icon.py" "$APP_RES/AppIcon.icns" 2>/dev/null; then
    ICON_KEY='<key>CFBundleIconFile</key><string>AppIcon</string>'
else
    warn "Icon generation skipped (will use default macOS icon)"
    ICON_KEY=''
fi

# Info.plist — LSUIElement hides the dock icon (menu-bar-only app)
cat > "$APP_DIR/Contents/Info.plist" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Claude Limits</string>
  <key>CFBundleDisplayName</key>
  <string>Claude Limits</string>
  <key>CFBundleIdentifier</key>
  <string>com.claude.limits.widget</string>
  <key>CFBundleVersion</key>
  <string>1.0</string>
  <key>CFBundleExecutable</key>
  <string>Claude Limits</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  ${ICON_KEY}
  <key>LSUIElement</key>
  <true/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST_EOF

# Remove quarantine so macOS won't block the bundle on first launch
xattr -rd com.apple.quarantine "$APP_DIR" 2>/dev/null || true

success "App bundle created: $APP_DIR"
info  "Open Finder → ~/Applications to add it to your Dock or Launchpad."

# ── 9. LaunchAgent (auto-start at login) ─────────────────────────────────────
header "Configuring auto-start at login…"

LOG_DIR="$HOME/Library/Logs/ClaudeLimits"
mkdir -p "$LOG_DIR"

# Kill any stale widget process before touching the agent
pkill -f "widget.py" 2>/dev/null || true
sleep 0.5

# Unload old agent — use modern bootout (macOS 13+), fall back to legacy unload
launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null \
    || launchctl unload "$PLIST_PATH" 2>/dev/null \
    || true

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
    <string>${VENV_PYTHON}</string>
    <string>${INSTALL_DIR}/widget.py</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
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

# Load agent — use modern bootstrap (macOS 13+), fall back to legacy load.
# RunAtLoad=true means launchd starts the widget immediately AND at every login.
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null \
    || launchctl load "$PLIST_PATH" 2>/dev/null \
    || true

# ── 10. Wait for widget to appear (RunAtLoad handles the actual launch) ────────
header "Launching widget…"

# Give launchd up to 5 s to start the widget via RunAtLoad
for i in 1 2 3 4 5; do
    sleep 1
    if pgrep -f "widget.py" &>/dev/null; then
        success "Widget is running!"
        break
    fi
    [[ $i -eq 5 ]] && warn "Widget did not start automatically — try opening it from ~/Applications or running: launchctl start ${PLIST_LABEL}"
done

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
