"""Group management: welcome, anti-spam, chat info."""
import json
import os
import time
from collections import defaultdict
from telethon import events, errors

import config
from core import sage
from core.auth import ambient_enabled
from core.bot import bot
from core.command import command
from core.db import get as db_get

# Persist alongside the rest of the state so it survives a container rebuild.
WELCOME_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "welcome.json"
)
welcome_settings = {}
message_counts = defaultdict(list)
SPAM_THRESHOLD = 5
SPAM_WINDOW = 10
# Never auto-mute these, whatever the settings say.
SPAM_EXEMPT = {config.OWNER_ID}


def load_welcome():
    global welcome_settings
    if os.path.exists(WELCOME_FILE):
        try:
            with open(WELCOME_FILE) as f:
                welcome_settings = json.load(f)
        except Exception:
            welcome_settings = {}


def save_welcome():
    os.makedirs(os.path.dirname(WELCOME_FILE), exist_ok=True)
    tmp = WELCOME_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(welcome_settings, f, indent=2)
    os.replace(tmp, WELCOME_FILE)


load_welcome()


@bot.on(events.ChatAction)
async def welcome_handler(event):
    chat_id = str(event.chat_id)
    if chat_id not in welcome_settings or not welcome_settings[chat_id].get("enabled"):
        return

    if event.user_added or event.user_joined:
        try:
            user = await event.get_user()
            name = user.first_name or "User"
            welcome_text = welcome_settings[chat_id].get(
                "text", f"Welcome {name}!"
            ).replace("{name}", name).replace("{chat}", str(event.chat_id))
            await event.reply(welcome_text)
        except Exception:
            pass


@bot.on(events.NewMessage(incoming=True))
async def antispam_handler(event):
    # incoming=True: never count our own traffic, or the bot mutes its owner.
    if event.is_private or event.from_id is None or event.out:
        return
    if not await ambient_enabled("antispam", event.chat_id):
        return

    chat_id = event.chat_id
    user_id = event.sender_id
    if user_id in SPAM_EXEMPT:
        return
    now = time.time()

    # A user who mutes someone is obviously an admin here; leave them alone.
    try:
        if (await event.client.get_permissions(chat_id, user_id)).is_admin:
            message_counts.pop((chat_id, user_id), None)
            return
    except Exception:
        pass

    threshold, window = SPAM_THRESHOLD, SPAM_WINDOW
    cfg = await db_get(f"flood:{chat_id}")
    if isinstance(cfg, (list, tuple)) and len(cfg) == 2:
        threshold, window = int(cfg[0]), int(cfg[1])

    key = (chat_id, user_id)
    message_counts[key].append(now)
    message_counts[key] = [t for t in message_counts[key] if now - t < window]

    if len(message_counts[key]) > threshold:
        try:
            await event.client.edit_permissions(chat_id, user_id, send_messages=False)
            await event.reply(f"**Auto-muted** user `{user_id}` for spamming.")
        except Exception:
            pass
        finally:
            message_counts.pop(key, None)


@command("welcome")
async def welcome_cmd(event):
    """Manage welcome messages: `welcome on/off` or `welcome <text>`."""
    chat_id = str(event.chat_id)
    args = event.text.split(maxsplit=1)

    if len(args) < 2:
        current = welcome_settings.get(chat_id, {})
        status = "ON" if current.get("enabled") else "OFF"
        text = current.get("text", "Welcome {name}!")
        await event.reply(
            f"**Welcome messages:** `{status}`\nText: `{text}`\n\n"
            f"Use `{config.PREFIXES[0]}welcome on/off` or `{config.PREFIXES[0]}welcome <text>`"
        )
        return

    arg = args[1].strip().lower()
    if arg == "on":
        if chat_id not in welcome_settings:
            welcome_settings[chat_id] = {}
        welcome_settings[chat_id]["enabled"] = True
        save_welcome()
        await event.reply(f"{sage.ack()} Welcome protocol engaged.")
    elif arg == "off":
        if chat_id in welcome_settings:
            welcome_settings[chat_id]["enabled"] = False
        save_welcome()
        await event.reply(f"{sage.ack()} Welcome protocol suspended.")
    else:
        if chat_id not in welcome_settings:
            welcome_settings[chat_id] = {}
        welcome_settings[chat_id]["text"] = args[1]
        welcome_settings[chat_id]["enabled"] = True
        save_welcome()
        await event.reply(f"**Welcome text set.**\nUse `{{name}}` for username, `{{chat}}` for chat ID.")


@command("stats")
async def stats_cmd(event):
    """Show chat stats: title, ID, type, member count."""
    chat = await event.get_chat()
    try:
        count = await event.client.get_chat_member_count(event.chat_id)
    except Exception:
        count = "N/A"

    text = (
        f"**Chat Stats**\n"
        f"Title: `{chat.title or 'Private'}`\n"
        f"ID: `{event.chat_id}`\n"
        f"Type: `{type(chat).__name__}`\n"
        f"Members: `{count}`"
    )
    if hasattr(chat, "about") and chat.about:
        text += f"\nAbout: `{chat.about}`"
    await event.reply(text)


@command("lock")
async def lock_cmd(event):
    """Lock a chat feature. Usage: `lock msg|media|sticker|gif|game|inline|poll|info`."""
    args = event.text.split()
    if len(args) < 2:
        return await event.reply(
            "Usage: `lock <feature>`\nFeatures: `msg, media, sticker, gif, game, inline, poll, info`"
        )
    feature = args[1].lower()
    perm_map = {
        "msg": ("send_messages", False),
        "media": ("send_media", False),
        "sticker": ("send_stickers", False),
        "gif": ("send_gifs", False),
        "game": ("send_games", False),
        "inline": ("send_inline", False),
        "poll": ("send_polls", False),
        "info": ("change_info", False),
    }
    if feature not in perm_map:
        return await event.reply(f"Unknown feature: `{feature}`")

    perm_name, perm_val = perm_map[feature]
    try:
        await event.client.edit_permissions(
            event.chat_id,
            **{perm_name: perm_val},
        )
        await event.reply(f"{sage.ack()} **Locked** — `{feature}` state sealed.")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("unlock")
async def unlock_cmd(event):
    """Unlock a locked chat feature. Usage: `unlock <feature>`."""
    args = event.text.split()
    if len(args) < 2:
        return await event.reply("Usage: `unlock <feature>`")
    feature = args[1].lower()
    perm_map = {
        "msg": ("send_messages", True),
        "media": ("send_media", True),
        "sticker": ("send_stickers", True),
        "gif": ("send_gifs", True),
        "game": ("send_games", True),
        "inline": ("send_inline", True),
        "poll": ("send_polls", True),
        "info": ("change_info", True),
    }
    if feature not in perm_map:
        return await event.reply(f"Unknown feature: `{feature}`")

    perm_name, perm_val = perm_map[feature]
    try:
        await event.client.edit_permissions(
            event.chat_id,
            **{perm_name: perm_val},
        )
        await event.reply(f"{sage.ack()} **Unlocked** — `{feature}` state opened.")
    except Exception as e:
        await event.reply(f"Error: `{e}`")
