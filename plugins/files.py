"""XENO file handling — every command that touches a file lives here.

One store, one set of helpers, one place to look. Previously these were spread
across media.py, extras.py, tools.py and manage.py, with the download path
written out three separate times.

  .save [name]          reply to media      -> downloads/     (.download, .savefile)
  .get <name>           send a stored file back
  .ls                   list the store                    (.files)
  .delfile <name> force delete a stored file              (.rm)
  .fileinfo             metadata for replied media
  .sticker              reply to an image  -> post as a sticker
  .webshot <url>        screenshot a page  -> post it
  .json                 dump a message as JSON -> post it

Two kinds of storage:

  downloads/   persists. Reachable only by exact filename, never by path.
  temp dirs    never persist. Created per call, deleted immediately after upload.
"""
import json as _json
import mimetypes
import os
import re
import shutil
import tempfile
import time
import urllib.parse

from telethon.tl.types import DocumentAttributeFilename

from core.command import command

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The persistent store. Was duplicated in three plugins; now defined once.
STORE = os.path.join(ROOT, "downloads")

#: Ephemeral scratch. A sibling of `data/` so it survives nothing.
TMP_ROOT = os.path.join(ROOT, "data", "tmp")

#: Guard rails. Downloads fill a 45GB VPS otherwise.
MAX_SAVE_BYTES = 50 * 1024 * 1024
MAX_TEXT_BYTES = 1024 * 1024

# A filename is a name, not a path. Same rule everywhere.
VALID_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


# ============================================================ helpers
def ensure_store():
    os.makedirs(STORE, exist_ok=True)
    return STORE


def filename_error(raw, want_extension=True):
    """Return an error string, or None if the filename is acceptable."""
    name = (raw or "").strip().strip('"').strip("'")
    if not name:
        return "Give a filename."
    if "/" in name or "\\" in name or "\x00" in name:
        return "Filenames only — no `/`, `\\` or subdirectories."
    if ".." in name:
        return "No `..` in filenames."
    if name.startswith("."):
        return "Filename can't start with a dot."
    if not VALID_FILENAME.match(name):
        return "Use letters, digits, dot, dash or underscore, up to 64 characters."
    if want_extension and "." not in name:
        return None  # caller decides the default extension
    return None


def resolve(name):
    """Full path for a stored file, or None. The only way in.

    Validation happens before the join, so this cannot escape the store.
    """
    name = (name or "").strip().strip('"').strip("'")
    if filename_error(name) is not None:
        return None
    path = os.path.join(STORE, name)
    # Belt and braces: confirm the join landed inside the store.
    if os.path.commonpath([os.path.abspath(path), STORE]) != STORE:
        return None
    return path if os.path.isfile(path) else None


def unique_path(name):
    """A free path in the store, appending (1), (2)… if the name is taken."""
    ensure_store()
    base, ext = os.path.splitext(name)
    candidate = os.path.join(STORE, name)
    n = 1
    while os.path.exists(candidate):
        candidate = os.path.join(STORE, f"{base} ({n}){ext}")
        n += 1
    return candidate


def list_store(limit=60):
    """[(name, size, modified)] newest first."""
    try:
        rows = []
        for f in os.listdir(STORE):
            p = os.path.join(STORE, f)
            if os.path.isfile(p):
                st = os.stat(p)
                rows.append((f, st.st_size, time.strftime(
                    "%Y-%m-%d %H:%M", time.localtime(st.st_mtime))))
        return sorted(rows, key=lambda r: r[2], reverse=True)[:limit]
    except (FileNotFoundError, OSError):
        return []


def store_bytes():
    try:
        return sum(os.path.getsize(os.path.join(STORE, f))
                   for f in os.listdir(STORE)
                   if os.path.isfile(os.path.join(STORE, f)))
    except OSError:
        return 0


def doc_name(msg):
    for attr in getattr(getattr(msg, "document", None), "attributes", []) or []:
        if isinstance(attr, DocumentAttributeFilename):
            return attr.file_name
    return None


def default_name(msg=None, ext=".txt"):
    """Filename when the user didn't give one."""
    if msg is not None:
        src = doc_name(msg)
        if src and filename_error(src) is None:
            return src
    mime = getattr(getattr(msg, "document", None), "mime_type", None)
    if mime:
        ext = mimetypes.guess_extension(mime.split(";")[0].strip()) or ext
    return f"xeno_{time.strftime('%Y%m%d-%H%M%S')}{ext}"


def ephemeral():
    """A scratch directory that gets deleted on the way out."""
    return tempfile.mkdtemp(prefix="xeno_", dir=_ensure_tmp_root())


