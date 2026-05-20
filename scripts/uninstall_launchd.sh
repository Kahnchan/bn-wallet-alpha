#!/usr/bin/env bash
set -euo pipefail

REFRESH_LABEL="com.codex.bn-alpha-calendar-refresh"
SERVER_LABEL="com.codex.bn-alpha-calendar-server"
AGENT_DIR="$HOME/Library/LaunchAgents"

launchctl bootout "gui/$(id -u)" "$AGENT_DIR/$REFRESH_LABEL.plist" >/dev/null 2>&1 || true
launchctl bootout "gui/$(id -u)" "$AGENT_DIR/$SERVER_LABEL.plist" >/dev/null 2>&1 || true
rm -f "$AGENT_DIR/$REFRESH_LABEL.plist" "$AGENT_DIR/$SERVER_LABEL.plist"

echo "Removed Binance Alpha calendar launchd jobs."
