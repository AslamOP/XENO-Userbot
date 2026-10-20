"""XENO text-engineering module: encoding, case, cipher, format tools.
All local, zero API. Original code."""
import base64
import binascii
import hashlib
import html
import random
import re
import secrets
import string
import urllib.parse
from datetime import datetime

from core.command import command


def _args(event, minlen=1):
    a = event.text.split(maxsplit=1)
    return a[1].strip() if len(a) > 1 and a[1].strip() else None


def _paste_out(event, label, txt, wrap="`"):
    return event.eor(f"**{label}:**\n{wrap}{txt[:3500]}{wrap}")


@command("b64")
async def b64_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.b64 <text>` — base64 encode")
    try: return await _paste_out(event, "Base64", base64.b64encode(t.encode()).decode())
    except Exception as e: return await event.eor(f"Error: `{e}`")


@command("unb64")
async def unb64_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.unb64 <base64>` — base64 decode")
    try:
        pad = t + "=" * (-len(t) % 4)
        return await _paste_out(event, "Decoded", base64.b64decode(pad).decode("utf-8", "replace"))
    except Exception as e: return await event.eor(f"Error: `{e}`")


@command("b64url")
async def b64url_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.b64url <text>` — URL-safe base64 encode")
    return await _paste_out(event, "Base64URL", base64.urlsafe_b64encode(t.encode()).decode())


@command("urlenc")
async def urlenc_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.urlenc <text>`")
    return await _paste_out(event, "URL-encoded", urllib.parse.quote(t))


@command("urldec")
async def urldec_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.urldec <url> `")
    try: return await _paste_out(event, "URL-decoded", urllib.parse.unquote(t))
    except Exception as e: return await event.eor(f"Error: `{e}`")


@command("hex")
async def hex_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.hex <text>` — to hex")
    return await _paste_out(event, "Hex", t.encode().hex())


@command("unhex")
async def unhex_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.unhex <hex>` — from hex")
    try:
        return await _paste_out(event, "Decoded", bytes.fromhex(t).decode("utf-8", "replace"))
    except ValueError:
        return await event.eor("Invalid hex.")
    except Exception as e:
        return await event.eor(f"Error: `{e}`")


@command("binary")
async def binary_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.binary <text>` — text to binary")
    return await _paste_out(event, "Binary", " ".join(format(ord(c), "08b") for c in t))


