#!/usr/bin/env python3
"""
Claude Limits – macOS menu bar app
Shows current-session and weekly token usage pulled from claude.ai.
Click the status bar icon to open the Liquid Glass usage panel.
"""

import os
import subprocess
import tempfile
import threading
import json
import sys
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

LOCAL_API_PORT = 8765

# ── curl_cffi / requests ──────────────────────────────────────────────────────
try:
    from curl_cffi import requests
    _CURL_CFFI = True
except ImportError:
    try:
        import requests          # type: ignore[no-redef]
        _CURL_CFFI = False
        print("WARNING: curl_cffi not found – falling back to requests "
              "(likely blocked by Cloudflare). Run: pip3 install curl_cffi")
    except ImportError:
        print("ERROR: install dependencies first:  pip3 install curl_cffi requests")
        sys.exit(1)

# ── PyObjC / AppKit ───────────────────────────────────────────────────────────
try:
    import objc
    from AppKit import (
        NSApplication, NSObject, NSViewController,
        NSStatusBar, NSVariableStatusItemLength,
        NSImage, NSColor, NSFont, NSBezierPath,
        NSFontAttributeName, NSForegroundColorAttributeName,
        NSView, NSTextField, NSButton, NSScrollView, NSTextView,
        NSPanel, NSVisualEffectView,
        NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
        NSBackingStoreBuffered,
        NSMakeRect, NSSize, NSPoint,
        NSTextAlignmentLeft, NSTextAlignmentRight, NSTextAlignmentCenter,
        NSBezelStyleRounded,
        NSImageView, NSPasteboard,
        NSMenu, NSMenuItem,
    )
    from AppKit import NSAppearance
    try:
        from AppKit import NSWorkspace
    except ImportError:
        NSWorkspace = None
    from Foundation import NSTimer, NSAttributedString, NSData, NSURL
    try:
        from Foundation import NSDistributedNotificationCenter
    except ImportError:
        NSDistributedNotificationCenter = None
    try:
        from AppKit import NSPopover
    except ImportError:
        from Cocoa import NSPopover  # type: ignore
except ImportError as _e:
    print(f"ERROR: PyObjC not installed. Run: pip3 install pyobjc-framework-Cocoa\n  ({_e})")
    sys.exit(1)

# ── Enum constants with integer fallbacks (macOS 26 / Tahoe safe) ─────────────
try:
    from AppKit import NSVisualEffectMaterialHUDWindow as _HUD_MAT
except (ImportError, AttributeError):
    _HUD_MAT = 14   # NSVisualEffectMaterialHUDWindow raw value

try:
    from AppKit import NSVisualEffectBlendingModeBehindWindow as _BLEND_BEHIND
except (ImportError, AttributeError):
    _BLEND_BEHIND = 0

try:
    from AppKit import NSVisualEffectStateActive as _VEV_ACTIVE
except (ImportError, AttributeError):
    _VEV_ACTIVE = 1

try:
    from AppKit import NSApplicationActivationPolicyAccessory as _POLICY_ACCESSORY
except (ImportError, AttributeError):
    _POLICY_ACCESSORY = 1

try:
    from AppKit import NSVisualEffectMaterialPopover as _POPOVER_MAT
except (ImportError, AttributeError):
    _POPOVER_MAT = 6   # NSVisualEffectMaterialPopover raw value

# Mouse event masks for sendActionOn_ (left + right click on status bar button)
try:
    from AppKit import NSEventMaskLeftMouseDown, NSEventMaskRightMouseDown
    _CLICK_MASK = int(NSEventMaskLeftMouseDown) | int(NSEventMaskRightMouseDown)
except (ImportError, AttributeError):
    _CLICK_MASK = 2 | 8   # NSEventMaskLeftMouseDown=2, NSEventMaskRightMouseDown=8

_RIGHT_MOUSE_DOWN = 3   # NSEventTypeRightMouseDown (stable integer value)

# NSButtonTypeSwitch = checkbox style
try:
    from AppKit import NSButtonTypeSwitch as _CHECKBOX_TYPE
except (ImportError, AttributeError):
    _CHECKBOX_TYPE = 3

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_FILE    = Path.home() / ".claude_widget_config.json"
LOG_FILE       = Path.home() / ".claude_widget_debug.log"
PLIST_LABEL    = "com.claude.limits.widget"
PLIST_PATH     = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
REFRESH_SEC    = 60
POPUP_W        = 280
POPUP_H        = 230
SETUP_W        = 500
SETUP_H        = 480
BASE_URL       = "https://claude.ai"
APP_VERSION    = "1.0.0"

# ── Icon colour endpoints (SRGB 0-1) ─────────────────────────────────────────
_ICON_DARK_0   = (1.0,   1.0,   1.0  )   # white — 0% usage in dark mode
_ICON_LIGHT_0  = (0.267, 0.267, 0.267)   # dark grey — 0% usage in light mode
_ICON_FULL     = (0.851, 0.467, 0.341)   # #D97757 orange — 100% usage

# Claude star glyph path (viewBox 0 0 24 24)
_CLAUDE_SVG_PATH = (
    "M4.709 15.955l4.72-2.647.08-.23-.08-.128H9.2l-.79-.048-2.698-.073"
    "-2.339-.097-2.266-.122-.571-.121L0 11.784l.055-.352.48-.321.686.06"
    " 1.52.103 2.278.158 1.652.097 2.449.255h.389l.055-.157-.134-.098"
    "-.103-.097-2.358-1.596-2.552-1.688-1.336-.972-.724-.491-.364-.462"
    "-.158-1.008.656-.722.881.06.225.061.893.686 1.908 1.476 2.491 1.833"
    ".365.304.145-.103.019-.073-.164-.274-1.355-2.446-1.446-2.49-.644-1.032"
    "-.17-.619a2.97 2.97 0 01-.104-.729L6.283.134 6.696 0l.996.134.42.364"
    ".62 1.414 1.002 2.229 1.555 3.03.456.898.243.832.091.255h.158V9.01"
    "l.128-1.706.237-2.095.23-2.695.08-.76.376-.91.747-.492.584.28.48.685"
    "-.067.444-.286 1.851-.559 2.903-.364 1.942h.212l.243-.242.985-1.306"
    " 1.652-2.064.73-.82.85-.904.547-.431h1.033l.76 1.129-.34 1.166"
    "-1.064 1.347-.881 1.142-1.264 1.7-.79 1.36.073.11.188-.02 2.856-.606"
    " 1.543-.28 1.841-.315.833.388.091.395-.328.807-1.969.486-2.309.462"
    "-3.439.813-.042.03.049.061 1.549.146.662.036h1.622l3.02.225.79.522"
    ".474.638-.079.485-1.215.62-1.64-.389-3.829-.91-1.312-.329h-.182v.11"
    "l1.093 1.068 2.006 1.81 2.509 2.33.127.578-.322.455-.34-.049-2.205"
    "-1.657-.851-.747-1.926-1.62h-.128v.17l.444.649 2.345 3.521.122 1.08"
    "-.17.353-.608.213-.668-.122-1.374-1.925-1.415-2.167-1.143-1.943-.14"
    ".08-.674 7.254-.316.37-.729.28-.607-.461-.322-.747.322-1.476.389"
    "-1.924.315-1.53.286-1.9.17-.632-.012-.042-.14.018-1.434 1.967-2.18"
    " 2.945-1.726 1.845-.414.164-.717-.37.067-.662.401-.589 2.388-3.036"
    " 1.44-1.882.93-1.086-.006-.158h-.055L4.132 18.56l-1.13.146-.487-.456"
    ".061-.746.231-.243 1.908-1.312-.006.006z"
)

