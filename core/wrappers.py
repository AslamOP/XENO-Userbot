"""core.wrappers — edit-or-reply helpers (Ultroid's eor/eod).

`eor` edits the triggering message in place when possible, falls back to a
fresh reply when the edit cannot land (media, deleted, permissions).
`eod` is eor + auto-delete after a short delay.

Monkey-patched onto telethon's Message at import time so every handler can
call `event.eor(...)` — NewMessage.Event.__getattr__ forwards unknown attrs
to the bound Message, so `event.eor` resolves to `message.eor`.
"""
import asyncio

from telethon.tl.custom.message import Message
from telethon.errors import (
    MessageNotModifiedError,
    MessageDeleteForbiddenError,
    ChatWriteForbiddenError,
)

# How long eod waits before deleting, seconds.
EOD_DEFAULT = 8


async def eor(event, text=None, time=None, **kwargs):
    """Edit-or-reply: edit the triggering message; reply fresh if edit fails.

    - outgoing message → edit in place
    - incoming message → send a new reply (a userbot cannot edit others' msgs)
    - ``file=`` kwarg  → send a new message (Telegram can't attach media via edit)
    - ``time=`` seconds → auto-delete after that delay (does not block)
    """
    try:
        if getattr(event, "out", False) and not kwargs.get("file"):
            try:
                out = await event.edit(text, **kwargs)
            except MessageNotModifiedError:
                out = event
            except Exception:
                # Deleted / no rights / media — fall through to a fresh reply.
                out = None
            if out is not None:
                if time:
                    asyncio.create_task(_auto_delete(out, time))
                return out

        # Incoming, file-bearing, or edit failed → fresh reply.
        out = await event.reply(text, **kwargs)
    except (ChatWriteForbiddenError, MessageDeleteForbiddenError):
        raise
    except Exception:
        # Last-ditch: plain reply without extra kwargs.
        out = await event.reply(text)

    if time:
        asyncio.create_task(_auto_delete(out, time))
    return out


async def eod(event, text=None, **kwargs):
    """Edit-or-reply, auto-deleted after EOD_DEFAULT seconds."""
    return await eor(event, text, time=EOD_DEFAULT, **kwargs)


async def _auto_delete(msg, delay):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


# Make `event.eor(...)` / `message.eor(...)` work everywhere.
if not hasattr(Message, "eor"):
    Message.eor = eor
if not hasattr(Message, "eod"):
    Message.eod = eod
