"""XENO notes module — per-chat save/recall notes."""
import time

from core.auth import is_owner
from core.command import command
from core.db import get as db_get
from core.db import set_ as db_set


def _key(event):
    """Notes are scoped per chat — a global dict silently collided across chats."""
    return f"notes:all:{event.chat_id}"


@command("noteadd")
async def savenote_cmd(event):
    """Save a note. Usage: `.noteadd <key> <text>` """
    a = event.text.split(maxsplit=2)
    if len(a) < 3:
        return await event.eor("Usage: `.noteadd <key> <text>`")
    key = a[1].strip().lower()
    text = a[2].strip()
    notes = await db_get(_key(event), {})
    notes[key] = text
    await db_set(_key(event), notes)
    await event.eor(f"📝 Note `{key}` saved.")


@command("getnote")
async def getnote_cmd(event):
    """Recall a note. Usage: `.getnote <key>` """
    a = event.text.split(maxsplit=1)
    key = a[1].strip().lower() if len(a) > 1 else ""
    notes = await db_get(_key(event), {})
    if key not in notes:
        return await event.eor(f"No note `{key}`. Use `.noteadd {key} <text>`")
    await event.eor(f"**{key}:**\n{notes[key]}")


@command("notedel")
async def delnote_cmd(event):
    """Delete a note. Usage: `.notedel <key>` """
    a = event.text.split(maxsplit=1)
    key = a[1].strip().lower() if len(a) > 1 else ""
    notes = await db_get(_key(event), {})
    if key in notes:
        del notes[key]
        await db_set(_key(event), notes)
        await event.eor(f"🗑 Note `{key}` deleted.")
    else:
        await event.eor(f"No note `{key}`.")


@command("notelist")
async def notes_cmd(event):
    """List all saved notes."""
    notes = await db_get(_key(event), {})
    if not notes:
        return await event.eor("No notes saved yet.")
    await event.eor("**📕 Your notes:**\n" + "\n".join(f"• `{k}`" for k in notes))


@command("savemsg")
async def savemsg_cmd(event):
    """Save a replied message as a note with auto-key. Usage: `.savemsg`"""
    if not event.reply_to:
        return await event.eor("Reply to a message to save it as a note.")
    r = await event.get_reply_message()
    txt = getattr(r, "raw_text", "")
    if not txt:
        return await event.eor("That message has no text.")
    key = f"msg{int(time.time())}"
    notes = await db_get(_key(event), {})
    notes[key] = txt
    await db_set(_key(event), notes)
    await event.eor(f"📝 Saved as note `{key}`. Get it with `.getnote {key}`")


@command("stickers")
async def stickers_cmd(event):
    """Owner: list installed sticker packs."""
    if not await is_owner(event):
        return await event.eor("Owner only.")
    try:
        from telethon.tl.functions.messages import GetAllStickersRequest
        r = await event.client(GetAllStickersRequest(hash=0))
        packs = r.sets if hasattr(r, "sets") else []
        lines = [f"**🧩 Sticker packs ({len(packs)}):**"]
        for p in packs[:15]:
            lines.append(f"• `{getattr(p, 'short_name', '?')}`")
        await event.eor("\n".join(lines))
    except Exception as e:
        await event.eor(f"Error: `{e}`")
