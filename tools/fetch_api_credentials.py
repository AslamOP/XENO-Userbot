"""Get API_ID / API_HASH from my.telegram.org and write them to .env.

Why this isn't a one-shot scraper: my.telegram.org requires you to log in
(phone + code, and sometimes a captcha). So the browser is opened VISIBLE and
you do the part only you can do. Everything after that — reading the app page,
merging into .env, validating against Telegram — is automated.

    pip install playwright && playwright install chromium
    python tools/fetch_api_credentials.py

If you'd rather not install a browser, the same script accepts a paste:

    python tools/fetch_api_credentials.py --manual

Run it locally, not on the server. A headless browser needs ~400MB of RAM and
libraries, which is silly to put on a box that already has to run the userbot.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
APPS_URL = "https://my.telegram.org/apps"


# ---------------------------------------------------------------- .env merge
def read_env(path):
    """Existing .env as an ordered list of (key, value) pairs."""
    path = Path(path)
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


def write_env(path, pairs):
    """Rewrite .env, swapping values in place and appending anything new.

    Comments and blank lines survive, so hand-written notes in .env aren't lost.
    """
    out = []
    seen = set()
    for k, v in pairs:
        if k is None:
            out.append(v)
            continue
        seen.add(k)
        out.append(f"{k}={v}" if v != "" else f"{k}=")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    path.chmod(0o600)


def upsert(pairs, updates):
    """Set keys in the pair list, keeping position for keys that exist."""
    remaining = dict(updates)
    out = []
    for k, v in pairs:
        if k in remaining:
            out.append((k, remaining.pop(k)))
        else:
            out.append((k, v))
    for k, v in remaining.items():
        out.append((k, v))
    return out


# ---------------------------------------------------------------- validation
def looks_valid(api_id, api_hash):
    if not api_id.isdigit() or not (6 <= len(api_id) <= 12):
        return False, "api_id should be 6-12 digits"
    if not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
        return False, "api_hash should be 32 hex characters"
    return True, "looks well-formed"


def ask_telegram(api_id, api_hash):
    """The only way to really know: Telegram will tell us if they're wrong.

    Calls getConfig with a throwaway auth key. Doesn't log in, doesn't touch
    your session, doesn't save anything.
    """
    try:
        from telethon import TelegramClient
        from telethon.tl.functions.help import GetConfigRequest
    except ImportError:
        return None, "telethon isn't installed — skipping the live check"

    client = TelegramClient(
        None, int(api_id), api_hash, connection_retries=1, timeout=10
    )
    try:
        asyncio_run(client(GetConfigRequest()))
        return True, "Telegram accepted these credentials"
    except Exception as e:
        name = type(e).__name__
        if name in ("ApiIdInvalidError", "FloodWaitError"):
            return False, f"Telegram rejected them ({name})"
        return None, f"couldn't reach Telegram to check ({name})"
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


def asyncio_run(coro):
    import asyncio

    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------- the browser
def scrape_with_browser(headed=True):
    """Drive a real browser to the apps page and read the values off it.

    Returns (api_id, api_hash) once you're logged in and the app page loads.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, None, (
            "playwright isn't installed. Run:\n"
            "  pip install playwright && playwright install chromium\n"
            "or use --manual to paste the values instead."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        page = browser.new_page()

        print(f"Opening {APPS_URL}\n")
        print("Log in with your phone number and the code Telegram sends you.")
        print("If a captcha shows up, solve it — the script can't do that part.")
        print("The app list loads when you're done. Waiting up to 5 minutes...\n")

        deadline = 600
        waited = 0
        while waited < deadline:
            try:
                page.goto(APPS_URL, timeout=20000)
            except Exception:
                waited += 5
                time_sleep(5)
                continue

            text = page.content()
            if "Log in" in text or "Sign in" in text:
                time_sleep(4)
                waited += 4
                continue

            api_id = scrape_text(page, r"App api_id:\s*(\d+)")
            api_hash = scrape_text(page, r"App api_hash:\s*([0-9a-fA-F]{32})")
            if api_id and api_hash:
                browser.close()
                return api_id, api_hash, None

            time_sleep(4)
            waited += 4

        browser.close()
        return None, None, "Timed out waiting for the app page."


def scrape_text(page, pattern):
    try:
        return re.search(pattern, page.inner_text("body"))
    except Exception:
        m = re.search(pattern, page.content())
        return m


def time_sleep(n):
    import time

    time.sleep(n)


def manual_entry():
    print(f"\nOpen {APPS_URL} in your browser and log in.")
    print("Your existing app is fine — don't create a new one.\n")
    api_id = input("App api_id: ").strip()
    api_hash = input("App api_hash: ").strip()
    return api_id, api_hash


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manual", action="store_true",
                    help="paste the values instead of opening a browser")
    args = ap.parse_args()

    if ENV_PATH.exists():
        env = dict((k, v) for k, v in read_env(ENV_PATH) if k)
        if env.get("API_ID") and env.get("API_HASH"):
            print(".env already has API_ID and API_HASH — nothing to fetch.")
            print("Delete those two lines first if you want to replace them.")
            return 0

    if args.manual:
        api_id, api_hash = manual_entry()
        err = None
    else:
        api_id, api_hash, err = scrape_with_browser()

    if err:
        print(f"\n{err}\n")
        return 1
    if not api_id or not api_hash:
        print("\nCouldn't read the values off the page.\n")
        return 1

    ok, why = looks_valid(api_id, api_hash)
    if not ok:
        print(f"\nThose don't look right: {why}")
        return 1
    print(f"\nRead API_ID={api_id}, API_HASH={'*' * 8}…")

    check, note = ask_telegram(api_id, api_hash)
    print(f"Live check: {note}")
    if check is False:
        print("\nTelegram says these are wrong. Check for a typo and retry.")
        return 1

    write_env(ENV_PATH, upsert(read_env(ENV_PATH), {
        "API_ID": api_id, "API_HASH": api_hash,
    }))
    print(f"\nWrote API_ID and API_HASH to {ENV_PATH} (mode 600).")
    print("Next: python login_helper.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
