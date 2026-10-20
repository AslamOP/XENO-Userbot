"""Shared runtime-config logic for the panel (/set) and the userbot (.set).

Both clients expose the same keys and must store identical normalized values,
so the validation/normalization lives here once. This module registers no
handlers — importing it from a plugin has no side effects.
"""
import config
from core import sage
from core.db import get as db_get
from core.db import set_ as db_set

# Keys safe to read/write from either client.
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

# Keys whose value is read straight off the config module at runtime. A set
# writes them live; apply_persisted() restores them from the db at boot.
LIVE_APPLIED = (
    "AI_MODEL", "AI_ALLOWED_IDS", "BOT_NAME", "PERSONA",
    "AI_AUTO_REPLY", "PREFIXES",
)
BOOT_ONLY = ()

# Environment defaults. Read straight from env, NOT getattr(config, ...): by the
# time a plugin is imported, apply_persisted() may already have overlaid db
# values onto config, so the attrs are no longer the defaults.
DEFAULTS = {
    "AI_MODEL": config.get("AI_MODEL", "gpt-4o"),
    "AI_ALLOWED_IDS": config.get("AI_ALLOWED_IDS", ""),
    "BOT_NAME": config.get("BOT_NAME", "xeno"),
    "PERSONA": config.get("PERSONA", ""),
    "AI_AUTO_REPLY": config.get("AI_AUTO_REPLY", "false").lower() == "true",
    "PREFIXES": (config.get("PREFIXES", ".,!,#") or ".,!,#").split(","),
    "THEME": sage.DEFAULT_THEME,
}


def coerce(key, val):
    """Normalize a stored/default value to the type config expects for `key`."""
    if key == "PREFIXES":
        if isinstance(val, list):
            return list(val)
        return [p for p in str(val).split(",") if p]
    if key == "AI_AUTO_REPLY":
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("1", "true", "yes", "on")
    return val


async def apply_persisted():
    """Overlay db-persisted keys onto the config module. Call once, at boot.

    Without this, a set wrote to the db but a restart reverted every value to
    its .env default (only THEME survived, via sage.load_theme()).
    """
    for key in LIVE_APPLIED + BOOT_ONLY:
        stored = await db_get(key, None)
        if stored is not None:
            setattr(config, key, coerce(key, stored))


async def apply_key(key, val):
    """Validate, normalize and live-apply one PANEL_KEYS entry.

    Returns (ok, message, val_out): val_out is what the caller should persist.
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
    elif key in LIVE_APPLIED:
        setattr(config, key, coerce(key, val))
    return True, "", val


async def current(key):
    """Current value of a key for display. THEME lives under a different db key."""
    if key == "THEME":
        return await db_get("theme:current", sage.DEFAULT_THEME)
    return await db_get(key, getattr(config, key, config.get(key, "")))
