"""XENO case & text transform series (loop-registered). Original code."""
from core.command import command

_CASES = {
    "scream": str.upper, "whisper": str.lower, "caps": lambda s: s.title(),
    "swapcase": lambda s: s.swapcase(),
    "snake": lambda s: "_".join(w.lower() for w in s.split()),
    "kebab": lambda s: "-".join(w.lower() for w in s.split()),
    "camel": lambda s: s.split()[0].lower() + "".join(w.title() for w in s.split()[1:]),
    "pascal": lambda s: "".join(w.title() for w in s.split()),
    "constant": lambda s: "_".join(w.upper() for w in s.split()),
    "altcase": lambda s: "".join(ch.upper() if i % 2 else ch.lower() for i, ch in enumerate(s)),
    "noise": lambda s: "".join(f"{c} " for c in s),
    "spaced": lambda s: " ".join(s),
    "noispaces": lambda s: s.replace(" ", ""),
    "piglatin": lambda s: " ".join(w[1:] + w[0] + "ay" if w else w for w in s.lower().split()),
    "prose": lambda s: s.capitalize(),
    "items": lambda s: "\n".join(f"• {x}" for x in s.split(",")),
    "listc": lambda s: "\n".join(f"{i}. {x}" for i, x in enumerate(s.split(","), 1)),
    "table": lambda s: "\t".join(s.split()),
    "nocomma": lambda s: s.replace(",", ""),
    "firstc": lambda s: s[0] if s else "",
    "lastc": lambda s: s[-1] if s else "",
    "capsfirst": lambda s: s[0].upper() + s[1:] if s else "",
}

for _cname, _cfunc in _CASES.items():
    def _cmake(name, fn):
        async def _chandler(event):
            a = event.text.split(maxsplit=1)
            arg = a[1].strip() if len(a) > 1 else ""
            if not arg:
                return await event.eor(f"Give text. Usage: `.{name} <text>`")
            try:
                val = fn(arg)
                out = val if str(val) else "(empty)"
                return await event.eor(f"**{name}:**\n`{out}`")
            except Exception as e:
                return await event.eor(f"Error: `{e}`")
        _chandler.__name__ = f"case_{name}"
        _chandler.__doc__ = f"Transform text via {name}."
        return _chandler
    command(_cname)(_cmake(_cname, _cfunc))


@command("cases")
async def cases_cmd(event):
    """List all case transforms."""
    return await event.eor(
        f"**🔤 Case transforms:**\n`{', '.join(sorted(_CASES.keys()))}`")