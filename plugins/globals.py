"""XENO god-mode: userbot-wide actions across all chats. Original code."""
import logging

from core.auth import is_owner, resolve_user
from core.command import command
from core.db import delete as db_delete
from core.db import get as db_get
from core.db import set_ as db_set

log = logging.getLogger("userbot")

GBAN_KEY = "globals:gbans"
GMUTE_KEY = "globals:gmutes"


async def _ok(event):
    if not await is_owner(event):
        await event.reply("🔒 Owner only.")
        return False
    return True


async def _dialogs(client):
    try:
        return [d.entity for d in await client.get_dialogs() if getattr(d.entity, "participants_count", 0) is not None and d.is_group]
    except Exception:
        return []


@command("ggban")
async def gban_cmd(event):
    """Gban a user from every group the bot is in (global, persistent)."""
    if not await _ok(event): return
    target = await resolve_user(event)
    if not target:
        return await event.reply("Reply to a user or give ID. Usage: `.gban <id/reply>`")
    try:
        uid = int(target)
    except Exception:
        return await event.reply(f"Cannot resolve `{target}`.")
    gb = await db_get(GBAN_KEY, [])
    if uid in gb:
        return await event.reply(f"`{uid}` is already gbanned.")
    gb.append(uid)
    await db_set(GBAN_KEY, gb)

    done = fail = 0
    msg = await event.reply(f"🌍 Gbanning `{uid}` across all chats…")
    for ent in await _dialogs(event.client):
        try:
            await event.client.edit_permissions(ent.id, uid, view_messages=False)
            done += 1
        except Exception:
            fail += 1
    await msg.edit(f"🌍 **Gban complete.** Applied in `{done}` chats" + (f", failed `{fail}`" if fail else "") + ".")


@command("gungban")
async def ungban_cmd(event):
    if not await _ok(event): return
    target = await resolve_user(event)
    if not target:
        return await event.reply("Give an ID to un-gban.")
    try:
        uid = int(target)
    except Exception:
        return await event.reply(f"Cannot resolve `{target}`.")
    gb = await db_get(GBAN_KEY, [])
    if uid not in gb:
        return await event.reply(f"`{uid}` is not gbanned.")
    gb.remove(uid)
    await db_set(GBAN_KEY, gb)
    done = fail = 0
    for ent in await _dialogs(event.client):
        try:
            await event.client.edit_permissions(ent.id, uid, view_messages=True)
            done += 1
        except Exception:
            fail += 1
    await event.reply(f"🌍 **Ungban complete.** Restored in `{done}` chats" + (f", failed `{fail}`" if fail else "") + ".")


@command("ggbanlist")
async def gbanlist_cmd(event):
    if not await _ok(event): return
    gb = await db_get(GBAN_KEY, [])
    if not gb:
        return await event.reply("No gbans stored.")
    return await event.reply("**🌍 Gbanned users:**\n" + "\n".join(f"• `{u}`" for u in gb))


@command("gkick")
async def gkick_cmd(event):
    if not await _ok(event): return
    target = await resolve_user(event)
    if not target:
        return await event.reply("Reply or give ID.")
    try:
        uid = int(target)
    except Exception:
        return await event.reply("Bad user ID.")
    done = fail = 0
    for ent in await _dialogs(event.client):
        try:
            await event.client.kick_participant(ent.id, uid)
            done += 1
        except Exception:
            fail += 1
    await event.reply(f"🦵 **Gkick done.** Kicked in `{done}` chats" + (f", failed `{fail}`" if fail else "") + ".")


@command("gmute")
async def gmute_cmd(event):
    if not await _ok(event): return
    target = await resolve_user(event)
    if not target:
        return await event.reply("Reply or give ID.")
    try:
        uid = int(target)
    except Exception:
        return await event.reply("Bad user ID.")
    gm = await db_get(GMUTE_KEY, [])
    if uid not in gm:
        gm.append(uid)
        await db_set(GMUTE_KEY, gm)
    done = fail = 0
    for ent in await _dialogs(event.client):
        try:
            await event.client.edit_permissions(ent.id, uid, send_messages=False)
            done += 1
        except Exception:
            fail += 1
    await event.reply(f"🔇 **Gmute done.** Muted in `{done}` chats" + (f", failed `{fail}`" if fail else "") + ".")


@command("ungmute")
async def ungmute_cmd(event):
    if not await _ok(event): return
    target = await resolve_user(event)
    if not target:
        return await event.reply("Reply or give ID.")
    try:
        uid = int(target)
    except Exception:
        return await event.reply("Bad user ID.")
    gm = await db_get(GMUTE_KEY, [])
    if uid in gm:
        gm.remove(uid)
        await db_set(GMUTE_KEY, gm)
    done = fail = 0
    for ent in await _dialogs(event.client):
        try:
            await event.client.edit_permissions(ent.id, uid, send_messages=True)
            done += 1
        except Exception:
            fail += 1
    await event.reply(f"🔊 **Ungmute done.** Unmuted in `{done}` chats" + (f", failed `{fail}`" if fail else "") + ".")


@command("gpromote")
async def gpromote_cmd(event):
    if not await _ok(event): return
    target = await resolve_user(event)
    if not target:
        return await event.reply("Reply or give ID.")
    try:
        uid = int(target)
    except Exception:
        return await event.reply("Bad user ID.")
    done = fail = 0
    for ent in await _dialogs(event.client):
        try:
            await event.client.edit_admin(ent.id, uid, is_admin=True, title="XENO Admin")
            done += 1
        except Exception:
            fail += 1
    await event.reply(f"⭐ **Gpromote done.** Admin in `{done}` chats" + (f", failed `{fail}`" if fail else "") + ".")


@command("gdemote")
async def gdemote_cmd(event):
    if not await _ok(event): return
    target = await resolve_user(event)
    if not target:
        return await event.reply("Reply or give ID.")
    try:
        uid = int(target)
    except Exception:
        return await event.reply("Bad user ID.")
    done = fail = 0
    for ent in await _dialogs(event.client):
        try:
            await event.client.edit_admin(ent.id, uid, is_admin=False)
            done += 1
        except Exception:
            fail += 1
    await event.reply(f"📉 **Gdemote done.** Demoted in `{done}` chats" + (f", failed `{fail}`" if fail else "") + ".")


@command("gucast")
async def gucast_cmd(event):
    """Broadcast a message to every group the bot is in."""
    if not await _ok(event): return
    if not event.reply_to:
        a = event.text.split(maxsplit=1)
        text = a[1].strip() if len(a) > 1 else ""
        if not text:
            return await event.reply("Give a message or reply to one. Usage: `.gucast <text>`")
    else:
        r = await event.get_reply_message()
        text = r.text or r.raw_text or ""
    sent = fail = 0
    msg = await event.reply("📣 Broadcasting…")
    for ent in await _dialogs(event.client):
        try:
            await event.client.send_message(ent.id, text)
            sent += 1
        except Exception:
            fail += 1
    await msg.edit(f"📣 **Broadcast sent** to `{sent}` chats." + (f" Failed: `{fail}`." if fail else ""))