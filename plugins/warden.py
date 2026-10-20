"""XENO warden module: group guardianship. Warns, rules, notes, filters, blacklist, global bans, verify-on-join, link locks, admin utilities, reporting. Original code."""
import asyncio
import random
import shutil
import string

from telethon import events, errors, functions as fn, types

from core.bot import bot
from core.auth import ambient_enabled, set_ambient
from core.command import command
from core.db import delete as db_delete
from core.db import get as db_get
from core.db import set_ as db_set
from core.db import update as db_update

WARN_LIMIT = 3


async def is_admin(event, user_id=None):
    user_id = user_id or event.sender_id
    try:
        part = await event.client.get_permissions(event.chat_id, user_id)
        return bool(part.is_admin or part.is_creator)
    except Exception:
        return False


async def owner_check(event, user_id=None):
    user_id = user_id or event.sender_id
    import config
    return user_id == config.OWNER_ID


async def resolve_target(event):
    if event.reply_to:
        return (await event.get_reply_message()).sender_id
    args = event.text.split()
    if len(args) > 1:
        try:
            return int(args[1])
        except ValueError:
            return args[1]
    return None


async def chat_id_str(event):
    return str(event.chat_id)


# ================================================================= warns
async def _warns(event):
    cid = await chat_id_str(event)
    return await db_get(f"warns:{cid}", {})


@command("warn")
async def warn_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights to warn.")
    target = await resolve_target(event)
    if not target:
        return await event.eor("Reply to someone or give a user ID.")
    args = event.text.split(maxsplit=2)
    reason = args[2] if len(args) > 2 else "No reason"

    async def _add(w):
        w[str(target)] = w.get(str(target), []) + [reason]
        return w

    cid = await chat_id_str(event)
    warns = await db_update(f"warns:{cid}", _add, {})
    n = len(warns[str(target)])
    limit = await db_get(f"warnlimit:{cid}", WARN_LIMIT)
    await event.eor(f"⚠️ **Warned** user {target}\nReason: `{reason}`\nTotal warns: `{n}/{limit}`")
    if n >= limit:
        try:
            await event.client.kick_participant(event.chat_id, target)
            await event.eor(f"**User {target} auto-kicked** after {n} warns.")
        except Exception as e:
            await event.eor(f"Auto-kick failed: `{e}`")
        await db_update(f"warns:{cid}", lambda w: w.pop(str(target), None) or w, {})


@command("warns")
async def warns_cmd(event):
    target = await resolve_target(event) or event.sender_id
    cid = await chat_id_str(event)
    warns = await _warns(event)
    list_w = warns.get(str(target), [])
    if not list_w:
        return await event.eor(f"User {target} has no warns.")
    limit = await db_get(f"warnlimit:{cid}", WARN_LIMIT)
    text = f"**Warns for {target}** ({len(list_w)}/{limit})\n"
    text += "\n".join(f"{i+1}. {r}" for i, r in enumerate(list_w))
    await event.eor(text)


@command("resetwarns")
async def resetwarns_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    target = await resolve_target(event)
    if not target:
        return await event.eor("Reply to someone or give a user ID.")
    cid = await chat_id_str(event)
    await db_update(f"warns:{cid}", lambda w: w.pop(str(target), None) or w, {})
    await event.eor(f"Cleared warns for {target}.")


@command("setwarnlimit")
async def setwarnlimit_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await event.eor("Usage: `setwarnlimit <number>`")
    cid = await chat_id_str(event)
    await db_set(f"warnlimit:{cid}", int(args[1]))
    await event.eor(f"Warn limit set to `{args[1]}`.")


# ================================================================= rules
@command("setrules")
async def setrules_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        return await event.eor("Give the rules text. Usage: `setrules <text>`")
    await db_set(f"rules:{await chat_id_str(event)}", args[1])
    await event.eor("✅ Rules saved.")


@command("rules")
async def rules_cmd(event):
    rules = await db_get(f"rules:{await chat_id_str(event)}")
    await event.eor(f"**📜 Rules**\n{rules}" if rules else "No rules set. Use `setrules <text>`.")


@command("clearrules")
async def clearrules_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    await db_delete(f"rules:{await chat_id_str(event)}")
    await event.eor("Rules removed.")


# ================================================================= notes
@command("savenote")
async def savenote_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split(maxsplit=2)
    if len(args) < 3:
        return await event.eor("Usage: `savenote <name> <content>`")
    name, content = args[1].lower(), args[2]
    cid = await chat_id_str(event)

    async def _add(n):
        n[name] = content
        return n

    await db_update(f"notes:{cid}", _add, {})
    await event.eor(f"Note **#{name}** saved. Use `#{name}` to view.")


