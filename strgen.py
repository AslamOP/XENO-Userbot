"""Generate a session string for your userbot (alternative to .session file)."""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import get


async def main():
    api_id = int(get("API_ID", 0))
    api_hash = get("API_HASH", "")

    if not api_id or not api_hash:
        print("Set API_ID and API_HASH in .env first.")
        return

    client = TelegramClient(StringSession(), api_id, api_hash)
    try:
        await client.start()
        session_str = client.session.save()
        print("\nYour session string:\n")
        print(session_str)
        print("\nKeep it secret! Paste into SESSION=<string> or run the bot with this session.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())