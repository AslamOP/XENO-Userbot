#!/usr/bin/env bash
# Add a plugin to a running XENO instance.
#
#   ./addplugin.sh myplugin.py                 # upload + restart + verify
#   ./addplugin.sh myplugin.py --no-restart    # upload only
#   ./addplugin.sh --remove myplugin.py        # delete it
#
# Env overrides: XENO_HOST XENO_USER XENO_KEY XENO_DIR XENO_SERVICE
set -uo pipefail

HOST="${XENO_HOST:-13.220.255.57}"
USER_="${XENO_USER:-ubuntu}"
KEY="${XENO_KEY:-/tmp/personal.pem}"
DIR="${XENO_DIR:-/home/ubuntu/xeno}"
SERVICE="${XENO_SERVICE:-xeno}"

SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
      -o ConnectTimeout=20 "$USER_@$HOST")

REMOVE=0
RESTART=1
for arg in "$@"; do
  case "$arg" in
    --no-restart) RESTART=0 ;;
    --remove|-r)  REMOVE=1 ;;
    -h|--help)    sed -n '2,12p' "$0"; exit 0 ;;
    -*)           echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

FILES=()
for arg in "$@"; do
  case "$arg" in
    -*) ;;
    *) FILES+=("$arg") ;;
  esac
done

if [ ${#FILES[@]} -eq 0 ]; then
  echo "usage: $0 [--remove] [--no-restart] <plugin.py> [...]" >&2
  exit 2
fi

[ -f "$KEY" ] || { echo "SSH key not found: $KEY" >&2; exit 1; }

for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "no such file: $f" >&2; exit 1; }
done

# Syntax-check locally before touching the server.
for f in "${FILES[@]}"; do
  case "$f" in
    *_*) continue ;;
  esac
  python3 -m py_compile "$f" || { echo "$f: syntax error — not uploading" >&2; exit 1; }
done

SSH_OK=1
"${SSH[@]}" true 2>/dev/null || SSH_OK=0
if [ "$SSH_OK" -eq 0 ]; then
  echo "cannot reach $USER_@$HOST — uploading anyway is not possible, copying locally instead:"
  DEST="plugins"
  for f in "${FILES[@]}"; do cp "$f" "$DEST/"; echo "  copied $f -> ./plugins/"; done
  echo
  echo "Then restart locally:  python main.py"
  exit 1
fi

if [ "$REMOVE" -eq 1 ]; then
  for f in "${FILES[@]}"; do
    base="$(basename "$f")"
    "${SSH[@]}" "rm -f '$DIR/plugins/$base' && echo removed $base"
  done
else
  for f in "${FILES[@]}"; do
    base="$(basename "$f")"
    scp -i "$KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -q "$f" "$USER_@$HOST:$DIR/plugins/$base" || exit 1
    echo "uploaded $base -> $DIR/plugins/$base"
  done
fi

if [ "$RESTART" -eq 0 ]; then
  echo "skipped restart (--no-restart); run: sudo systemctl restart $SERVICE"
  exit 0
fi

state="$("${SSH[@]}" "systemctl is-active $SERVICE 2>/dev/null || echo inactive")"
if [ "$state" != "active" ]; then
  echo
  echo "service is '$state' — files are in place but not reloaded."
  echo "If this is a fresh install it needs .env first:"
  echo "  ssh -i $KEY $USER_@$HOST 'nano $DIR/.env'   # API_ID / API_HASH / OWNER_ID"
  echo "then:  ssh -i $KEY $USER_@$HOST 'sudo systemctl start $SERVICE'"
  exit 0
fi

echo "restarting $SERVICE ..."
"${SSH[@]}" "sudo systemctl restart $SERVICE && sleep 6"

echo
echo "=== plugin load results ==="
"${SSH[@]}" "sudo journalctl -u $SERVICE --since '30 seconds ago' --no-pager \
   | grep -E 'Loaded plugin: |Failed to load plugin' | tail -20"

for f in "${FILES[@]}"; do
  base="$(basename "$f" .py)"
  if "${SSH[@]}" "sudo journalctl -u $SERVICE --since '30 seconds ago' --no-pager \
       | grep -q 'Failed to load plugin .$base.'"; then
    echo
    echo "!! $base FAILED to load — fix it and re-run:"
    echo "   scp -i $KEY $f $USER_@$HOST:$DIR/plugins/$base && sudo systemctl restart $SERVICE"
  fi
done