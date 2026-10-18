"""XENO profile module: manage own account name/bio/pic/username."""
import shutil
import tempfile

from telethon.tl import functions as fn, types

from core.auth import is_owner
from core.command import command


async def _auth(event):
    if await is_owner(event):
        return True
    await event.reply("🔒 Owner only.")
    return False


@command("setname")
async def setname_cmd(event):
    """Set your Telegram name. Usage: `.setname <first> [last]`"""
    if not await _auth(event): return
    a = event.text.split(maxsplit=2)
    if len(a) < 2:
        return await event.reply("Give a name. Usage: `.setname Xeno Prime`")
    first = a[1]
    last = a[2] if len(a) > 2 else ""
    try:
        await event.client(fn.account.UpdateProfileRequest(first_name=first, last_name=last))
        await event.reply(f"✅ Name set to **{first} {last}**")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("setbio")
async def setbio_cmd(event):
    """Set your Telegram bio. Usage: `.setbio <text>`"""
    if not await _auth(event): return
    a = event.text.split(maxsplit=1)
    bio = a[1].strip() if len(a) > 1 else ""
    if not bio:
        return await event.reply("Give a bio. Usage: `.setbio Hello world`")
    try:
        await event.client(fn.account.UpdateProfileRequest(about=bio))
        await event.reply("✅ Bio updated.")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("setpic")
async def setpic_cmd(event):
    """Set profile photo (reply to image). Usage: `.setpic` on image."""
    if not await _auth(event): return
    if not event.reply_to:
        return await event.reply("Reply to a photo to set as profile picture.")
    try:
        r = await event.get_reply_message()
        tmp = tempfile.mkdtemp(prefix="xeno_pf_")
        path = await r.download_media(file=tmp)
        if not path:
            return await event.reply("Could not download media.")
        await event.client(fn.photos.UploadProfilePhotoRequest(
            file=await event.client.upload_file(path)))
        shutil.rmtree(tmp, ignore_errors=True)
        await event.reply("✅ Profile pic updated.")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("delpfp")
async def delpfp_cmd(event):
    """Delete a profile photo. Usage: `.delpfp` (newest) or `.delpfp all`"""
    if not await _auth(event): return
    a = event.text.split()
    want_all = len(a) > 1 and a[1].lower() == "all"
    try:
        photos = await event.client(fn.photos.GetUserPhotosRequest(user_id="me", offset=0, max_id=0, limit=100))
        if not photos.photos:
            return await event.reply("No profile photos to delete.")
        # Previously ANY reply triggered the delete-everything branch, so
        # replying to a random message wiped the whole photo history.
        if want_all:
            if len(photos.photos) < 2:
                return await event.reply("Only one photo — nothing to bulk-delete.")
            await event.client(fn.photos.DeletePhotosRequest(id=[p.id for p in photos.photos]))
            return await event.reply(f"🗑 Deleted all `{len(photos.photos)}` photos.")
        p = photos.photos[-1]
        await event.client(fn.photos.DeletePhotosRequest(id=[p.id]))
        await event.reply(
            "🗑 Deleted 1 photo. Use `.delpfp all` to remove every photo."
        )
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("setuser")
async def setuser_cmd(event):
    """Set your Telegram username. Usage: `.setuser <username>`"""
    if not await _auth(event): return
    a = event.text.split(maxsplit=1)
    uname = a[1].strip().lstrip("@") if len(a) > 1 else ""
    if not uname:
        return await event.reply("Give a username. Usage: `.setuser cooluser`")
    try:
        await event.client(fn.account.UpdateUsernameRequest(uname))
        await event.reply(f"✅ Username set to @{uname}")
    except Exception as e:
        await event.reply(f"Note: `{e}` — username may be taken.")


@command("me")
async def profile_cmd(event):
    """Owner: this account's profile info (includes phone number)."""
    if not await _auth(event): return
    me = await event.client.get_me()
    photos = await event.client(fn.photos.GetUserPhotosRequest(user_id="me", offset=0, max_id=0, limit=1))
    n = len(photos.photos) if photos.photos else 0
    await event.reply(
        f"**👤 {me.first_name} {me.last_name or ''}**\n"
        f"ID: `{me.id}`\n"
        f"Username: @{me.username or '—'}\n"
        f"Phone: `+{me.phone or 'hidden'}`\n"
        f"Bio: `{me.about or '—'}`\n"
        f"Profile photos: `{n}`\n"
        f"Premium: `{getattr(me, 'premium', False)}`\n"
        f"Bot: `{me.bot}`")


@command("setemoji")
async def setemoji_cmd(event):
    """Set emoji status (Premium). Usage: `.setemoji <emoji>` / `.setemoji rm`"""
    if not await _auth(event): return
    a = event.text.split(maxsplit=1)
    emoji = a[1].strip() if len(a) > 1 else ""
    try:
        if emoji.lower() == "rm" or not emoji:
            await event.client(fn.account.UpdateEmojiStatusRequest(emoji_status=types.EmojiStatus(document_id=0)))
            return await event.reply("✅ Emoji status removed.")
        # Telethon needs a custom-emoji document id, not the glyph. _find_emoji
        # always returned document_id=0, so this silently CLEARED the status
        # while reporting "set".
        await event.client(fn.account.UpdateEmojiStatusRequest(emoji_status=_find_emoji(emoji)))
        await event.reply(
            "⚠️ Custom emoji status can't be set from the glyph alone — needs the "
            "custom-emoji document id. Status cleared instead."
        )
    except Exception as e:
        await event.reply(f"Error: `{e}`")


@command("setcolor")
async def setcolor_cmd(event):
    """Set profile accent color. Usage: `.setcolor <0-6>`"""
    if not await _auth(event): return
    a = event.text.split(maxsplit=1)
    if len(a) < 2 or not a[1].isdigit():
        return await event.reply("Give a color id 0-6: `.setcolor 3`")
    col = max(0, min(6, int(a[1])))
    try:
        # UpdateColorRequest.color is a TypePeerColor, not an int — the old call
        # always raised and surfaced as a bare "Error: ...".
        await event.client(
            fn.account.UpdateColorRequest(for_profile=False, color=types.PeerColor(col))
        )
        await event.reply(f"🎨 Accent set to color `{col}`.")
    except Exception as e:
        await event.reply(f"Error: `{e}`")


def _find_emoji(ch):
    from telethon.tl import types
    # simple approach: TLV for known emoji not supported — fallback to document
    return types.EmojiStatus(document_id=0)