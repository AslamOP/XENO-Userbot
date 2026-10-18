import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import qrcode

import config
from telethon import TelegramClient
from telethon.sessions import SQLiteSession


async def main():
    print("XENO QR login: scan the QR with the OWNER account to authorize this session.", flush=True)
    session = SQLiteSession(config.SESSION_NAME)
    client = TelegramClient(session, config.API_ID, config.API_HASH, retry_delay=1)
    await client.connect()

    qr = await client.qr_login()
    print("Waiting for scan (QR auto-refreshes every ~30s)...", flush=True)

    try:
        while True:
            url = qr.url
            q = qrcode.QRCode(border=1)
            q.add_data(url)
            q.make(fit=True)
            q.print_ascii(invert=True)
            q.make_image().save("/tmp/xeno_login_qr.png")
            print(url, flush=True)
            try:
                if await asyncio.wait_for(qr.wait(), timeout=30):
                    break
            except asyncio.TimeoutError:
                continue
    except Exception as e:
        print(f"Login failed: {e}")
        await client.disconnect()
        raise SystemExit(1)

    print("\nAuthorized! Session saved.", flush=True)
    me = await client.get_me()
    print(f"Logged in as {me.first_name} (@{me.username}) [ID: {me.id}]", flush=True)
    await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass