"""XENO text-style module: unicode fonts, banner letters, art, text-graphics.
All local transforms, original code."""
import random

from core.command import command

_FONTS = {
    "bold": {"a": "𝗮", "b": "𝗯", "c": "𝗰", "d": "𝗱", "e": "𝗲", "f": "𝗳", "g": "𝗴",
             "h": "𝗵", "i": "𝗶", "j": "𝗷", "k": "𝗸", "l": "𝗹", "m": "𝗺", "n": "𝗻",
             "o": "𝗼", "p": "𝗽", "q": "𝗾", "r": "𝗿", "s": "𝘀", "t": "𝘁", "u": "𝘂",
             "v": "𝘃", "w": "𝘄", "x": "𝘅", "y": "𝘆", "z": "𝘇", "A": "𝗔", "B": "𝗕",
             "C": "𝗖", "D": "𝗗", "E": "𝗘", "F": "𝗙", "G": "𝗚", "H": "𝗛", "I": "𝗜",
             "J": "𝗝", "K": "𝗞", "L": "𝗟", "M": "𝗠", "N": "𝗡", "O": "𝗢", "P": "𝗣",
             "Q": "𝗤", "R": "𝗥", "S": "𝗦", "T": "𝗧", "U": "𝗨", "V": "𝗩", "W": "𝗪",
             "X": "𝗫", "Y": "𝗬", "Z": "𝗭"},
    "italic": {"a": "𝘢", "b": "𝘣", "c": "𝘤", "d": "𝘥", "e": "𝘦", "f": "𝘧", "g": "𝘨",
               "h": "𝘩", "i": "𝘪", "j": "𝘫", "k": "𝘬", "l": "𝘭", "m": "𝘮", "n": "𝘯",
               "o": "𝘰", "p": "𝘱", "q": "𝘲", "r": "𝘳", "s": "𝘴", "t": "𝘵", "u": "𝘶",
               "v": "𝘷", "w": "𝘸", "x": "𝘹", "y": "𝘺", "z": "𝘻", "A": "𝘈", "B": "𝘉",
               "C": "𝘊", "D": "𝘋", "E": "𝘌", "F": "𝘍", "G": "𝘎", "H": "𝘏", "I": "𝘐",
               "J": "𝘑", "K": "𝘒", "L": "𝘓", "M": "𝘔", "N": "𝘕", "O": "𝘖", "P": "𝘗",
               "Q": "𝘘", "R": "𝘙", "S": "𝘚", "T": "𝘛", "U": "𝘜", "V": "𝘝", "W": "𝘞",
               "X": "𝘟", "Y": "𝘠", "Z": "𝘡"},
    "mono": {"a": "𝚊", "b": "𝚋", "c": "𝚌", "d": "𝚍", "e": "𝚎", "f": "𝚏", "g": "𝚐",
             "h": "𝚑", "i": "𝚒", "j": "𝚓", "k": "𝚔", "l": "𝚕", "m": "𝚖", "n": "𝚗",
             "o": "𝚘", "p": "𝚙", "q": "𝚚", "r": "𝚛", "s": "𝚜", "t": "𝚝", "u": "𝚞",
             "v": "𝚟", "w": "𝚠", "x": "𝚡", "y": "𝚢", "z": "𝚣", "A": "𝙰", "B": "𝙱",
             "C": "𝙲", "D": "𝙳", "E": "𝙴", "F": "𝙵", "G": "𝙶", "H": "𝙷", "I": "𝙸",
             "J": "𝙹", "K": "𝙺", "L": "𝙻", "M": "𝙼", "N": "𝙽", "O": "𝙾", "P": "𝙿",
             "Q": "𝚀", "R": "𝚁", "S": "𝚂", "T": "𝚃", "U": "𝚄", "V": "𝚅", "W": "𝚆",
             "X": "𝚇", "Y": "𝚈", "Z": "𝚉"},
    "script": {"a": "𝒶", "b": "𝒷", "c": "𝒸", "d": "𝒹", "e": "ℯ", "f": "𝒻", "g": "ℊ",
               "h": "𝒽", "i": "𝒾", "j": "𝒿", "k": "𝓀", "l": "𝓁", "m": "𝓂", "n": "𝓃",
               "o": "ℴ", "p": "𝓅", "q": "𝓆", "r": "𝓇", "s": "𝓈", "t": "𝓉", "u": "𝓊",
               "v": "𝓋", "w": "𝓌", "x": "𝓍", "y": "𝓎", "z": "𝓏", "A": "𝒜", "B": "ℬ",
               "C": "𝒞", "D": "𝒟", "E": "ℰ", "F": "ℱ", "G": "𝒢", "H": "ℋ", "I": "ℐ",
               "J": "𝒥", "K": "𝒦", "L": "ℒ", "M": "ℳ", "N": "𝒩", "O": "𝒪", "P": "𝒫",
               "Q": "𝒬", "R": "ℛ", "S": "𝒮", "T": "𝒯", "U": "𝒰", "V": "𝒱", "W": "𝒲",
               "X": "𝒳", "Y": "𝒴", "Z": "𝒵"},
    "fraktur": {"a": "𝔞", "b": "𝔟", "c": "𝔠", "d": "𝔡", "e": "𝔢", "f": "𝔣", "g": "𝔤",
                "h": "𝔥", "i": "𝔦", "j": "𝔧", "k": "𝔨", "l": "𝔩", "m": "𝔪", "n": "𝔫",
                "o": "𝔬", "p": "𝔭", "q": "𝔮", "r": "𝔯", "s": "𝔰", "t": "𝔱", "u": "𝔲",
                "v": "𝔳", "w": "𝔴", "x": "𝔵", "y": "𝔶", "z": "𝔷", "A": "𝔄", "B": "𝔅",
                "C": "ℭ", "D": "𝔇", "E": "𝔈", "F": "𝔉", "G": "𝔊", "H": "ℌ", "I": "ℑ",
                "J": "𝔍", "K": "𝔎", "L": "𝔏", "M": "𝔐", "N": "𝔑", "O": "𝔒", "P": "𝔓",
                "Q": "𝔔", "R": "ℜ", "S": "𝔖", "T": "𝔗", "U": "𝔘", "V": "𝔙", "W": "𝔚",
                "X": "𝔛", "Y": "𝔜", "Z": "ℨ"},
    "circled": {"a": "ⓐ", "b": "ⓑ", "c": "ⓒ", "d": "ⓓ", "e": "ⓔ", "f": "ⓕ", "g": "ⓖ",
                "h": "ⓗ", "i": "ⓘ", "j": "ⓙ", "k": "ⓚ", "l": "ⓛ", "m": "ⓜ", "n": "ⓝ",
                "o": "ⓞ", "p": "ⓟ", "q": "ⓠ", "r": "ⓡ", "s": "ⓢ", "t": "ⓣ", "u": "ⓤ",
                "v": "ⓥ", "w": "ⓦ", "x": "ⓧ", "y": "ⓨ", "z": "ⓩ", "A": "Ⓐ", "B": "Ⓑ",
                "C": "Ⓒ", "D": "Ⓓ", "E": "Ⓔ", "F": "Ⓕ", "G": "Ⓖ", "H": "Ⓗ", "I": "Ⓘ",
                "J": "Ⓙ", "K": "Ⓚ", "L": "Ⓛ", "M": "Ⓜ", "N": "Ⓝ", "O": "Ⓞ", "P": "Ⓟ",
                "Q": "Ⓠ", "R": "Ⓡ", "S": "Ⓢ", "T": "Ⓣ", "U": "Ⓤ", "V": "Ⓥ", "W": "Ⓦ",
                "X": "Ⓧ", "Y": "Ⓨ", "Z": "Ⓩ"},
    "squared": {"a": "🄰", "b": "🄱", "c": "🄲", "d": "🄳", "e": "🄴", "f": "🄵", "g": "🄶",
                "h": "🄷", "i": "🄸", "j": "🄹", "k": "🄺", "l": "🄻", "m": "🄼", "n": "🄽",
                "o": "🄾", "p": "🄿", "q": "🅀", "r": "🅁", "s": "🅂", "t": "🅃", "u": "🅄",
                "v": "🅅", "w": "🅆", "x": "🅇", "y": "🅈", "z": "🅉", "A": "🄰", "B": "🄱",
                "C": "🄲", "D": "🄳", "E": "🄴", "F": "🄵", "G": "🄶", "H": "🄷", "I": "🄸",
                "J": "🄹", "K": "🄺", "L": "🄻", "M": "🄼", "N": "🄽", "O": "🄾", "P": "🄿",
                "Q": "🅀", "R": "🅁", "S": "🅂", "T": "🅃", "U": "🅄", "V": "🅅", "W": "🅆",
                "X": "🅇", "Y": "🅈", "Z": "🅉"},
}

