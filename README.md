# Claude Limits Widget

> A lightweight macOS menu bar widget that **monitors your Claude API usage in real time**. Glance at the menu bar icon to see how much of your 5-hour session quota you've used, or click to see exact percentages, weekly usage, and time until reset. Never run out of tokens unexpectedly.
>
> <p align="center"><img width="286" height="273" alt="image" src="https://github.com/user-attachments/assets/d78ddc72-f8e8-476e-8e1e-a0e32ba51d47" /></p>


---

## Features

- **Live usage indicator** — circular progress ring in the menu bar; updates every 30 seconds. Glance to see how much of your 5-hour session quota remains
- **Session & weekly tracking** — click the icon to see your current session % (5-hour window), 7-day usage %, and exact reset time
- **Always visible** — uses macOS template images; the icon automatically adapts to light mode, dark mode, full-screen apps, wallpaper tinting, and even the "active/clicked" state
- **Token visibility** — know exactly how much capacity you have left before your session resets, so you can plan longer tasks or break them up as needed
- **Auto-start at login** — installs as a native macOS LaunchAgent; runs in the background silently
- **Zero setup friction** — one-command installer; just paste your Claude session cookie once

---

## Requirements

| Requirement | Details |
|---|---|
| **macOS** | 12 Monterey or later |
| **Python** | 3.9 or later — from [python.org](https://www.python.org/downloads/) or Homebrew |
| **Claude account** | Free, Pro, Team, or Enterprise (all have 5-hour session limits) |

> **No Xcode or developer tools required.**
> macOS ships a `python3` stub at `/usr/bin/python3` that triggers an Xcode install prompt — the installer automatically skips it and only uses real Python installations.

**Don't have Python? Install without Xcode:**

- **Option 1 (easiest)** — download the installer from [python.org/downloads](https://www.python.org/downloads/) and run it. Done.
- **Option 2 (Homebrew)** — if you have Homebrew: `brew install python`

---

## Install (one command)

Open **Terminal** and run:

```bash
curl -fsSL https://raw.githubusercontent.com/DimaNeskorodiev/claude-limits/main/install.sh | bash
```

The installer will:
1. Check Python 3.9+
2. Download the app to `~/Library/Application Support/ClaudeLimits/`
3. Install Python dependencies (`pyobjc`, `curl_cffi`)
4. Register a login item so the widget starts automatically
5. Launch the widget immediately

**If the widget isn't running** (e.g. after a reboot before first login), start it manually:

```bash
python3 ~/Library/Application\ Support/ClaudeLimits/widget.py &
```

---

## First-time setup

**After installation:**
1. A small icon appears in your menu bar (top-right of screen)
2. **Click the icon** to open the usage popover
3. **Click the gear ⚙️** button to open Settings
4. **Paste your Claude session cookie** (see "Getting your session cookie" below)
5. Click **Connect** — usage data loads instantly

### Getting your session cookie

The widget reads your Claude usage via your browser session. No Xcode or developer tools required — just your browser's built-in inspector:

1. Open [claude.ai](https://claude.ai) in **Chrome** or **Safari** (must be logged in)
2. Press **`Cmd + Option + I`** to open the browser inspector
3. Click the **Application** tab at the top of the inspector panel
4. In the left sidebar, expand **Cookies** → click `https://claude.ai`
5. Find the cookie named **`sessionKey`**
6. Click on it, then copy the full **Value** (a long string starting with `sk-ant-…`)
7. Paste it into the widget's Settings panel and click **Connect**

**Privacy note:**
- Your session cookie is stored **locally only** on your Mac (`~/.claude_limits_config.json`), readable only by you
- The widget only sends API requests to `claude.ai` using your cookie; it never shares data with third parties or our servers
- To revoke access, simply disconnect in the widget or delete your session on claude.ai

---

## Usage

**Menu bar icon:**
The circular progress ring shows your **current 5-hour session usage**. At a glance:
- Empty ring (0%) = fresh session, plenty of tokens available
- Half-filled ring (50%) = you're at the midpoint; plan accordingly if you have a large task
- Nearly full ring (90%+) = nearing your session limit; upcoming task might hit the reset window

**Click the icon to open the popover and see:**

| Metric | Meaning |
|---|---|
| **Current session %** | How much of your 5-hour rolling window you've consumed |
| **Weekly %** | How much of your 7-day total limit you've used (Pro/Team/Enterprise plans) |
| **Time until reset** | When your current session window expires and resets to 0% |

| Button | Action |
|---|---|
| **Gear ⚙️** | Open Settings to manage or change your session cookie |
| **Copy Key** | Copy your masked session ID to clipboard (for reference/debugging) |
| **Disconnect** | Remove your stored session and stop monitoring usage |
| **Open claude.ai ↗** | Jump directly to claude.ai in your browser |

**Why this matters:**
Claude API and web usage share the same session window. If you're near your 5-hour limit, starting a long task might be interrupted. This widget lets you check instantly from your menu bar — no need to open Claude or dig through the UI.

---

## Manual install

```bash
# Clone the repo
git clone https://github.com/DimaNeskorodiev/claude-limits.git
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
curl -fsSL https://raw.githubusercontent.com/DimaNeskorodiev/claude-limits/main/install.sh | bash
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
- Start it manually (no Xcode or extra tools needed — just Python):
  ```bash
  python3 ~/Library/Application\ Support/ClaudeLimits/widget.py &
  ```
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

## Privacy & Security

✅ **Your data stays on your Mac**
- The session cookie is stored locally in `~/.claude_limits_config.json`, encrypted for your user only
- Usage data is fetched directly from `claude.ai` API using your own session cookie
- No data is sent to our servers, third-party analytics, or ad networks

✅ **Transparent & open**
- This is free, open-source software under the MIT license
- You can review the source code to see exactly what requests are made

✅ **Revoke access anytime**
- Click "Disconnect" in Settings to forget your session cookie immediately
- Or log out of claude.ai to invalidate your session token globally

---

## License

MIT — see [LICENSE](LICENSE)
