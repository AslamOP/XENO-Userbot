"""Utilitools (XENO): id, profile, userinfo, invite, kickme, date, bots,
listreserved, ipinfo, tr, short, hl, calc, paste, eod.

File handling (.ls / .json / .webshot) lives in files.py."""
import ast
import calendar
import datetime as dt
import math
import operator

from telethon import functions as fn
from telethon import types as tgtypes

from core.command import command
from core.http import get_json, get_text

# .ls / .json / .webshot moved to plugins/files.py — the store path is defined
# there once instead of in three modules.


def _n(x):
    return f"`{x}`"


async def _get_json(url, params=None):
    return await get_json(url, params) if params is not None else await get_json(url)


# ---------------------------------------------------------------- ids / info
@command("id")
async def id_cmd(event):
    """Get IDs of user / chat / replied media / current chat."""
    if event.is_reply:
        msg = await event.get_reply_message()
        lines = [f"**User ID:** {_n(msg.sender_id)}"]
        if msg.media:
            mid = getattr(msg.media, "id", None)
            if mid:
                lines.append(f"**Media ID:** {_n(mid)}")
        if event.client and getattr(msg, "sender", None) and getattr(msg.sender, "bot", False):
            lines.append("_replied sender is a bot_")
        return await event.eor("\n".join(lines))
    ent = None
    args = event.text.split(maxsplit=1)
    if len(args) > 1:
        try:
            ent = await event.client.get_entity(args[1].strip())
        except Exception:
            ent = None
    if ent is not None:
        title = getattr(ent, "title", None) or getattr(ent, "first_name", "") or ""
        lines = [f"**Entity:** `{title}`", f"**ID:** {_n(getattr(ent, 'id', '?'))}"]
        if getattr(ent, "username", None):
            lines.append(f"**Username:** @{ent.username}")
        return await event.eor("\n".join(lines))
    chat = None
    try:
        chat = await event.get_chat()
    except Exception:
        chat = None
    cid = getattr(chat, "id", event.chat_id)
    ctitle = getattr(chat, "title", None) or getattr(chat, "first_name", None) or "this chat"
    me = await event.client.get_me()
    return await event.eor(f"**Chat:** `{ctitle}`\n**Chat ID:** {_n(cid)}\n**My ID:** {_n(me.id)}")


@command("profile")
async def profile_cmd(event):
    """Detailed profile: Ultroid-style info for reply / @username / id / yourself."""
    target = None
    if event.is_reply:
        target = (await event.get_reply_message()).sender_id
    args = event.text.split(maxsplit=1)
    if len(args) > 1:
        target = args[1].strip()
    try:
        ent = (
            await event.client.get_entity(target)
            if target
            else await event.client.get_me()
        )
    except Exception as e:
        return await event.eor(f"Error: `{e}`")

    first = getattr(ent, "first_name", "") or ""
    last = getattr(ent, "last_name", "") or ""
    name = (first + " " + last).strip()
    lines = ["**ℹ️ Profile**", f"**Name:** `{name or 'unknown'}`", f"**ID:** {_n(ent.id)}"]
    lines.append(f"**Username:** @{getattr(ent, 'username', None) or 'None'}")
    lines.append(f"**Bot:** `{getattr(ent, 'bot', False)}`")
    lines.append(f"**Premium:** `{getattr(ent, 'premium', False)}`")
    if getattr(ent, "scam", False):
        lines.append("⚠️ **SCAM**")
    if getattr(ent, "restricted", False):
        lines.append("⚠️ **Restricted**")
    if isinstance(ent, (tgtypes.Channel, tgtypes.Chat)):
        lines.insert(1, f"**Title:** `{getattr(ent, 'title', '') or ''}`")
        lines.append(f"**Scope:** `{'Channel' if isinstance(ent, tgtypes.Channel) else 'Group'}`")
    await event.eor("\n".join(lines))


