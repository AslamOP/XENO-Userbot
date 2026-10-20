"""XENO meta module: about, version, starter.

Ping/alive/help/count live in misc.py — the `.pingx`/`.alivex`/`.helpx`/`.cmds`
aliases here were duplicates (and `.cmds` under-counted, since it only grepped
for literal `@command(` and missed every loop-registered command).
"""
from core.command import command

# XENO is ALPHA. It runs and is tested, but it has never been run against a
# live Telegram account by anyone but its author, and the plugin surface takes
# arbitrary code. Treat the version number as a rough guide only; the maturity
# label is the honest part. See README "Status".
VERSION = "2.1.0-alpha"
CHANNEL = "alpha"
STAGE = (
    "🧪 **ALPHA** — not audited, not hardened for strangers' accounts.\n"
    "`.install` runs code as this process. Use a spare Telegram account."
)


def _version_line():
    return f"{VERSION} ({CHANNEL})"


@command("about")
async def about_cmd(event):
    """About XENO."""
    from plugins.misc import _scan_commands

    mods = _scan_commands()
    total = sum(len(i["cmds"]) for i in mods.values())
    await event.eor(
        "**🤖 XENO** — a modular Telegram userbot (Python / Telethon).\n"
        f"Version: `{_version_line()}`\n"
        f"`{len(mods)}` modules • `{total}` commands\n"
        "Prefixes: `.` `!` `#` `,`\n\n"
        "Autonomous handlers are **off by default** — see `.ambient`.\n\n"
        f"{STAGE}"
    )


@command("version")
async def version_cmd(event):
    """XENO version and maturity channel."""
    await event.eor(f"**🧩 XENO:** `{_version_line()}`\n\n{STAGE}")


@command("maturity")
async def maturity_cmd(event):
    """Maturity, known gaps, and what XENO has not been tested against.

    Named `.maturity` rather than `.status` so it doesn't shadow the
    assistant panel's `/status`.
    """
    await event.eor(
        f"**🧪 XENO status — `{_version_line()}`**\n\n"
        "**Tested:** offline suite (283 checks) on the deployment target.\n"
        "**Not tested:** live Telegram traffic, long-running sessions, "
        "multi-account use.\n\n"
        "**Known gaps, in priority order:**\n"
        "1. Plugins can read `*.session` at runtime — that file *is* your "
        "account. Only install code you trust.\n"
        "2. No module backup/restore or update rollback.\n"
        "3. One access tier (owner); no sudo/support levels.\n"
        "4. No LICENSE file.\n\n"
        "Run a userbot on a spare account until you disagree."
    )


@command("starter")
async def starter_cmd(event):
    """First-run primer."""
    await event.eor(
        "👋 **XENO online.**\n"
        "• `.help` — every module\n"
        "• `.help <module>` or `.help <command>` — detail\n"
        "• `.ambient` — see which autonomous handlers are on (all off by default)\n"
        "• `.ping` / `.alive` — liveness\n"
        "• `.maturity` — what's known-broken\n"
        f"• `{_version_line()}` — alpha, on a spare account\n"
        "Any prefix works: `.` `!` `#` `,`"
    )
