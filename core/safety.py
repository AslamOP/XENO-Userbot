"""Dangerous-pattern scan for plugins before they're installed.

Ultroid does this via a `KEEP_SAFE().All` regex blocklist run over the plugin
source, aborting unless you pass `f` to force. Same idea here: a static scan is
not a sandbox and will never catch everything, but it catches the obvious
foot-guns before you `exec` code you were sent in a group.

What this is NOT: a security boundary. A determined plugin can obfuscate past
any regex. It exists to stop accidents, not attacks.
"""
import re

# (label, pattern, why)
RULES = [
    ("os.system",
     r"\bos\s*\.\s*system\s*\(",
     "runs a shell command"),
    ("subprocess",
     r"\b(subprocess|commands)\s*\.\s*(run|call|Popen|check_output|check_call)\s*\(",
     "spawns a process"),
    ("shell=True",
     r"shell\s*=\s*True",
     "spawns a shell"),
    ("eval/exec",
     r"\b(eval|exec)\s*\(",
     "executes code at runtime"),
    ("__import__",
     r"__import__\s*\(",
     "imports modules dynamically"),
    ("os.remove/rmtree",
     r"\bos\s*\.\s*(remove|unlink|rmdir|removedirs)\s*\(|\bshutil\s*\.\s*rmtree\s*\(",
     "deletes files"),
    ("writes outside plugins",
     r"open\s*\(\s*[\"']/(etc|root|home|var|usr|bin|sbin|boot)",
     "writes to a system path"),
    ("reads secrets",
     r"[\"']/etc/(passwd|shadow)[\"']|\.env[\"']\s*,\s*[\"']w",
     "touches credentials"),
    ("network egress to raw IPs",
     r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
     "hardcoded IP endpoint"),
    ("curl/wget via shell",
     r"\b(curl|wget|nc|netcat)\b",
     "network tool in a shell"),
]

COMPILED = [(label, re.compile(pat), why) for label, pat, why in RULES]


def scan(source):
    """Return [(label, why)] of every rule the source trips."""
    hits = []
    for label, pat, why in COMPILED:
        try:
            if pat.search(source):
                hits.append((label, why))
        except re.error:
            continue
    return hits


def report(hits, name):
    lines = [f"**⚠️ Installation aborted** — `{name}` trips {len(hits)} rule(s):\n"]
    for label, why in hits:
        lines.append(f"• `{label}` — {why}")
    lines.append(
        "\nThis is a static scan, not a sandbox. If you wrote this and trust "
        "it, force it with `.install f`."
    )
    return "\n".join(lines)
