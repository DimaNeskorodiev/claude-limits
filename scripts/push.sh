#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# push.sh — called by the repo-local git alias `push`.
# Bumps the patch version in version.txt + APP_VERSION in widget.py,
# commits the change, then does the actual push.
#
# Using `git -c alias.push=` clears our alias for this one call so the
# recursive git push here goes straight to the built-in command.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_DIR="$(git rev-parse --show-toplevel)"
VERSION_FILE="$REPO_DIR/version.txt"
WIDGET_FILE="$REPO_DIR/widget.py"

# ── Read & bump version ───────────────────────────────────────────────────────
current=$(tr -d '[:space:]' < "$VERSION_FILE")
IFS='.' read -r major minor patch <<< "$current"
new_version="${major}.${minor}.$(( patch + 1 ))"

# ── Update version.txt ────────────────────────────────────────────────────────
printf '%s\n' "$new_version" > "$VERSION_FILE"

# ── Update APP_VERSION in widget.py ──────────────────────────────────────────
python3 - "$WIDGET_FILE" "$new_version" <<'PYEOF'
import sys, re
path, new_v = sys.argv[1], sys.argv[2]
txt = open(path).read()
txt = re.sub(r'(APP_VERSION\s*=\s*")[^"]+(")', r'\g<1>' + new_v + r'\g<2>', txt)
open(path, 'w').write(txt)
PYEOF

# ── Commit the bump ───────────────────────────────────────────────────────────
git -C "$REPO_DIR" add "$VERSION_FILE" "$WIDGET_FILE"
git -C "$REPO_DIR" commit --no-verify -m "Bump version to ${new_version}"

# ── Push — clear the `push` alias for this call to avoid infinite recursion ──
git -C "$REPO_DIR" -c alias.push= push "$@"

echo "▶ Version bumped: ${current} → ${new_version}"
