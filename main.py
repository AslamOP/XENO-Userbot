"""Telegram Userbot - main entry point."""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from core import assistant as assistant_mod
from core.bot import bot, log, start_bot
from core.db import flush as db_flush
from core.db import load as db_load
from core.db import update as db_update
from core.plugin_loader import load_plugins

# Keyspace that used to hold plaintext passwords (notesx.savepw). Purged on boot
# so an upgraded install doesn't leave the old blob sitting in data/xeno_db.json.
DEPRECATED_KEYS = ("pw:all",)


async def main():
    if not config.API_ID or not config.API_HASH:
        log.error(
            "Missing API_ID or API_HASH. Copy .env.example to .env and fill in your values "
            "from https://my.telegram.org"
        )
        sys.exit(1)

    me = await start_bot()

    # Load persisted data store (notes, approvals, ambient flags, etc.)
    db_load()
    for key in DEPRECATED_KEYS:
        if await db_update(key, lambda v: None) is None:
            log.warning(f"Purged deprecated db key `{key}` from disk.")
    await db_flush()

    # Temporary plugins are session-only by design: wipe any left over from the
    # previous run before anything imports them.
    from core import custom as custom_mod

    custom_mod.sweep_tmp()

    # Second identity: the control-panel bot. Must be up BEFORE plugins load,
    # because @asst_cmd registers handlers on it at import time.
    await assistant_mod.start_assistant(bot, log_channel=config.LOG_CHAT_ID or None)

    # Load plugins
    load_plugins()

    log.info(f"Starting userbot as {me.username or me.id}… Run `Ctrl+C` to stop.")
    try:
        # Only the main client needs run_until_disconnected(). The assistant's
        # update loop is already running as a background task from .start() —
        # calling run_until_disconnected() on both clients in an asyncio.gather()
        # starves the assistant's update dispatch, so it never sees incoming DMs.
        if assistant_mod.asst:
            log.info("Assistant update loop running in background.")
        await bot.run_until_disconnected()
    finally:
        # Writes are debounced; make sure nothing is lost on exit.
        await db_flush()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped by user.")
    except Exception as e:
        log.error(f"Fatal error: {e}")
        sys.exit(1)
