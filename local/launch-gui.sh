#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL="$ROOT/local"
URL="http://127.0.0.1:43122"

port_open() {
  (echo >/dev/tcp/127.0.0.1/"$1") >/dev/null 2>&1
}

if ! port_open 43121; then
  cd "$ROOT/server"
  export PYTHONPATH="$ROOT/server"
  nohup python3 -m app.main >/tmp/chat-admin-server.log 2>&1 &
fi

if ! port_open 43122; then
  cd "$LOCAL"
  nohup npm run dev >/tmp/chat-admin-gui.log 2>&1 &
fi

for _ in $(seq 1 40); do
  if port_open 43122; then
    break
  fi
  sleep 0.25
done

xdg-open "$URL" >/dev/null 2>&1 || gio open "$URL" >/dev/null 2>&1 || true