# ── Palette (SRGB 0-1 tuples) ────────────────────────────────────────────────
_CLR_BLUE    = (0.290, 0.561, 0.910, 1.0)   # #4A8FE8
_CLR_TRACK   = (0.180, 0.180, 0.180, 1.0)   # #2e2e2e (fallback only)
_CLR_TEXT    = (0.910, 0.910, 0.910, 1.0)   # #e8e8e8 (fallback only)
_CLR_SEC     = (0.533, 0.533, 0.533, 1.0)   # #888888 (fallback only)
_CLR_OK      = (0.298, 0.686, 0.490, 1.0)   # #4caf7d
_CLR_ERR     = (0.878, 0.322, 0.322, 1.0)   # #e05252
_CLR_ORANGE  = (0.851, 0.467, 0.341, 1.0)   # #D97757


def _nscolor(rgba):
    r, g, b, a = rgba
    return NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, a)


def _is_dark_mode() -> bool:
    """Return True when the system is currently in dark mode."""
    try:
        from AppKit import NSAppearanceNameAqua, NSAppearanceNameDarkAqua
        names = [NSAppearanceNameAqua, NSAppearanceNameDarkAqua]
        best  = NSAppearance.currentAppearance().bestMatchFromAppearancesWithNames_(names)
        return best == NSAppearanceNameDarkAqua
    except Exception:
        return True  # safe default: dark


def _lerp_color(t: float, c0: tuple, c1: tuple) -> tuple:
    """Linearly interpolate between two RGB 3-tuples. t in [0, 1]."""
    t = max(0.0, min(1.0, t))
    return tuple(c0[i] + (c1[i] - c0[i]) * t for i in range(3))


def _mask_session_key(raw: str) -> str:
    """Return first 8 chars + '…' + last 4 chars of a session cookie string."""
    raw = (raw or "").strip()
    if not raw:
        return "—"
    if len(raw) <= 16:
        return raw[:4] + "…"
    return raw[:8] + "…" + raw[-4:]


# ── Launch-at-login helpers (LaunchAgent plist) ───────────────────────────────

def _autostart_enabled() -> bool:
    """Return True if the LaunchAgent plist is installed."""
    return PLIST_PATH.exists()


def _write_plist_file() -> None:
    """Write (or overwrite) the LaunchAgent plist with the current Python & widget path."""
    python_exe  = sys.executable
    widget_path = str(Path(__file__).resolve())
    log_dir     = Path.home() / "Library" / "Logs" / "ClaudeLimits"
    log_dir.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python_exe}</string>
    <string>{widget_path}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>{log_dir}/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>{log_dir}/stderr.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