@command("userinfo")
async def userinfo_cmd(event):
    """Detailed profile: same as .info but forces reply/@user/id (no fallback to yourself)."""
    target = None
    if event.is_reply:
        target = (await event.get_reply_message()).sender_id
    args = event.text.split(maxsplit=1)
    if len(args) > 1:
        target = args[1].strip()
    if not target:
        return await event.eor("Reply to someone or give @username / user id.")
    try:
        ent = await event.client.get_entity(target)
    except Exception as e:
        return await event.eor(f"Error: `{e}`")

    first = getattr(ent, "first_name", "") or ""
    last = getattr(ent, "last_name", "") or ""
    name = (first + " " + last).strip()
    lines = ["**👤 Userinfo**", f"**Name:** `{name or 'unknown'}`", f"**ID:** {_n(ent.id)}"]
    lines.append(f"**Username:** @{getattr(ent, 'username', None) or 'None'}")
    lines.append(f"**Bot:** `{getattr(ent, 'bot', False)}`")
    lines.append(f"**Premium:** `{getattr(ent, 'premium', False)}`")
    if getattr(ent, "scam", False):
        lines.append("⚠️ **SCAM**")
    if getattr(ent, "fake", False):
        lines.append("⚠️ **Fake**")
    try:
        ph = await event.client.get_profile_photos(ent, limit=1)
        if ph:
            lines.append("**Has profile photo:** yes")
    except Exception:
        pass
    await event.eor("\n".join(lines))


# ---------------------------------------------------------------- chat utils
@command("invite")
async def invite_cmd(event):
    """Invite a user (reply / @username / id) to the current chat."""
    target = None
    if event.is_reply:
        target = (await event.get_reply_message()).sender_id
    args = event.text.split(maxsplit=1)
    if len(args) > 1:
        target = args[1].strip()
    if not target:
        return await event.eor("Reply to someone or give @username / user id.")
    try:
        await event.client(fn.messages.AddChatUserRequest(event.chat_id, target, fwd_limit=10))
        await event.eor(f"**Invited** `{target}`")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("kickme")
async def kickme_cmd(event):
    """Kick yourself out of the current group."""
    me = await event.client.get_me()
    await event.eor(f"`{me.first_name} left this group. Bye!`")
    await event.client.delete_dialog(event.chat_id)


@command("date")
async def date_cmd(event):
    """Show today's date & a calendar for the current month."""
    now = dt.datetime.now()
    cal = calendar.month(now.year, now.month)
    await event.eor(
        f"**🗓 {now.strftime('%A, %d %B %Y')}**\n"
        f"Time: `{now.strftime('%I:%M %p')}`\n```{cal}```"
    )


@command("bots")
async def bots_cmd(event):
    """List all bots in the current chat."""
    out = []
    count = 0
    try:
        async for u in event.client.iter_participants(event.chat_id):
            if getattr(u, "bot", False):
                count += 1
                out.append(f"• @{getattr(u, 'username', None) or u.first_name or u.id}")
    except Exception as e:
        return await event.eor(f"Error: `{e}`")
    if not out:
        return await event.eor("No bots found in this chat.")
    await event.eor(f"**🤖 Bots found: {count}**\n" + "\n".join(out[:50]))


@command("listreserved")
async def listreserved_cmd(event):
    """List all usernames you've reserved (owned public chats/channels)."""
    try:
        r = await event.client(fn.channels.GetAdminedPublicChannelsRequest())
    except Exception as e:
        return await event.eor(f"Error: `{e}`")
    names = [
        f"• @{c.username} — {getattr(c, 'title', '') or ''}"
        for c in r.chats
        if getattr(c, "username", None)
    ]
    if not names:
        return await event.eor("No reserved usernames found.")
    await event.eor(f"**🗂 Reserved usernames ({len(names)}):**\n" + "\n".join(names[:60]))


# ---------------------------------------------------------------- network
@command("ipinfo")
async def ipinfo_cmd(event):
    """Get info about an IP address (default: your public IP)."""
    args = event.text.split(maxsplit=1)
    ip = args[1].strip() if len(args) > 1 else ""
    url = f"https://ipinfo.io/{ip}/json" if ip else "https://ipinfo.io/json"
    try:
        d = await _get_json(url)
    except Exception as e:
        return await event.eor(f"Error: `{e}`")
    keys = ["ip", "hostname", "city", "region", "country", "loc", "org", "postal", "timezone"]
    lines = ["**🌐 IP Info**"]
    for k in keys:
        if d.get(k):
            lines.append(f"**{k.title()}:** `{d[k]}`")
    await event.eor("\n".join(lines))


