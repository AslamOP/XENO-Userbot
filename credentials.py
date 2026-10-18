"""Get everything XENO needs from Telegram, in one ordered place.

    python credentials.py            API id/hash, then RSA keys if you're logged in
    python credentials.py --rsa      just the RSA keys
    python credentials.py --manual   skip the browser, paste the values
    python credentials.py --status   show what you've got

What "the RSA keys" means today, because it's changed:

  * The old secret-chat RSA keys (four DC keys, modulus + exponent, used to
    derive auth keys for Secret chats) were REMOVED by Telegram. Telethon 1.45
    doesn't even ship a `PublicKeyRSA` type any more. There is nothing to
    fetch — the feature they served is gone.

  * The CDN RSA keys are still live. `help.getCdnConfig` returns one key per
    CDN DC, each a `{n, e}` pair used for CDN file encryption. Those need an
    authenticated session: calling it before you log in gets you
    AuthKeyUnregisteredError, which is why this runs after login.

So this script writes API_ID/API_HASH into .env, and CDN RSA keys into
data/rsa_keys.json. It does not invent secret-chat keys, because they no
longer exist to be fetched.
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import config  # noqa: E402

ENV_PATH = ROOT / ".env"
RSA_PATH = ROOT / "data" / "rsa_keys.json"
APPS_URL = "https://my.telegram.org/apps"

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GRN = "\033[32m"
YEL = "\033[33m"
CYN = "\033[36m"
OFF = "\033[0m"


def say(msg=""):
    print(msg)


def ok(msg):
    say(f"{GRN}  ✓{OFF} {msg}")


def warn(msg):
    say(f"{YEL}  !{OFF} {msg}")


def bad(msg):
    say(f"{RED}  ✗{OFF} {msg}")


# =========================================================== .env handling
def read_env(path=ENV_PATH):
    if not path.exists():
        return []
    pairs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            pairs.append((k.strip(), v.strip()))
        else:
            pairs.append((None, line))
    return pairs


def write_env(pairs, path=ENV_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    seen, out = set(), []
    for k, v in pairs:
        if k is None:
            out.append(v)
            continue
        seen.add(k)
        out.append(f"{k}={v}" if v != "" else f"{k}=")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def upsert(pairs, updates):
    """Set keys in place, keeping order and any comments already in the file."""
    remaining = dict(updates)
    out = []
    for k, v in pairs:
        if k in remaining:
            out.append((k, remaining.pop(k)))
        else:
            out.append((k, v))
    out.extend(remaining.items())
    return out


def env_dict(pairs=None):
    pairs = read_env() if pairs is None else pairs
    return {k: v for k, v in pairs if k}


# =========================================================== API id / hash
def validate_api_pair(api_id, api_hash):
    if not api_id.isdigit() or not (6 <= len(api_id) <= 12):
        return False, "api_id should be 6-12 digits"
    if not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
        return False, "api_hash should be 32 hex characters"
    return True, "well-formed"


async def telegram_rejects(api_id, api_hash):
    """Ask Telegram directly. No login, no session, nothing written."""
    from telethon import TelegramClient
    from telethon.tl.functions.help import GetConfigRequest

    client = TelegramClient(None, int(api_id), api_hash,
                            connection_retries=2, timeout=15)
    await client.connect()
    try:
        cfg = await client(GetConfigRequest())
        dc = getattr(cfg, "this_dc", "?")
        return None, f"accepted — DC {dc}, test_mode={cfg.test_mode}"
    except Exception as e:
        name = type(e).__name__
        if name == "ApiIdInvalidError":
            return "bad", f"Telegram rejected the pair ({name})"
        # FloodWait/timeout: can't prove it either way, so don't block on it.
        return None, f"couldn't confirm ({name})"
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def fetch_via_browser():
    """Open a real browser and read the app page after you log in.

    my.telegram.org requires a login and sometimes a captcha, so this cannot be
    fully automated — the login is the one part only you can do. Everything
    after it is handled here.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, (
            "playwright isn't installed.\n"
            "    pip install playwright && playwright install chromium\n"
            "  or use --manual to paste the two values."
        )

    import time

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        say(f"  Opening {APPS_URL}")
        say(f"  {DIM}Log in with your phone number + code. Solve any captcha —")
        say(f"  I can't do that part. Waiting up to 5 minutes.{OFF}")

        waited = 0
        while waited < 300:
            try:
                page.goto(APPS_URL, timeout=20000)
                text = page.inner_text("body")
            except Exception:
                time.sleep(5)
                waited += 5
                continue

            if "Log in" not in text and "Sign in" not in text:
                m_id = re.search(r"App api_id:\s*(\d+)", text)
                m_hash = re.search(r"App api_hash:\s*([0-9a-fA-F]{32})", text)
                if m_id and m_hash:
                    browser.close()
                    return (m_id.group(1), m_hash.group(1)), None
            time.sleep(4)
            waited += 4

        browser.close()
        return None, "timed out waiting for the app page"


def manual_entry():
    say(f"\n  Open {APPS_URL}, log in, and read your existing app's values.")
    say(f"  {DIM}Don't create a new app — reuse the one that's already there.{OFF}\n")
    return (input("  App api_id: ").strip(),
            input("  App api_hash: ").strip()), None


