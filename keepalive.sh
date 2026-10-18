#!/usr/bin/env bash
# Keep the userbot alive 24/7. Restarts it if it crashes.
# Usage: ./keepalive.sh   (starts in background, logs to userbot.log)
set -u

PY="${PY:-/data/data/com.termux/files/usr/bin/python}"
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$DIR/userbot.log"

log() { echo "[keepalive $(date '+%F %T')] $*" >> "$LOG"; }

if [ -f "$DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$DIR/.env"
  set +a
fi

log "keeper starting; initial launch"
while true; do
  if [ -f "$DIR/userbot.pid" ]; then
    pid="$(cat "$DIR/userbot.pid" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      sleep 15
      continue
    fi
    rm -f "$DIR/userbot.pid"
  fi

  (cd "$DIR" && exec "$PY" main.py) >> "$LOG" 2>&1 &
  echo $! > "$DIR/userbot.pid"
  log "bot started (pid $!)"

  wait "$!" 2>/dev/null
  log "bot exited; restarting in 5s"
  sleep 5
done