_BANNER = {
    "A": [" ▄▀█ ", " █▀█ "], "B": [" █▄ █ ", " ▄▀▄ "], "C": [" ▄▀█ ", " █   "],
    "D": [" █▄ █ ", " █  █ "], "E": [" █▄▄ ", " █▄█ "], "F": [" █▄▄ ", " █   "],
    "G": [" ▄▀█ ", " █ ▄█ "], "H": [" █ █ ", " █▀█▄ "], "I": [" █ ", " █ "],
    "J": [" █ ", " █▀ "], "K": [" █ ▄▀ ", " █▀ ▄ "], "L": [" █", " █▄█ "],
    "M": [" █▀▄▀█ ", " █ ▀ █ "], "N": [" █▄▀█ ", " █ ▀█ "], "O": [" ▄▀█▄ ", " █ █ "],
    "P": [" █▄▀█ ", " █   "], "Q": [" ▄▀█▄ ", " █ ▀▄ "], "R": [" █▄▀█ ", " █ ▄▀ "],
    "S": [" ▄▀▄ ", " ▄▀▄ "], "T": [" ▀█▀ ", "  █  "], "U": [" █ █ ", " █▄█ "],
    "W": [" █ █ ", " █▀█▀█ "], "X": [" ▀▄▄▀ ", " ▄▀▀▄ "], "Y": [" ▀▄▀ ", "  █  "],
    "Z": [" ▀▄▄ ", " ▄▄▀ "], " ": ["    ", "    "], "0": [" ▄▀█ ", " █▄█ "],
    "1": [" ▄█ ", "  █ "], "2": [" ▀█▄ ", " ▄▄▀ "], "3": [" ▀▀█ ", " ▄▀█ "],
    "4": [" █ █ ", " ▀▀█ "], "5": [" █▄▄ ", " ▀█ "], "6": [" ▄▀▄ ", " █▄█ "],
    "7": [" ▀▄█ ", "   █ "], "8": [" ▄▀█ ", " ▄▀█ "], "9": [" ▄▀█ ", " ▀▀█ "],
}


