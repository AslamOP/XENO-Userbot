"""Plugin management.

    .addplugin         reply to a .py    -> temporary (this run only)
    .delplugin <name>                      remove a temporary one
    .install [f]       reply to a .py    -> addons/, survives restarts
    .uninstall <name>                      delete an installed one
    .load <name>                           re-enable an installed one
    .unload <name>                         disable one, keeping the file
    .plugins                            -> list all three groups

File handling (.save/.get/.ls/.delfile/.fileinfo/.sticker/.webshot/.json)
lives in files.py.

⚠️ `.addplugin` and `.install` run code as this process. Whoever can send them
owns the VPS — treat any .py you receive like a shell script. Both are
owner-only, and built-in modules can't be replaced either way.

`.install` scans the source for dangerous patterns first and refuses to touch
the server if any trip, unless you pass `f` to force it. That scan is a
static regex pass, NOT a sandbox — it catches accidents, not attackers.
"""
import shutil
import tempfile

from telethon.tl.types import DocumentAttributeFilename

from core import custom, safety
from core.command import command


async def _deny(event, what):
    from core.auth import is_owner

    if not await is_owner(event):
        await event.reply(f"🔒 Owner only — {what}.")
        return True
    return False


def _doc_name(rep):
    for attr in getattr(rep.document, "attributes", []) or []:
        if isinstance(attr, DocumentAttributeFilename):
            return attr.file_name
    return None


