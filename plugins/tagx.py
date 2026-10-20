"""XENO tag & mention module: mention-all in groups, member/admin listing."""
from core.command import command

TAG_LIMIT = 30  # Telegram's own anti-spam ceiling for mentions is ~100/msg


async def _mention(m):
    uname = getattr(m, "username", None)
    if uname:
        return f"@{uname}"
    return f"[{getattr(m, 'first_name', 'user')}](tg://user?id={getattr(m, 'id', 0)})"


@command("tag")
async def tag_cmd(event):
    """Mention up to 30 members of this group. Usage: `.tag <text>`"""
    if not event.is_group:
        return await event.eor("This only works in groups.")
    a = event.text.split(maxsplit=1)
    msg = a[1].strip() if len(a) > 1 else "Attention!"
    try:
        # Note: get_participants takes `filter=`, not `aggressive=` — passing the
        # latter is a TypeError, which is why this used to always fail.
        members = await event.client.get_participants(event.chat_id, limit=TAG_LIMIT)
        names = [_mention(m) for m in members if not isinstance(m, int)]
        if not names:
            return await event.eor("No members to tag.")
        await event.eor(f"**{msg}**\n\n" + " ".join(names), link_preview=False)
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("tagall")
async def tagall_cmd(event):
    """Mention all members with a default message."""
    await tag_cmd(_retagged(event))


class _Retagged:
    """View over an event with rewritten text, so tag_cmd can be reused."""

    def __init__(self, event):
        self._e = event
        self.text = f"{event.text.split()[0]} all"

    def __getattr__(self, k):
        return getattr(self._e, k)


def _retagged(event):
    return _Retagged(event)


@command("groupadmins")
async def admins_cmd(event):
    """List group admins. Usage: `.groupadmins`"""
    if not event.is_group:
        return await event.eor("Groups only.")
    from telethon.tl.functions.channels import GetParticipantsRequest
    from telethon.tl.types import ChannelParticipantsAdmins

    try:
        r = await event.client(
            GetParticipantsRequest(
                channel=event.chat_id,
                filter=ChannelParticipantsAdmins(),
                offset=0,
                limit=100,
                hash=0,
            )
        )
    except Exception as e:
        return await event.eor(f"Error: `{e}`")
    admins = [_mention(u) for u in getattr(r, "users", [])]
    if not admins:
        return await event.eor("No admins found.")
    await event.eor("**🛡 Group admins:**\n" + "\n".join(f"• {a}" for a in admins[:50]))


@command("listmembers")
async def listmembers_cmd(event):
    """List the first 40 members of this group. Usage: `.listmembers`"""
    if not event.is_group:
        return await event.eor("Groups only.")
    try:
        members = await event.client.get_participants(event.chat_id, limit=40)
    except Exception as e:
        return await event.eor(f"Error: `{e}`")
    if not members:
        return await event.eor("Could not fetch members (are you an admin?).")
    await event.eor(
        f"**👥 Members (first {len(members)}):**\n"
        + "\n".join(f"• {getattr(m, 'first_name', '?')} — `{m.id}`" for m in members)
    )


@command("raw")
async def raw_cmd(event):
    """Raw text of a replied message. Usage: `.raw` (reply to msg)"""
    if not event.reply_to:
        return await event.eor("Reply to a message.")
    r = await event.get_reply_message()
    txt = getattr(r, "raw_text", "") or "(no text)"
    await event.eor(f"**Raw text:**\n`{txt[:1500]}`")


@command("quotex")
async def quote_cmd(event):
    """Quote a replied message. Usage: `.quotex` (reply)"""
    if not event.reply_to:
        return await event.eor("Reply to a message to quote it.")
    r = await event.get_reply_message()
    nm = getattr(r.sender, "first_name", "Unknown") if r.sender else "Unknown"
    txt = getattr(r, "raw_text", "")
    if not txt:
        return await event.eor("No text to quote.")
    await event.eor(f"**» {nm}:**\n{txt}")


@command("linkprod")
async def linkprod_cmd(event):
    """Link to a replied message (public chats only). Usage: `.linkprod` (reply)"""
    if not event.reply_to:
        return await event.eor("Reply to a message.")
    if not event.is_group:
        return await event.eor("Only works in public groups/channels.")
    chat = await event.get_chat()
    uname = getattr(chat, "username", None)
    if not uname:
        return await event.eor("This chat has no public link.")
    await event.eor(f"Message link: `https://t.me/{uname}/{event.reply_to.msg_id}`")


@command("markread")
async def markread_cmd(event):
    """Mark current chat read. Usage: `.markread`"""
    try:
        from telethon.tl.functions.messages import ReadHistoryRequest

        await event.client(ReadHistoryRequest(event.chat_id, 0))
    except Exception as e:
        return await event.eor(f"Couldn't mark read: `{e}`")
    await event.eor("🆗 Marked read.")