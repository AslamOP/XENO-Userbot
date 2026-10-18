"""XENO finish module — last batch of gadget commands to round out 500+."""
import asyncio
import time

from core.command import command


@command("typing")
async def typing_cmd(event):
    """Send a fake typing indicator for n seconds. Usage: `.typing <sec>`"""
    a = event.text.split(maxsplit=1)
    try:
        n = min(int(a[1]), 10)
    except (IndexError, ValueError):
        n = 3
    from telethon.tl.functions.messages import SetTypingRequest
    from telethon.tl.types import SendMessageTypingAction
    for _ in range(n):
        await event.client(SetTypingRequest(event.chat_id, SendMessageTypingAction()))
        await asyncio.sleep(1)
    await event.reply("✍️ Done typing (fake).")


@command("readonce")
async def readonce_cmd(event):
    """Mark current chat read (alias)."""
    try:
        from telethon.tl.functions.messages import ReadHistoryRequest
        await event.client(ReadHistoryRequest(event.chat_id, 0))
        await event.reply("✅ Read.")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("saved")
async def saved_cmd(event):
    """Check saved-messages access."""
    me = await event.client.get_me()
    return await event.reply(f"Saved messages ID: `{me.id}`")


@command("dc")
async def dc_cmd(event):
    """Report which datacenter this session is connected to."""
    # me.dc_id doesn't exist on a User entity — this always printed "auto".
    me = await event.client.get_me()
    dc = getattr(event.client, "_sender_dc", None) or getattr(event.client, "dc_id", None)
    if dc is None:
        conn = getattr(event.client, "_connection", None)
        dc = getattr(conn, "dc_id", None)
    return await event.reply(
        f"🖥 Session DC: `{dc if dc is not None else 'unknown'}`\n"
        f"Account: `{me.id}`"
    )


@command("jsonfmt")
async def jsonfmt_cmd(event):
    """Pretty-print a replied JSON. Usage: `.jsonfmt` (reply to JSON msg)"""
    if not event.reply_to:
        return await event.reply("Reply to a JSON text message.")
    import json
    r = await event.get_reply_message()
    txt = getattr(r, "raw_text", "")
    try:
        data = json.loads(txt)
        return await event.reply(f"```json\n{json.dumps(data, indent=2)[:3000]}\n```")
    except Exception:
        return await event.reply("Not valid JSON.")


@command("urlparse")
async def urlparse_cmd(event):
    """Split a URL into its components. Usage: `.urlparse <url>`"""
    from urllib.parse import urlsplit
    a = event.text.split(maxsplit=1)
    u = a[1].strip() if len(a) > 1 else ""
    if not u:
        return await event.reply("Give a URL.")
    s = urlsplit(u if "//" in u else "//" + u)
    return await event.reply(
        f"**🔗 URL parts:**\nscheme: `{s.scheme}`\nnetloc: `{s.netloc}`\n"
        f"path: `{s.path}`\nquery: `{s.query}`\nfragment: `{s.fragment}`")


@command("chars")
async def chars_cmd(event):
    """Count characters & words in a text. Usage: `.chars <text>`"""
    a = event.text.split(maxsplit=1)
    t = a[1].strip() if len(a) > 1 else ""
    if not t:
        return await event.reply("Give text.")
    return await event.reply(
        f"**🔢 Text stats:**\nCharacters: `{len(t)}`\nWords: `{len(t.split())}`\n"
        f"Lines: `{t.count(chr(10))+1}`")


@command("emojiinfo")
async def emojiinfo_cmd(event):
    """Info about a single emoji char. Usage: `.emojiinfo 🙂`"""
    a = event.text.split(maxsplit=1)
    e = a[1].strip() if len(a) > 1 else ""
    if not e:
        return await event.reply("Give an emoji.")
    ch = e[0]
    return await event.reply(
        f"**🕵️ Emoji:**\nChar: `{ch}`\nCodepoint: `U+{ord(ch):04X}`\n"
        f"Unicode name: `{__import__('unicodedata').name(ch, '?')}`")

@command("source")
async def source_cmd(event):
    """XENO source info."""
    return await event.reply(
        "**🧬 XENO Userbot**\n"
        "Original Python/Telethon project.\n"
        "Modules live in `plugins/` — browse with editors.")


@command("shrug")
async def shrug_cmd(event):
    """Classic shrug (append optional text)."""
    a = event.text.split(maxsplit=1)
    extra = (" " + a[1].strip()) if len(a) > 1 and a[1].strip() else ""
    return await event.reply(f"¯\\_(ツ)_/¯{extra}")
