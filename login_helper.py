"""Interactive first-time login.

    ./venv/bin/python login_helper.py            # asks which you want
    ./venv/bin/python login_helper.py qr         # or force QR
    ./venv/bin/python login_helper.py +1555...   # or force the code path

Both paths reuse one session file, so you only ever do this once. Re-running
after a successful login just prints who you're logged in as.

QR is the better option on a headless box: the code path needs the code typed
back over SSH, and Telegram's login code is short-lived. A QR just sits there
until you scan it.
"""
import asyncio
import re
import sys

from telethon import TelegramClient
from telethon.errors import (
    AuthKeyError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)

import config


def die(msg):
    print(f"\n{msg}\n", file=sys.stderr)
    sys.exit(1)


def ok(msg):
    print(f"\n\033[32m{msg}\033[0m", file=sys.stderr)


async def show_identity(client):
    me = await client.get_me()
    ok(f"Logged in as {me.first_name} (id {me.id})")
    print(f"ALREADY_LOGGED_IN {me.id}")
    return me


async def do_qr(client):
    """Log in by QR. Scan it from Telegram: Settings -> Devices -> Link Desktop."""
    qr = await client.qr_login()
    print("\nScan this with Telegram (Settings → Devices → Link Desktop Device):\n")
    # Telethon renders the QR as text; also print the URL for the web version.
    print(f"  {qr.url}\n")
    print("Waiting for the scan… (Ctrl-C to cancel)")
    try:
        await qr.wait_for_scan(timeout=180)
    except asyncio.TimeoutError:
        die("Timed out after 3 minutes — run it again to get a fresh QR.")
    return await finish(client)


async def do_phone(client, phone):
    """Log in with a code sent to the Telegram app."""
    try:
        await client.send_code_request(phone)
    except PhoneNumberInvalidError:
        die(f"Telegram rejected {phone!r}. Use international format: +15551234567")
    print(f"Code sent to {phone}. It shows up in the Telegram service chat.\n")
    code = input("Enter the code (or empty to cancel): ").strip()
    if not code:
        die("Cancelled — nothing was changed.")
    try:
        await client.sign_in(phone, code)
    except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
        die(f"That code didn't work: {type(e).__name__}. Run it again for a new one.")
    except SessionPasswordNeededError:
        pwd = input("2FA is on — enter your account password: ").strip()
        try:
            await client.sign_in(password=pwd)
        except AuthKeyError:
            die("Wrong password.")
    return await finish(client)


async def finish(client):
    me = await client.get_me()
    ok(f"Logged in as {me.first_name} (id {me.id})")
    print(f"LOGGED_IN {me.id} {me.first_name}")
    return me


def ask_method():
    """Let the user pick QR or code. Returns 'qr' or a phone number."""
    print("\nHow do you want to log in?\n")
    print("  1) QR code   scan it from Telegram — Settings → Devices →"
          " Link Desktop Device")
    print("  2) Code      Telegram texts you a code, you type it back here")
    print("\nQR is easier over SSH: nothing to copy, and it doesn't expire"
          " in a minute.\n")

    while True:
        choice = input("Choice [1]: ").strip().lower()
        if choice in ("", "1", "qr"):
            return "qr"
        if choice in ("2", "code"):
            break
        print("  Enter 1 or 2.")

    while True:
        phone = input("\nPhone number in international format, e.g. +15551234567: ").strip()
        if phone.startswith("+") and len(re.sub(r"\D", "", phone)) >= 8:
            return phone
        print("  That doesn't look right — include the +, like +15551234567.")


async def main():
    if config.credentials_missing():
        die(config.CREDENTIAL_HELP)

    mode = sys.argv[1] if len(sys.argv) > 1 else None

    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        await show_identity(client)
        await client.disconnect()
        return

    print(f"Session file: {client.session.filename}")

    if mode is None:
        if not sys.stdin.isatty():
            die(
                "No TTY to ask on, and no argument given.\n"
                "Run it with 'qr' or a phone number:\n"
                "  ./venv/bin/python login_helper.py qr\n"
                "  ./venv/bin/python login_helper.py +15551234567"
            )
        mode = await asyncio.get_event_loop().run_in_executor(None, ask_method)

    try:
        if mode.lower() == "qr":
            await do_qr(client)
        else:
            await do_phone(client, mode)
    finally:
        await client.disconnect()

    print("\nNow start the bot:  sudo systemctl start xeno.service")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