@command("unbinary")
async def unbinary_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.unbinary <0101 1010>`")
    try:
        out = "".join(chr(int(b, 2)) for b in t.replace(" ", "").strip().split() if b)
        if not t.replace(" ", "").strip():
            return await event.eor("Give binary digits.")
        return await _paste_out(event, "Decoded", out)
    except ValueError:
        return await event.eor("Invalid binary. Split bytes with spaces.")
    except Exception as e:
        return await event.eor(f"Error: `{e}`")


@command("rot13")
async def rot13_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.rot13 <text>`")
    return await _paste_out(event, "ROT13", t.translate(str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm")))


@command("caesar")
async def caesar_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.caesar <shift> <text>` e.g. `.caesar 3 hi`")
    parts = t.split(maxsplit=1)
    if len(parts) < 2 or not parts[0].lstrip("-").isdigit():
        return await event.eor("Usage: `.caesar <shift> <text>`")
    shift = int(parts[0]) % 26
    out = []
    for ch in parts[1]:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            out.append(ch)
    return await _paste_out(event, f"Caesar {shift:+d}", "".join(out))


@command("atbash")
async def atbash_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.atbash <text>`")
    out = []
    for ch in t:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr(base + 25 - (ord(ch) - base)))
        else:
            out.append(ch)
    return await _paste_out(event, "Atbash", "".join(out))


@command("upsidedown")
async def upsidedown_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.upsidedown <text>` ˙ʇǝʞɔoɹd")
    m = str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!.,'\"- ",
        "ɐqɔpǝɟƃɥıɾʞlɯuodbɹsʇnʌʍxʎz∀qƆpƎℲפHIſʞ˥WNOԀQᴚS┴∩ΛMX⅄Z0ƖᄅƐㄣϛ9ㄥ86¿¡˙'\"- ")
    return await event.eor("̞" + "".join(m.get(c, c) for c in t)[::-1])


@command("smallcase")
async def smallcase_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.smallcase <text>` — ᴜɴɪᴄᴏᴅᴇ sᴍᴀʟʟ ᴄᴀᴘs")
    m = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ")
    return await event.eor(t.upper().translate(m))


@command("strike")
async def strike_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.strike <text>`")
    return await _paste_out(event, "Struck", "\u0336".join(t) + "\u0336")


@command("unders")
async def underscore_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.unders <text>`")
    return await _paste_out(event, "Underlined", "\u0332".join(t) + "\u0332")


@command("emojify")
async def emojify_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.emojify <text>`")
    m = {"a": "🇦", "b": "🇧", "c": "🇨", "d": "🇩", "e": "🇪", "f": "🇫", "g": "🇬",
         "h": "🇭", "i": "🇮", "j": "🇯", "k": "🇰", "l": "🇱", "m": "🇲", "n": "🇳",
         "o": "🇴", "p": "🇵", "q": "🇶", "r": "🇷", "s": "🇸", "t": "🇹", "u": "🇺",
         "v": "🇻", "w": "🇼", "x": "🇽", "y": "🇾", "z": "🇿", "0": "0️⃣", "1": "1️⃣",
         "2": "2️⃣", "3": "3️⃣", "4": "4️⃣", "5": "5️⃣", "6": "6️⃣", "7": "7️⃣",
         "8": "8️⃣", "9": "9️⃣", " ": "  "}
    return await event.eor("".join(m.get(c.lower(), c) for c in t))


@command("morse")
async def morse_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.morse <text>`")
    code = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
            "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
            "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
            "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
            "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
            "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
            "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--", "?": "..--..",
            "'": ".----.", "!": "-.-.--", "/": "-..-.", "(": "-.--.", ")": "-.--.-",
            "&": ".-...", ":": "---...", ";": "-.-.-.", "=": "-...-", "+": ".-.-.",
            "-": "-....-", "_": "..--.-", '"': ".-..-.", "$": "...-..-", "@": ".--.-."}
    try:
        return await _paste_out(event, "Morse", " ".join(code[c.upper()] for c in t if c.upper() in code))
    except Exception as e:
        return await event.eor(f"Error: `{e}`")


@command("unmorse")
async def unmorse_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.unmorse <..-. --- --->`")
    code = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
            "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
            "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
            "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
            "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
            "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
            "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--", "?": "..--..",
            "'": ".----.", "!": "-.-.--", "/": "-..-.", "(": "-.--.", ")": "-.--.-",
            "&": ".-...", ":": "---...", ";": "-.-.-.", "=": "-...-", "+": ".-.-.",
            "-": "-....-", "_": "..--.-", '"': ".-..-.", "$": "...-..-", "@": ".--.-."}
    rev = {v: k for k, v in code.items()}
    try:
        out = "".join(rev.get(w, "?") for w in t.split())
        return await _paste_out(event, "Decoded", out)
    except Exception as e:
        return await event.eor(f"Error: `{e}`")


@command("leet")
async def leet_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.leet <text>` — 1337 5p34k")
    m = {"a": "4", "b": "8", "e": "3", "g": "6", "i": "1", "l": "1", "o": "0",
         "s": "5", "t": "7", "z": "2", "c": "(", "u": "|_|", "m": "/\\\\/\\\\"}
    return await event.eor("".join(m.get(c.lower(), c) for c in t))


@command("mirror")
async def mirror_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.mirror <text>`")
    return await _paste_out(event, "Mirrored", t[::-1])


@command("shuffle")
async def shuffle_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.shuffle <text>`")
    chars = list(t)
    random.shuffle(chars)
    return await _paste_out(event, "Shuffled", "".join(chars))


