"""Shared XENO helpers: owner check, target resolution, admin rights check."""
from telethon.tl.types import ChannelParticipantCreator, ChannelParticipantAdmin

import config


async def is_owner(event):
    return event.sender_id == config.OWNER_ID


async def is_sudo(event):
    if await is_owner(event):
        return True
    try:
        from core.db import get as db_get
        sudo = await db_get("sudo_users", [])
        return event.sender_id in sudo
    except Exception:
        return False


async def require_owner(event):
    return await is_owner(event)


async def resolve_user(event, index=1):
    """Get target user id from reply or mention text at `index`."""
    if event.reply_to:
        r = await event.get_reply_message()
        return getattr(r.sender, "id", r.sender_id)
    parts = event.text.split()
    if len(parts) > index:
        raw = parts[index]
        try:
            return int(raw)
        except ValueError:
            try:
                e = await event.client.get_entity(raw)
                return e.id
            except Exception:
                return raw
    return None


async def is_admin(client, chat_id, user_id):
    try:
        p = await client.get_permissions(chat_id, user_id)
        return p.is_admin or p.is_creator
    except Exception:
        return False


async def get_admin_rank(client, chat_id, user_id):
    """Return creator/admin/member status."""
    p = await client.get_permissions(chat_id, user_id)
    if p.is_creator:
        return "creator"
    if p.is_admin:
        return "admin"
    return "member"


# --------------------------------------------------------------------------
# Ambient-handler gating.
#
# @command handlers are outgoing=True, so only the account owner can trigger
# them. Raw @bot.on(...) handlers are different: they react to OTHER people's
# messages (delete them, mute them, auto-reply). Those get no such guarantee, so
# every one of them must be opted into explicitly by the owner.
# --------------------------------------------------------------------------
AMBIENT_FEATURES = {
    "antispam": "group.py — auto-mute flooders (5 msgs / 10s)",
    "blacklist": "warden.py — auto-delete messages containing blacklisted words",
    "filters": "warden.py — auto-reply to messages containing triggers",
    "captcha": "warden.py — mute + kick new joiners unless they verify",
    "linklock": "warden.py — auto-delete messages containing links",
    "gban": "warden.py — auto-kick globally banned users on join",
    "persona": "persona.py — reactive greetings/partings in DMs",
    "ai_auto": "ai.py — LLM auto-reply to every inbound DM",
}


async def ambient_enabled(feature, chat_id=None):
    """True only if the owner turned this ambient feature on.

    Global toggle: `ambient:on:<feature>` (default False).
    Per-chat override: `ambient:chat:<feature>:<chat_id>`.
    """
    from core.db import get as db_get

    if not await db_get(f"ambient:on:{feature}", False):
        return False
    if chat_id is not None:
        return bool(await db_get(f"ambient:chat:{feature}:{chat_id}", True))
    return True


async def set_ambient(feature, on, chat_id=None):
    from core.db import set_ as db_set

    if chat_id is not None:
        await db_set(f"ambient:chat:{feature}:{chat_id}", bool(on))
    else:
        await db_set(f"ambient:on:{feature}", bool(on))