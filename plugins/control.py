"""XENO control panel — commands reachable by DMing the assistant bot.

Owner-only by default (`asst_cmd(..., owner=True)`), private-only for anything
that touches the host, and deliberately does NOT expose `.evalx` / `.execx`:
putting arbitrary Python behind a bot DM is remote code execution with an extra
hop. Use those from the userbot client, where outgoing=True already proves
you're the one typing.
"""
import asyncio
import os
import sys
import time

from telethon import Button

import config
from core import assistant as assistant_mod
from core.auth import AMBIENT_FEATURES, ambient_enabled, set_ambient
from core.command import asst_callback, asst_cmd
from core.db import get as db_get
from core.db import set_ as db_set
from core.plugin_loader import PLUGINS_DIR

# Keys safe to read/write from the panel.
PANEL_KEYS = {
    "PREFIXES": "Command prefixes for the userbot client",
    "AI_MODEL": "Model used by .ai / game agent",
    "AI_AUTO_REPLY": "Auto-reply to inbound DMs (true/false)",
    "AI_ALLOWED_IDS": "Allowlist for auto-reply, blank = anyone",
    "BOT_NAME": "Name the persona speaks as",
    "PERSONA": "System prompt for the AI",
    "THEME": "Reply accent (see core/sage.py THEMES)",
}
# OWNER_ID is deliberately NOT here. Writing it from the panel has no way back:
# a typo locks you out of the panel AND every owner-gated command, and the bad
# value persists. Change it in .env.

# Deliberately absent: any eval/exec/execjs, anything touching secrets, anything
# that sends to arbitrary chats.

PANEL_PREFIX = config.ASSISTANT_PREFIX


def _panel_here():
    return f"`{PANEL_PREFIX}"


