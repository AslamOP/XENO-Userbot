#!/usr/bin/env bash
# XENO setup — one ordered pass, safe to re-run.
#
#   ./setup.sh              interactive
#   ./setup.sh --check      report status and exit
#
# Each step is idempotent: already-done steps are detected and skipped, so a
# half-finished install picks up where it left off instead of breaking.
set -uo pipefail

cd "$(dirname "$0")" || exit 1

BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GRN=$'\033[32m'
YEL=$'\033[33m'; CYN=$'\033[36m'; OFF=$'\033[0m'

step()  { printf '\n%s==>%s %s%s%s\n' "$CYN" "$OFF" "$BOLD" "$1" "$OFF"; }
ok()    { printf '    %s✓%s %s\n' "$GRN" "$OFF" "$1"; }
warn()  { printf '    %s!%s %s\n' "$YEL" "$OFF" "$1"; }
bad()   { printf '    %s✗%s %s\n' "$RED" "$OFF" "$1"; }
note()  { printf '    %s%s%s\n' "$DIM" "$1" "$OFF"; }
die()   { bad "$1"; exit 1; }

PY="${PY:-python3}"
VENV=".venv"

# ---------------------------------------------------------------- status
status() {
    step "Status"
    [ -d "$VENV" ] && ok "virtualenv at $VENV" || bad "no virtualenv — run ./setup.sh"
    if [ -f .env ]; then
        ok ".env exists (mode $(stat -c %a .env 2>/dev/null || echo '?'))"
    else
        bad "no .env"
    fi
    "$VENV/bin/python" - <<'PY' 2>/dev/null || true
import config, os
print(f"    {'✓' if not config.credentials_missing() else '✗'} "
      f"API credentials {'(shared fallback)' if config.USING_SHARED_CREDENTIALS else '(own)'}")
print(f"    {'✓' if config.OWNER_ID else '✗'} OWNER_ID = {config.OWNER_ID or '(unset)'}")
sess = config.SESSION_NAME + ".session"
print(f"    {'✓' if os.path.exists(sess) else '✗'} Telegram session {'present' if os.path.exists(sess) else 'missing — not logged in yet'}")
PY
    if command -v systemctl >/dev/null && systemctl list-unit-files 2>/dev/null | grep -q xeno; then
        st=$(systemctl is-active xeno.service 2>/dev/null)
        [ "$st" = "active" ] && ok "xeno.service active" || warn "xeno.service is $st"
    fi
}

[ "${1:-}" = "--check" ] && { status; exit 0; }

# ---------------------------------------------------------------- 1. python
step "1/6  Python environment"
if ! command -v "$PY" >/dev/null; then
    die "python3 not found. Install it and re-run."
fi
note "$($PY --version)"
if [ ! -d "$VENV" ]; then
    "$PY" -m venv "$VENV" || die "could not create the virtualenv"
    ok "created $VENV"
else
    ok "$VENV already exists"
fi
VPY="$VENV/bin/python"
[ -x "$VPY" ] || die "$VPY is missing — delete $VENV and re-run"

step "2/6  Dependencies"
if "$VPY" -c "import telethon, dotenv, PIL" 2>/dev/null; then
    ok "core packages present"
else
    "$VPY" -m pip install --quiet --upgrade pip || warn "pip upgrade failed"
    "$VPY" -m pip install --quiet -r requirements.txt || die "dependency install failed"
    ok "installed from requirements.txt"
fi

# ---------------------------------------------------------------- 3. creds
step "3/6  API credentials"
touch .env && chmod 600 .env
have_creds() {
    "$VPY" -c "import config,sys; sys.exit(1 if config.credentials_missing() else 0)" 2>/dev/null
}
if have_creds; then
    ok "API_ID / API_HASH already set"