@command("tr")
async def tr_cmd(event):
    """Translate text. Usage: `.tr <target-lang> <text>` or reply to a msg."""
    args = event.text.split(maxsplit=2)
    text = ""
    if event.is_reply:
        text = (await event.get_reply_message()).message or ""
    tgt = args[1] if len(args) > 1 else "en"
    if len(args) > 2:
        text = text or args[2]
    if not text:
        return await event.eor("Give text or reply. Usage: `.tr <lang> <text>`")
    url = "https://translate.googleapis.com/translate_a/single"
    params = {"client": "gtx", "sl": "auto", "tl": tgt, "dt": "t", "q": text}
    try:
        data = await get_json(url, params)
        res = "".join(x[0] for x in data[0] if x and x[0]) if isinstance(data, list) else ""
        src = data[2] if isinstance(data, list) and len(data) > 2 else "?"
        await event.eor(f"**Translated** ({src} → {tgt}):\n`{res}`")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("short")
async def short_cmd(event):
    """Shorten a URL via is.gd (no key)."""
    args = event.text.split(maxsplit=1)
    url = args[1].strip() if len(args) > 1 else ""
    if not url and event.is_reply:
        url = (await event.get_reply_message()).message or ""
    if not url:
        return await event.eor("Give a URL. Usage: `.short <url>`")
    try:
        d = await _get_json("https://is.gd/create.php", {"format": "json", "url": url})
        await event.eor(f"**Shortened:** {d.get('shorturl') or ('error: ' + str(d))}")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("hl")
async def hl_cmd(event):
    """Send a hidden link (invisible name, shows preview)."""
    args = event.text.split(maxsplit=1)
    url = args[1].strip() if len(args) > 1 else ""
    if not url:
        return await event.eor("Give a URL. Usage: `.hl <url>`")
    if not url.startswith("http"):
        url = "https://" + url
    await event.eor(f"[ㅤ]({url})")


# ---------------------------------------------------------------- compute / paste
@command("calc")
async def calc_cmd(event):
    """Safe calculator: `.calc 2+3*4` (only numbers and + - * / % ** ( ))."""
    args = event.text.split(maxsplit=1)
    expr = args[1].strip() if len(args) > 1 else ""
    if not expr:
        return await event.eor("Give an expression. Usage: `.calc 2+3*4`")
    expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**").replace(",", "")

    def _safe_eval(node):
        if isinstance(node, ast.Expression):
            node = node.body
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            return OPS[type(node.op)](_safe_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            left, right = _safe_eval(node.left), _safe_eval(node.right)
            # `.calc 9**9**9` would otherwise hang the worker indefinitely.
            if isinstance(node.op, ast.Pow) and (
                abs(right) > 64 or (isinstance(left, int) and abs(left) > 10)
            ):
                raise ValueError("exponent or base too large")
            result = OPS[type(node.op)](left, right)
            if isinstance(result, (int, float)) and abs(result) > 10 ** 400:
                raise ValueError("result too large")
            return result
        raise ValueError("unsupported expression")

    OPS = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow,
        ast.USub: operator.neg, ast.UAdd: operator.pos,
    }
    try:
        node = ast.parse(expr, mode="eval")
        result = _safe_eval(node)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        await event.eor(f"`{expr}`\n= **{result}**")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("paste")
async def paste_cmd(event):
    """Paste text to a Telegraph page. Usage: `.paste <text>` or reply to a msg."""
    text = ""
    if event.is_reply:
        text = (await event.get_reply_message()).message or ""
    args = event.text.split(maxsplit=1)
    if len(args) > 1:
        text = text or args[1]
    if not text:
        return await event.eor("Give text or reply. Usage: `.paste <text>`")

    # Shared helper in minitools: anonymous account -> createAccount -> createPage.
    from plugins.minitools import create_telegraph

    try:
        url = await create_telegraph(text.split("\n", 1)[0].strip()[:60] or "Xeno Paste", text)
        await event.eor(f"**Pasted on Telegraph:**\n{url}")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("eod")
async def eod_cmd(event):
    """Event of the day: English Wikipedia's featured events for today. (Ultroid .eod equivalent.)"""
    import datetime as _dt

    today = _dt.date.today().isoformat()
    try:
        d = await _get_json(f"https://api.wikimedia.org/feed/v1/wikipedia/en/featured/{today}")
    except Exception as e:
        return await event.eor(f"Error: `{e}`")
    evts = d.get("onthisday", [])
    lines = [f"**🗓 On this day — {today}**"]
    for ev in evts[:5]:
        lines.append(f"• `{ev.get('year')}` — {ev.get('text', '')}")
    tfa = d.get("tfa")
    if tfa:
        lines.insert(1, f"\n**⭐ Featured article:** {tfa.get('titles', {}).get('normalized', '')}")
    await event.eor("\n".join(lines)[:4000])