@asst_cmd("start")
async def panel_start(event):
    """Control panel home."""
    me = await event.client.get_me()
    up = int(time.time() - config.BOT_START_TIME) if config.BOT_START_TIME else 0
    h, m = divmod(up // 60, 60)
    d, h = divmod(h, 24)
    lines = [
        f"**XENO control panel** — @{me.username}",
        f"Owner: `{config.OWNER_ID}`",
        f"Userbot uptime: `{d}d {h}h {m}m`",
        "",
        "**Configuration**",
        f"{_panel_here()}config` — list settings",
        f"{_panel_here()}get <key>` — read one",
        f"{_panel_here()}set <key> <value>` — write one",
        f"{_panel_here()}ambient` — autonomous handlers (all off by default)",
        f"{_panel_here()}setambient <feature> on|off [everywhere]",
        "",
        "**Diagnostics**",
        f"{_panel_here()}status` — clients, uptime, handler count",
        f"{_panel_here()}modules` — loaded plugins",
        f"{_panel_here()}commands [module]` — live command index",
        f"{_panel_here()}logs [n]` — last log lines",
        "",
        "**Danger zone**",
        f"{_panel_here()}restart` — restart the process",
        "",
        "_Run these in any chat on the userbot account instead: `.evalx`, "
        "`.execx`, `.srestart`, `.broadcast`, `.setpic`._",
    ]
    await event.reply("\n".join(lines), buttons=[
        [Button.inline("Status", data="xeno_status"), Button.inline("Ambient", data="xeno_ambient")],
        [Button.inline("Modules", data="xeno_modules"), Button.inline("Config", data="xeno_config")],
        [Button.inline("Logs", data="xeno_logs")],
    ])


@asst_callback("xeno_status")
async def panel_status_button(event):
    await event.answer("Refreshing…")
    return await status_cmd(event)


@asst_callback("xeno_ambient")
async def panel_ambient_button(event):
    await event.answer()
    return await ambient_cmd(event)


@asst_callback("xeno_modules")
async def panel_modules_button(event):
    await event.answer()
    return await modules_cmd(event)


@asst_callback("xeno_config")
async def panel_config_button(event):
    await event.answer()
    return await config_cmd(event)


@asst_callback("xeno_logs")
async def panel_logs_button(event):
    await event.answer()
    return await logs_cmd(event)


@asst_cmd("status")
async def status_cmd(event):
    """Clients, uptime, handler count."""
    from core.bot import bot

    user_up = int(time.time() - config.BOT_START_TIME) if config.BOT_START_TIME else 0
    asst_up = (
        int(time.time() - config.ASSISTANT_START_TIME) if config.ASSISTANT_START_TIME else 0
    )
    try:
        ume = await bot.get_me()
        user_line = f"@{ume.username} (id `{ume.id}`)"
    except Exception:
        user_line = "unknown"
    handlers = len(getattr(bot, "_event_builders", []) or [])
    ahandlers = len(getattr(assistant_mod.asst, "_event_builders", []) or []) if assistant_mod.asst else 0

    def fmt(s):
        d, r = divmod(s, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        return f"{d}d {h}h {m}m {s}s"

    lines = [
        "**XENO status**",
        f"Userbot: `{user_line}` — up `{fmt(user_up)}`",
        f"  handlers: `{handlers}`",
        f"Assistant: `{assistant_mod.status}`",
    ]
    if assistant_mod.asst:
        lines.append(f"  up `{fmt(asst_up)}` · handlers: `{ahandlers}`")
    lines.append(f"Prefixes: `{' '.join(config.PREFIXES)}`   Panel: `{PANEL_PREFIX}`")
    lines.append(f"Plugins: `{len([f for f in os.listdir(PLUGINS_DIR) if f.endswith('.py') and not f.startswith('_')])}` files")
    on = [f for f in AMBIENT_FEATURES if await ambient_enabled(f, event.chat_id)]
    lines.append(f"Autonomous handlers: `{', '.join(on) if on else 'none'}`")
    await event.reply("\n".join(lines))


@asst_cmd("config")
async def config_cmd(event):
    """List the settings you can change from the panel."""
    lines = ["**Configurable keys**", ""]
    for k, desc in PANEL_KEYS.items():
        cur = await db_get(k, getattr(config, k, config.get(k, "")))
        lines.append(f"`{k}` — {desc}\n   now: `{cur}`")
    await event.reply("\n".join(lines))


@asst_cmd(r"get\s+(\w+)")
async def get_cmd(event):
    """Read one setting. Usage: `/get PREFIXES`"""
    key = event.pattern_match.group(1).upper()
    if key not in PANEL_KEYS:
        return await event.reply(f"`{key}` isn't a panel key. Use `{PANEL_PREFIX}config`.")
    cur = await db_get(key, getattr(config, key, config.get(key, "")))
    await event.reply(f"`{key}` = `{cur}`")


@asst_cmd(r"set\s+(\w+)\s+(.+)", private_only=True)
async def set_cmd(event):
    """Write one setting. Usage: `/set PREFIXES .!,!`"""
    key = event.pattern_match.group(1).upper()
    val = event.pattern_match.group(2).strip()
    if key not in PANEL_KEYS:
        return await event.reply(
            f"`{key}` isn't a panel key. Use `{PANEL_PREFIX}config` for the list."
        )
    if key == "PREFIXES":
        parts = [p for p in val.split() if p]
        if not parts or any(len(p) != 1 for p in parts):
            return await event.reply("Prefixes must be single characters, space separated: `. ! ,`")
        val = ",".join(parts)
    if key == "AI_AUTO_REPLY":
        val = str(val).lower() in ("1", "true", "yes", "on")
    if key in ("AI_MODEL", "BOT_NAME", "PERSONA", "THEME", "AI_ALLOWED_IDS"):
        # Live-apply the ones that are read at runtime.
        if key == "AI_MODEL":
            config.AI_MODEL = val
        elif key == "BOT_NAME":
            config.BOT_NAME = val
        elif key == "PERSONA":
            config.PERSONA = val
        elif key == "AI_ALLOWED_IDS":
            config.AI_ALLOWED_IDS = val
        else:
            await db_set("theme:current", val)
    if key == "PREFIXES":
        # Handlers were bound to the old prefixes when the plugins were
        # imported, so mutating config.PREFIXES here only changes what .help
        # *claims* — worse than not applying it at all. Persist for next boot.
        await db_set(key, val)
        return await event.reply(
            f"✅ `{key}` saved as `{val}`.\n"
            f"⚠️ Takes effect after a restart — the live handlers are still bound "
            f"to `{' '.join(config.PREFIXES)}`."
        )
    await db_set(key, val)
    await event.reply(f"✅ `{key}` = `{val}`")


@asst_cmd("ambient")
async def ambient_cmd(event):
    """Show the state of every autonomous handler."""
    lines = ["**Autonomous handlers** — these act on *other people's* messages."]
    for feat in AMBIENT_FEATURES:
        on = await ambient_enabled(feat, event.chat_id)
        lines.append(f"{'🟢' if on else '⚪️'} `{feat}` — {AMBIENT_FEATURES[feat]}")
    lines.append("")
    lines.append(f"Toggle here: `{PANEL_PREFIX}setambient <feature> on|off`")
    lines.append(f"Everywhere:   `{PANEL_PREFIX}setambient <feature> on|off everywhere`")
    await event.reply("\n".join(lines))


# Distinct name on purpose: sharing "ambient" with the lister above meant
# `/ambient x on` matched BOTH handlers and printed the list and the receipt.
@asst_cmd(r"setambient\s+(\w+)\s+(on|off)(\s+(everywhere))?")
async def ambient_toggle(event):
    """Toggle an autonomous handler for this chat, or everywhere."""
    feat = event.pattern_match.group(1).lower()
    on = event.pattern_match.group(2) == "on"
    everywhere = bool(event.pattern_match.group(4))
    if feat not in AMBIENT_FEATURES:
        return await event.reply(f"Unknown feature. Pick: `{'`, `'.join(AMBIENT_FEATURES)}`")
    await set_ambient(feat, on, None if everywhere else event.chat_id)
    scope = "everywhere" if everywhere else "this chat"
    await event.reply(f"🧯 `{feat}` turned **{'on' if on else 'off'}** ({scope}).")


@asst_cmd("modules")
async def modules_cmd(event):
    """List loaded plugin modules and their command counts."""
    from plugins.misc import _scan_commands

    mods = _scan_commands()
    rows = []
    for mod, info in sorted(mods.items(), key=lambda kv: -len(kv[1]["cmds"])):
        desc = (info["desc"] or "").split(".")[0][:58]
        rows.append(f"`{mod}` — {len(info['cmds'])} cmds · {desc}")
    total = sum(len(i["cmds"]) for i in mods.values())
    await event.reply(
        f"**{len(mods)} modules · {total} commands**\n" + "\n".join(rows),
    )


@asst_cmd(r"commands\s+(\w+)?")
async def commands_cmd(event):
    """Live command index, same source as `.help`."""
    from plugins.misc import _scan_commands

    mods = _scan_commands()
    target = (event.pattern_match.group(1) or "").lower()
    if not target:
        rows = "\n".join(
            f"`{m}` — {len(i['cmds'])}" for m, i in sorted(mods.items())
        )
        return await event.reply(f"**{len(mods)} modules**\n{rows}")
    info = mods.get(target)
    if not info:
        return await event.reply(f"No module `{target}`. Use `{PANEL_PREFIX}commands`.")
    body = "\n".join(f"`{c}`" + (f" — {d}" if d else "") for c, d in info["cmds"])
    await event.reply(f"**{target.upper()}** — {len(info['cmds'])} commands\n{body[:3500]}")


@asst_cmd(r"logs\s*(\d+)?", private_only=True)
async def logs_cmd(event):
    """Last N lines of the local log. Usage: `/logs 40`"""
    n = min(int(event.pattern_match.group(1) or 30), 200)
    from core.bot import LOG_FILE

    path = LOG_FILE
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            tail = "".join(f.readlines()[-n:])
    except FileNotFoundError:
        return await event.reply(
            f"No log file yet at `{path}`. It appears once XENO has been running."
        )
    except OSError as e:
        return await event.reply(f"Could not read the log: `{e}`")
    if not tail.strip():
        return await event.reply("Log is empty.")
    await event.reply(f"**xeno.log (last {n})**\n`{tail[-3500:]}`")


@asst_cmd("restart", private_only=True)
async def restart_cmd(event):
    """Restart the XENO process."""
    await event.reply("♻️ Restarting in a moment — this is the last message from me.")

    # Give the reply time to actually leave Telegram. Without this the process
    # is replaced before the message is flushed and it is silently lost.
    await asyncio.sleep(2)

    # Close the SQLite session files first, otherwise the re-exec'd process can
    # hit "database is locked" on userbot_session / userbot_session_assistant.
    from core import assistant as assistant_mod
    from core.bot import bot

    for client in (assistant_mod.asst, bot):
        if client is None:
            continue
        try:
            await client.disconnect()
        except Exception:
            pass

    sys.stdout.flush()
    sys.stderr.flush()

    # Absolute path: execl replaces the image, so a relative "main.py" breaks
    # whenever the cwd isn't the project root (e.g. `python -m main`).
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(root, "main.py")
    os.execl(sys.executable, sys.executable, script)
