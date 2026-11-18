#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
venv_directory="$project_root/.venv"

if ! command -v brew >/dev/null 2>&1 && [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Local Transcriber supports only Apple Silicon Macs (M1, M2, M3, M4 and newer)."
  exit 1
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is not installed. Follow docs/installation-macos.md, then run this file again."
  exit 1
fi

missing_packages=()
command -v python3.11 >/dev/null 2>&1 || missing_packages+=("python@3.11")
command -v ffmpeg >/dev/null 2>&1 || missing_packages+=("ffmpeg")

if ((${#missing_packages[@]})); then
  echo "Installing required components: ${missing_packages[*]}"
  brew install "${missing_packages[@]}"
fi

if [[ ! -x "$venv_directory/bin/python" ]]; then
  echo "Creating the Python 3.11 environment..."
  python3.11 -m venv "$venv_directory"
fi

venv_version="$($venv_directory/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$venv_version" != "3.11" ]]; then
  echo "The .venv directory uses Python $venv_version instead of 3.11."
  echo "Delete .venv and run start-macos.command again."
  exit 1
fi

echo "Installing Local Transcriber components..."
"$venv_directory/bin/python" -m pip install --upgrade pip
"$venv_directory/bin/python" -m pip install -e "$project_root"
"$venv_directory/bin/transcriber" doctor

echo "Installation complete. Use start-macos.command next time."
