"""XENO sys-ops: RCE-lite, service control, broadcast. Owner/sudo only.

Note: `.evalx` and `.execx` execute arbitrary Python as this process's user.
They are deliberately not "safe" — restrict sudo_users accordingly.
"""
import asyncio
import time

from core.auth import is_owner, is_sudo
from core.command import command


async def _deny(event, sudo_ok=False):
    allowed = await is_owner(event) or (sudo_ok and await is_sudo(event))
    if not allowed:
        await event.eor("🔒 Owner only." if not sudo_ok else "🔒 Owner or sudo only.")
        return True
    return False


@command("evalx")
async def evalx_cmd(event):
    """Owner/sudo: evaluate a python expression. Usage: `.evalx 2+2`"""
    if await _deny(event, sudo_ok=True):
        return
    code = event.text.split(maxsplit=1)[-1]
    try:
        out = eval(code, {"event": event, "bot": event.client})  # noqa: S307
        if asyncio.iscoroutine(out):
            out = await out
        await event.eor(f"**Eval:**\n`{out}`")
    except Exception as e:
        await event.eor(f"**Error:** `{e}`")


@command("execx")
async def execx_cmd(event):
    """Owner/sudo: run python statements. Usage: ````.execx print(1)````"""
    if await _deny(event, sudo_ok=True):
        return
    code = event.text.split(maxsplit=1)[-1]
    import contextlib
    import io

    buf = io.StringIO()
    try:
        # exec has no await; use asyncio.run for coroutines if needed.
        with contextlib.redirect_stdout(buf):
            exec(code, {"event": event, "bot": event.client})  # noqa: S102
        out = buf.getvalue()
        await event.eor(f"**Exec:**\n`{out[:4000]}`" if out else "**Exec:** (no output)")
    except Exception as e:
        await event.eor(f"**Error:** `{e}`")


@command("logsx")
async def logsx_cmd(event):
    """Owner: recent log lines. Usage: `.logsx`"""
    if await _deny(event):
        return
    import os
    import subprocess

    out = ""
    try:
        r = subprocess.run(
            ["journalctl", "-u", "telegram-userbot", "-n", "30", "--no-pager"],
            capture_output=True, text=True, timeout=10,
        )
        # No sudo, so journalctl is usually empty outside the systemd group.
        out = (r.stdout or r.stderr or "").strip()
    except Exception as e:
        out = f"journalctl failed: {e}"
    if not out:
        log = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "userbot.log")
        try:
            with open(log) as f:
                out = "".join(f.readlines()[-30:])
        except Exception:
            out = (
                "(no journal output and no userbot.log — running under Docker? "
                "use `docker compose logs --tail 30`)"
            )
    await event.eor(f"**📜 Logs (last 30):**\n`{out[-1500:]}`")


@command("srestart")
async def srestart_cmd(event):
    """Owner: restart the XENO systemd service. Usage: `.srestart`"""
    if await _deny(event):
        return
    import subprocess

    try:
        # -n: never prompt for a password, or this blocks the event loop forever.
        r = subprocess.run(
            ["sudo", "-n", "systemctl", "restart", "telegram-userbot"],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode == 0:
            await event.eor("♻️ Restart requested (this reply may not be delivered).")
        else:
            await event.eor(
                "⚠️ `systemctl` failed:\n`"
                + (r.stderr or r.stdout).strip()[-500:]
                + "`\nIf you're on Docker, use `docker compose restart` instead."
            )
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("broadcast")
async def broadcast_cmd(event):
    """Owner: send a message to all group chats. Usage: `.broadcast <text>`"""
    if await _deny(event):
        return
    txt = event.text.split(maxsplit=1)
    msg = txt[1].strip() if len(txt) > 1 else ""
    if not msg:
        return await event.eor("Give a message: `.broadcast <text>`")
    try:
        from telethon.tl.functions.messages import GetDialogsRequest
        from telethon.tl.types import InputPeerEmpty

        me = await event.client.get_me()
        d = await event.client(
            GetDialogsRequest(
                offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(), limit=100, hash=0
            )
        )
        sent = failed = skipped = 0
        for dl in d.dialogs:
            # Never broadcast into Saved Messages.
            if dl.id == me.id:
                continue
            if not getattr(dl, "is_group", False):
                skipped += 1
                continue
            try:
                await event.client.send_message(dl.id, msg)
                sent += 1
                await asyncio.sleep(0.5)  # stay under flood limits
            except Exception:
                failed += 1
        await event.eor(
            f"📣 Broadcast: `{sent}` groups sent, `{failed}` failed, "
            f"`{skipped}` non-groups skipped."
        )
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("unbanall")
async def unbanall_cmd(event):
    """Owner: unban everyone banned in this group."""
    if await _deny(event):
        return
    if not event.is_group:
        return await event.eor("Groups only.")
    try:
        from telethon.tl.functions.channels import EditBannedRequest, GetParticipantsRequest
        from telethon.tl.types import ChannelParticipantsKicked, ChatBannedRights

        chat = await event.get_chat()
        r = await event.client(
            GetParticipantsRequest(
                channel=chat, filter=ChannelParticipantsKicked(), offset=0, limit=100, hash=0
            )
        )
        cnt = 0
        for u in r.users:
            try:
                await event.client(
                    EditBannedRequest(
                        chat, u.id, ChatBannedRights(
                            until_date=None, view_messages=None, send_messages=None,
                            send_media=None, send_stickers=None, send_gifs=None,
                            send_games=None, send_inline=None, embed_links=None,
                        )
                    )
                )
                cnt += 1
            except Exception:
                continue
        await event.eor(f"✅ Unbanned `{cnt}` users.")
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("spamx")
async def spamx_cmd(event):
    """Owner: send n copies of a line. Usage: `.spamx <n> <text>`"""
    if await _deny(event):
        return
    from telethon.errors import FloodWaitError

    parts = event.text.split(maxsplit=2)
    try:
        n = min(int(parts[1]), 10)
        msg = parts[2] if len(parts) > 2 else "spam"
    except (IndexError, ValueError):
        return await event.eor("Usage: `.spamx <n> <text>` (max 10)")
    sent = 0
    for _ in range(n):
        try:
            await event.client.send_message(event.chat_id, msg)
            sent += 1
            await asyncio.sleep(1.0)
        except FloodWaitError as e:
            await event.eor(f"🛑 Flood wait: `{e.seconds}s`. Stopped after {sent}.")
            return
    await event.eor(f"✅ Sent `{sent}`.")


@command("digest")
async def digest_cmd(event):
    """Owner: unread counts across your chats. Usage: `.digest`"""
    # Was ungated: it printed the whole chat list to anyone who asked.
    if await _deny(event):
        return
    try:
        from telethon.tl.functions.messages import GetDialogsRequest
        from telethon.tl.types import InputPeerEmpty

        d = await event.client(
            GetDialogsRequest(
                offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(), limit=50, hash=0
            )
        )
        lines = ["**📬 Unread:**"]
        n = 0
        for dl in d.dialogs:
            if getattr(dl, "unread_count", 0) > 0 and n < 15:
                lines.append(f"• `{dl.id}` — {dl.unread_count} unread")
                n += 1
        await event.eor("\n".join(lines) if n else "All caught up ✅")
    except Exception as e:
        await event.eor(f"Error: `{e}`")