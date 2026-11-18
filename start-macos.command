#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")" && pwd)"
transcriber="$project_root/.venv/bin/transcriber"

# GitHub source ZIP archives can lose executable permissions after extraction. When the user
# starts this file once with `bash`, repair the permissions so future launches work by double-click.
chmod +x "$0" "$project_root/scripts/setup-macos.sh" 2>/dev/null || true

if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

if [[ ! -x "$transcriber" ]]; then
  echo "First launch: preparing Local Transcriber..."
  bash "$project_root/scripts/setup-macos.sh"
fi

url="http://127.0.0.1:8000"
echo "Starting Local Transcriber: $url"
echo "Keep this window open while the application is running. Press Control+C to stop."
(sleep 2; open "$url") &
exec "$transcriber" web