@command("delnote")
async def delnote_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split()
    if len(args) < 2:
        return await event.eor("Usage: `delnote <name>`")
    cid = await chat_id_str(event)
    name = args[1].lower()
    await db_update(f"notes:{cid}", lambda n: n.pop(name, None) or n, {})
    await event.eor(f"Note #{name} deleted.")


@command("notes")
async def notes_cmd(event):
    notes = await db_get(f"notes:{await chat_id_str(event)}", {})
    if not notes:
        return await event.eor("No notes here. Use `savenote`.")
    text = "**Saved notes:**\n" + "\n".join(f"#{k}" for k in notes)
    await event.eor(text)


@bot.on(events.NewMessage(pattern=r"^#(\w+)", outgoing=True))
async def note_trigger(event):
    name = event.pattern_match.group(1).lower()
    notes = await db_get(f"notes:{str(event.chat_id)}", {})
    if name in notes:
        await event.eor(notes[name])


# ================================================================= filters
@command("addfilter")
async def addfilter_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split(maxsplit=2)
    if len(args) < 3:
        return await event.eor("Usage: `addfilter <trigger> <reply>`")
    trigger, content = args[1].lower(), args[2]
    cid = await chat_id_str(event)

    async def _add(f):
        f[trigger] = content
        return f

    await db_update(f"filters:{cid}", _add, {})
    await event.eor(f"Filter saved: `{trigger}` → `{content[:30]}`")


@command("delfilter")
async def delfilter_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split()
    if len(args) < 2:
        return await event.eor("Usage: `delfilter <trigger>`")
    cid = await chat_id_str(event)
    await db_update(f"filters:{cid}", lambda f: f.pop(args[1].lower(), None) or f, {})
    await event.eor("Filter removed.")


@command("filters")
async def filters_cmd(event):
    filters = await db_get(f"filters:{await chat_id_str(event)}", {})
    if not filters:
        return await event.eor("No filters here.")
    text = "**Filters:**\n" + "\n".join(f"`{k}` → `{v[:25]}`" for k, v in filters.items())
    await event.eor(text)


@bot.on(events.NewMessage(outgoing=False))
async def filter_trigger(event):
    if event.is_private or event.out or not event.text:
        return
    if not await ambient_enabled("filters", event.chat_id):
        return
    filters = await db_get(f"filters:{str(event.chat_id)}", {})
    for trigger, content in filters.items():
        if trigger in (event.text or "").lower():
            await event.eor(content)
            return


# ================================================================= blacklist
@command("addbl")
async def addbl_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split(maxsplit=2)
    if len(args) < 3:
        return await event.eor("Usage: `addbl <word> <reason>`")
    word, reason = args[1].lower(), args[2]
    cid = await chat_id_str(event)

    async def _add(b):
        b[word] = reason
        return b

    await db_update(f"blacklist:{cid}", _add, {})
    await event.eor(f"Blacklisted `{word}` (reason: {reason})")


@command("delbl")
async def delbl_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split()
    if len(args) < 2:
        return await event.eor("Usage: `delbl <word>`")
    cid = await chat_id_str(event)
    await db_update(f"blacklist:{cid}", lambda b: b.pop(args[1].lower(), None) or b, {})
    await event.eor("Removed from blacklist.")


@command("blist")
async def blist_cmd(event):
    bl = await db_get(f"blacklist:{await chat_id_str(event)}", {})
    if not bl:
        return await event.eor("No blacklisted words.")
    text = "**Blacklist:**\n" + "\n".join(f"`{w}` — {r}" for w, r in bl.items())
    await event.eor(text)


@bot.on(events.NewMessage(outgoing=False))
async def blacklist_trigger(event):
    if event.is_private or event.out or not event.text:
        return
    if not await ambient_enabled("blacklist", event.chat_id):
        return
    bl = await db_get(f"blacklist:{str(event.chat_id)}", {})
    low = (event.text or "").lower()
    for word in bl:
        if word in low:
            try:
                await event.delete()
            except Exception:
                pass
            me = await event.client.get_me()
            can = await event.client.get_permissions(event.chat_id, me.id)
            if can.is_admin:
                await event.eor(f"**Message removed** — blacklisted word `{word}`.")
            return


# ================================================================= global ban
@command("gban")
async def gban_cmd(event):
    if not await owner_check(event):
        return await event.eor("Owner only.")
    target = await resolve_target(event)
    if not target:
        return await event.eor("Reply to someone or give a user ID.")
    args = event.text.split(maxsplit=2)
    reason = args[2] if len(args) > 2 else "No reason"

    async def _add(g):
        g[str(target)] = reason
        return g

    await db_update("gbans", _add, {})
    await event.eor(f"🌐 **User {target} globally banned.** Reason: `{reason}`")


@command("ungban")
async def ungban_cmd(event):
    if not await owner_check(event):
        return await event.eor("Owner only.")
    target = await resolve_target(event)
    if not target:
        return await event.eor("Reply to someone or give a user ID.")
    await db_update("gbans", lambda g: g.pop(str(target), None) or g, {})
    await event.eor(f"Removed user {target} from global bans.")


