"""Admin tools: ban, kick, mute, purge, pin, etc."""
import asyncio
from telethon import errors
from telethon.tl import functions as fn, types

from core import sage
from core.command import command


async def get_target(event):
    """Get target user from reply or mention."""
    if event.reply_to:
        reply = await event.get_reply_message()
        return reply.sender_id
    args = event.text.split()
    if len(args) > 1:
        try:
            return int(args[1])
        except ValueError:
            return args[1]
    return None


@command("ban")
async def ban_cmd(event):
    """Ban a user (reply or user ID)."""
    target = await get_target(event)
    if not target:
        return await event.reply("Reply to a user or provide user ID.")
    try:
        await event.client.edit_permissions(
            event.chat_id, target, view_messages=False
        )
        await event.reply(f"{sage.ack()} **Banned** — operative `{target}` removed from premises.")
    except errors.ChatAdminRequiredError:
        await event.reply("I need admin rights to ban.")
    except errors.UserAdminInvalidError:
        await event.reply("Cannot ban this user (admin/creator).")


@command("unban")
async def unban_cmd(event):
    """Unban a user (reply or user ID)."""
    target = await get_target(event)
    if not target:
        return await event.reply("Reply to a user or provide user ID.")
    try:
        await event.client.edit_permissions(
            event.chat_id, target, view_messages=True
        )
        await event.reply(f"{sage.ack()} **Unbanned** — access restored for `{target}`.")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("kick")
async def kick_cmd(event):
    """Kick a user (reply or user ID)."""
    target = await get_target(event)
    if not target:
        return await event.reply("Reply to a user or provide user ID.")
    try:
        await event.client.kick_participant(event.chat_id, target)
        await event.reply(f"{sage.ack()} **Kicked** — `{target}` ejected. Zero residuals.")
    except errors.ChatAdminRequiredError:
        await event.reply("I need admin rights to kick.")
    except errors.UserAdminInvalidError:
        await event.reply("Cannot kick this user.")


@command("mute")
async def mute_cmd(event):
    """Mute a user (reply or user ID)."""
    target = await get_target(event)
    if not target:
        return await event.reply("Reply to a user or provide user ID.")
    try:
        await event.client.edit_permissions(
            event.chat_id, target, send_messages=False
        )
        await event.reply(f"{sage.ack()} **Muted** — `{target}` communication channel sealed.")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("unmute")
async def unmute_cmd(event):
    """Unmute a user (reply or user ID)."""
    target = await get_target(event)
    if not target:
        return await event.reply("Reply to a user or provide user ID.")
    try:
        await event.client.edit_permissions(
            event.chat_id, target, send_messages=True
        )
        await event.reply(f"{sage.ack()} **Unmuted** — channel reopened for `{target}`.")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("del")
async def del_cmd(event):
    """Delete the replied message."""
    if not event.reply_to:
        return await event.reply("Reply to a message to delete it.")
    reply = await event.get_reply_message()
    await reply.delete()
    await event.delete()


@command("purge")
async def purge_cmd(event):
    """Delete messages from the replied one to your last."""
    if not event.reply_to:
        return await event.reply("Reply to the first message to start purging from.")
    chat = event.chat_id
    start_msg = (await event.get_reply_message()).id
    end_msg = event.id

    messages = list(range(start_msg, end_msg + 1))
    if len(messages) > 100:
        chunks = [messages[i:i+100] for i in range(0, len(messages), 100)]
        for chunk in chunks:
            await event.client.delete_messages(chat, chunk)
            await asyncio.sleep(0.5)
    else:
        await event.client.delete_messages(chat, messages)

    count = end_msg - start_msg + 1
    await event.reply(f"{sage.done()} Cleared `{count}` messages. Log purged.")


@command("pin")
async def pin_cmd(event):
    """Pin the replied message."""
    if not event.reply_to:
        return await event.reply("Reply to a message to pin it.")
    reply = await event.get_reply_message()
    await event.client.pin_message(event.chat_id, reply.id)
    await event.reply(f"{sage.ack()} Message anchored to channel top.")


@command("unpin")
async def unpin_cmd(event):
    """Unpin the replied message."""
    if not event.reply_to:
        return await event.reply("Reply to a pinned message to unpin it.")
    reply = await event.get_reply_message()
    await event.client.unpin_message(event.chat_id, reply.id)
    await event.reply(f"{sage.ack()} Anchor released.")


@command("promote")
async def promote_cmd(event):
    """Promote a user to admin (reply or user ID)."""
    target = await get_target(event)
    if not target:
        return await event.reply("Reply to a user or provide user ID.")
    try:
        await event.client.edit_admin(
            event.chat_id,
            target,
            is_admin=True,
            title="Admin",
        )
        await event.reply(f"{sage.ack()} **Promoted** — `{target}` granted elevated clearance.")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("demote")
async def demote_cmd(event):
    """Demote an admin (reply or user ID)."""
    target = await get_target(event)
    if not target:
        return await event.reply("Reply to a user or provide user ID.")
    try:
        await event.client.edit_admin(
            event.chat_id,
            target,
            is_admin=False,
        )
        await event.reply(f"{sage.ack()} **Demoted** — clearance revoked for `{target}`.")
    except Exception as e:
        await event.reply(f"Error: `{e}`")
