"""Misc commands: ping, help, info, alive."""
import ast
import os
import re
import time
import platform
import asyncio
from telethon import functions

import config
from core.bot import bot
from core.command import command

PLUGINS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins")

# Loop-registered command tables (dict name -> key is a command)
_LOOP_TABLES = ("_CONV", "_UNITS", "_CASES", "_HASHES", "_ENCS", "SYMS", "_TOOLS", "_IMGS", "DICE")


def _first_line(text, limit=80):
    line = (text or "").strip().split("\n")[0].strip()
    return line if len(line) <= limit else line[: limit - 1] + "…"


def _scan_commands():
    """Return {module: {"desc": str, "cmds": [(name, desc), ...]}}.

    Command names come from the LIVE handler registry (authoritative count),
    descriptions from module + command docstrings via AST.
    """
    ast_mods = _ast_descriptions()
    live = _live_commands()
    if not live:
        return ast_mods
    modules = {}
    for mod, names in live.items():
        desc_map = {n: d for n, d in ast_mods.get(mod, {}).get("cmds", [])}
        modules[mod] = {
            "desc": ast_mods.get(mod, {}).get("desc", ""),
            "cmds": sorted((n, desc_map.get(n, "")) for n in names),
        }
    return modules


def _live_commands():
    """{module: [cmd_names]} extracted from the running bot's handlers.

    Telethon stores `event.pattern` as `re.compile(src).match`, so the source is
    at `event.pattern.__self__.pattern` — e.g. `'^\\.lcm(?:\\s.+)?$'`. The old
    version ran `re.match(re.escape(prefix), src_without_caret)`, which compared
    the escaped-dot pattern against a literal backslash character and never
    matched, so this always returned {} and `.help` silently used AST data only.
    """
    result = {}
    for builder in getattr(bot, "_event_builders", []) or []:
        ev = builder[0]
        fn = builder[1]
        pat = getattr(getattr(ev, "pattern", None), "__self__", None)
        if pat is None:
            continue
        # Strip the caret and the regex escapes command() introduced.
        src = pat.pattern.lstrip("^").replace("\\", "")
        for prefix in config.PREFIXES:
            m = re.match(re.escape(prefix) + r"([^()]+)", src)
            if not m:
                continue
            mod = getattr(fn, "__module__", "?")
            if mod.startswith("plugins."):
                mod = mod.split(".", 1)[1]
            # Hand-written regexes (e.g. r"play(?:\s+(.+))?") must not surface
            # their syntax in the help index.
            result.setdefault(mod, set()).add(m.group(1).split("(")[0].rstrip("\\$"))
            break
    return {m: sorted(v) for m, v in result.items()}


