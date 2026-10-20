import re

from telethon import events

import config
from core import assistant as assistant_mod
from core import wrappers  # noqa: F401  — monkeypatches Message.eor / Message.eod
from core.bot import bot


def _client(which):
    """Resolve the TelegramClient a handler should be registered on."""
    return assistant_mod.asst if which == "assistant" else bot


def _tail(pattern):
    """Optional-args tail, unless the plugin already wrote a full regex."""
    return "" if (pattern.endswith("$") or pattern[-1:] in (")", "*", "+")) else r"(?:\s.+)?$"


def command(pattern, client="user", **kwargs):
    """
    Decorator to register a command handler.

    Usage:
        @command("ping")
        async def ping_handler(event):
            await event.reply("Pong!")

    Registers once per prefix in config.PREFIXES on the userbot client with
    outgoing=True, so only messages your own account sends can trigger it.

    client="assistant" registers on the control-panel bot instead, using
    config.ASSISTANT_PREFIX and incoming=True — on the bot side you can't
    "type" a command, so the outgoing filter doesn't apply.
    """
    def decorator(func):
        target = _client(client)
        if target is None:
            # Assistant not running: skip registration instead of crashing the
            # whole plugin load.
            return func

        if client == "assistant":
            full = rf"^{re.escape(config.ASSISTANT_PREFIX)}{pattern}{_tail(pattern)}"
            target.add_event_handler(
                func,
                events.NewMessage(pattern=full, incoming=True, **kwargs),
            )
        else:
            for prefix in config.PREFIXES:
                full = rf"^{re.escape(prefix)}{pattern}{_tail(pattern)}"
                target.add_event_handler(
                    func,
                    events.NewMessage(pattern=full, outgoing=True, **kwargs),
                )
        return func

    return decorator


def asst_cmd(pattern, owner=True, admins=False, private_only=False, **kwargs):
    """
    Register a control-panel command on the assistant bot.

    Unlike @command, these arrive as inbound DMs, so authorization is checked
    on sender_id instead of relying on outgoing=True. owner defaults to True —
    a control panel with no gate is an open door.

    Usage:
        @asst_cmd("status")
        async def status(event):
            await event.reply("ok")
    """
    def decorator(func):
        target = _client("assistant")
        if target is None:
            return func

        async def wrapped(event):
            if owner:
                from core.auth import is_owner

                if not await is_owner(event):
                    # Silent: don't confirm the panel exists to strangers.
                    return
            if private_only and not event.is_private:
                return
            if admins and not event.is_private:
                from core.auth import is_admin

                if not await is_admin(event.client, event.chat_id, event.sender_id):
                    return
            return await func(event)

        wrapped.__name__ = func.__name__
        wrapped.__doc__ = func.__doc__
        wrapped.__module__ = func.__module__
        full = rf"^{re.escape(config.ASSISTANT_PREFIX)}{pattern}{_tail(pattern)}"
        target.add_event_handler(
            wrapped, events.NewMessage(pattern=full, incoming=True, **kwargs)
        )
        return func

    return decorator


def asst_callback(pattern, owner=True, **kwargs):
    """Register an inline-button callback handler on the assistant bot."""
    def decorator(func):
        target = _client("assistant")
        if target is None:
            return func

        async def wrapped(event):
            if owner:
                from core.auth import is_owner

                if not await is_owner(event):
                    return
            return await func(event)

        wrapped.__name__ = func.__name__
        wrapped.__doc__ = func.__doc__
        wrapped.__module__ = func.__module__
        target.add_event_handler(
            wrapped, events.CallbackQuery(pattern=pattern, **kwargs)
        )
        return func

    return decorator


def event_handler(event_class=events.NewMessage, **kwargs):
    """Generic event handler decorator on the userbot client."""
    def decorator(func):
        bot.add_event_handler(func, event_class(**kwargs))
        return func
    return decorator
