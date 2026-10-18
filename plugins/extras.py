"""XENO extras module: AFK marker, demotivators, one-off commands.

Two things used to live here and no longer do:
  * .pmpermit / .approve / .disapprove / .listapproved — they only ever wrote db
    keys nothing read, so the "guard" blocked nobody.
  * .savefile and the downloads/ path constant — file handling moved to files.py,
    where the store is defined once instead of three times.
"""
import random
import time

from core import sage
from core.auth import is_owner
from core.command import command
from core.db import get as db_get
from core.db import set_ as db_set


@command("afk")
async def afk_cmd(event):
    """Set AFK with reason. Usage: `.afk <reason>`

    The stored state was never read by any handler, so this used to do nothing.
    It is now surfaced by `.afkstatus`, which is the only consumer.
    """
    reason = event.text.split(maxsplit=1)
    reason = reason[1].strip() if len(reason) > 1 else ""
    await db_set("afk:reason", reason or "gone")
    await db_set("afk:since", int(time.time()))
    await event.reply(f"💤 **AFK**: {reason or 'gone'}\n*(`.afkstatus` to check, `.unafk` to clear.)*")


@command("afkstatus")
async def afkstatus_cmd(event):
    """Show the current AFK state. Usage: `.afkstatus`"""
    reason = await db_get("afk:reason", None)
    since = await db_get("afk:since", None)
    if not reason or not since:
        return await event.reply("🟢 Not AFK.")
    mins = int((time.time() - since) // 60)
    return await event.reply(f"💤 **AFK** for {mins}m — {reason}")


@command("unafk")
async def unafk_cmd(event):
    """Clear AFK status. Usage: `.unafk`"""
    await db_set("afk:reason", None)
    await db_set("afk:since", None)
    await event.reply("👋 Welcome back.")


@command("echo")
async def echo_cmd(event):
    """Echo a message in this chat. Usage: `.echo <text>`"""
    a = event.text.split(maxsplit=1)
    txt = a[1].strip() if len(a) > 1 else ""
    if not txt:
        return await event.reply("Give text to echo.")
    await event.delete()
    await event.client.send_message(event.chat_id, txt)


@command("emote")
async def emote_cmd(event):
    """Send a random action emote. Usage: `.emote <target>`"""
    acts = [
        "pats {t} on the head and smiles.", "gives {t} a cold, silent nod.",
        "throws a pillow at {t}, laughing.", "hands {t} a freshly brewed coffee.",
        "stares at {t} judgingly.", "high-fives {t} with cosmic energy.",
        "dabs sadly but with style towards {t}.", "sends {t} virtual hugs.",
        "challenges {t} to a staring contest.", "awards {t} 5 bonus points.",
    ]
    t = event.text.split(maxsplit=1)
    target = t[1].strip() if len(t) > 1 else "the void"
    await event.reply("_*" + random.choice(acts).format(t=target) + "*_")


@command("dm")
async def dm_cmd(event):
    """DM a user. Usage: `.dm <userid> <text>` or `.dm <text>` (replies to context)"""
    if not await is_owner(event):
        return await event.reply("🔒 Owner only.")
    parts = event.text.split(maxsplit=2)
    if len(parts) < 3:
        return await event.reply("Usage: `.dm <userid> <text>`")
    try:
        uid = int(parts[1])
    except ValueError:
        return await event.reply("Give numeric user id.")
    text = parts[2]
    try:
        await event.client.send_message(uid, text)
        await event.reply(f"✉️ Sent to `{uid}`")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("forward")
async def forward_cmd(event):
    """Forward a message to dm/chat. Usage: `.forward <chatid>` (reply to a message)"""
    if not await is_owner(event):
        return await event.reply("🔒 Owner only.")
    if not event.reply_to:
        return await event.reply("Reply to a message and give target chat: `.forward <id>`")
    parts = event.text.split()
    if len(parts) < 2:
        return await event.reply("Give target chat id.")
    try:
        target = int(parts[1])
    except ValueError:
        return await event.reply("Bad target id.")
    try:
        r = await event.get_reply_message()
        await event.client.forward_messages(target, r.id, event.chat_id)
        await event.reply(f"↪️ Forwarded to `{target}`")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("getpic")
async def getpic_cmd(event):
    """Download a profile picture. Usage: `.getpic <id|username>`"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else "me"
    try:
        ent = await event.client.get_entity(q)
        photos = await event.client(fn.photos.GetUserPhotosRequest(
            user_id=ent.id, offset=0, max_id=0, limit=1))
        if not photos.photos:
            return await event.reply(f"No photos for `{q}`.")
        p = photos.photos[0]
        import io
        buf = io.BytesIO()
        await event.client.download_media(p, buf)
        buf.seek(0)
        await event.reply("**Profile photo:**", file=buf)
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("theme")
async def theme_cmd(event):
    """Show or set the XENO reply accent. Usage: `.theme [name]`"""
    names = list(sage.THEMES)
    a = event.text.split(maxsplit=1)
    if len(a) < 2:
        current = await db_get("theme:current", "void")
        return await event.reply(
            f"🎨 Theme: **{current}**\nAvailable: `{'`, `'.join(names)}`"
        )
    name = a[1].strip().lower()
    if name not in names:
        return await event.reply(f"Themes: `{'`, `'.join(names)}`")
    await db_set("theme:current", name)
    await event.reply(f"🎨 XENO theme → **{name}**")


@command("insultme")
async def insultme_cmd(event):
    line = random.choice([
        "You're the reason auto-correct was invented.",
        "Your brain waves are measured in Hz — pity.",
        "You're like a cloud: when you disappear, it's a beautiful day.",
        "I'd tell you to go to hell but that would be an upgrade.",
        "You bring everyone so much joy — when you leave.",
        "You're proof that evolution can go backwards.",
    ])
    await event.reply(f"😈 {line}")


@command("rank")
async def rank_cmd(event):
    """Mild self-rank. Usage: `.rank`"""
    ranks = ["S-Tier Legend", "Certified Main Character", "Resident Genius",
             "Emotional Support Human", "Professional Napper", "Council Member",
             "Unknown Variable", "Civilian (rare)", "CEO of Chaos", "Plot Armor Holder"]
    await event.reply(f"🏅 Rank: **{random.choice(ranks)}**")