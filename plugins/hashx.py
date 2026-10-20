"""XENO hash & encoding series (loop-registered). Standard library only."""
import base64
import hashlib
import zlib

from core.command import command

_HASHES = {
    "sha224": "sha224",
    "sha384": "sha384",
    "sha512256": "sha512_256",
    "sha3_256": "sha3_256",
    "sha3_512": "sha3_512",
    "blake2s": "blake2s",
    "blake2b": "blake2b",
    "shake": "shake_128",
}
# md4 dropped: not in the OpenSSL 3 default provider, so hashlib.new("md4")
# raises on modern distros. MD5/MD6-class digests are also not worth exposing.

for _hname, _hmod in _HASHES.items():
    def _hmake(name, mod):
        async def _hhandler(event):
            a = event.text.split(maxsplit=1)
            arg = a[1].strip() if len(a) > 1 else ""
            if not arg:
                return await event.eor(f"Give text. Usage: `.{name} <text>`")
            try:
                h = hashlib.new(mod)
                h.update(arg.encode())
                if name == "shake":
                    return await event.eor(f"**{name}:** `{h.hexdigest(16)}`")
                return await event.eor(f"**{name}:** `{h.hexdigest()}`")
            except Exception as e:
                return await event.eor(f"Error: `{e}`")
        _hhandler.__name__ = f"hash_{name}"
        return _hhandler
    command(_hname)(_hmake(_hname, _hmod))


@command("crc32")
async def crc32_cmd(event):
    a = event.text.split(maxsplit=1)
    arg = a[1].strip() if len(a) > 1 else ""
    if not arg:
        return await event.eor("Give text: `.crc32 <text>`")
    return await event.eor(f"**crc32:** `{zlib.crc32(arg.encode()):08x}`")


@command("adler")
async def adler_cmd(event):
    a = event.text.split(maxsplit=1)
    arg = a[1].strip() if len(a) > 1 else ""
    if not arg:
        return await event.eor("Give text: `.adler <text>`")
    return await event.eor(f"**adler32:** `{zlib.adler32(arg.encode()):08x}`")


@command("hashall")
async def hashall_cmd(event):
    a = event.text.split(maxsplit=1)
    arg = a[1].strip() if len(a) > 1 else ""
    if not arg:
        return await event.eor("Give text: `.hashall <text>`")
    data = arg.encode()
    lines = ["**🔐 All hashes:**"]
    for name in ("md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_256", "sha3_512"):
        lines.append(f"`{name}`: `{hashlib.new(name, data).hexdigest()}`")
    lines.append(f"`crc32`: `{zlib.crc32(data):08x}`")
    lines.append(f"`adler`: `{zlib.adler32(data):08x}`")
    await event.eor("\n".join(lines))


# ---- encodings ----
# value = (callable, is_decoder). The direction is explicit — inferring it from the
# name substring "dec" misrouted ascii85/a85un/urlb64d, which are all decoders
# or encoders as the opposite of what the heuristic assumed.
_ENCS = {
    "b32enc": (lambda d: base64.b32encode(d).decode(), False),
    "b32dec": (lambda s: base64.b32decode(s).decode(errors="replace"), True),
    "b85enc": (lambda d: base64.b85encode(d).decode(), False),
    "b85dec": (lambda s: base64.b85decode(s).decode(errors="replace"), True),
    "a85enc": (lambda d: base64.a85encode(d).decode(), False),
    "a85dec": (lambda s: base64.a85decode(s).decode(errors="replace"), True),
    "ascii85": (lambda s: base64.a85encode(s.encode()).decode(), False),
    "a85un": (lambda s: base64.a85decode(s).decode(errors="replace"), True),
    "urlb64": (lambda d: base64.urlsafe_b64encode(d).decode(), False),
    "urlb64d": (
        lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode(errors="replace"),
        True,
    ),
}


for _ename, (_efn, _edec) in _ENCS.items():
    def _emake(name, fn, is_dec):
        async def _ehandler(event):
            a = event.text.split(maxsplit=1)
            arg = a[1].strip() if len(a) > 1 else ""
            if not arg:
                return await event.eor(f"Give text. Usage: `.{name} <text>`")
            try:
                out = fn(arg) if is_dec else fn(arg.encode())
                return await event.eor(f"**{name}:**\n`{out}`")
            except Exception:
                return await event.eor(f"`{name}`: invalid input for this {'decoder' if is_dec else 'encoder'}.")
        _ehandler.__name__ = f"enc_{name}"
        _ehandler.__doc__ = f"{'Decode' if is_dec else 'Encode'} text via {name}."
        return _ehandler
    command(_ename)(_emake(_ename, _efn, _edec))


@command("hashmenux")
async def hashmenux_cmd(event):
    return await event.eor(
        "**🔐 Hash/Encode tools:**\n"
        "Hashes: `sha1 sha224 sha256 sha384 sha512 sha3_256 sha3_512`\n"
        "`sha512256 blake2s blake2b shake crc32 adler hashall`\n"
        "Encode: `b64 b32enc b85enc a85enc ascii85 urlb64`\n"
        "Decode: `unb64 b32dec b85dec a85dec a85un urlb64d`\n"
        "`hex unhex binary unbinary morse unmorse` come from textify")