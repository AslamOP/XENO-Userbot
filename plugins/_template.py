"""TEMPLATE — copy this file, rename it, edit the @command blocks, drop it in
plugins/, restart. Delete it once you've copied it.

    ./addplugin.sh plugins/mytask.py

Anything whose filename starts with "_" is skipped by the loader, which is how
this template avoids registering itself.
"""
import os
import time

# The four imports you actually need.
from core.command import command
from core.auth import is_owner, is_admin
from core.db import get as db_get
from core.db import set_ as db_set
from core.http import get_json, get_text


# --- 1. the simplest thing: a command ---------------------------------------
@command("mytask")
async def mytask_cmd(event):
    """One-line description — this is what `.help mytask` shows.

    Usage: `.mytask [optional arg]`
    """
    args = event.text.split(maxsplit=1)
    arg = args[1].strip() if len(args) > 1 else ""
    await event.eor(f"got: `{arg}`" if arg else "Usage: `.mytask <something>`")


# --- 2. a command that reads and writes the shared db -----------------------
@command("memo")
async def memo_cmd(event):
    """Store or show a note. Usage: `.memo <key> <text>` / `.memo <key>`

    Demonstrates the debounced json store: read with db_get, write with db_set.
    """
    a = event.text.split(maxsplit=2)
    if len(a) < 2:
        return await event.eor("Usage: `.memo <key> [text]`")

    key = a[1].lower()
    if len(a) < 3:
        val = await db_get(f"memo:{key}", None)
        if val is None:
            return await event.eor(f"No memo `{key}`.")
        return await event.eor(f"**{key}**\n{val}")

    await db_set(f"memo:{key}", a[2].strip())
    await event.eor(f"📌 `{key}` saved.")


# --- 3. an owner-only command ------------------------------------------------
@command("mytask_reset")
async def mytask_reset_cmd(event):
    """Owner: clear every memo. Usage: `.mytask_reset`"""
    if not await is_owner(event):
        return await event.eor("🔒 Owner only.")
    from core.db import delete as db_delete

    keys = [k for k in (await db_get("_memo_keys", [])) or []]
    for k in keys:
        await db_delete(f"memo:{k}")
    await db_set("_memo_keys", [])
    await event.eor(f"🧹 Cleared `{len(keys)}` memos.")


# --- 4. a command that needs an API key --------------------------------------
@command("example_api")
async def example_api_cmd(event):
    """Fetch something over HTTP. Usage: `.example_api <query>`

    Use core.http rather than raw aiohttp: it handles JSON and errors for you.
    """
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else ""
    if not q:
        return await event.eor("Give a query. Usage: `.example_api <query>`")
    try:
        data = await get_json("https://api.example.com/search", {"q": q})
    except Exception as e:
        return await event.eor(f"Error: `{e}`")
    await event.eor(f"got {len(data) if hasattr(data, '__len__') else '?'} results")


# --- 5. a command that acts on a replied message ------------------------------
@command("mytask_react")
async def mytask_react_cmd(event):
    """React to the replied message. Usage: on a reply"""
    if not event.reply_to:
        return await event.eor("Reply to a message.")
    rep = await event.get_reply_message()
    await event.client.send_reaction(event.chat_id, rep.id, emoji="✅")
    await event.eor("Done.")


# --- 6. an ambient handler (reacts to OTHER people's messages) ---------------
# These are OFF by default on purpose — they act on messages you didn't send.
# Use the raw @bot.on() decorator for these, NOT @command (which is
# outgoing=True and would never fire on inbound traffic).
#
# Two rules:
#   1. Give it an ambient_enabled() gate, and add the feature name to
#      AMBIENT_FEATURES in core/auth.py so `.ambient` can switch it on.
#      Without the gate it fires in every chat, forever.
#   2. Guard on `not event.is_private` unless you really want DMs handled.
from telethon import events

from core.auth import ambient_enabled
from core.bot import bot


@bot.on(events.NewMessage(func=lambda e: not e.out and bool(e.text)))
async def mytask_greeter(event):
    """Reply 'Hi there.' when someone says hello. Needs `.ambient mytask on`."""
    if not await ambient_enabled("mytask", event.chat_id):
        return
    if event.is_private:
        return
    if "hello" in (event.text or "").lower():
        await event.eor("Hi there.")