@command("gbanlist")
async def gbanlist_cmd(event):
    gbans = await db_get("gbans", {})
    if not gbans:
        return await event.eor("Global ban list is empty.")
    text = "**🌐 Global bans**\n" + "\n".join(f"{u} — {r}" for u, r in gbans.items())
    await event.eor(text)


@bot.on(events.ChatAction)
async def gban_joiner(event):
    uid = event.user_id
    if not uid:
        return
    if not await ambient_enabled("gban", event.chat_id):
        return
    gbans = await db_get("gbans", {})
    if str(uid) not in gbans:
        return
    try:
        await event.client.kick_participant(event.chat_id, uid)
        await event.eor(f"**Kicked: user {uid} is globally banned.**")
    except Exception:
        pass


# ================================================================= captcha / verify on join
@command("captcha")
async def captcha_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split()
    if len(args) < 2 or args[1].lower() not in ("on", "off"):
        return await event.eor("Usage: `captcha on|off`")
    await db_set(f"captcha:{await chat_id_str(event)}", args[1].lower() == "on")
    await event.eor(f"🛡 Captcha verification **{args[1].upper()}**.")


@bot.on(events.ChatAction)
async def captcha_joiner(event):
    if not (event.user_joined or event.user_added):
        return
    if not await ambient_enabled("captcha", event.chat_id):
        return
    if not await db_get(f"captcha:{str(event.chat_id)}", False):
        return
    uid = event.user_id
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
    try:
        await event.client.edit_permissions(event.chat_id, uid, send_messages=False)
        msg = await event.eor(
            f"⛔ **Please verify you're human!**\nSend `!verify {code}` here to join.\n"
            f"Miss the code? You will remain muted until verified."
        )
        await db_set(f"captchacode:{event.chat_id}:{uid}", code)
        asyncio.ensure_future(_captcha_watchdog(event, uid, code))
    except Exception:
        pass


async def _captcha_watchdog(event, uid, code):
    """Kick unverified joiners after the grace period. Runs off the event loop task."""
    await asyncio.sleep(300)
    if await db_get(f"captchacode:{event.chat_id}:{uid}") != code:
        return  # verified (or captcha disabled) in the meantime
    try:
        await event.client.kick_participant(event.chat_id, uid)
    except Exception:
        pass
    finally:
        await db_delete(f"captchacode:{event.chat_id}:{uid}")


@bot.on(events.NewMessage(outgoing=False))
async def captcha_verify(event):
    if event.is_private or not event.text or not event.text.startswith("!verify"):
        return
    parts = event.text.split()
    if len(parts) < 2:
        return await event.eor("Usage: `!verify <code>`")
    stored = await db_get(f"captchacode:{event.chat_id}:{event.sender_id}")
    if stored and parts[1].upper() == stored:
        await event.client.edit_permissions(event.chat_id, event.sender_id, send_messages=True)
        await db_delete(f"captchacode:{event.chat_id}:{event.sender_id}")
        await event.delete()
        await event.eor("✅ Verified! Welcome.")


# ================================================================= extra locks (links / forwards)
@command("locklinks")
async def locklinks_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    await db_set(f"locklinks:{await chat_id_str(event)}", True)
    await event.eor("🔒 Link posting locked (messages with links will be removed).")


@command("unlocklinks")
async def unlocklinks_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    await db_set(f"locklinks:{await chat_id_str(event)}", False)
    await event.eor("🔓 Links allowed again.")


@bot.on(events.NewMessage(outgoing=False))
async def linklock_trigger(event):
    if event.is_private or event.out or not event.text:
        return
    if not await ambient_enabled("linklock", event.chat_id):
        return
    if await db_get(f"locklinks:{str(event.chat_id)}", False):
        me = await event.client.get_me()
        can = await event.client.get_permissions(event.chat_id, me.id)
        if can.is_admin and any(t in (event.text or "") for t in (".com", ".net", ".org", "http:", "https:", "t.me/")):
            try:
                await event.delete()
                await event.eor("🔒 **Links are locked** in this chat.")
            except Exception:
                pass


# ================================================================= admin tools
@command("admins")
async def admins_cmd(event):
    out = []
    try:
        async for part in event.client.iter_participants(event.chat_id, filter=types.ChannelParticipantsAdmins):
            out.append(f"• `{part.id}` — {part.first_name or ''}")
    except Exception as e:
        return await event.eor(f"Error: `{e}`")
    if not out:
        return await event.eor("No admins found.")
    await event.eor("**👑 Admins here:**\n" + "\n".join(out[:50]))