def acquire_api_pair(manual=False):
    existing = env_dict()
    if existing.get("API_ID") and existing.get("API_HASH"):
        ok(f"API_ID/API_HASH already in .env (id {existing['API_ID']})")
        return existing["API_ID"], existing["API_HASH"], False

    say()
    if manual:
        pair, err = manual_entry()
    else:
        pair, err = fetch_via_browser()

    if err:
        bad(err)
        return None, None, False

    api_id, api_hash = pair
    good, why = validate_api_pair(api_id, api_hash)
    if not good:
        bad(f"those don't look right: {why}")
        return None, None, False

    ok(f"read API_ID={api_id}, API_HASH={'*' * 6}…")
    verdict, note = asyncio.run(telegram_rejects(api_id, api_hash))
    say(f"  {DIM}Telegram: {note}{OFF}")
    if verdict == "bad":
        bad("Telegram says those are wrong — check for a typo.")
        return None, None, False

    write_env(upsert(read_env(), {"API_ID": api_id, "API_HASH": api_hash}))
    ok("written to .env (mode 600)")
    return api_id, api_hash, True


# =========================================================== CDN RSA keys
async def fetch_rsa_keys(api_id, api_hash):
    """Pull the CDN public RSA keys. Requires an authenticated session.

    Returns (keys_dict, error).
    """
    from telethon import TelegramClient
    from telethon.errors import AuthKeyUnregisteredError
    from telethon.tl.functions.help import GetCdnConfigRequest

    if not api_id or not api_hash:
        return None, "no API_ID/API_HASH yet"

    session_path = str(ROOT / f"{config.SESSION_NAME}.session")
    if not Path(session_path).exists():
        return None, ("not logged in yet — the CDN keys need a real session.\n"
                      "  Run: python login_helper.py   then come back and use --rsa")

    client = TelegramClient(
        str(ROOT / config.SESSION_NAME), api_id, api_hash, connection_retries=2
    )
    await client.connect()
    try:
        if not await client.is_user_authorized():
            return None, ("the session file exists but isn't authorised.\n"
                          "  Run: python login_helper.py")
        cfg = await client(GetCdnConfigRequest())
        keys = {}
        for k in getattr(cfg, "public_keys", []) or []:
            keys[str(k.dc_id)] = {"n": str(k.public_key.n), "e": k.public_key.e}
        if not keys:
            return None, "Telegram returned no CDN keys"
        return keys, None
    except AuthKeyUnregisteredError:
        return None, ("the stored auth key was rejected — log in again.\n"
                      "  Run: python login_helper.py")
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def save_rsa(keys, meta):
    RSA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_note": ("Telegram CDN public RSA keys, from help.getCdnConfig. "
                  "Used for CDN file encryption, not secret chats — Telegram "
                  "removed the old secret-chat keys entirely."),
        "fetched": meta,
        "keys": keys,
    }
    RSA_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def do_rsa(api_id, api_hash):
    say(f"\n{CYN}==> CDN RSA keys{OFF}")
    keys, err = asyncio.run(fetch_rsa_keys(api_id, api_hash))
    if err:
        bad(err)
        return 1

    import datetime
    save_rsa(keys, datetime.datetime.now().isoformat(timespec="seconds"))
    for dc, k in sorted(keys.items(), key=lambda kv: int(kv[0])):
        say(f"    dc {dc:>2}  e={k['e']}  n={k['n'][:24]}… ({len(k['n'])} digits)")
    ok(f"{len(keys)} CDN key(s) → {RSA_PATH.relative_to(ROOT)}")
    return 0


# =========================================================== status
def do_status():
    say(f"\n{CYN}==> Status{OFF}")
    env = env_dict()
    if env.get("API_ID") and env.get("API_HASH"):
        ok(f"API_ID={env['API_ID']} (API_HASH set)")
    elif config.USING_SHARED_CREDENTIALS:
        warn(f"using shared credentials ({config.SHARED_API_ID})")
    else:
        bad("no API_ID/API_HASH")
    if env.get("OWNER_ID"):
        ok(f"OWNER_ID={env['OWNER_ID']}")
    else:
        bad("OWNER_ID unset — owner-gated commands stay locked")

    sess = ROOT / f"{config.SESSION_NAME}.session"
    if sess.exists():
        ok(f"session present ({sess.name})")
    else:
        bad("not logged in")
    if RSA_PATH.exists():
        try:
            n = len(json.loads(RSA_PATH.read_text())["keys"])
            ok(f"CDN RSA keys: {n}")
        except Exception:
            bad("rsa_keys.json is corrupt")
    else:
        bad("no CDN RSA keys yet")


# =========================================================== main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rsa", action="store_true", help="only fetch CDN RSA keys")
    ap.add_argument("--manual", action="store_true",
                    help="paste api id/hash instead of opening a browser")
    ap.add_argument("--status", action="store_true", help="show what's present")
    args = ap.parse_args()

    if args.status:
        do_status()
        return 0

    if args.rsa:
        env = env_dict()
        aid = env.get("API_ID") or (config.API_ID or None)
        ah = env.get("API_HASH") or (config.API_HASH or None)
        return do_rsa(aid, ah)

    say(f"\n{CYN}{BOLD}==> Step 1/2 — API id and hash{OFF}")
    api_id, api_hash, changed = acquire_api_pair(manual=args.manual)
    if not api_id:
        return 1

    say(f"\n{CYN}{BOLD}==> Step 2/2 — CDN RSA keys{OFF}")
    rc = do_rsa(api_id, api_hash)

    say()
    do_status()
    say(f"\n{GRN}Done.{OFF} Next: {CYN}python login_helper.py{OFF}\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