@command("slugify")
async def slugify_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.slugify <Text with spaces>`")
    s = re.sub(r"[^\w\s-]", "", t.lower().strip())
    return await _paste_out(event, "Slug", re.sub(r"[-\s]+", "-", s))


@command("counts")
async def counts_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.counts <text>`")
    letters = sum(c.isalpha() for c in t)
    digits = sum(c.isdigit() for c in t)
    spaces = sum(c.isspace() for c in t)
    punct = len(t) - letters - digits - spaces
    words = len(t.split())
    return await event.eor(
        f"**Stats:**\n"
        f"Chars: `{len(t)}`\nWords: `{words}`\n"
        f"Letters: `{letters}`  Digits: `{digits}`\n"
        f"Spaces: `{spaces}`  Punct: `{punct}`")


@command("md5")
async def md5_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.md5 <text>`")
    return await _paste_out(event, "MD5", hashlib.md5(t.encode()).hexdigest())


@command("sha1")
async def sha1_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.sha1 <text>`")
    return await _paste_out(event, "SHA1", hashlib.sha1(t.encode()).hexdigest())


@command("sha256")
async def sha256_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.sha256 <text>`")
    return await _paste_out(event, "SHA256", hashlib.sha256(t.encode()).hexdigest())


@command("sha512")
async def sha512_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.sha512 <text>`")
    return await _paste_out(event, "SHA512", hashlib.sha512(t.encode()).hexdigest())


@command("uuid")
async def uuid_cmd(event):
    import uuid as _uuid
    return await event.eor(f"**UUID4:** `{_uuid.uuid4()}`")


@command("rand")
async def rand_cmd(event):
    t = _args(event)
    if not t:
        return await event.eor(f"**Random number:** `{random.randint(0, 100)}`")
    parts = t.split()
    try:
        if len(parts) == 1:
            lo, hi = 0, int(parts[0])
        else:
            lo, hi = int(parts[0]), int(parts[1])
        if lo > hi:
            lo, hi = hi, lo
        return await event.eor(f"**Random [{lo}–{hi}]:** `{random.randint(lo, hi)}`")
    except ValueError:
        return await event.eor("Give integers: `.rand` / `.rand 100` / `.rand 10 50`")


@command("pick")
async def pick_cmd(event):
    t = _args(event)
    if not t: return await event.eor("Usage: `.pick a, b, c` — random choice")
    items = [x.strip() for x in t.split(",") if x.strip()]
    if not items: return await event.eor("Give comma-separated options.")
    return await event.eor(f"🎲 I pick: **{random.choice(items)}**")


@command("namegen")
async def namegen_cmd(event):
    prefixes = ["Cy", "Neo", "Xy", "Aero", "Zap", "Oni", "Vor", "Sil", "Kra", "Umbra",
                "Ember", "Nyx", "Raze", "Glitch", "Vex", "Pixel", "Hex", "Null", "Byte", "Omen"]
    suffixes = ["forge", "wave", "byte", "wing", "lark", "node", "storm", "shade", "peak", "core",
                "flux", "guard", "song", "blade", "muse", "drift", "scope", "vis", "tem", "ra"]
    n = random.randint(1, 2)
    names = [random.choice(prefixes) + random.choice(suffixes) for _ in range(min(n, 5))]
    return await event.eor("**Name ideas:**\n" + "\n".join(f"• `{x}`" for x in names[:5]))


@command("passgen")
async def passgen_cmd(event):
    t = _args(event)
    try:
        ln = int(t) if t and t.strip().isdigit() else 16
    except ValueError:
        ln = 16
    ln = max(8, min(64, ln))
    # secrets, not random: `random` is Mersenne Twister and predictable from a
    # few outputs, which is not what anyone calling .passgen wants.
    pool = string.ascii_letters + string.digits + "!@#$%^&*"
    pw = "".join(secrets.choice(pool) for _ in range(ln))
    return await event.eor(f"`{pw}`")