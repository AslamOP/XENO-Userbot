"""XENO runtime config — .set/.get/.config/.unset on the userbot client.

The assistant panel's /set /get /config, mirrored for the account itself:
same PANEL_KEYS, same validation, live-applied where the value is read at
runtime. See plugins/control.py for the assistant side.
"""
import config
from core import sage
from core.command import command
from core.db import delete as db_delete
from core.db import get as db_get
from core.db import set_ as db_set

# keep in sync with plugins/control.py PANEL_KEYS — importing that module
# here would also register the assistant panel handlers on this client.
PANEL_KEYS = {
    "PREFIXES": "Command prefixes for the userbot client",
    "AI_MODEL": "Model used by .ai / game agent",
    "AI_AUTO_REPLY": "Auto-reply to inbound DMs (true/false)",
    "AI_ALLOWED_IDS": "Allowlist for auto-reply, blank = anyone",
    "BOT_NAME": "Name the persona speaks as",
    "PERSONA": "System prompt for the AI",
    "THEME": "Reply accent (see core/sage.py THEMES)",
}
# OWNER_ID stays out: a typo locks you out of every owner-gated command.
# Change it in .env.

# Keys apply_key writes straight onto the config module at runtime.
_LIVE_APPLIED = ("AI_MODEL", "AI_ALLOWED_IDS", "BOT_NAME", "PERSONA")

# Boot defaults, snapshotted before .set can mutate config attrs — .unset
# restores from here (getattr(config, ...) would read the just-set value).
_DEFAULTS = {k: getattr(config, k, config.get(k, "")) for k in PANEL_KEYS}


async def apply_key(key, val):
    """Validate, normalize and live-apply one PANEL_KEYS entry.

    Mirrors the assistant panel's /set so both clients store the same
    normalized value. Returns (ok, message, val_out): val_out is what the
    caller should persist.
    """
    if key not in PANEL_KEYS:
        return False, f"config key `{key}`", val
    if key == "PREFIXES":
        parts = [p for p in val.split() if p]
        if not parts or any(len(p) != 1 for p in parts):
            why = "single character prefixes, space separated: `. ! ,`"
            return False, why, val
        val = ",".join(parts)
    elif key == "AI_AUTO_REPLY":
        on = str(val).lower() in ("1", "true", "yes", "on")
        val = "true" if on else "false"
    elif key == "THEME":
        name = val.lower().strip()
        if name not in sage.THEMES:
            valid = "`, `".join(sage.THEMES)
            return False, f"theme `{name}` — valid: `{valid}`", val
        sage.set_theme(name)
        await db_set("theme:current", name)
        val = name
    elif key in _LIVE_APPLIED:
        setattr(config, key, val)
    return True, "", val


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
        bound = " ".join(config.PREFIXES)
        return await event.eor(
            f"{sage.done(f'{key}={val}')}\n"
            "⚠️ Takes effect after a restart — the live handlers "
            f"are still bound to `{bound}`."
        )
    await event.eor(sage.done(f"{key}={val}"))


async def _current(key):
    """Current value of a panel key. THEME lives under a different db key."""
    if key == "THEME":
        return await db_get("theme:current", sage.DEFAULT_THEME)
    return await db_get(key, getattr(config, key, config.get(key, "")))


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
        cur = await _current(k)
        lines.append(f"`{k}` — {desc}\n   now: `{cur}`")
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
    if key in _LIVE_APPLIED:
        setattr(config, key, _DEFAULTS[key])
    if key == "THEME":
        # The live accent is stored under db key "theme:current", not THEME.
        await db_delete("theme:current")
        sage.set_theme(sage.DEFAULT_THEME)
    default = sage.DEFAULT_THEME if key == "THEME" else _DEFAULTS[key]
    await event.eor(sage.done(f"{key} reset to `{default}`"))
