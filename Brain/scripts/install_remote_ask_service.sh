#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.sanchit.aibrain.remote-ask"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON_BIN="$(command -v python3)"
LOG_DIR="$ROOT/.aibrain/logs"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$ROOT/scripts/remote_ask_server.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/remote-ask.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/remote-ask.error.log</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo "Ask My Brain service installed at http://127.0.0.1:8766"
