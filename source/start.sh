#!/usr/bin/env sh
# One-command launcher for macOS and Linux.
set -eu
cd "$(dirname "$0")"
PORT="${PORT:-8412}"
echo "C2M craft prototype -> http://127.0.0.1:${PORT}"
exec python -m c2m_craft serve --host 127.0.0.1 --port "${PORT}"