def _convert(args, font, name):
    if not args:
        return None
    table = _FONTS.get(font)
    if not table:
        return args
    return "".join(table.get(c, c) for c in args)


def _banner_txt(word):
    lines = ["`" + "".join(line) + "`" for line in zip(*[_BANNER.get(c.upper(), ["   ", "   "]) for c in word])]
    return "\n".join(lines)


@command("font")
async def font_cmd(event):
    """Info on available fonts for text styling."""
    return await event.eor(
        "**Font styles (usage `.txt <style> <text>`):**\n"
        "`bold`, `italic`, `mono`, `script`, `fraktur`, `circled`, `squared`\n\n"
        "Example: `.txt bold XENO IS LIVE`")


@command("txt")
async def txt_cmd(event):
    """Style a text with a font. Usage: `.txt <style> <text>`"""
    a = event.text.split(maxsplit=2)
    if len(a) < 3:
        return await event.eor("Usage: `.txt <bold|italic|mono|script|fraktur|circled|squared> <text>`")
    style = a[1].lower()
    text = a[2]
    if style not in _FONTS:
        return await event.eor("Unknown style. Run `.font` for the list.")
    out = _convert(text, style, None)
    await event.eor(out if out else "Empty.")


@command("banner")
async def banner_cmd(event):
    """Text to ASCII banner. Usage: `.banner <text>`"""
    a = event.text.split(maxsplit=1)
    text = a[1].strip() if len(a) > 1 else ""
    if not text or len(text) > 12:
        return await event.eor("Give up to 12 chars: `.banner <text>`")
    try:
        await event.eor(_banner_txt(text))
    except Exception as e:
        await event.eor(f"Error: `{e}`")


@command("art")
async def art_cmd(event):
    """Pick a random ASCII art. Usage: `.art`"""
    arts = [
        "(\\_/)\n( •_•)\n/ >🍕 Want a slice?",
        "  /\\_/\\\n ( o.o )\n  > ^ <",
        "  ____\n /    \\\n| ^  ^ |\n|  --  |\n \\____/",
        "  .--.\n /    \\\n|  __  |\n| |  | |\n| |  | |\n'--''--'",
        "   /\n  //\n //\\\n||  \\_\n||   /\n \\\\ /\n  \\\\",
        "   .'`'.\n  / ,   \\\n |  .'.  |\n  \\ /^\\ /\n   `---'",
    ]
    await event.eor("```\n" + random.choice(arts) + "\n```")


@command("now")
async def now_cmd(event):
    """Current UTC time + uptime. Usage: `.now`"""
    import time as _t
    import datetime
    import config
    upt = ""
    if config.BOT_START_TIME:
        secs = int(_t.time() - config.BOT_START_TIME)
        days, rem = divmod(secs, 86400)
        hrs, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        upt = f"**Uptime:** `{days}d {hrs}h {mins}m {secs}s`"
    await event.eor(
        f"**🕐 UTC:** `{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"**Local:** `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"{upt}")


@command("when")
async def when_cmd(event):
    """Time in an IANA timezone. Usage: `.when <Asia/Kolkata>`"""
    a = event.text.split(maxsplit=1)
    q = a[1].strip() if len(a) > 1 else ""
    if not q:
        return await event.eor("Give a timezone. Usage: `.when Asia/Kolkata`")
    from plugins.world import _zone_now

    now, off, _abbr = _zone_now(q)
    if now is None:
        return await event.eor(
            f"Can't resolve `{q}`. Use an IANA zone like `Asia/Kolkata` — "
            "`.zones <substring>` lists them."
        )
    await event.eor(f"**🕐 {q}**\n`{now.strftime('%Y-%m-%d %H:%M:%S %Z')}`\nUTC offset: `{off}`")