''')


def _toggle_autostart() -> bool:
    """Toggle LaunchAgent on/off.  Returns the *new* enabled state (True = enabled)."""
    if _autostart_enabled():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                       capture_output=True)
        try:
            PLIST_PATH.unlink()
        except Exception:
            pass
        return False
    else:
        _write_plist_file()
        subprocess.run(["launchctl", "load", str(PLIST_PATH)],
                       capture_output=True)
        return True


# ── Debug log ─────────────────────────────────────────────────────────────────
def _init_log_file():
    """Create log file with owner-only permissions before first write."""
    try:
        if not LOG_FILE.exists():
            LOG_FILE.touch(mode=0o600)
        else:
            os.chmod(LOG_FILE, 0o600)
    except Exception:
        pass


def log(msg: str):
    ts   = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── Cookie helpers ────────────────────────────────────────────────────────────
def parse_cookie_string(raw: str) -> dict:
    """Parse 'name=value; name2=value2' into a dict."""
    out = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, value = part.partition("=")
            # Strip whitespace then sanitize CR/LF/NUL to prevent HTTP header injection
            name  = name.strip().translate({0x0D: None, 0x0A: None, 0x00: None})
            value = value.strip().translate({0x0D: None, 0x0A: None, 0x00: None})
            if name:
                out[name] = value
    return out


def cookie_string_looks_valid(raw: str) -> tuple:
    """Return (ok, error_message)."""
    if not raw or not raw.strip():
        return False, "Please paste your Cookie header value."
    cookies = parse_cookie_string(raw)
    if not cookies:
        return False, "Could not parse any cookies from that string."
    has_session = any(
        k in cookies
        for k in ("sessionKey", "__Secure-next-auth.session-token",
                  "next-auth.session-token", "CF_Authorization")
    )
    if not has_session:
        return False, ("No recognised session cookie found.\n"
                       "Make sure you copied the full Cookie header.")
    return True, ""


# ── Absolute time format for weekly resets ────────────────────────────────────
def fmt_reset_absolute(ts) -> str:
    """Return 'Today 15:00', 'Tomorrow 15:00', or 'Friday 15:00'."""
    if not ts:
        return "–"
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts).astimezone()
        else:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone()
        delta_days = (dt.date() - datetime.now().astimezone().date()).days
        time_str = dt.strftime("%H:%M")
        if delta_days == 0:
            return f"Today {time_str}"
        if delta_days == 1:
            return f"Tomorrow {time_str}"
        return dt.strftime(f"%A {time_str}")   # e.g. "Friday 15:00"
    except Exception:
        return str(ts)


# ── Claude.ai API client ──────────────────────────────────────────────────────
class ClaudeAPI:
    # Browser-like request headers – helps pass Cloudflare when cf_clearance is present
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         "https://claude.ai/settings",
        "Origin":          "https://claude.ai",
        "sec-fetch-site":  "same-origin",
        "sec-fetch-mode":  "cors",
        "sec-fetch-dest":  "empty",
        "sec-ch-ua":       '"Chromium";v="122", "Not(A:Brand";v="24"',
        "sec-ch-ua-mobile":   "?0",
        "sec-ch-ua-platform": '"macOS"',
    }

    def __init__(self, cookie_str: str):
        self.cookie_str = cookie_str
        if _CURL_CFFI:
            self.s = requests.Session(impersonate="chrome120")
        else:
            self.s = requests.Session()
        self.s.headers.update(self.HEADERS)
        for name, value in parse_cookie_string(cookie_str).items():
            self.s.cookies.set(name, value, domain="claude.ai", path="/")

    # ── Validation ─────────────────────────────────────────────────────────
    def validate(self) -> tuple:
        """
        Returns (is_valid, error_message).
        Uses /api/bootstrap which always returns JSON and exposes "account": null
        when not authenticated.
        """
        try:
            r = self.s.get(BASE_URL + "/api/bootstrap", timeout=12)
            log(f"validate /api/bootstrap -> {r.status_code}")
            ct = r.headers.get("content-type", "")
            if "json" not in ct:
                body = r.text[:300]
                if "just a moment" in body.lower() or "cloudflare" in body.lower():
                    return False, (
                        "Cloudflare is blocking requests.\n"
                        "Install curl_cffi:  pip3 install curl_cffi  and restart."
                    )
                return False, f"Unexpected non-JSON response (HTTP {r.status_code})."
            if not r.ok:
                return False, f"Server error: HTTP {r.status_code}"
            data    = r.json()
            account = data.get("account")
            if account is None:
                return False, (
                    "Cookies were accepted but the session is not authenticated.\n"
                    "The cookies may have expired – log in again, then re-copy "
                    "the Cookie header from DevTools."
                )
            log("  ✓ session authenticated")
            return True, ""
        except Exception as e:
            msg = str(e)
            if "ssl" in msg.lower():
                return False, "SSL error reaching claude.ai."
            if "connection" in msg.lower() or "timeout" in msg.lower():
                return False, "Cannot reach claude.ai. Check your internet."
            return False, msg[:120]

    # ── Account / org ID ───────────────────────────────────────────────────
    def get_account(self) -> dict:
        try:
            r = self.s.get(BASE_URL + "/api/bootstrap", timeout=10)
            log(f"bootstrap -> {r.status_code}")
            ct = r.headers.get("content-type", "")
            if r.ok and "json" in ct:
                data    = r.json()
                account = data.get("account") or {}
                return account
        except Exception as e:
            log(f"  bootstrap error: {e}")
        return {}

    def _org_id(self, account: dict):
        paths = [
            ("memberships", 0, "organization", "uuid"),
            ("memberships", 0, "organization", "id"),
            ("organizations", 0, "uuid"),
            ("organizations", 0, "id"),
            ("organization", "uuid"),
            ("organization", "id"),
            ("uuid",),
            ("id",),
        ]
        for path in paths:
            node = account
            try:
                for key in path:
                    node = node[key]
                if node:
                    return str(node)
            except (KeyError, IndexError, TypeError):
                continue
        return None

    # ── Limits ─────────────────────────────────────────────────────────────
    def get_limits(self, org_id=None) -> tuple:
        candidates = []
        if org_id:
            candidates += [
                f"/api/organizations/{org_id}/usage",
                f"/api/organizations/{org_id}/limits",
                f"/api/organizations/{org_id}/rate_limits",
                f"/api/organizations/{org_id}/billing_usage",
            ]
        candidates += [
            "/api/usage", "/api/limits", "/api/rate_limits",
            "/api/account/limits", "/api/account/usage",
        ]
        for ep in candidates:
            try:
                headers = {"Referer": "https://claude.ai/settings/usage"}
                r = self.s.get(BASE_URL + ep, headers=headers, timeout=10)
                log(f"limits {ep} -> {r.status_code}")
                ct = r.headers.get("content-type", "")
                if r.ok and "json" in ct:
                    data = r.json()
                    if not data:
                        continue
                    parsed = ClaudeAPI.parse(data)
                    if parsed["session"] or parsed["weekly"]:
                        log(f"  ✓ usable data found at {ep}")
                        return data, ep
                    else:
                        log(f"  ✗ {ep} returned JSON but parse() found no usage data — skipping")
            except Exception as e:
                log(f"  {ep} error: {e}")
        return None, None

    # ── Parse into normalised shape ─────────────────────────────────────────
    @staticmethod
    def parse(data) -> dict:
        out = {"session": None, "weekly": None}

        # B-7: guard against non-dict top-level values (e.g. bare JSON array)
        if not isinstance(data, dict):
            data = {"rate_limits": data} if isinstance(data, list) else {}

        def pct(used, limit):
            try:
                return round(100 * used / limit, 1) if limit else 0.0
            except Exception:
                return 0.0

        def fmt_reset(ts):
            if not ts:
                return "–"
            try:
                if isinstance(ts, (int, float)):
                    # B-8: use .astimezone() so the result is tz-aware, preventing
                    # TypeError when subtracting from datetime.now().astimezone()
                    dt = datetime.fromtimestamp(ts).astimezone()
                else:
                    ts = ts.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(ts).astimezone()
                delta = dt - datetime.now().astimezone()
                secs  = int(delta.total_seconds())
                if secs <= 0:
                    return "now"
                h, rem = divmod(secs, 3600)
                m = rem // 60
                return f"in {h} hr {m} min" if h else f"in {m} min"
            except Exception:
                return str(ts)

        # Pattern A
        if "session" in data or "current_session" in data:
            s = data.get("session") or data.get("current_session") or {}
            out["session"] = {
                "used_pct":  s.get("percent_used") or pct(s.get("used"), s.get("limit")),
                "resets_in": fmt_reset(s.get("reset_at") or s.get("resets_at")),
            }
        if "weekly" in data or "week" in data:
            w = data.get("weekly") or data.get("week") or {}
            out["weekly"] = {
                "used_pct":  w.get("percent_used") or pct(w.get("used"), w.get("limit")),
                "resets_at": fmt_reset(w.get("reset_at") or w.get("resets_at")),
            }

        # Pattern B: list of rate limit objects
        items = (data if isinstance(data, list)
                 else data.get("rate_limits") or data.get("limits") or [])
        for item in items:
            if not isinstance(item, dict):
                continue
            window = (item.get("window") or item.get("period") or "").lower()
            used   = item.get("tokens_used") or item.get("used") or 0
            limit  = item.get("tokens_limit") or item.get("limit") or 0
            reset  = item.get("reset_at") or item.get("resets_at")
            if "session" in window or "hour" in window:
                out["session"] = {"used_pct": pct(used, limit), "resets_in": fmt_reset(reset)}
            elif "week" in window:
                out["weekly"]  = {"used_pct": pct(used, limit), "resets_at": fmt_reset(reset)}

        # Pattern C: flat numeric fields
        if not out["session"] and "session_percent" in data:
            out["session"] = {
                "used_pct":  float(data["session_percent"]),
                "resets_in": fmt_reset(data.get("session_reset_at")),
            }
        if not out["weekly"] and "weekly_percent" in data:
            out["weekly"] = {
                "used_pct":  float(data["weekly_percent"]),
                "resets_at": fmt_reset(data.get("weekly_reset_at")),
            }

        # Pattern D: five_hour / seven_day from /api/organizations/{id}/usage
        sess_raw = data.get("five_hour") or data.get("fiveHour")
        if not out["session"] and sess_raw:
            s = sess_raw or {}
            used_pct = (
                s.get("utilization") or s.get("percentUsed") or s.get("percent_used")
                or pct(s.get("used") or s.get("tokensUsed"),
                       s.get("limit") or s.get("tokensLimit"))
            )
            out["session"] = {
                "used_pct":  float(used_pct or 0.0),
                "resets_in": fmt_reset(
                    s.get("resets_at") or s.get("reset_at") or s.get("resetsAt")),
            }

        week_raw = data.get("seven_day") or data.get("sevenDay")
        if not out["weekly"] and week_raw:
            w = week_raw or {}
            used_pct = (
                w.get("utilization") or w.get("percentUsed") or w.get("percent_used")
                or pct(w.get("used") or w.get("tokensUsed"),
                       w.get("limit") or w.get("tokensLimit"))
            )
            out["weekly"] = {
                "used_pct":  float(used_pct or 0.0),
                "resets_at": fmt_reset(
                    w.get("resets_at") or w.get("reset_at") or w.get("resetsAt")),
            }

        return out


# ── UI helper factories (module-level — used by view controllers) ─────────────
def _make_label(text: str, font, color, frame, align=0, wraps=False):
    lbl = NSTextField.alloc().initWithFrame_(frame)
    lbl.setStringValue_(text)
    lbl.setFont_(font)
    # Accept either a (r,g,b,a) tuple or a ready-made NSColor object
    if isinstance(color, tuple):
        lbl.setTextColor_(_nscolor(color))
    else:
        lbl.setTextColor_(color)
    lbl.setBezeled_(False)
    lbl.setDrawsBackground_(False)
    lbl.setEditable_(False)
    lbl.setSelectable_(False)
    lbl.setAlignment_(align)
    if wraps:
        # setWraps_ lives on NSTextFieldCell in PyObjC, not on NSTextField directly
        try:
            lbl.cell().setWraps_(True)
        except Exception:
            try:
                lbl.setWraps_(True)
            except Exception:
                pass
    return lbl


class _DividerLine(NSView):
    """1-pt horizontal rule drawn with NSBezierPath — avoids CGColorRef bridging."""
    def drawRect_(self, rect):
        NSColor.separatorColor().setFill()
        NSBezierPath.fillRect_(self.bounds())


def _make_divider(frame):
    return _DividerLine.alloc().initWithFrame_(frame)


def _make_icon_btn(symbol: str, frame, target, action: str):
    btn = NSButton.alloc().initWithFrame_(frame)
    btn.setTitle_(symbol)
    btn.setBordered_(False)
    btn.setFont_(NSFont.systemFontOfSize_(14.0))
    btn.setContentTintColor_(NSColor.secondaryLabelColor())
    btn.setTarget_(target)
    btn.setAction_(action)
    return btn


# ── Rounded progress bar (native NSView) ─────────────────────────────────────
class RoundedProgressBar(NSView):
    """Native NSView that draws a pill-shaped progress track + fill."""

    def initWithFrame_(self, frame):
        self = objc.super(RoundedProgressBar, self).initWithFrame_(frame)
        if self is None:
            return None
        self._pct = 0.0
        return self

    def setPct_(self, pct):
        self._pct = max(0.0, min(100.0, float(pct)))
        self.setNeedsDisplay_(True)

    def drawRect_(self, dirty_rect):
        b  = self.bounds()
        w  = b.size.width
        h  = b.size.height
        r  = h / 2.0

        # Track — adaptive: dim in dark mode, light grey in light mode
        NSColor.tertiaryLabelColor().setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(b, r, r).fill()

        # Fill — B-9: use getattr fallback in case ObjC GC cleared __dict__
        fw = w * getattr(self, '_pct', 0.0) / 100.0
        if fw >= r * 2:
            _nscolor(_CLR_BLUE).setFill()
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(0, 0, fw, h), r, r).fill()
        elif fw > 0:
            _nscolor(_CLR_BLUE).setFill()
            NSBezierPath.bezierPathWithRect_(NSMakeRect(0, 0, fw, h)).fill()


# ── Status bar icon ───────────────────────────────────────────────────────────
def _make_status_icon(session_pct: float) -> NSImage:
    """
    22×22 menu-bar icon drawn entirely with lockFocus (always works):
      • thin circular ring track (full circle, dim)
      • coloured progress arc, clockwise from 12-o'clock, proportion = session_pct
      • small Claude star glyph rendered in the upper half via SVG sub-image
      • percentage text centred in the lower half
    Colour interpolates: white/dark-grey (0%) → #D97757 orange (100%).
    """
    SIZE   = 22.0
    t      = max(0.0, min(100.0, float(session_pct))) / 100.0
    dark   = _is_dark_mode()
    c0     = _ICON_DARK_0 if dark else _ICON_LIGHT_0
    ri, gi, bi = _lerp_color(t, c0, _ICON_FULL)
    fg         = _nscolor((ri, gi, bi, 1.0))
    hex_col    = "#{:02X}{:02X}{:02X}".format(int(ri * 255), int(gi * 255), int(bi * 255))

    img = NSImage.alloc().initWithSize_(NSSize(SIZE, SIZE))
    img.lockFocus()
    NSColor.clearColor().set()
    NSBezierPath.fillRect_(NSMakeRect(0, 0, SIZE, SIZE))

    cx, cy  = SIZE / 2.0, SIZE / 2.0   # (11, 11)
    RING_R  = SIZE / 2.0 - 1.5         # 9.5 pt radius (leaves 1.5 pt margin)
    RING_W  = 1.5

    # ── Track: full circle, dim ────────────────────────────────────────────
    tr_c = NSColor.colorWithWhite_alpha_(0.6 if dark else 0.0,
                                         0.28 if dark else 0.18)
    oval = NSBezierPath.bezierPathWithOvalInRect_(
        NSMakeRect(cx - RING_R, cy - RING_R, RING_R * 2, RING_R * 2)
    )
    oval.setLineWidth_(RING_W)
    tr_c.setStroke()
    oval.stroke()

    # ── Progress arc: clockwise from 12-o'clock ────────────────────────────
    # In Cocoa: 90° = top; clockwise = decreasing angle
    if t > 0.005:
        end_deg = 90.0 - t * 360.0
        arc = NSBezierPath.bezierPath()
        arc.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
            NSPoint(cx, cy), RING_R, 90.0, end_deg, True
        )
        arc.setLineWidth_(RING_W)
        try:
            arc.setLineCapStyle_(1)   # NSLineCapStyleRound
        except Exception:
            pass
        fg.setStroke()
        arc.stroke()

    # ── Claude star glyph: small, pinned to the top of the ring interior ────
    # Reduce star to leave most vertical space for the large percentage number
    STAR  = 5.5
    sx    = cx - STAR / 2.0
    # In Cocoa coords y=0=bottom; cy=11; placing star at cy+1.5 puts it
    # in the upper screen half (y≈13 → y≈18.5 on screen).
    sy    = cy + 1.5

    svg_bytes = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="{STAR}" height="{STAR}">'
        f'<path fill="{hex_col}" fill-rule="nonzero" d="{_CLAUDE_SVG_PATH}"/>'
        f'</svg>'
    ).encode("utf-8")

    star_drawn = False
    try:
        d  = NSData.dataWithBytes_length_(svg_bytes, len(svg_bytes))
        si = NSImage.alloc().initWithData_(d)
        if si is not None:
            si.setSize_(NSSize(STAR, STAR))
            si.drawInRect_fromRect_operation_fraction_(
                NSMakeRect(sx, sy, STAR, STAR),
                NSMakeRect(0, 0, STAR, STAR),
                2,     # NSCompositeSourceOver
                1.0,
            )
            star_drawn = True
    except Exception:
        pass

    if not star_drawn:
        # Fallback: small filled oval in the upper half
        fg.setFill()
        NSBezierPath.bezierPathWithOvalInRect_(
            NSMakeRect(sx + 1.0, sy + 1.0, STAR - 2.0, STAR - 2.0)
        ).fill()

    # ── Percentage text: large, centred, lower portion of ring ────────────
    # Font size is scaled by string length so the number always fits inside
    # the ring interior (≈16 pt wide clear area).
    pct_str   = f"{int(session_pct)}%"
    n         = len(pct_str)
    font_size = 7.5 if n >= 4 else (8.5 if n == 3 else 9.5)
    font      = NSFont.boldSystemFontOfSize_(font_size)
    attrs     = {
        NSFontAttributeName:            font,
        NSForegroundColorAttributeName: fg,
    }
    astr = NSAttributedString.alloc().initWithString_attributes_(pct_str, attrs)
    sz   = astr.size()
    astr.drawAtPoint_(NSPoint(
        (SIZE - sz.width) / 2.0,
        1.5,    # near bottom of ring interior
    ))

    img.unlockFocus()
    return img


# ── Usage popup view controller ───────────────────────────────────────────────
class UsageViewController(NSViewController):
    """Content view controller for the NSPopover panel."""

    def init(self):
        self = objc.super(UsageViewController, self).initWithNibName_bundle_(None, None)
        if self is None:
            return None
        # Build the view directly in init — do NOT rely on loadView lazy-loading,
        # which is unreliable when overridden in Python via PyObjC's bridge.
        self._buildView()
        return self

    # ── Build UI ─────────────────────────────────────────────────────────
    @objc.python_method
    def _buildView(self):
        W, H  = float(POPUP_W), float(POPUP_H)
        PAD   = 16.0

        # Root: NSVisualEffectView — Popover material adapts to dark/light automatically
        vev = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))
        vev.setWantsLayer_(True)      # required: enables CA compositing & subview rendering
        vev.setMaterial_(_POPOVER_MAT)
        vev.setBlendingMode_(_BLEND_BEHIND)
        vev.setState_(_VEV_ACTIVE)
        # No forced appearance — NSVisualEffectMaterialPopover auto-adapts to system theme
        self.setView_(vev)

        # ── Header row ────────────────────────────────────────────────────
        vev.addSubview_(_make_label(
            "Claude",
            font=NSFont.boldSystemFontOfSize_(13.0),
            color=NSColor.labelColor(),
            frame=NSMakeRect(PAD, H - 28, 58, 20),
        ))
        vev.addSubview_(_make_label(
            " Limits",
            font=NSFont.systemFontOfSize_(13.0),
            color=NSColor.secondaryLabelColor(),
            frame=NSMakeRect(PAD + 55, H - 28, 70, 20),
        ))

        self._refresh_btn = _make_icon_btn(
            "↻", frame=NSMakeRect(W - PAD - 44, H - 29, 22, 22),
            target=self, action="onRefresh:"
        )
        vev.addSubview_(self._refresh_btn)

        self._settings_btn = _make_icon_btn(
            "⚙", frame=NSMakeRect(W - PAD - 20, H - 29, 22, 22),
            target=self, action="onSettings:"
        )
        vev.addSubview_(self._settings_btn)

        # Auth error (hidden by default, shown below header)
        self._auth_lbl = _make_label(
            "", font=NSFont.systemFontOfSize_(10.0), color=_CLR_ERR,
            frame=NSMakeRect(PAD, H - 46, W - PAD * 2, 14), wraps=True,
        )
        self._auth_lbl.setHidden_(True)
        vev.addSubview_(self._auth_lbl)

        # Top divider
        vev.addSubview_(_make_divider(NSMakeRect(PAD, H - 36, W - PAD * 2, 1)))

        # ── Current session section ───────────────────────────────────────
        # y layout (Cocoa bottom-origin):
        # H=230 → header at 202..222, divider at 193, session block 100..193, mid-div 96
        # weekly block 30..96, bot-div 20, footer 4..18

        self._s_title = _make_label(
            "Current session",
            font=NSFont.boldSystemFontOfSize_(12.0),
            color=NSColor.labelColor(),
            frame=NSMakeRect(PAD, 172, 160, 18),
        )
        vev.addSubview_(self._s_title)

        self._s_pct = _make_label(
            "–",
            font=NSFont.systemFontOfSize_(12.0),
            color=NSColor.labelColor(),
            frame=NSMakeRect(W - PAD - 90, 172, 90, 18),
            align=NSTextAlignmentRight,
        )
        vev.addSubview_(self._s_pct)

        self._s_bar = RoundedProgressBar.alloc().initWithFrame_(
            NSMakeRect(PAD, 157, W - PAD * 2, 8)
        )
        vev.addSubview_(self._s_bar)

        self._s_sub = _make_label(
            "–",
            font=NSFont.systemFontOfSize_(11.0),
            color=NSColor.secondaryLabelColor(),
            frame=NSMakeRect(PAD, 138, W - PAD * 2, 16),
        )
        vev.addSubview_(self._s_sub)

        # Middle divider
        vev.addSubview_(_make_divider(NSMakeRect(PAD, 126, W - PAD * 2, 1)))

        # ── Weekly section ────────────────────────────────────────────────
        self._w_title = _make_label(
            "Weekly limits",
            font=NSFont.boldSystemFontOfSize_(12.0),
            color=NSColor.labelColor(),
            frame=NSMakeRect(PAD, 108, 150, 18),
        )
        vev.addSubview_(self._w_title)

        self._w_pct = _make_label(
            "–",
            font=NSFont.systemFontOfSize_(12.0),
            color=NSColor.labelColor(),
            frame=NSMakeRect(W - PAD - 90, 108, 90, 18),
            align=NSTextAlignmentRight,
        )
        vev.addSubview_(self._w_pct)

        self._w_models = _make_label(
            "All models",
            font=NSFont.systemFontOfSize_(11.0),
            color=NSColor.secondaryLabelColor(),
            frame=NSMakeRect(PAD, 94, 100, 14),
        )
        vev.addSubview_(self._w_models)

        self._w_bar = RoundedProgressBar.alloc().initWithFrame_(
            NSMakeRect(PAD, 75, W - PAD * 2, 8)
        )
        vev.addSubview_(self._w_bar)

        self._w_sub = _make_label(
            "–",
            font=NSFont.systemFontOfSize_(11.0),
            color=NSColor.secondaryLabelColor(),
            frame=NSMakeRect(PAD, 56, W - PAD * 2, 16),
        )
        vev.addSubview_(self._w_sub)

        # Bottom divider
        vev.addSubview_(_make_divider(NSMakeRect(PAD, 44, W - PAD * 2, 1)))

        # Footer status
        self._status_lbl = _make_label(
            "No session configured",
            font=NSFont.systemFontOfSize_(10.0),
            color=NSColor.tertiaryLabelColor(),
            frame=NSMakeRect(PAD, 12, W - PAD * 2, 28),
        )
        vev.addSubview_(self._status_lbl)

    # ── Public update API (always called on main thread) ──────────────────
    @objc.python_method   # B-10: never dispatched via ObjC — mark as Python-only
    def applyData_weeklyTs_(self, payload, weekly_ts):
        """
        payload = {"session": {...}|None, "weekly": {...}|None}
        weekly_ts = raw ISO resets_at string for absolute formatting
        """
        session = payload.get("session")
        weekly  = payload.get("weekly")

        if session:
            p = session["used_pct"]
            self._s_pct.setStringValue_(f"{p:.0f}% used")
            self._s_bar.setPct_(p)
            self._s_sub.setStringValue_(f"Resets {session['resets_in']}")
        else:
            self._s_pct.setStringValue_("–")
            self._s_bar.setPct_(0)
            self._s_sub.setStringValue_("No session data")

        if weekly:
            p = weekly["used_pct"]
            self._w_pct.setStringValue_(f"{p:.0f}% used")
            self._w_bar.setPct_(p)
            # Absolute format for weekly reset (it's days away)
            reset_str = fmt_reset_absolute(weekly_ts) if weekly_ts else weekly.get("resets_at", "–")
            self._w_sub.setStringValue_(f"Resets {reset_str}")
        else:
            self._w_pct.setStringValue_("–")
            self._w_bar.setPct_(0)
            self._w_sub.setStringValue_("No weekly data")

    def setStatus_(self, msg):
        self._status_lbl.setStringValue_(str(msg))

    def showAuthError_(self, msg):
        self._auth_lbl.setStringValue_(str(msg)[:90])
        self._auth_lbl.setHidden_(False)

    def hideAuthError(self):
        self._auth_lbl.setHidden_(True)

    # ── Button actions ────────────────────────────────────────────────────
    def onRefresh_(self, sender):
        d = NSApplication.sharedApplication().delegate()
        if d:
            d.refreshNow_(None)

    def onSettings_(self, sender):
        d = NSApplication.sharedApplication().delegate()
        if d:
            d.showSetup_(None)


# ── Settings panel (account info + cookie setup) ──────────────────────────────
def _open_setup(on_save, on_disconnect=None, current_cookie: str = ""):
    """Open the settings panel.  Called by AppDelegate.showSetup_."""
    ctrl = SetupWindowController.alloc().init()
    ctrl._on_save_cb       = on_save
    ctrl._on_disconnect_cb = on_disconnect
    ctrl._current_cookie   = current_cookie
    ctrl._buildPanel()
    SetupWindowController._instance = ctrl


class SetupWindowController(NSObject):
    """
    NSPanel-based settings dialog.
    Shows current account info + option to disconnect or enter a new session.
    Open via module-level _open_setup(on_save, on_disconnect, current_cookie).
    _instance holds a strong reference to prevent GC.
    """
    _instance = None

    @objc.python_method
    def _buildPanel(self):
        W, H  = float(SETUP_W), float(SETUP_H)
        PAD   = 20.0
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, W, H), style, NSBackingStoreBuffered, False
        )
        self._panel.setTitle_("Claude Usage Monitor – Settings")
        self._panel.center()
        c = self._panel.contentView()

        # ── Header (y = H-68 … H) ─────────────────────────────────────────
        # Claude star icon rendered from SVG
        star_iv = NSImageView.alloc().initWithFrame_(NSMakeRect(PAD, H - 58, 28, 28))
        star_iv.setImage_(_make_status_icon(50.0))   # half-used → orange-ish tint
        c.addSubview_(star_iv)

        c.addSubview_(_make_label(
            "Claude Usage Monitor",
            font=NSFont.boldSystemFontOfSize_(15.0),
            color=NSColor.labelColor(),
            frame=NSMakeRect(PAD + 38, H - 44, W - PAD * 2 - 38, 22),
        ))
        c.addSubview_(_make_label(
            f"Version {APP_VERSION}",
            font=NSFont.systemFontOfSize_(11.0),
            color=NSColor.tertiaryLabelColor(),
            frame=NSMakeRect(PAD + 38, H - 60, W - PAD * 2 - 38, 16),
        ))

        # Header divider
        c.addSubview_(_make_divider(NSMakeRect(0, H - 72, W, 1)))

        # ── CURRENT ACCOUNT section (y = H-72 … H-206) ───────────────────
        c.addSubview_(_make_label(
            "CURRENT ACCOUNT",
            font=NSFont.systemFontOfSize_(10.0),
            color=NSColor.tertiaryLabelColor(),
            frame=NSMakeRect(PAD, H - 92, W - PAD * 2, 14),
        ))

        # Connection status dot + label
        has_session = bool(getattr(self, '_current_cookie', ''))
        status_text = ("● Connected" if has_session else "○ Not connected")
        status_col  = (_nscolor(_CLR_OK) if has_session else NSColor.secondaryLabelColor())
        self._acct_status_lbl = _make_label(
            status_text,
            font=NSFont.systemFontOfSize_(12.0),
            color=status_col,
            frame=NSMakeRect(PAD, H - 114, 220, 18),
        )
        c.addSubview_(self._acct_status_lbl)

        # Session key row
        c.addSubview_(_make_label(
            "Session key",
            font=NSFont.systemFontOfSize_(11.0),
            color=NSColor.secondaryLabelColor(),
            frame=NSMakeRect(PAD, H - 136, 100, 16),
        ))
        masked = _mask_session_key(getattr(self, '_current_cookie', ''))
        self._key_val_lbl = _make_label(
            masked,
            font=NSFont.monospacedSystemFontOfSize_weight_(11.0, 0.0),
            color=NSColor.labelColor(),
            frame=NSMakeRect(PAD, H - 156, W - PAD * 2 - 100, 18),
        )
        c.addSubview_(self._key_val_lbl)

        # [Copy Key] button (top-right of key row)
        self._copy_btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(W - PAD - 90, H - 158, 90, 22)
        )
        self._copy_btn.setTitle_("Copy Key")
        self._copy_btn.setBezelStyle_(NSBezelStyleRounded)
        self._copy_btn.setFont_(NSFont.systemFontOfSize_(11.0))
        self._copy_btn.setTarget_(self)
        self._copy_btn.setAction_("onCopyKey:")
        self._copy_btn.setEnabled_(has_session)
        c.addSubview_(self._copy_btn)

        # [Disconnect] button
        self._disconnect_btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(W - PAD - 110, H - 188, 110, 26)
        )
        self._disconnect_btn.setTitle_("Disconnect")
        self._disconnect_btn.setBezelStyle_(NSBezelStyleRounded)
        self._disconnect_btn.setTarget_(self)
        self._disconnect_btn.setAction_("onDisconnect:")
        self._disconnect_btn.setEnabled_(has_session)
        try:
            self._disconnect_btn.setContentTintColor_(_nscolor(_CLR_ERR))
        except AttributeError:
            pass
        c.addSubview_(self._disconnect_btn)

        # Account section divider
        c.addSubview_(_make_divider(NSMakeRect(0, H - 204, W, 1)))

        # ── ADD / REPLACE SESSION section (y = H-204 … H-408) ────────────
        c.addSubview_(_make_label(
            "ADD / REPLACE SESSION",
            font=NSFont.systemFontOfSize_(10.0),
            color=NSColor.tertiaryLabelColor(),
            frame=NSMakeRect(PAD, H - 222, W - PAD * 2, 14),
        ))

        instr_text = (
            "1. Open claude.ai in Chrome  →  F12  →  Network tab  →  reload the page\n"
            "2. Click any claude.ai request  →  Request Headers  →  find 'Cookie:'\n"
            "3. Right-click the value  →  Copy  →  paste below, then click Connect"
        )
        c.addSubview_(_make_label(
            instr_text,
            font=NSFont.systemFontOfSize_(11.0),
            color=NSColor.secondaryLabelColor(),
            frame=NSMakeRect(PAD, H - 278, W - PAD * 2, 52), wraps=True,
        ))

        # Scroll + text view for cookie input
        scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(PAD, H - 364, W - PAD * 2, 80)
        )
        scroll.setBorderType_(2)
        scroll.setHasVerticalScroller_(True)
        tv = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, W - PAD * 2 - 20, 80)
        )
        tv.setFont_(NSFont.monospacedSystemFontOfSize_weight_(10.0, 0.0))
        tv.setEditable_(True)
        tv.setSelectable_(True)
        try:
            tv.setAutomaticQuoteSubstitutionEnabled_(False)
        except AttributeError:
            pass
        tv.setSmartInsertDeleteEnabled_(False)
        scroll.setDocumentView_(tv)
        c.addSubview_(scroll)
        self._tv = tv

        # Validation status label (left of Connect button)
        self._connect_status_lbl = _make_label(
            "",
            font=NSFont.systemFontOfSize_(11.0),
            color=_nscolor(_CLR_ERR),
            frame=NSMakeRect(PAD, H - 386, W - PAD * 2 - 100, 16),
        )
        c.addSubview_(self._connect_status_lbl)

        # [Connect] button
        self._connect_btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(W - PAD - 90, H - 388, 90, 26)
        )
        self._connect_btn.setTitle_("Connect")
        self._connect_btn.setBezelStyle_(NSBezelStyleRounded)
        self._connect_btn.setKeyEquivalent_("\r")
        self._connect_btn.setTarget_(self)
        self._connect_btn.setAction_("onConnect:")
        c.addSubview_(self._connect_btn)

        # Session section divider
        c.addSubview_(_make_divider(NSMakeRect(0, H - 404, W, 1)))

        # ── Footer (y = 0 … H-404) ────────────────────────────────────────
        # Launch at Login checkbox (top of footer, below divider)
        autostart_chk = NSButton.alloc().initWithFrame_(
            NSMakeRect(PAD, 46, 200, 18)
        )
        autostart_chk.setButtonType_(_CHECKBOX_TYPE)
        autostart_chk.setTitle_("Launch at Login")
        autostart_chk.setFont_(NSFont.systemFontOfSize_(12.0))
        autostart_chk.setState_(1 if _autostart_enabled() else 0)
        autostart_chk.setTarget_(self)
        autostart_chk.setAction_("onToggleAutostart:")
        c.addSubview_(autostart_chk)
        self._autostart_chk = autostart_chk

        # [Open claude.ai] link button
        link_btn = NSButton.alloc().initWithFrame_(NSMakeRect(PAD, 14, 150, 26))
        link_btn.setTitle_("Open claude.ai ↗")
        link_btn.setBordered_(False)
        link_btn.setFont_(NSFont.systemFontOfSize_(11.0))
        try:
            link_btn.setContentTintColor_(NSColor.linkColor())
        except AttributeError:
            pass
        link_btn.setTarget_(self)
        link_btn.setAction_("onOpenClaude:")
        c.addSubview_(link_btn)

        # Version centred in footer
        c.addSubview_(_make_label(
            f"v{APP_VERSION}",
            font=NSFont.systemFontOfSize_(10.0),
            color=NSColor.tertiaryLabelColor(),
            frame=NSMakeRect(0, 18, W, 16),
            align=NSTextAlignmentCenter,
        ))

        # [Close] button
        close_btn = NSButton.alloc().initWithFrame_(NSMakeRect(W - PAD - 80, 14, 80, 26))
        close_btn.setTitle_("Close")
        close_btn.setBezelStyle_(NSBezelStyleRounded)
        close_btn.setTarget_(self)
        close_btn.setAction_("onCancel:")
        c.addSubview_(close_btn)

        # Temporarily promote to regular app so the panel can receive keyboard events.
        # Menu-bar-only (accessory) apps don't get keyboard routing by default.
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(0)          # NSApplicationActivationPolicyRegular
        app.activateIgnoringOtherApps_(True) # bring app to front BEFORE making key
        self._panel.makeKeyAndOrderFront_(None)
        self._panel.makeFirstResponder_(self._tv)  # put cursor straight into the field

    @objc.python_method
    def _restore_accessory_policy(self):
        """Switch back to menu-bar-only mode after the settings panel closes."""
        NSApplication.sharedApplication().setActivationPolicy_(_POLICY_ACCESSORY)

    def onCancel_(self, sender):
        # Cancel any pending performSelector:afterDelay: (e.g. finishSave:) before
        # dropping the strong reference, otherwise ObjC may call into a freed object.
        NSObject.cancelPreviousPerformRequestsWithTarget_(self)
        self._panel.close()
        SetupWindowController._instance = None
        self._restore_accessory_policy()

    def onCopyKey_(self, sender):
        raw = getattr(self, '_current_cookie', '')
        if raw:
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(raw, "public.utf8-plain-text")
            self._copy_btn.setTitle_("Copied!")
            self.performSelector_withObject_afterDelay_("resetCopyBtn:", None, 1.5)

    def resetCopyBtn_(self, _):
        self._copy_btn.setTitle_("Copy Key")

    def onDisconnect_(self, sender):
        NSObject.cancelPreviousPerformRequestsWithTarget_(self)
        self._panel.close()
        SetupWindowController._instance = None
        self._restore_accessory_policy()
        cb = getattr(self, '_on_disconnect_cb', None)
        if cb:
            cb()

    def onOpenClaude_(self, sender):
        try:
            url = NSURL.URLWithString_("https://claude.ai")
            if NSWorkspace:
                NSWorkspace.sharedWorkspace().openURL_(url)
        except Exception:
            pass

    def onToggleAutostart_(self, sender):
        """Called when the Launch at Login checkbox is clicked in Settings."""
        new_state = _toggle_autostart()
        # Keep checkbox in sync (toggle_autostart returns the new enabled state)
        self._autostart_chk.setState_(1 if new_state else 0)

    def onConnect_(self, sender):
        raw = str(self._tv.string()).strip()
        ok, err = cookie_string_looks_valid(raw)
        if not ok:
            self._connect_status_lbl.setStringValue_(err)
            self._connect_status_lbl.setTextColor_(_nscolor(_CLR_ERR))
            return
        self._connect_btn.setEnabled_(False)
        self._connect_status_lbl.setStringValue_("Validating…")
        self._connect_status_lbl.setTextColor_(NSColor.secondaryLabelColor())
        threading.Thread(target=self._validate_worker, args=(raw,), daemon=True).start()

    @objc.python_method
    def _validate_worker(self, raw):
        api = ClaudeAPI(raw)
        ok, err = api.validate()
        # Pass results via withObject: — avoids shared mutable instance variables
        # that could be clobbered if a second validation is started concurrently.
        result = {"ok": ok, "err": err, "raw": raw}
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "afterValidate:", result, False
        )

    def afterValidate_(self, result):
        ok  = result["ok"]
        err = result.get("err", "")
        raw = result.get("raw", "")
        if ok:
            self._connect_status_lbl.setStringValue_("✓ Session verified!")
            self._connect_status_lbl.setTextColor_(_nscolor(_CLR_OK))
            self._save_raw = raw
            self.performSelector_withObject_afterDelay_("finishSave:", None, 0.6)
        else:
            self._connect_status_lbl.setStringValue_(str(err)[:120])
            self._connect_status_lbl.setTextColor_(_nscolor(_CLR_ERR))
            self._connect_btn.setEnabled_(True)

    def finishSave_(self, _):
        self._on_save_cb(self._save_raw)
        self._panel.close()
        SetupWindowController._instance = None
        self._restore_accessory_policy()


# ── App delegate ──────────────────────────────────────────────────────────────
class AppDelegate(NSObject):
    """
    NSApplicationDelegate.
    Owns the status bar item, NSPopover, polling timer, and coordinates all UI updates.
    """

    _AUTH_PHRASES = ("403", "401", "cloudflare", "not authenticated",
                     "invalid", "expired", "session")

    def applicationDidFinishLaunching_(self, notification):
        app = NSApplication.sharedApplication()

        # Hide from Dock — this is a menu bar only app
        app.setActivationPolicy_(_POLICY_ACCESSORY)

        # Build a minimal main menu so that Cmd+V / Cmd+C / Cmd+A etc. are
        # dispatched to NSTextView first-responders in the Settings panel.
        # Without an Edit submenu the system has no key-equivalent table to
        # consult and all editing shortcuts are silently swallowed.
        self._build_main_menu(app)

        # State
        self._cfg              = self._load_cfg()
        self._api              = None
        self._org_id           = None
        self._auth_bad         = False
        self._timer            = None
        self._last_session_pct = 0.0           # for icon redraw on theme change
        self._worker_lock      = threading.Lock()   # B-3: prevent concurrent workers
        self._org_id_lock      = threading.Lock()   # B-2: protect _org_id check-then-set

        # Register for system dark/light mode changes (to redraw the icon)
        if NSDistributedNotificationCenter is not None:
            try:
                nc = NSDistributedNotificationCenter.defaultCenter()
                nc.addObserver_selector_name_object_(
                    self,
                    "themeDidChange:",
                    "AppleInterfaceThemeChangedNotification",
                    None,
                )
            except Exception:
                pass

        # Status bar item
        self._item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        btn = self._item.button()
        btn.setImage_(_make_status_icon(0.0))
        btn.setTarget_(self)
        btn.setAction_("handleClick:")
        # Fire action on both left-click and right-click
        btn.sendActionOn_(_CLICK_MASK)

        # Popover + view controller
        self._vc = UsageViewController.alloc().init()
        self._popover = NSPopover.alloc().init()
        self._popover.setContentViewController_(self._vc)
        self._popover.setBehavior_(1)   # NSPopoverBehaviorTransient
        self._popover.setContentSize_(NSSize(POPUP_W, POPUP_H))

        # Start data or show setup
        if self._cfg.get("cookie_str"):
            self._init_api(self._cfg["cookie_str"])
            self._start_polling()
        else:
            self.performSelector_withObject_afterDelay_("showSetup:", None, 0.15)

    def handleClick_(self, sender):
        """Dispatch left-click → popover, right-click → context menu."""
        event = NSApplication.sharedApplication().currentEvent()
        if event is not None and int(event.type()) == _RIGHT_MOUSE_DOWN:
            self._showContextMenu()
        else:
            self.togglePopover_(sender)

    def togglePopover_(self, sender):
        if self._popover.isShown():
            self._popover.performClose_(sender)
        else:
            btn = self._item.button()
            self._popover.showRelativeToRect_ofView_preferredEdge_(
                btn.bounds(), btn,
                3   # NSRectEdgeMaxY — opens below the menu bar
            )

    @objc.python_method
    def _showContextMenu(self):
        """Build and display the right-click context menu."""
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)

        # ── Launch at Login (checkmark reflects current state) ─────────────
        autostart_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Launch at Login", "toggleAutostart:", ""
        )
        autostart_item.setTarget_(self)
        autostart_item.setState_(1 if _autostart_enabled() else 0)
        autostart_item.setEnabled_(True)
        menu.addItem_(autostart_item)

        menu.addItem_(NSMenuItem.separatorItem())

        # ── Quit ────────────────────────────────────────────────────────────
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "quitApp:", ""
        )
        quit_item.setTarget_(self)
        quit_item.setEnabled_(True)
        menu.addItem_(quit_item)

        # popUpStatusItemMenu_ positions the menu correctly under the icon
        self._item.popUpStatusItemMenu_(menu)

    def toggleAutostart_(self, sender):
        """Toggle LaunchAgent on/off (called from both context menu and Settings)."""
        _toggle_autostart()

    def quitApp_(self, sender):
        NSApplication.sharedApplication().terminate_(sender)

    def showSetup_(self, _):
        _open_setup(
            on_save=self._on_cookie_saved,
            on_disconnect=self._on_disconnect,
            current_cookie=self._cfg.get("cookie_str", ""),
        )

    def refreshNow_(self, _):
        self._refresh_now()

    def themeDidChange_(self, notification):
        """Called when the system switches between dark and light mode."""
        # Redraw the status bar icon with the last-known usage %
        self._item.button().setImage_(_make_status_icon(self._last_session_pct))

    @objc.python_method
    def _build_main_menu(self, app):
        """
        Install a minimal NSApplication main menu containing an Edit submenu.
        This is required for Cmd+V / Cmd+C / Cmd+X / Cmd+A / Cmd+Z to be
        dispatched as key-equivalents to any NSTextView first-responder.
        Without it the system has no key-equivalent table and all shortcuts
        are silently swallowed, even when the app is the active foreground app.
        """
        main_menu = NSMenu.alloc().init()

        # ── Apple / app menu (index 0 — title is ignored by macOS) ────────
        app_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Apple", "", ""
        )
        app_menu = NSMenu.alloc().init()
        app_item.setSubmenu_(app_menu)
        main_menu.addItem_(app_item)

        # ── Edit menu ──────────────────────────────────────────────────────
        edit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Edit", "", ""
        )
        edit_menu = NSMenu.alloc().initWithTitle_("Edit")
        for title, action, key in [
            ("Undo",       "undo:",      "z"),
            ("Redo",       "redo:",      "Z"),
            ("-", None, None),
            ("Cut",        "cut:",       "x"),
            ("Copy",       "copy:",      "c"),
            ("Paste",      "paste:",     "v"),
            ("Select All", "selectAll:", "a"),
        ]:
            if title == "-":
                edit_menu.addItem_(NSMenuItem.separatorItem())
            else:
                edit_menu.addItem_(
                    NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                        title, action, key
                    )
                )
        edit_item.setSubmenu_(edit_menu)
        main_menu.addItem_(edit_item)

        app.setMainMenu_(main_menu)

    # ── Config ────────────────────────────────────────────────────────────
    @objc.python_method
    def _load_cfg(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text())
            except Exception:
                pass
        return {}

    @objc.python_method
    def _save_cfg(self):
        # Write atomically: create tmp → chmod 0600 → write → rename.
        # This prevents partial-write corruption and keeps the credential file
        # owner-readable only (not world-readable like the default 0644 umask).
        data = json.dumps(self._cfg, indent=2).encode()
        fd, tmp = tempfile.mkstemp(dir=CONFIG_FILE.parent, prefix=".claude_w_")
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, data)
            os.close(fd)
            os.replace(tmp, CONFIG_FILE)  # POSIX atomic rename
        except Exception:
            try: os.close(fd)
            except Exception: pass
            try: os.unlink(tmp)
            except Exception: pass
            raise

    @objc.python_method
    def _init_api(self, cookie_str: str):
        self._api    = ClaudeAPI(cookie_str)
        self._org_id = None

    @objc.python_method
    def _on_cookie_saved(self, cookie_str: str):
        self._cfg["cookie_str"] = cookie_str
        self._cfg.pop("session_key", None)
        self._save_cfg()
        self._init_api(cookie_str)
        self._auth_bad         = False
        self._last_session_pct = 0.0
        self._vc.hideAuthError()
        if self._timer:
            self._timer.invalidate()
            self._timer = None
        self._start_polling()

    @objc.python_method
    def _on_disconnect(self):
        """Called when the user clicks Disconnect in the settings panel."""
        self._cfg.pop("cookie_str", None)
        self._cfg.pop("session_key", None)
        try:
            self._save_cfg()
        except Exception:
            pass
        self._api              = None
        self._org_id           = None
        self._auth_bad         = False
        self._last_session_pct = 0.0
        if self._timer:
            self._timer.invalidate()
            self._timer = None
        # Reset icon and popup status
        self._item.button().setImage_(_make_status_icon(0.0))
        self._vc.setStatus_("No session configured")
        self._vc.hideAuthError()
        # Re-open setup panel so the user can connect a new session
        self.performSelector_withObject_afterDelay_("showSetup:", None, 0.3)

    # ── Polling ───────────────────────────────────────────────────────────
    @objc.python_method
    def _start_polling(self):
        # B-4: always invalidate an existing timer before creating a new one
        if self._timer:
            self._timer.invalidate()
            self._timer = None
        self._refresh_now()
        self._timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            float(REFRESH_SEC), self, "timerFired:", None, True
        )

    def timerFired_(self, timer):
        self._refresh_now()

    @objc.python_method
    def _refresh_now(self):
        # B-3: skip if a worker is already running (e.g. user hammers refresh button)
        if not self._worker_lock.acquire(blocking=False):
            return
        self._vc.setStatus_("Refreshing…")
        def _run():
            try:
                self._worker()
            finally:
                self._worker_lock.release()
        threading.Thread(target=_run, daemon=True).start()

    # ── Background worker ─────────────────────────────────────────────────
    @objc.python_method
    def _worker(self):
        try:
            if not self._api:
                return
            # B-2: double-checked lock prevents concurrent threads from both
            # calling get_account() when _org_id is None on first run.
            if not self._org_id:
                with self._org_id_lock:
                    if not self._org_id:
                        account      = self._api.get_account()
                        self._org_id = self._api._org_id(account)
                        log(f"org_id resolved: {bool(self._org_id)}")

            data, endpoint = self._api.get_limits(self._org_id)

            if data is None:
                # B-1: pass error string via withObject: — no shared instance var
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "consumeError:", "No limits endpoint found.", False
                )
            else:
                parsed = ClaudeAPI.parse(data)
                log(f"parsed session={parsed.get('session') and 'ok' or 'none'} "
                    f"weekly={parsed.get('weekly') and 'ok' or 'none'}")
                # Extract raw weekly reset timestamp for absolute formatting
                week_raw  = data.get("seven_day") or data.get("sevenDay") or {}
                weekly_ts = (
                    week_raw.get("resets_at") or week_raw.get("reset_at")
                    or week_raw.get("resetsAt")
                ) if isinstance(week_raw, dict) else None

                # B-1: pass result dict via withObject: — eliminates shared mutable state
                result = {
                    "parsed":    parsed,
                    "endpoint":  endpoint,
                    "weekly_ts": weekly_ts,
                }
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "consumeResult:", result, False
                )
        except Exception as e:
            log(f"worker error: {e}")
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "consumeError:", str(e)[:120], False
            )

    # ── Main-thread consumers ─────────────────────────────────────────────
    def consumeResult_(self, result):
        # result is the dict passed via withObject: — no shared mutable state (B-1)
        global _limits_cache
        parsed    = result["parsed"]
        endpoint  = result["endpoint"]
        weekly_ts = result.get("weekly_ts")

        _limits_cache = {
            "updated_at": datetime.now().isoformat(),
            "endpoint":   endpoint,
            **parsed,
        }

        s = parsed.get("session")
        session_pct = s["used_pct"] if s else 0.0
        self._last_session_pct = session_pct   # keep for icon redraw on theme change

        # Refresh icon with current session usage
        self._item.button().setImage_(_make_status_icon(session_pct))

        # Update popup content
        self._vc.applyData_weeklyTs_(parsed, weekly_ts)

        if self._auth_bad:
            self._auth_bad = False
            self._vc.hideAuthError()

        now = datetime.now().strftime("%H:%M")
        self._vc.setStatus_(f"Updated {now}")

    def consumeError_(self, msg):
        # msg is the string passed via withObject: — no shared mutable state (B-1)
        msg = str(msg)
        self._vc.setStatus_(f"⚠ {msg[:70]}")
        msg_lower = msg.lower()
        if any(p in msg_lower for p in self._AUTH_PHRASES) and not self._auth_bad:
            self._auth_bad = True
            self._vc.showAuthError_(msg)


# ── Local HTTP API ────────────────────────────────────────────────────────────
_limits_cache: dict = {}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def do_GET(self):
        if self.path in ("/", "/limits"):
            body = json.dumps(_limits_cache, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            # CORS: only allow same-machine origins (localhost / 127.x), never wildcard.
            # This prevents any browser tab from silently reading the org UUID.
            origin = self.headers.get("Origin", "")
            if origin.startswith("http://localhost:") or origin.startswith("http://127."):
                self.send_header("Access-Control-Allow-Origin", origin)
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()


def _start_local_api():
    try:
        srv = HTTPServer(("127.0.0.1", LOCAL_API_PORT), _Handler)
        log(f"Local API on http://127.0.0.1:{LOCAL_API_PORT}/")
        srv.serve_forever()
    except OSError as e:
        log(f"Local API failed on port {LOCAL_API_PORT}: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _init_log_file()   # lock down log file permissions before first write
    # S-1: also lock down the config file if it already exists at wrong permissions
    try:
        if CONFIG_FILE.exists():
            os.chmod(CONFIG_FILE, 0o600)
    except Exception:
        pass
    threading.Thread(target=_start_local_api, daemon=True).start()

    app = NSApplication.sharedApplication()
    # Belt-and-suspenders: hide dock icon before delegate fires
    app.setActivationPolicy_(_POLICY_ACCESSORY)

    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()   # blocks like mainloop() — daemon threads keep running