def _ast_descriptions():
    """{module: {"desc": str, "cmds": [(name, desc), ...]}} via AST."""
    modules = {}
    for fname in sorted(os.listdir(PLUGINS_DIR)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        path = os.path.join(PLUGINS_DIR, fname)
        mod = fname[:-3]
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except SyntaxError:
            continue
        desc = _first_line(ast.get_docstring(tree) or "")
        cmd_map = {}  # name -> one-line doc
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "command" and dec.args:
                    if isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                        cmd_map[dec.args[0].value] = _first_line(ast.get_docstring(node) or "")
        src = open(path, encoding="utf-8").read()
        for table in _LOOP_TABLES:
            m = re.search(r"\b" + table + r"\s*=\s*\{", src)
            if not m:
                continue
            rest = src[m.end():]
            depth = 1
            body = ""
            for ch in rest:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        break
                body += ch
            for k in re.findall(r'^\s*"([^"]+)":', body, re.M):
                cmd_map.setdefault(k, "")
        if cmd_map:
            modules[mod] = {"desc": desc, "cmds": sorted(cmd_map.items())}
    return modules


MODULE_ICONS = {
    "admin": "🛡", "ai": "🤖", "animex": "🎌", "casex": "🔤", "commander": "🧭",
    "crypto": "₿", "datetimex": "🗓", "extras": "🧰", "finishx": "🏁", "fun": "😂",
    "game": "🎮", "games": "🎲", "generators": "✨", "globals": "🌍",
    "group": "👥", "hashx": "🔐", "langx": "🌐", "media": "🎬", "mediacli": "📰",
    "minitools": "🛠", "misc": "🧩", "notesx": "📝", "numconv": "🔢", "opsx": "⚙️",
    "persona": "🎭", "photofx": "🖼", "profile": "🧑‍🚀", "search": "🔎", "sysx": "💻",
    "tagx": "🏷", "textify": "✒️", "textstyle": "🎨", "tools": "🧰", "warden": "🗄",
    "words": "📖", "world": "🌏",
}


def _fmt_index(modules):
    total = sum(len(info["cmds"]) for info in modules.values())
    rule = "━" * 30
    top = (
        f"⚡ **XENO** — _the ultimate command skill_ ⚡\n"
        f"{rule}\n"
        f"**{total}** commands • **{len(modules)}** modules\n"
        f"Prefixes: `{' '.join(config.PREFIXES)}`"
    )
    lines = []
    for mod, info in modules.items():
        n = len(info["cmds"])
        lines.append(
            f"{MODULE_ICONS.get(mod, '▫')} **{mod}** — _{n} cmds_"
            + (f"\n   {info['desc']}" if info["desc"] else "")
        )
    body = "\n".join(lines)
    footer = (
        f"{rule}\n"
        f"💡 **Explore:** `.help <module>`  e.g. `.help textify`\n"
        f"🔍 **Search:** `.help <command>`  e.g. `.help ban`\n"
        f"🧯 **Ambient:** `.ambient` — autonomous handlers, all off by default"
    )
    return f"{top}\n\n{body}\n{footer}"


@command("help")
async def help_cmd(event):
    """Interactive help: `.help`, `.help <module>` or `.help <command>`."""
    modules = _scan_commands()
    a = event.text.split(maxsplit=1)
    target = (a[1].strip() if len(a) > 1 else "").strip(".")
    if not target:
        return await event.reply(_fmt_index(modules))
    # Allow searching by command name across all modules
    if target not in modules:
        hits = [
            m for m, info in modules.items()
            if any(c[0] == target for c in info["cmds"])
        ]
        if hits:
            mod = hits[0]
            # Was: `_, d = next(c for c, _ in ...)` — that unpacks the command
            # NAME (a str) into two vars and raised on every `.help <command>`.
            name, desc = next(c for c in modules[mod]["cmds"] if c[0] == target)
            return await event.reply(
                f"🔍 **`{target}`** — in module `{mod}`\n"
                + (f"{desc}\n" if desc else "")
                + f"\nTry `.help {mod}` for the full module.")
        return await event.reply(_fmt_index(modules) + f"\n\n⚠️ No module or command named `{target}`.")
    info = modules[target]
    icon = MODULE_ICONS.get(target, "▫")
    rule = "━" * 30
    header = (
        f"{icon} **{target.upper()}**  —  `{len(info['cmds'])}` commands\n"
        f"{rule}"
    )
    if info["desc"]:
        header += f"\n{info['desc']}"
    lines = []
    for cname, d in info["cmds"]:
        lines.append(f"`{cname}`" + (f" — {d}" if d else ""))
    body = "\n".join(lines)
    return await event.reply(
        f"{header}\n\n{body}\n\n📌 Prefixes: `.name` `!name` `#name`")


@command("ping")
async def ping_cmd(event):
    """Check bot latency / responsiveness."""
    start = time.monotonic()
    msg = await event.reply("Pinging...")
    elapsed = (time.monotonic() - start) * 1000
    verdict = "within acceptable parameters." if elapsed < 250 else "marginal. recalibrating route."
    await msg.edit(f"Latency: `{elapsed:.1f}ms` — {verdict}")


@command("alive")
async def alive_cmd(event):
    """Show uptime, Python version and prefixes."""
    uptime = int(time.time() - config.BOT_START_TIME)
    m, s = divmod(uptime, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    text = (
        f"**XENO operational.** All processes nominal.\n"
        f"Uptime: `{d}d {h}h {m}m {s}s`\n"
        f"Runtime: `Python {platform.python_version()}`\n"
        f"Prefixes: `{' '.join(config.PREFIXES)}`"
    )
    await event.reply(text)


@command("info")
async def info_cmd(event):
    """Your Telegram profile info (name, ID, username)."""
    user = await event.get_sender()
    text = (
        f"**Your Info**\n"
        f"Name: `{user.first_name}` {user.last_name or ''}\n"
        f"ID: `{user.id}`\n"
        f"Username: @{user.username or 'none'}\n"
        f"Premium: `{user.premium or False}`"
    )
    await event.reply(text)


@command("myid")
async def myid_cmd(event):
    """Your user ID and this chat's ID."""
    await event.reply(f"Your ID: `{event.sender_id}`\nChat ID: `{event.chat_id}`")


HACK_PHASES = [
    "⚠️ Initializing H4CK-T00L v9.9.9 ...",
    "[1/6] Scanning network for {target} ... found",
    "[2/6] Bypassing firewall ........ 40%",
    "[3/6] Cracking hash ............. 100%",
    "[4/6] Injecting payload ...",
    "[5/6] Downloading data .......... 104.2 MB",
    "[6/6] Erasing traces ... OK",
    "✅ ACCESS GRANTED: {target}",
    "…just kidding 😉 nothing was actually hacked.",
]


@command(r"hack(?:\s+(.+))?")
async def hack_cmd(event):
    """Fake hack animation (reply or give a name)."""
    if event.sender_id != config.OWNER_ID:
        return
    target = (event.pattern_match.group(1) or "").strip()
    reply = None
    if event.is_reply:
        reply = await event.get_reply_message()
    if not target:
        if reply:
            target = " ".join((reply.sender.first_name or "user").split())
        else:
            return await event.reply("Usage: `.hack <username>` (or reply to someone)")
    msg = await event.reply(HACK_PHASES[0].format(target=target))
    for phase in HACK_PHASES[1:]:
        await asyncio.sleep(1.2)
        try:
            await msg.edit(phase.format(target=target))
        except Exception:
            break
    await asyncio.sleep(2.5)
    try:
        await msg.delete()
    except Exception:
        pass
