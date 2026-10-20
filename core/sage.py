"""core.sage — Raphael-protocol accent lines for command confirmations.

Every free-text confirmation across plugins should read as a system readout.
Structured output (tables/coordinates/media) stays clean — Raphael reports data as it is.

The accent is cached at boot (`load_theme()`) and updated live by
`.theme` / the panel's `/set THEME` — ack()/done()/err()/warn() read the
cache synchronously so they stay zero-cost and work offline.
"""
import random

# Selected by `.theme <name>` and stored in db key "theme:current".
THEMES = {
    "void": "",
    "neon": " ▍ ",
    "sunset": " ✦ ",
    "matrix": " > ",
    "royal": " ♛ ",
    "cyber": " ▚ ",
    "pastel": " ❀ ",
    "gold": " ★ ",
}
DEFAULT_THEME = "neon"

_THEME_NAME = DEFAULT_THEME
_ACCENT = THEMES[DEFAULT_THEME]

_ACK = [
    "Acknowledged.",
    "Affirmative.",
    "Understood.",
    "Compliance confirmed.",
    "Directive received.",
]
_DONE = [
    "Operation complete.",
    "Executed successfully.",
    "Done. Zero margin for error.",
    "Action performed within parameters.",
    "Transaction finished. No residuals.",
    "Target state reached.",
]
_ERR = [
    "Insufficient data: {what}.",
    "Error: {what} required. Recalculating...",
    "Illogical request. {what} cannot be located.",
    "Failed. {what} returned 404.",
    "Missing variable: {what}.",
]
_WARN = [
    "Warning: {what}. Proceed with caution.",
    "Anomaly detected: {what}.",
    "Caution: {what}.",
]
_ANALYSIS = [
    "Calculating...",
    "Analyzing variables...",
    "Querying records...",
]
_VERDICT = [
    "Conclusion: {what}.",
    "Result: {what}.",
    "Optimal reading: {what}.",
    "Final calculation: {what}.",
]


def current_theme() -> str:
    """Name of the active theme."""
    return _THEME_NAME


def accent_now() -> str:
    """Accent string of the active theme (may be empty for ``void``)."""
    return _ACCENT


def set_theme(name: str) -> str:
    """Sync-update the cached theme. Unknown names fall back to the default."""
    global _THEME_NAME, _ACCENT
    _THEME_NAME = name if name in THEMES else DEFAULT_THEME
    _ACCENT = THEMES[_THEME_NAME]
    return _THEME_NAME


async def load_theme():
    """Read theme:current from db and prime the cache. Call once at boot."""
    from core.db import get as db_get

    name = await db_get("theme:current", DEFAULT_THEME)
    return set_theme(name)


def themed(msg: str) -> str:
    """Wrap a line in the active theme accent, if any."""
    return f"{_ACCENT}{msg}" if _ACCENT else msg


def ack():
    return themed(random.choice(_ACK))


def done(action=None):
    if action:
        return themed(f"{random.choice(_DONE)} — {action}.")
    return themed(random.choice(_DONE))


def err(what):
    return themed(random.choice(_ERR).format(what=what))


def warn(what):
    return themed(random.choice(_WARN).format(what=what))


def analysis():
    return themed(random.choice(_ANALYSIS))


def verdict(what):
    return themed(random.choice(_VERDICT).format(what=what))
