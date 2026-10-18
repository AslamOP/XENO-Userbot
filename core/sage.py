"""core.sage — Raphael-protocol accent lines for command confirmations.

Every free-text confirmation across plugins should read as a system readout.
Structured output (tables/coordinates/media) stays clean — Raphael reports data as it is.
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
    "Caution. {what}.",
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


def ack():
    return random.choice(_ACK)


def done(action=None):
    if action:
        return f"{random.choice(_DONE)} — {action}."
    return random.choice(_DONE)


async def accent():
    """Theme prefix for confirmations. Honours db key "theme:current"."""
    from core.db import get as db_get

    name = await db_get("theme:current", "void")
    return THEMES.get(name, "")


async def themed(msg):
    """Wrap a confirmation line in the active theme accent, if any."""
    mark = await accent()
    return f"{mark}{msg}" if mark else msg


def err(what):
    return random.choice(_ERR).format(what=what)


def warn(what):
    return random.choice(_WARN).format(what=what)


def analysis():
    return random.choice(_ANALYSIS)


def verdict(what):
    return random.choice(_VERDICT).format(what=what)