@command("report")
async def report_cmd(event):
    admins = []
    async for part in event.client.iter_participants(event.chat_id, filter=types.ChannelParticipantsAdmins):
        if getattr(part, "bot", False):
            continue
        admins.append(f"@{part.username}" if getattr(part, "username", None) else f"[{part.first_name or 'admin'}](tg://user?id={part.id})")
    if not admins:
        return await event.eor("No admin to notify.")
    await event.eor("**🚨 Report!** " + " ".join(admins))


@command("clean")
async def clean_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split()
    n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 20
    deleted = 0
    async for msg in event.client.iter_messages(event.chat_id, limit=n):
        if msg.service or msg.out:
            await msg.delete()
            deleted += 1
            if deleted >= n:
                break
    await event.eor(f"🧹 Cleaned `{deleted}` service/recent messages.")


@command("setgtitle")
async def setgtitle_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        return await event.eor("Usage: `setgtitle <title>`")
    try:
        await event.client(fn.messages.EditChatTitleRequest(event.chat_id, args[1]))
        await event.eor("✅ Title updated.")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("setgabout")
async def setgabout_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split(maxsplit=1)
    if len(args) < 2:
        return await event.eor("Usage: `setgabout <text>`")
    try:
        await event.client(fn.messages.EditChatAboutRequest(event.chat_id, args[1]))
        await event.eor("✅ Description updated.")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("setgphoto")
async def setgphoto_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    rep = await event.get_reply_message() if event.reply_to else None
    if not rep or not rep.photo:
        return await event.eor("Reply to a photo to set it as the group photo.")
    try:
        import tempfile
        tmp = tempfile.mkdtemp(prefix="xeno_pfp_")
        path = await rep.download_media(file=tmp)
        await event.client(fn.messages.EditChatPhotoRequest(event.chat_id, path))
        shutil.rmtree(tmp, ignore_errors=True)
        await event.eor("✅ Group photo updated.")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("kickbots")
async def kickbots_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    count = 0
    async for part in event.client.iter_participants(event.chat_id):
        if getattr(part, "bot", False) and not (await event.client.get_permissions(event.chat_id, part.id)).is_admin:
            try:
                await event.client.kick_participant(event.chat_id, part.id)
                count += 1
            except Exception:
                pass
    await event.eor(f"🤖 Kicked `{count}` bots (non-admin).")


@command("floodwindow")
async def floodwindow_cmd(event):
    if not await is_admin(event):
        return await event.eor("You need admin rights.")
    args = event.text.split()
    if len(args) < 3 or not args[1].isdigit() or not args[2].isdigit():
        return await event.eor("Usage: `floodwindow <threshold> <seconds>`")
    threshold, window = int(args[1]), int(args[2])
    if threshold < 2 or window < 2 or threshold > 50 or window > 300:
        return await event.eor("Threshold 2-50, window 2-300 seconds.")
    cid = await chat_id_str(event)
    await db_set(f"flood:{cid}", [threshold, window])
    await event.eor(f"Anti-flood window set: {threshold} msgs / {window}s.")
    if not await ambient_enabled("antispam", event.chat_id):
        await event.eor("ℹ️ Anti-spam is currently **off** — `.ambient antispam on` to activate.")


@command("ambient")
async def ambient_cmd(event):
    """Owner-only: turn autonomous handlers on/off.

    Usage:
      `.ambient`               — show status
      `.ambient <feature> on|off` — global toggle
      `.ambient <feature> on|off here` — this chat only
    """
    from core.auth import AMBIENT_FEATURES, is_owner

    if not await is_owner(event):
        return await event.eor("🔒 Owner only.")

    args = event.text.split()
    if len(args) == 1:
        from core.db import get as _get

        lines = []
        for feat in AMBIENT_FEATURES:
            on = await _get(f"ambient:on:{feat}", False)
            here = await _get(f"ambient:chat:{feat}:{event.chat_id}", True)
            mark = "🟢 on" if on and here else "⚪️ off"
            lines.append(f"{mark} — `{feat}` _({AMBIENT_FEATURES[feat]})_")
        return await event.eor(
            "**🧯 Ambient handlers** — these act on other people's messages.\n"
            + "\n".join(lines)
            + "\n\nAll are **off by default**."
        )

    feat = args[1].lower()
    if feat not in AMBIENT_FEATURES:
        return await event.eor(f"Unknown feature. Pick one: `{'`, `'.join(AMBIENT_FEATURES)}`")
    if len(args) < 3 or args[2].lower() not in ("on", "off"):
        return await event.eor("Usage: `.ambient <feature> on|off [here]`")
    on = args[2].lower() == "on"
    here = len(args) > 3 and args[3].lower() == "here"
    await set_ambient(feat, on, event.chat_id if here else None)
    scope = "this chat" if here else "everywhere"
    return await event.eor(f"🧯 `{feat}` turned **{'on' if on else 'off'}** ({scope}).")