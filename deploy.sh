#!/usr/bin/env bash
# ------------------------------------------------------------------
# XENO one-shot deploy -> Docker on your VPS
#
#   ./deploy.sh <ssh-user@host> [ssh-key]
#     e.g. ./deploy.sh root@your-vps  (uses ~/.ssh/id_rsa by default)
#
# Steps:
#   1. rsync repo to $REMOTE_DIR on the VPS (excludes .git, downloads, sessions)
#   2. install Docker + compose plugin if missing
#   3. copy local .env (if present) so the container reads real credentials
#   4. docker compose up -d --build
#   5. verify: prints container status + first logs
# ------------------------------------------------------------------
set -euo pipefail

HOST="${1:?usage: ./deploy.sh <ssh-user@host> [ssh-key]}"
KEY="${2:-$HOME/.ssh/id_rsa}"
REMOTE_DIR="${XENO_REMOTE_DIR:-/opt/xeno}"

echo_color(){ printf '\033[1;34m== %s ==\033[0m\n' "$1"; }

SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$HOST")
SCP=(scp -i "$KEY" -o StrictHostKeyChecking=no)

echo_color "1/5 rsync repo -> $HOST:$REMOTE_DIR"
# data/ holds live state (xeno_db.json, scores, session). --delete plus an
# unexcluded data/ would wipe the running instance's state on every deploy.
ssh "${SSH[@]}" "mkdir -p '$REMOTE_DIR/data'"
rsync -az --delete --exclude='.git' --exclude='downloads' --exclude='*.session*' \
  --exclude='*.log' --exclude='__pycache__' --exclude='*.pyc' --exclude='data/' \
  --exclude='.env' \
  -e "ssh -i '$KEY' -o StrictHostKeyChecking=no" \
  ./ "$HOST:$REMOTE_DIR/"

echo_color "2/5 ensure docker is installed"
ssh "${SSH[@]}" 'command -v docker >/dev/null 2>&1 || curl -fsSL https://get.docker.com | sh'
ssh "${SSH[@]}" 'command -v docker compose >/dev/null 2>&1 || (apt-get update -y && apt-get install -y docker-compose-plugin || pip3 install docker-compose) || true'

echo_color "3/5 ship .env (real creds) if we have one locally"
if [ -f .env ]; then
  "${SCP[@]}" .env "$HOST:$REMOTE_DIR/.env"
  echo "  -> copied .env ($(wc -c < .env) bytes)"
else
  echo "  ! no local .env — create one on the VPS at $REMOTE_DIR/.env with API_ID, API_HASH, SESSION, OWNER_ID, PREFIXES"
fi

echo_color "4/5 build + start container"
ssh "${SSH[@]}" "cd '$REMOTE_DIR' && docker compose up -d --build"

echo_color "5/5 status + first logs"
sleep 5
ssh "${SSH[@]}" "cd '$REMOTE_DIR' && docker compose ps && echo ---- && docker compose logs --tail 30 2>&1 | tail -40"

echo "Done. Manage with: ssh $HOST 'cd $REMOTE_DIR && docker compose <down|restart|logs -f>'"
