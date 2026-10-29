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
import os
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
    me = await user_client.get_me()
    sir = f"@{me.username}" if me.username else me.first_name
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
        env_path = ".env"
        try:
            with open(env_path, encoding="utf-8") as f:
                existing = f.read()
        except FileNotFoundError:
            existing = ""
        if "BOT_TOKEN=" in existing:
            lines = [
                f"BOT_TOKEN={token}" if ln.strip().startswith("BOT_TOKEN=") else ln
                for ln in existing.splitlines()
            ]
            new_content = "\n".join(lines)
            if new_content and not new_content.endswith("\n"):
                new_content += "\n"
            tmp_path = env_path + ".tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                os.replace(tmp_path, env_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        else:
            tmp_path = env_path + ".tmp"
            try:
                with open(tmp_path, "a", encoding="utf-8") as f:
                    if existing and not existing.endswith("\n"):
                        f.write("\n")
                    if existing:
                        f.write(existing)
                        if not existing.endswith("\n"):
                            f.write("\n")
                    f.write(
                        f"# auto-created by XENO {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"BOT_TOKEN={token}\n"
                    )
                os.replace(tmp_path, env_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
    except OSError as e:
        log.info(f"Token stored in the db (couldn't write .env: {e})")


async def _stored_token():
    from core.db import get as db_get

    return await db_get("ASSISTANT_TOKEN", "") or config.BOT_TOKEN


_LOGO_PATH = "resources/logo.jpg"
_BANNER_PATH = "resources/banner.jpg"


async def customize(user_client, assistant_client, log_channel=None):
    """Set the assistant's profile picture via BotFather (Ultroid's customize()).

    Bots cannot set their own avatar — UploadProfilePhotoRequest only works on
    user accounts — so the user client drives @BotFather exactly the way
    Ultroid's pyUltroid/startup/funcs.py customize() does. Skipped entirely if
    the bot already has a photo, so it runs at most once per deployment.
    """
    if not assistant_client or not assistant_client.is_connected():
        return
    try:
        me = await assistant_client.get_me()
        if me.photo:
            return
        if not me.username:
            log.info("Assistant has no username; cannot set profile pic.")
            return
        import os

        if not os.path.exists(_LOGO_PATH):
            log.warning(f"Assistant logo missing at {_LOGO_PATH}; skipping.")
            return
        log.info("Customising assistant profile picture via @BotFather")
        for step in ("/cancel", "/setuserpic", f"@{me.username}"):
            await user_client.send_message("BotFather", step)
            await asyncio.sleep(1.2)
        await user_client.send_file("BotFather", _LOGO_PATH)
        await asyncio.sleep(2)
        log.info("Assistant profile picture set via @BotFather")
    except Exception as e:
        log.warning(f"Assistant profile-pic customisation failed ({type(e).__name__}: {e})")


async def ready(assistant_client, log_channel=None, user_client=None):
    """Send the XENO startup banner to the log channel (Ultroid's ready()).

    Mirrors pyUltroid/startup/funcs.py ready(): the assistant delivers the
    boot message with the banner image attached. Falls back to the user
    client if the assistant is unavailable.
    """
    if not log_channel:
        return
    me = await user_client.get_me() if user_client else None
    who = f"@{me.username}" if me and me.username else (me.first_name if me else "unknown")
    asst_me = await assistant_client.get_me() if assistant_client else None
    asst_tag = f"@{asst_me.username}" if asst_me and asst_me.username else "offline"
    try:
        from plugins.commander import VERSION
    except Exception:
        VERSION = "2.1.0-alpha"
    msg = (
        f"**XENO is live!**\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"**UserMode**: {who}\n"
        f"**Assistant**: {asst_tag}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"**Version**: `{VERSION}`\n"
        f"➖➖➖➖➖➖➖➖➖➖"
    )
    import os

    photo = _BANNER_PATH if os.path.exists(_BANNER_PATH) else None
    # Bots can't start conversations with groups they aren't in — same
    # failure Ultroid's ready() catches, and it retries with the user client.
    for fallback in (assistant_client, user_client):
        if not fallback or not fallback.is_connected():
            continue
        try:
            await fallback.send_message(log_channel, msg, file=photo)
            log.info("Startup banner sent to log channel.")
            return
        except Exception as e:
            log.warning(
                f"Startup banner via {fallback.__class__.__name__} failed "
                f"({type(e).__name__}: {e})"
            )
    log.warning("Startup banner could not be delivered to log channel.")


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
            connection_retries=3,
            timeout=20,
            request_retries=3,
        )
        client.parse_mode = "md"
        await asyncio.wait_for(client.start(bot_token=token), timeout=60)
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
