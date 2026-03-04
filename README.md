# Claude Limits Widget

> A lightweight macOS menu bar app that shows your **Claude AI usage** in real time — session percentage, weekly usage, and time until reset — right from your menu bar.

---

## Features

- **Live usage ring** — circular progress arc in the menu bar updates every 30 s
- **Color-coded** — fades from white → orange as you approach your limit
- **Popover panel** — click the icon to see current session %, weekly %, and reset time
- **Auto dark/light mode** — adapts instantly when you switch macOS themes
- **Auto-start at login** — installed as a native macOS LaunchAgent
- **Simple setup** — paste your Claude session cookie once; the widget handles the rest

---

## Requirements

| Requirement | Minimum |
|---|---|
| macOS | 12 Monterey or later |
| Python | 3.9 or later |
| Claude plan | Any (Pro / Team / Enterprise) |

> **Python not installed?**
> `brew install python` or download from [python.org](https://www.python.org/downloads/)

---

## Install (one command)

Open **Terminal** and run:

```bash
curl -fsSL https://raw.githubusercontent.com/GITHUB_USER/claude-limits/main/install.sh | bash
```

The installer will:
1. Check Python 3.9+
2. Download the app to `~/Library/Application Support/ClaudeLimits/`
3. Install Python dependencies (`pyobjc`, `curl_cffi`)
4. Register a login item so the widget starts automatically
5. Launch the widget immediately

---

## First-time setup

After installation, a small icon appears in your menu bar:

1. **Click the icon** → popover opens
2. **Click the gear ⚙️** → Settings panel opens
3. **Paste your Claude session cookie** (see below)
4. Click **Connect** — the icon starts showing live data

### Getting your session cookie

1. Open [claude.ai](https://claude.ai) in Safari or Chrome
2. Open DevTools → **Application** tab → **Cookies** → `https://claude.ai`
3. Find the cookie named **`sessionKey`**
4. Copy its **Value** and paste it into the widget's Settings panel

> The cookie is stored **locally only** (`~/.claude_limits_config.json`).
> It is never sent anywhere except Claude's own API.

---

## Usage

| Action | Result |
|---|---|
| **Click menu bar icon** | Open usage popover |
| **Click gear ⚙️** in popover | Open Settings |
| **Copy Key** button | Copy masked session key to clipboard |
| **Disconnect** button | Remove stored session, stop fetching |
| **Open claude.ai ↗** | Open Claude in your browser |

The icon ring shows your **current 5-hour session** usage.
The popover also shows **weekly** (7-day) usage and the next reset time.

---

## Manual install

```bash
# Clone the repo
git clone https://github.com/GITHUB_USER/claude-limits.git
cd claude-limits

# Install Python dependencies
pip3 install -r requirements.txt

# Run immediately
python3 widget.py

# (Optional) Install auto-start at login
bash install.sh
```

---

## Update

Re-run the one-liner — it will pull the latest version and restart the widget:

```bash
curl -fsSL https://raw.githubusercontent.com/GITHUB_USER/claude-limits/main/install.sh | bash
```

---

## Uninstall

```bash
bash ~/Library/Application\ Support/ClaudeLimits/uninstall.sh
```

This removes the app files, the login agent, and the logs.
It optionally removes your saved session config.

---

## Troubleshooting

### Widget doesn't appear in menu bar
- Make sure you're on macOS 12+
- Try running manually: `python3 ~/Library/Application\ Support/ClaudeLimits/widget.py`
- Check logs: `~/Library/Logs/ClaudeLimits/stderr.log`

### Shows "—%" or no data
- Open Settings and paste a fresh `sessionKey` cookie value
- The cookie expires periodically — refresh it from claude.ai

### "Permission denied" when running install.sh
```bash
chmod +x install.sh && ./install.sh
```

### Dependencies fail to install
```bash
pip3 install --upgrade pip
pip3 install pyobjc-framework-Cocoa curl_cffi requests
```

---

## Privacy

- **No data leaves your machine** except API calls to `claude.ai` using your own session cookie
- The session cookie is stored in `~/.claude_limits_config.json` (readable only by you)
- No analytics, no telemetry, no third-party services

---

## License

MIT — see [LICENSE](LICENSE)
