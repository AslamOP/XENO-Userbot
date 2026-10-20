"""XENO runtime config — .set/.get/.config/.unset on the userbot client.

The assistant panel's /set /get /config, mirrored for the account itself:
same keys, same validation, live-applied where the value is read at runtime.
Shared logic lives in core/panelcfg.py so the two clients can't drift.
"""
from core import sage
from core.command import command
from core.db import delete as db_delete
from core.db import set_ as db_set
from core.panelcfg import DEFAULTS, LIVE_APPLIED, PANEL_KEYS, apply_key, coerce
from core.panelcfg import current as _current

# Re-export for tests / other importers that historically read these here.
__all__ = ["PANEL_KEYS", "apply_key", "apply_persisted"]


async def apply_persisted():
    from core.panelcfg import apply_persisted as _ap

    return await _ap()


@command("set")
async def set_cmd(event):
    """Write one config key. Usage: `.set PREFIXES . !`"""
    parts = event.text.split(maxsplit=2)
    if len(parts) < 3:
        return await event.eor(sage.err("`set KEY VALUE`"))
    key = parts[1].upper()
    ok, msg, val = await apply_key(key, parts[2].strip())
    if not ok:
        return await event.eor(sage.err(msg))
    await db_set(key, val)
    if key == "PREFIXES":
        bound = " ".join(DEFAULTS["PREFIXES"])
        return await event.eor(
            f"{sage.done(f'{key}={val}')}\n"
            "⚠️ Takes effect after a restart — Telethon binds command "
            f"handlers to the prefix at load time (was `{bound}`)."
        )
    await event.eor(sage.done(f"{key}={val}"))


@command("get")
async def get_cmd(event):
    """Read one config key. Usage: `.get THEME`"""
    parts = event.text.split(maxsplit=1)
    if len(parts) < 2:
        return await event.eor(sage.err("`get KEY`"))
    key = parts[1].strip().upper()
    if key not in PANEL_KEYS:
        return await event.eor(sage.err(f"config key `{key}`"))
    await event.eor(f"`{key}` = `{await _current(key)}`")


@command("config")
async def config_cmd(event):
    """List config keys and current values. Usage: `.config`"""
    lines = ["**Configurable keys**", ""]
    for k, desc in PANEL_KEYS.items():
        lines.append(f"`{k}` — {desc}\n   now: `{await _current(k)}`")
    await event.eor("\n".join(lines))


@command("unset")
async def unset_cmd(event):
    """Reset a config key to its default. Usage: `.unset THEME`"""
    parts = event.text.split(maxsplit=1)
    if len(parts) < 2:
        return await event.eor(sage.err("`unset KEY`"))
    key = parts[1].strip().upper()
    if key not in PANEL_KEYS:
        return await event.eor(sage.err(f"config key `{key}`"))
    await db_delete(key)
    if key in LIVE_APPLIED:
        import config

        setattr(config, key, coerce(key, DEFAULTS[key]))
    if key == "THEME":
        # The live accent is stored under db key "theme:current", not THEME.
        await db_delete("theme:current")
        sage.set_theme(sage.DEFAULT_THEME)
    default = DEFAULTS["THEME"] if key == "THEME" else DEFAULTS[key]
    await event.eor(sage.done(f"{key} reset to `{default}`"))
