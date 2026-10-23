#!/usr/bin/env bash
# Renders og-image.html to _deploy/assets/og-image.png (1200x630) with headless Edge (WSL).
# After changing the image, bump IMAGE_VERSION in site_meta.py and re-run it so
# LinkedIn/Slack fetch the new picture instead of a cached one.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
edge="/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
"$edge" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=1200,630 \
  --screenshot="$(wslpath -w "$here/../../../../_deploy/assets/og-image.png")" \
  "$(wslpath -w "$here/og-image.html")"