async def _read_source(event, err_prefix="❌"):
    """Pull a .py document out of the replied message and validate it.

    Returns (name, source, error_message). Exactly one of the first two is set.
    """
    if not event.reply_to:
        return None, None, f"{err_prefix} Reply to a `.py` file."
    rep = await event.get_reply_message()
    if not getattr(rep, "document", None):
        return None, None, f"{err_prefix} That's not a file. Reply to a `.py` document."

    filename = _doc_name(rep)
    if not filename:
        return None, None, f"{err_prefix} No filename on that upload — save it as something.py."

    name, err = custom.validate_name(filename)
    if err:
        return None, None, f"{err_prefix} {err}"

    if rep.document.size > custom.MAX_PLUGIN_BYTES:
        return None, None, (
            f"{err_prefix} Too big ({rep.document.size // 1024}KB, "
            f"limit {custom.MAX_PLUGIN_BYTES // 1024}KB)."
        )

    tmp = tempfile.mkdtemp(prefix="xeno_add_")
    try:
        path = await rep.download_media(file=tmp)
        if not path:
            return None, None, f"{err_prefix} Download failed."
        with open(path, encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception as e:
        return None, None, f"{err_prefix} Download failed: `{e}`"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    err = custom.validate_source(source, name)
    if err:
        return None, None, f"{err_prefix} Not valid Python — nothing installed.\n`{err}`"
    return name, source, None


# ---------------------------------------------------------------- temporary
@command("addplugin")
async def addplugin_cmd(event):
    """Install a plugin for this run only. Usage: reply to a .py with `.addplugin`

    Gone after a restart — use `.install` to keep it.
    """
    if await _deny(event, "this installs code on the server"):
        return

    name, source, err = await _read_source(event)
    if err:
        return await event.reply(err)

    replacing = name in custom.temp_list()
    ok, msg = custom.temp_install(name, source, origin=f"msg {event.id}")
    if not ok:
        return await event.reply(f"❌ {msg}")

    kind = "Updated" if replacing else "Added"
    await event.reply(
        f"⚡ **{kind}** `{name}.py` — {msg}, live now.\n"
        f"Session-only: a restart deletes it. `.install` to make it permanent.\n"
        f"`.delplugin {name}` to drop it sooner."
    )


@command("delplugin")
async def delplugin_cmd(event):
    """Remove a temporary plugin. Usage: `.delplugin <name>`"""
    if await _deny(event, "this modifies the running process"):
        return
    a = event.text.split(maxsplit=1)
    if len(a) < 2:
        names = ", ".join(sorted(custom.temp_list())) or "none"
        return await event.reply(f"Usage: `.delplugin <name>`\nTemporary: {names}")
    name = a[1].strip().lstrip("./").removesuffix(".py")
    ok, msg = custom.temp_remove(name)
    await event.reply(("🗑 " if ok else "❌ ") + msg)


# ---------------------------------------------------------------- persistent
@command(r"install\s*(f)?")
async def install_cmd(event):
    """Install a plugin into addons/. Usage: reply to a .py with `.install`

    Survives restarts. `.uninstall <name>` deletes it, `.unload <name>` just
    switches it off and keeps the file.

    If the source trips the dangerous-pattern scan the install is refused and
    nothing is written. Pass `.install f` to force it anyway.
    """
    if await _deny(event, "this installs code on the server"):
        return

    m = getattr(event, "pattern_match", None)
    force = bool(m.group(1)) if m else False

    name, source, err = await _read_source(event)
    if err:
        return await event.reply(err)

    if custom.is_protected(name):
        return await event.reply(
            f"❌ `{name}` is a built-in XENO module. Rename your file."
        )

    hits = safety.scan(source)
    if hits and not force:
        return await event.reply(safety.report(hits, f"{name}.py"))

    replacing = custom.is_custom(name)
    ok, msg = custom.install(name, source, origin=f"msg {event.id}")
    if not ok:
        return await event.reply(f"❌ {msg}")

    if hits and force:
        warn = (
            f"\n\n⚠️ Forced past {len(hits)} scan hit(s): "
            + ", ".join(f"`{h[0]}`" for h in hits)
        )
    else:
        warn = ""

    kind = "Updated" if replacing else "Installed"
    await event.reply(
        f"💾 **{kind}** `addons/{name}.py` — {msg}.\n"
        f"Survives restarts · `.unload {name}` to switch off · "
        f"`.uninstall {name}` to delete{warn}"
    )


@command("uninstall")
async def uninstall_cmd(event):
    """Delete an installed plugin and its file. Usage: `.uninstall <name>`"""
    if await _deny(event, "this deletes a file on the server"):
        return
    a = event.text.split(maxsplit=1)
    if len(a) < 2:
        names = ", ".join(sorted(custom.list_custom())) or "none"
        return await event.reply(f"Usage: `.uninstall <name>`\nInstalled: {names}")
    name = a[1].strip().lstrip("./").removesuffix(".py")
    ok, msg = custom.remove(name)
    await event.reply(("🗑 " if ok else "❌ ") + msg)


# ---------------------------------------------------- load / unload a toggle
@command(r"load\s+(\S+)")
async def load_cmd(event):
    """Switch an installed addon back on. Usage: `.load <name>`"""
    if await _deny(event, "this modifies the running process"):
        return
    name = event.pattern_match.group(1).strip().lstrip("./").removesuffix(".py")
    if not custom.is_custom(name):
        return await event.reply(
            f"❌ No installed addon called `{name}`. `.plugins` to list them."
        )
    custom.set_disabled(name, False)
    ok, msg = custom.load(name)
    if not ok:
        return await event.reply(f"❌ Still disabled — {msg}")
    await event.reply(f"▶️ **`{name}` loaded** — {msg}. It stays on across restarts.")


@command(r"unload\s+(\S+)")
async def unload_cmd(event):
    """Disable an installed addon but keep the file. Usage: `.unload <name>`"""
    if await _deny(event, "this modifies the running process"):
        return
    name = event.pattern_match.group(1).strip().lstrip("./").removesuffix(".py")
    if custom.is_protected(name) and not custom.is_custom(name):
        return await event.reply(
            f"❌ `{name}` is a built-in module — you can't unload it from chat."
        )
    if not custom.is_custom(name):
        return await event.reply(
            f"❌ No installed addon called `{name}`. `.plugins` to list them."
        )
    n = custom.unload(name)
    custom.set_disabled(name, True)
    await event.reply(
        f"⏸️ **`{name}` unloaded** — {n} command(s) removed.\n"
        f"The file is still in `addons/`, so you can read it or `.load {name}` "
        f"to bring it back."
    )


# ---------------------------------------------------------------- listing
@command("plugins")
async def plugins_cmd(event):
    """List temporary, persistent, and built-in modules."""
    if await _deny(event, "this lists what the process is running"):
        return

    tmp = custom.temp_list()
    perm = custom.list_custom()
    lines = []

    if tmp:
        lines.append(f"**⚡ Temporary ({len(tmp)})** — gone on restart\n")
        for n, m in sorted(tmp.items()):
            lines.append(f"• `{n}` — {m.get('bytes', 0)}B `{m.get('sha256', '')[:8]}`")
        lines.append("\n🗑 `.delplugin <name>`")
    else:
        lines.append("**⚡ Temporary:** none. Reply to a `.py` with `.addplugin`.")

    lines.append("")
    if perm:
        lines.append(f"**💾 Installed addons ({len(perm)})** — `addons/`, survives restarts\n")
        for n, m in sorted(perm.items()):
            state = "⏸️ unloaded" if custom.is_disabled(n) else "▶️ active"
            lines.append(
                f"• `{n}` — {state} · {m.get('bytes', 0)}B "
                f"`{m.get('sha256', '')[:8]}` · {m.get('added', '?')}"
            )
        lines.append("\n`.unload <name>` to disable · `.uninstall <name>` to delete")
    else:
        lines.append(
            "**💾 Installed addons:** none. Reply to a `.py` with `.install`."
        )

    officials = custom.official_modules()
    lines.append("")
    lines.append(f"**Built-in modules ({len(officials)})**")
    lines.append(" ".join(f"`{m}`" for m in officials) if officials else "(none)")
    lines.append(
        "\n_Built-ins can't be removed here — delete the file on the server for that._"
    )
    await event.reply("\n".join(lines)[:4000])