else
    note "No credentials yet."
    printf '\n'
    note "  1) automated — python tools/fetch_api_credentials.py"
    note "     (opens a browser, you log in, it writes .env)"
    note "  2) manual    — https://my.telegram.org -> API development tools"
    note "  3) shared    — reuse Telegram Desktop's published credentials"
    note "                 (works, but throttled harder; fine for one tester)"
    printf '\n'
    read -rp "    Which? [1] " pick
    case "${pick:-1}" in
        1)
            note "needs: pip install playwright && playwright install chromium"
            note "run that in $VENV first if the browser won't open"
            "$VPY" tools/fetch_api_credentials.py || warn "fetch didn't finish"
            ;;
        2)
            read -rp "    API_ID: " aid
            read -rp "    API_HASH: " ahash
            grep -q '^API_ID=' .env && sed -i "s/^API_ID=.*/API_ID=$aid/" .env || echo "API_ID=$aid" >> .env
            grep -q '^API_HASH=' .env && sed -i "s/^API_HASH=.*/API_HASH=$ahash/" .env || echo "API_HASH=$ahash" >> .env
            ok "wrote API_ID / API_HASH"
            ;;
        3)
            echo "ALLOW_SHARED_CREDENTIALS=true" >> .env
            warn "using Telegram Desktop's shared API id — throttled harder than your own"
            ;;
        *)
            die "cancelled"
            ;;
    esac
fi

if ! have_creds; then
    die "still no credentials — nothing below this line can work"
fi
ok "credentials usable"

# ---------------------------------------------------------------- 4. owner
step "4/6  Owner ID"
if "$VPY" -c "import config,sys; sys.exit(0 if config.OWNER_ID else 1)" 2>/dev/null; then
    ok "OWNER_ID already set"
else
    note "It's the numeric id of YOUR Telegram account."
    note "login_helper.py prints it once you're logged in, so you can fill it in then."
    read -rp "    OWNER_ID (or leave blank to do it after login): " oid
    if [ -n "$oid" ]; then
        grep -q '^OWNER_ID=' .env && sed -i "s/^OWNER_ID=.*/OWNER_ID=$oid/" .env || echo "OWNER_ID=$oid" >> .env
        ok "wrote OWNER_ID"
    else
        warn "skipped — add it after login, or every owner-gated command stays locked"
    fi
fi

grep -q '^ASSISTANT_ENABLED=' .env || echo "ASSISTANT_ENABLED=true" >> .env
grep -q '^AUTO_BOTFATHER=' .env || echo "AUTO_BOTFATHER=true" >> .env
chmod 600 .env

# ---------------------------------------------------------------- 5. login
step "5/6  Telegram login"
if [ -f "${SESSION_NAME:-userbot_session}.session" ] || "$VPY" -c "
import config, os, sys
sys.exit(0 if os.path.exists(config.SESSION_NAME + '.session') else 1)" 2>/dev/null; then
    ok "session file already exists — skipping login"
else
    note "You'll pick QR or a texted code next."
    "$VPY" login_helper.py || warn "login didn't complete — run: $VPY login_helper.py"
fi

# ---------------------------------------------------------------- 6. service
step "6/6  Service"
if command -v systemctl >/dev/null && [ -f xeno.service ]; then
    sudo cp xeno.service /etc/systemd/system/xeno.service 2>/dev/null \
        && sudo sed -i "s|/home/ubuntu/xeno|$(pwd)|g; s|User=ubuntu|User=$(whoami)|g" /etc/systemd/system/xeno.service \
        && sudo systemctl daemon-reload \
        && sudo systemctl enable xeno >/dev/null 2>&1 \
        && ok "unit installed and enabled" \
        || warn "couldn't install the unit (need sudo?)"
    sudo systemctl restart xeno 2>/dev/null && ok "started" || warn "start failed"
else
    note "no systemd here — start it manually: $VPY main.py"
fi

status
printf '\n%sDone.%s Next: %s.plugins\n\n' "$GRN" "$OFF" "$CYN"