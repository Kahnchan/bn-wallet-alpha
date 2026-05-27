#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
PORT="${BN_ALPHA_CALENDAR_PORT:-8765}"
APP_DIR="${BN_ALPHA_CALENDAR_HOME:-$HOME/Library/Application Support/BnWalletAlphaCalendar}"
APP_SCRIPT_DIR="$APP_DIR/scripts"
APP_PUBLIC_DIR="$APP_DIR/public"
REFRESH_LABEL="com.codex.bn-alpha-calendar-refresh"
SERVER_LABEL="com.codex.bn-alpha-calendar-server"
AGENT_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$APP_DIR/logs"
PUBLIC_DIR="$APP_PUBLIC_DIR"

mkdir -p "$AGENT_DIR" "$LOG_DIR" "$PUBLIC_DIR" "$APP_SCRIPT_DIR" "$APP_DIR/data"
cp "$ROOT/scripts/update_binance_alpha_calendar.py" "$APP_SCRIPT_DIR/update_binance_alpha_calendar.py"
chmod +x "$APP_SCRIPT_DIR/update_binance_alpha_calendar.py"

"$PYTHON_BIN" "$APP_SCRIPT_DIR/update_binance_alpha_calendar.py" --lookback-days 3 --horizon-days 30 --check-time 20:30

cat > "$AGENT_DIR/$REFRESH_LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$REFRESH_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$APP_SCRIPT_DIR/update_binance_alpha_calendar.py</string>
    <string>--lookback-days</string>
    <string>3</string>
    <string>--horizon-days</string>
    <string>30</string>
    <string>--check-time</string>
    <string>20:30</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$APP_DIR</string>
  <key>StartInterval</key>
  <integer>600</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/refresh.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/refresh.err.log</string>
</dict>
</plist>
PLIST

cat > "$AGENT_DIR/$SERVER_LABEL.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$SERVER_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>-m</string>
    <string>http.server</string>
    <string>$PORT</string>
    <string>--bind</string>
    <string>127.0.0.1</string>
    <string>--directory</string>
    <string>$PUBLIC_DIR</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$PUBLIC_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/server.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/server.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$AGENT_DIR/$REFRESH_LABEL.plist" >/dev/null 2>&1 || true
launchctl bootout "gui/$(id -u)" "$AGENT_DIR/$SERVER_LABEL.plist" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$AGENT_DIR/$REFRESH_LABEL.plist"
launchctl bootstrap "gui/$(id -u)" "$AGENT_DIR/$SERVER_LABEL.plist"
launchctl kickstart -k "gui/$(id -u)/$REFRESH_LABEL"
launchctl kickstart -k "gui/$(id -u)/$SERVER_LABEL"

echo "Installed launchd jobs:"
echo "  $REFRESH_LABEL refreshes the ICS every 10 minutes"
echo "  $SERVER_LABEL serves the calendar feed locally"
echo
echo "Apple Calendar subscription URL:"
echo "  http://127.0.0.1:$PORT/binance-alpha-airdrops.ics"
echo
echo "In Calendar.app: File > New Calendar Subscription... > paste the URL above."