def _ensure_tmp_root():
    os.makedirs(TMP_ROOT, exist_ok=True)
    return TMP_ROOT


async def _deny(event, what):
    from core.auth import is_owner

    if not await is_owner(event):
        await event.reply(f"🔒 Owner only — {what}.")
        return True
    return False


def _human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


# ============================================================ the store
@command(r"save(?:\s+(\S+))?")
async def save_cmd(event):
    """Store a replied file. Usage: reply, then `.save [name]`

    Aliases: `.download`, `.savefile`
    """
    if await _deny(event, "this writes to the server"):
        return
    if not event.reply_to:
        return await event.reply("Reply to a file or photo to store it.")

    rep = await event.get_reply_message()
    if not getattr(rep, "media", None):
        return await event.reply("That message has no media.")

    size = getattr(getattr(rep, "document", None), "size", 0) or 0
    if size > MAX_SAVE_BYTES:
        return await event.reply(
            f"❌ Too big ({_human(size)}). Limit is {_human(MAX_SAVE_BYTES)}."
        )

    name = event.pattern_match.group(1)
    if name:
        err = filename_error(name)
        if err:
            return await event.reply(f"❌ {err}")
        if "." not in name:
            name += ".bin"
    else:
        name = default_name(rep)

    ensure_store()
    try:
        path = await rep.download_media(file=STORE)
        if not path:
            return await event.reply("❌ Download failed.")
        target = unique_path(name)
        if os.path.abspath(path) != os.path.abspath(target):
            os.replace(path, target)
        actual = os.path.basename(target)
        await event.reply(
            f"💾 `{actual}` stored ({_human(os.path.getsize(target))}).\n"
            f"`.get {actual}` to send it back · `.ls` to list · "
            f"`.delfile {actual} force`"
        )
    except Exception as e:
        await event.reply(f"❌ `{type(e).__name__}: {e}`")


@command(r"get\s+(\S+)")
async def get_cmd(event):
    """Send a stored file into this chat. Usage: `.get <name>`"""
    if await _deny(event, "this reads files off the server"):
        return
    name = event.pattern_match.group(1)
    path = resolve(name)
    if not path:
        rows = list_store(10)
        hint = ", ".join(r[0] for r in rows) or "store is empty"
        return await event.reply(f"❌ No stored file called `{name}`.\nAvailable: {hint}")
    try:
        await event.client.send_file(
            event.chat_id, path, force_document=True, file_name=os.path.basename(path)
        )
    except Exception as e:
        await event.reply(f"❌ `{type(e).__name__}: {e}`")


@command("ls")
async def ls_cmd(event):
    """List stored files. Usage: `.ls` — alias: `.files`"""
    if await _deny(event, "this lists files on the server"):
        return
    rows = list_store()
    if not rows:
        return await event.reply(f"**📂 Store is empty.**\n`{STORE}`")
    lines = [f"**📂 Stored files** ({len(rows)}) — {_human(store_bytes())} total\n"]
    lines += [f"• `{n}` — {_human(sz)} · {when}" for n, sz, when in rows]
    lines.append("\nSend one with `.get <name>` · delete with `.delfile <name> force`")
    await event.reply("\n".join(lines)[:3500])


# NB: no `.del` here on purpose — admin.py owns that, and it deletes the
# replied *message*. Registering it again would fire two handlers per command.


async def _do_del(event, name, force):
    path = resolve(name)
    if not path:
        return await event.reply(f"❌ No stored file called `{name}`.")
    if not force:
        size = _human(os.path.getsize(path))
        return await event.reply(
            f"`{name}` is {size}. Add `force` to delete it: "
            f"`.delfile {name} force`"
        )
    try:
        os.remove(path)
    except OSError as e:
        return await event.reply(f"❌ `{e}`")
    await event.reply(f"🗑 Deleted `{name}`.")


