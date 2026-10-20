"""Second TelegramClient: the XENO control-panel bot.

Why this exists: every @command handler is registered `outgoing=True`, so only
messages *your own account* sends can trigger them. The assistant is a separate
Telegram identity, which means you can DM a bot and drive the userbot out-of-band
— including from a phone, without touching a group.

The bot token is either supplied manually (BOT_TOKEN) or created automatically
via @BotFather when AUTO_BOTFATHER=true. Unlike Ultroid's autobot(), every
failure here is non-fatal: if bot creation fails, XENO still boots as a
userbot and logs why.
"""
import asyncio
import random
import time

from telethon import TelegramClient
from telethon.tl.functions.contacts import UnblockRequest

import config
from core.bot import log

# Populated by start_assistant(). Read (not imported by value) by
# core.command at plugin-import time, which happens after boot.
asst = None
# Human-readable reason the assistant is unavailable, for /status and logs.
status = "not started"


def _session_name():
    return config.SESSION_NAME + "_assistant"


async def _botfather_name(me):
    if config.ASSISTANT_NAME:
        return config.ASSISTANT_NAME
    return "Assistant Bot"


async def _botfather_username_candidates(me):
    """Ordered candidate usernames, mirroring Ultroid's autobot():
      1. `<your username>_bot`      — most likely free, it's yours
      2. `assistant_<id-tail>_bot`  — no username on the account
      3. `assistant_<id-tail><n>_bot` — collision retry
    ASSISTANT_USERNAME overrides the stem entirely.
    """
    if config.ASSISTANT_USERNAME:
        base = config.ASSISTANT_USERNAME.strip().lstrip("@").removesuffix("_bot")
        yield f"{base}_bot"
        for n in range(1, 6):
            yield f"{base}_{n}_bot"
        return
    me_id = str(me.id)
    if me.username:
        yield f"{me.username}_bot"
    else:
        yield f"assistant_{me_id[5:]}_bot"
    for _ in range(4):
        yield f"assistant_{me_id[6:]}{random.randint(1, 100)}_bot"


async def _bf_read(client, chat="BotFather", tries=8):
    """Poll BotFather's last message until it stops changing, then return text."""
    prev = None
    for _ in range(tries):
        await asyncio.sleep(1.2)
        try:
            msgs = await client.get_messages(chat, limit=1)
            text = msgs[0].text if msgs and msgs[0].text else ""
        except Exception:
            return ""
        if text and text == prev:
            return text
        prev = text
    return prev or ""


async def _bf_send(client, text):
    """Send one BotFather command and read the reply. Never raises.

    Every step of the BotFather dialogue is network I/O against another user's
    chat, so a dropped connection or a flood wait must not escape: the whole
    point of this feature being optional is that XENO still boots as a userbot.
    """
    try:
        await client.send_message("BotFather", text)
    except Exception as e:
        log.warning(f"BotFather: could not send {text!r} ({type(e).__name__}: {e})")
        return f"__transport_error__ {e}"
    return await _bf_read(client)


async def autobot(user_client, log_channel=None):
    """Create an assistant bot via @BotFather and return (token, username).

    Mirrors Ultroid/Jarvis's autobot(): /cancel to clear any pending state,
    /newbot, then name -> username -> scrape the token out of the Done! reply.

    One deliberate divergence: every failure returns None instead of calling
    sys.exit(). Ultroid's version hard-exits, which means a BotFather hiccup
    leaves you with no userbot at all. Here the bot is optional and the
    userbot boots either way.
    """
    me = await user_client.get_me()
    name = await _botfather_name(me)

    log.info("XENO: creating an assistant bot via @BotFather — this runs only once")
    try:
        await user_client(UnblockRequest("BotFather"))
    except Exception:
        pass  # already a contact, or no contact-import permission

    async def send(text):
        return await _bf_send(user_client, text)

    reply = await send("/cancel")
    if reply.startswith("__transport_error__"):
        log.error(f"BotFather unreachable ({reply[22:120]}). Running as userbot only.")
        return None
    reply = await send("/newbot")

    # BotFather refuses once you're out of bot slots.
    if reply.startswith("That I cannot do") or "20 bots" in reply:
        log.error(
            "BotFather refused /newbot (bot limit reached). Create a bot manually "
            "and set BOT_TOKEN in .env — XENO is running as a userbot only."
        )
        return None

    reply = await send(name)
    if not reply.startswith("Good."):
        # Display name rejected. The fallback must NOT be the same string as the
        # configured name, or the retry is a no-op. BotFather caps names at 64
        # chars, so a long custom ASSISTANT_NAME lands here.
        fallback = "Assistant" if name != "Assistant" else "Xeno"
        log.warning(f"BotFather rejected the name '{name}', trying '{fallback}'")
        reply = await send(fallback)
        if not reply.startswith("Good."):
            log.error(f"BotFather rejected the bot name. Reply was: {reply[:120]}")
            return None

    token = None
    username = None
    async for candidate in _botfather_username_candidates(me):
        reply = await send(candidate)
        if reply.startswith("Done!"):
            token = reply.split("`")[1]
            username = candidate
            break
        if not reply.startswith("Sorry,"):
            log.error(f"Unexpected BotFather reply: {reply[:120]}")
            return None
        log.warning(f"@{candidate} is taken, trying another")

    if not token:
        log.error(
            "Could not create a bot: every candidate username was taken. "
            "Create one manually and set BOT_TOKEN in .env."
        )
        return None

    log.info(f"XENO: created @{username} as the assistant bot")
    if log_channel:
        try:
            await user_client.send_message(
                log_channel,
                f"**Assistant bot created**\n`@{username}`\n\nControl panel is live — "
                f"DM it with `{config.ASSISTANT_PREFIX}start`.",
            )
        except Exception:
            pass
    return token, username


