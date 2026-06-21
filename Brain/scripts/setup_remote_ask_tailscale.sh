#!/usr/bin/env bash
set -euo pipefail

TAILSCALE_BIN="$(command -v tailscale || true)"
if [[ -z "$TAILSCALE_BIN" && -x "/Applications/Tailscale.app/Contents/MacOS/Tailscale" ]]; then
  TAILSCALE_BIN="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
fi

if [[ -z "$TAILSCALE_BIN" ]]; then
  echo "Tailscale is not installed. Install it on this Mac and your phone, sign into both, then run this script again."
  exit 1
fi

"$TAILSCALE_BIN" status >/dev/null
"$TAILSCALE_BIN" serve --bg 8766
"$TAILSCALE_BIN" serve status
