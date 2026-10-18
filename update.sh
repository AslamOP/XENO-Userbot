#!/usr/bin/env bash
# Pull a new version of XENO from GitHub, and roll back if it won't start.
#
#   ./update.sh              deploy origin/main
#   ./update.sh --check      is there anything new?
#   ./update.sh --rollback   go back one known-good version, by hand
#
# Named update.sh rather than deploy.sh: deploy.sh is the Docker push-to-a-VPS
# helper, which is a different job.
#
# The point is that a bad push should be a non-event. `git pull` is the risky
# part, so everything after it is verified: if the code doesn't import, the
# tests don't pass, or the unit won't come up, we put the old commit back and
# restart that instead. You find out from the log, not from a dead bot.
set -uo pipefail

cd "$(dirname "$0")" || exit 1

BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GRN=$'\033[32m'
YEL=$'\033[33m'; CYN=$'\033[36m'; OFF=$'\033[0m'

LAST_GOOD_FILE=".last_good"
UNIT="xeno.service"
VPY="venv/bin/python"

step() { printf '\n%s==>%s %s%s%s\n' "$CYN" "$OFF" "$BOLD" "$1" "$OFF"; }
ok()   { printf '    %s✓%s %s\n' "$GRN" "$OFF" "$1"; }
warn() { printf '    %s!%s %s\n' "$YEL" "$OFF" "$1"; }
bad()  { printf '    %s✗%s %s\n' "$RED" "$OFF" "$1"; }
note() { printf '    %s%s%s\n' "$DIM" "$1" "$OFF"; }
die()  { bad "$1"; exit 1; }

[ -d .git ] || die "not a git repo — nothing to deploy from"

last_good() { [ -f "$LAST_GOOD_FILE" ] && cat "$LAST_GOOD_FILE" || echo ""; }
mark_good() { git rev-parse HEAD > "$LAST_GOOD_FILE"; note "marked $(git rev-parse --short HEAD) as last-good"; }

# ------------------------------------------------------------ check mode
if [ "${1:-}" = "--check" ]; then
    step "Checking for updates"
    timeout 60 git fetch --quiet origin || die "could not reach GitHub (deploy key not added?)"
    LOCAL=$(git rev-parse --short HEAD)
    REMOTE=$(git rev-parse --short origin/main)
    LG=$(last_good)
    echo "    local:     $LOCAL"
    echo "    origin:    $REMOTE"
    if [ -n "$LG" ]; then
        echo "    last-good: $(git rev-parse --short "$LG" 2>/dev/null || echo "$LG")"
    else
        echo "    last-good: none"
    fi
    [ "$LOCAL" = "$REMOTE" ] && ok "up to date" || warn "update available: $LOCAL -> $REMOTE"
    exit 0
fi

# ------------------------------------------------------------ manual rollback
if [ "${1:-}" = "--rollback" ]; then
    step "Rolling back"
    LG=$(last_good)
    [ -n "$LG" ] || die "no known-good commit recorded yet"
    git log --oneline -1 "$LG" 2>/dev/null || die "last-good commit $LG isn't in this repo"
    note "current: $(git rev-parse --short HEAD)"
    note "target:  $(git rev-parse --short "$LG")"
    git checkout --quiet "$LG" 2>/dev/null || git reset --hard --quiet "$LG"
    if sudo systemctl restart "$UNIT" 2>/dev/null; then
        ok "rolled back and restarted"
    else
        bad "restart failed — check: journalctl -u $UNIT -n 40"
    fi
    exit 0
fi

# ------------------------------------------------------------ deploy
step "Before"
CURRENT=$(git rev-parse HEAD)
echo "    current:    $(git rev-parse --short HEAD)"
LG=$(last_good)
[ -n "$LG" ] && echo "    last-good: $(git rev-parse --short "$LG" 2>/dev/null || echo "$LG")" \
              || warn "no last-good recorded yet — nothing to roll back to"

if [ -z "$LG" ]; then
    # First deploy: whatever is running now is the only thing known to work.
    mark_good
fi

step "Pulling"
timeout 120 git fetch --quiet origin || die "could not reach GitHub"
timeout 120 git pull --ff-only --quiet origin main || die "git pull failed — nothing changed"
NEW=$(git rev-parse HEAD)
if [ "$NEW" = "$CURRENT" ]; then
    ok "already up to date ($(git rev-parse --short HEAD))"
    exit 0
fi
ok "updated $(git rev-parse --short "$CURRENT") -> $(git rev-parse --short HEAD)"
note "$(git log --oneline "$CURRENT"..HEAD | wc -l) commit(s) pulled"

step "Verifying"
ROLLBACK=0
[ -d "$VPY" ] || { bad "no venv at $VPY"; ROLLBACK=1; }

if [ "$ROLLBACK" -eq 0 ]; then
    if "$VPY" -c "
import sys
sys.path.insert(0, '.')
import core.custom, core.safety, core.plugin_loader
import plugins.manage, plugins.files, plugins.commander
print('    modules import ok')
" 2>&1 | grep -q "import ok"; then
        ok "core modules import"
    else
        bad "core modules failed to import"
        ROLLBACK=1
    fi
fi

if [ "$ROLLBACK" -eq 0 ] && [ -d tests ]; then
    note "running offline suite..."
    if timeout 400 "$VPY" tests/run.py >/tmp/xeno_deploy_tests.log 2>&1; then
        ok "test suite passed ($(grep -oE '[0-9]+ checks? passed' /tmp/xeno_deploy_tests.log | tail -1))"
    else
        bad "test suite FAILED"
        tail -12 /tmp/xeno_deploy_tests.log | sed 's/^/      /'
        ROLLBACK=1
    fi
fi

if [ "$ROLLBACK" -ne 0 ]; then
    step "Rolling back"
    [ -n "$LG" ] || die "new code is broken and there's no last-good to return to — fix it by hand"
    git reset --hard --quiet "$LG"
    bad "reverted to $(git rev-parse --short HEAD)"
    sudo systemctl restart "$UNIT" 2>/dev/null && ok "restarted on the old code" \
        || warn "restart failed — check: journalctl -u $UNIT -n 40"
    exit 1
fi

step "Restarting"
if sudo systemctl restart "$UNIT" 2>/dev/null; then
    ok "$UNIT restarted"
else
    warn "restart command failed — check: systemctl status $UNIT"
fi

# Give it a beat, then see whether it actually stayed up.
sleep 6
if systemctl is-active --quiet "$UNIT" 2>/dev/null; then
    ok "$UNIT is active on $(git rev-parse --short HEAD)"
    mark_good
else
    step "It did not stay up"
    bad "$UNIT is not active"
    note "journalctl -u $UNIT -n 40 --no-pager"
    if [ -n "$LG" ] && [ "$(git rev-parse --short HEAD)" != "$(git rev-parse --short "$LG")" ]; then
        note "rolling back to $(git rev-parse --short "$LG")"
        git reset --hard --quiet "$LG"
        sudo systemctl restart "$UNIT" 2>/dev/null && ok "back up on the old code" \
            || warn "restart failed again — needs hands on"
        exit 1
    fi
fi

printf '\n%sDeployed.%s %s\n\n' "$GRN" "$OFF" "$(git log --oneline -1)"