async def _enable_inline(client, username):
    """Turn on inline mode for the assistant via BotFather. Never raises."""
    for step in ("/setinline", f"@{username}", "Search"):
        try:
            await client.send_message("BotFather", step)
            await asyncio.sleep(1.2)
        except Exception as e:
            log.warning(f"Could not enable inline mode ({step!r}): {e}")
            return


async def _decorate(user_client, username, log_channel=None):
    """Give the new bot a bio and description so it isn't a bare @handle."""
    sir = f"@{user_client.me.username}" if user_client.me.username else user_client.me.first_name
    for cmd, payload in (
        ("/setabouttext", f"Control panel for {sir}'s XENO."),
        ("/setdescription", "Remote control panel for the XENO userbot. Owner-only."),
    ):
        try:
            for step in (cmd, f"@{username}", payload):
                await user_client.send_message("BotFather", step)
                await asyncio.sleep(1.2)
        except Exception as e:
            log.warning(f"Bot decoration skipped at {cmd} ({type(e).__name__}: {e})")
            return
    log.info("XENO: set assistant bot bio/description")


async def _persist_token(token):
    """Store the token where it'll survive.

    Ultroid keeps it in the db (udB.set_key("BOT_TOKEN", token)); .env is also
    written as a convenience, but under Docker the env file is often read-only,
    so the db is the authoritative copy.
    """
    from core.db import set_ as db_set

    await db_set("ASSISTANT_TOKEN", token)
    try:
        with open(".env", encoding="utf-8") as f:
            existing = f.read()
        if "BOT_TOKEN=" in existing:
            lines = [
                f"BOT_TOKEN={token}" if ln.strip().startswith("BOT_TOKEN=") else ln
                for ln in existing.splitlines()
            ]
            with open(".env", "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        else:
            with open(".env", "a", encoding="utf-8") as f:
                f.write(
                    f"\n# auto-created by XENO {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"BOT_TOKEN={token}\n"
                )
    except OSError as e:
        log.info(f"Token stored in the db (couldn't write .env: {e})")


async def _stored_token():
    from core.db import get as db_get

    return await db_get("ASSISTANT_TOKEN", "") or config.BOT_TOKEN


async def start_assistant(user_client, log_channel=None):
    """Start the assistant client. Never raises — returns (client, status)."""
    global asst, status

    if not config.ASSISTANT_ENABLED:
        status = "disabled (ASSISTANT_ENABLED=false)"
        log.info("Assistant bot: disabled.")
        return None, status

    token, username = await _stored_token(), None

    if not token and config.AUTO_BOTFATHER:
        log_channel = log_channel or (config.LOG_CHAT_ID or None)
        # Belt and braces: autobot() guards its own I/O, but anything unexpected
        # here must not take the userbot down with it.
        try:
            result = await autobot(user_client, log_channel)
        except Exception as e:
            log.error(f"Assistant bot: creation failed ({type(e).__name__}: {e})")
            result = None
        if result:
            token, username = result
            try:
                await _persist_token(token)
            except Exception as e:
                log.warning(f"Could not store the assistant token: {e}")
            log.info("XENO: stored the assistant token — this only runs once")

    if not token:
        status = "no token (set BOT_TOKEN in .env)"
        log.warning(
            f"Assistant bot: {status}. XENO is running as a userbot only."
        )
        return None, status

    try:
        client = TelegramClient(
            _session_name(),
            config.API_ID,
            config.API_HASH,
            retry_delay=1,
            auto_reconnect=True,
        )
        await client.start(bot_token=token)
        me = await client.get_me()
    except Exception as e:
        status = f"failed to start ({type(e).__name__}: {e})"
        log.error(f"Assistant bot: {status}")
        return None, status

    asst = client
    config.ASSISTANT_START_TIME = time.time()
    username = username or me.username
    status = f"online as @{me.username} (id {me.id})"
    log.info(f"Assistant bot: {status}")

    # Ultroid always turns on inline mode for a freshly created bot.
    if username and not config.BOT_TOKEN:
        await _enable_inline(user_client, username)
        if config.ASSISTANT_DECORATE:
            await _decorate(user_client, username, log_channel)
    if log_channel:
        try:
            await client.send_message(
                log_channel,
                f"**Assistant bot connected**\n@{me.username}\n"
                f"DM it with `{config.ASSISTANT_PREFIX}start`.",
            )
        except Exception:
            pass
    return client, status
