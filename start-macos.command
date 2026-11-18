#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")" && pwd)"
transcriber="$project_root/.venv/bin/transcriber"

if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

if [[ ! -x "$transcriber" ]]; then
  echo "First launch: preparing Local Transcriber..."
  "$project_root/scripts/setup-macos.sh"
fi

url="http://127.0.0.1:8000"
echo "Starting Local Transcriber: $url"
echo "Keep this window open while the application is running. Press Control+C to stop."
(sleep 2; open "$url") &
exec "$transcriber" web