# ============================================================ ephemeral
@command("fileinfo")
async def fileinfo_cmd(event):
    """Technical metadata for replied media. Reply to a file or photo."""
    if not event.reply_to:
        return await event.reply("Reply to a message with media.")
    rep = await event.get_reply_message()
    if not rep.media:
        return await event.reply("No media found.")

    media = rep.media
    info = "**File Info**\n"
    leaked = False
    if hasattr(media, "document"):
        doc = media.document
        info += f"Name: `{doc_name(rep) or 'unnamed'}`\n"
        info += f"ID: `{doc.id}`\n"
        leaked = True
        info += f"Size: `{doc.size:,} bytes`\n"
        info += f"MIME: `{doc.mime_type}`\n"
        for attr in doc.attributes:
            if hasattr(attr, "duration"):
                info += f"Duration: `{attr.duration}s`\n"
            if hasattr(attr, "w"):
                info += f"Resolution: `{attr.w}x{attr.h}`\n"
    elif hasattr(media, "photo"):
        sizes = [f"{s.w}x{s.h}" for s in media.photo.sizes if hasattr(s, "w")]
        info += f"Sizes: {', '.join(sizes)}"

    if leaked:
        # A Telegram file id is a permanent handle: anyone holding it can fetch
        # the media over MTProto, so say it out loud rather than gate it.
        info += "\n\n⚠️ That file ID is permanent and re-downloadable — don't paste "
        info += "this in a chat with people you don't trust."
    await event.reply(info)


@command("sticker")
async def sticker_cmd(event):
    """Convert a replied image to a sticker and post it."""
    if not event.reply_to:
        return await event.reply("Reply to an image.")
    rep = await event.get_reply_message()
    if not rep.photo and not rep.document:
        return await event.reply("Reply to an image.")

    tmpdir = ephemeral()
    try:
        path = await rep.download_media(file=tmpdir)
        if not path:
            return await event.reply("Could not download the image.")
        await event.client.send_file(
            event.chat_id, path, force_document=False, as_sticker=True
        )
    except Exception as e:
        await event.reply(f"❌ `{type(e).__name__}: {e}`")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@command("webshot")
async def webshot_cmd(event):
    """Screenshot a webpage and post it. Usage: `.webshot <url>`"""
    a = event.text.split(maxsplit=1)
    url = a[1].strip() if len(a) > 1 else ""
    if not url:
        return await event.reply("Give a URL. Usage: `.webshot example.com`")
    if not url.startswith("http"):
        url = "https://" + url
    host = urllib.parse.urlparse(url).netloc or "example"
    tmpdir = ephemeral()
    try:
        import aiohttp

        shot = f"https://image.thum.io/get/width/1280/crop/800/noanimate/{url}"
        async with aiohttp.ClientSession() as s:
            async with s.get(shot, timeout=30) as r:
                data = await r.read()
        if len(data) < 1000:
            return await event.reply("❌ thum.io returned nothing useful.")
        path = os.path.join(tmpdir, "screenshot.png")
        with open(path, "wb") as f:
            f.write(data)
        await event.client.send_file(
            event.chat_id, path, force_document=False, file_name=f"{host}.png"
        )
    except Exception as e:
        await event.reply(f"❌ `{type(e).__name__}: {e}`")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@command("json")
async def json_cmd(event):
    """Post the raw JSON of the replied (or current) message. Usage: `.json`"""
    rep = await event.get_reply_message() if event.is_reply else event
    try:
        data = rep.to_dict() if hasattr(rep, "to_dict") else {}
        blob = _json.dumps(data, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        return await event.reply(f"❌ `{type(e).__name__}: {e}`")
    if len(blob) > 1_000_000:
        return await event.reply("❌ That's too much JSON to post.")
    tmpdir = ephemeral()
    try:
        path = os.path.join(tmpdir, "message.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(blob)
        await event.client.send_file(
            event.chat_id, path, force_document=True, file_name="message.json"
        )
    except Exception as e:
        await event.reply(f"❌ `{type(e).__name__}: {e}`")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================ aliases
# Old names keep working so nothing breaks. Each is a thin re-registration.
@command("download")
async def download_alias(event):
    """Alias of `.save`. Reply to media to store it."""
    await save_cmd(event)


@command("savefile")
async def savefile_alias(event):
    """Alias of `.save`. Reply to media to store it."""
    await save_cmd(event)


@command("files")
async def files_alias(event):
    """Alias of `.ls`. List stored files."""
    await ls_cmd(event)


@command(r"delfile\s+(\S+)(?:\s+(force))?")
async def delfile_cmd(event):
    """Delete a stored file. Usage: `.delfile <name> force` — alias: `.rm`"""
    if await _deny(event, "this deletes a file on the server"):
        return
    await _do_del(
        event,
        event.pattern_match.group(1),
        event.pattern_match.group(2) is not None,
    )


@command(r"rm\s+(\S+)(?:\s+(force))?")
async def rm_alias(event):
    """Alias of `.delfile <name> force`. Delete a stored file."""
    if await _deny(event, "this deletes a file on the server"):
        return
    await _do_del(
        event,
        event.pattern_match.group(1),
        event.pattern_match.group(2) is not None,
    )
