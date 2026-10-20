"""File handling: the store, aliases, and the ephemeral guarantee."""
import asyncio
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(ROOT))
os.chdir(ROOT)

import config  # noqa: E402

config.PREFIXES = [".", "!", "#", ","]
config.OWNER_ID = 111
config.ASSISTANT_ENABLED = False
config.BOT_TOKEN = ""

from fakes import check, test  # noqa: E402

from core.bot import bot
from core.db import load as db_load
from core.plugin_loader import load_plugins

db_load()
load_plugins()

import plugins.files as F  # noqa: E402


class SendClient:
    def __init__(self):
        self.calls = []
        self.snaps = []

    async def send_file(self, chat, path, **kw):
        with open(path, "rb") as f:
            self.snaps.append((os.path.basename(path), f.read()))
        self.calls.append((chat, path, kw))

    async def send_message(self, *a, **k):
        return None


class Ev:
    def __init__(self, text, rep=None, sender_id=111, chat_id=-100123):
        self.text = text
        self.sender_id = sender_id
        self.chat_id = chat_id
        self.is_private = chat_id > 0
        self.is_group = chat_id < 0
        self.reply_to = rep
        self.is_reply = rep is not None
        self.out = True
        self.id = 7
        self.message_id = 7
        self.pattern_match = None
        self.client = SendClient()
        self.sent = None
        self._rep = rep

    async def reply(self, *a, **k):
        self.sent = a[0] if a else None
        return self

    async def eor(self, *a, **k):
        return await self.reply(*a, **k)

    async def eod(self, *a, **k):
        return await self.reply(*a, **k)

    async def get_reply_message(self):
        return self._rep


class TextRep:
    """A plain text message: no media at all."""
    photo = None

    def __init__(self, text):
        self.raw_text = text
        self.message = text
        self.media = None
        self.document = None


class MediaRep:
    def __init__(self, data, filename=None, mime="application/octet-stream", text=None):
        self.raw_text = text
        self.message = text
        self.photo = None
        self.media = object()
        self._data = data
        attrs = []
        if filename:
            from telethon.tl.types import DocumentAttributeFilename
            attrs.append(DocumentAttributeFilename(file_name=filename))
        self.document = type("D", (), {"mime_type": mime, "size": len(data),
                                       "attributes": attrs})()

    async def download_media(self, file=None):
        p = os.path.join(file, "orig")
        with open(p, "wb") as f:
            f.write(self._data)
        return p


def cmds():
    out = {}
    for ev, fn in bot._event_builders:
        if getattr(fn, "__module__", None) != "plugins.files":
            continue
        pat = getattr(getattr(ev, "pattern", None), "__self__", None)
        if pat is None:
            continue
        body = re.sub(r"\\(?![swdb])", "", pat.pattern).lstrip("^")
        m = re.match(r"\.([A-Za-z_]+)", body)
        if m:
            out[m.group(1)] = (fn, pat.pattern)
    return out


C = cmds()


def run(cmd, text, rep=None, sender_id=111, chat_id=-100123):
    fn, src = C[cmd]
    ev = Ev(text, rep=rep, sender_id=sender_id, chat_id=chat_id)
    ev.pattern_match = re.compile(src).match(ev.text)
    asyncio.run(fn(ev))
    return ev


def wipe():
    if os.path.isdir(F.STORE):
        for f in os.listdir(F.STORE):
            p = os.path.join(F.STORE, f)
            if os.path.isfile(p):
                os.remove(p)


# --- the module ------------------------------------------------------------
@test
def test_all_file_commands_in_one_module():
    for n in ("save", "fetch", "ls", "delfile", "rm",
              "fileinfo", "sticker", "webshot", "json"):
        check(f".{n} in files.py", n in C, sorted(C))
    for n in ("download", "savefile", "files"):
        check(f".{n} kept as an alias", n in C, sorted(C))
    check(".del NOT taken from admin.py", "del" not in C, sorted(C))


@test
def test_store_is_defined_once():
    others = []
    for mod in ("tools", "extras", "manage", "photofx"):
        p = os.path.join(ROOT, "plugins", f"{mod}.py")
        if os.path.exists(p) and '"downloads"' in open(p).read():
            others.append(mod)
    check("no other module hardcodes the store path", not others, others)
    check("store exists and is absolute", os.path.isabs(F.STORE), F.STORE)
    check("media.py is gone", not os.path.exists(os.path.join(ROOT, "plugins", "media.py")))


# --- store -----------------------------------------------------------------
@test
def test_save_and_get_roundtrip():
    wipe()
    payload = b"the file bytes"
    ev = run("save", ".save doc.txt", rep=MediaRep(payload, "orig.bin"))
    check("save stores the file", "stored" in str(ev.sent), ev.sent)
    check("file landed in the store", os.path.isfile(os.path.join(F.STORE, "doc.txt")))
    check("bytes intact",
          open(os.path.join(F.STORE, "doc.txt"), "rb").read() == payload)

    ev = run("fetch", ".fetch doc.txt")
    check("fetch sends it back", len(ev.client.snaps) == 1, ev.client.snaps)
    if ev.client.snaps:
        check("same name", ev.client.snaps[0][0] == "doc.txt", ev.client.snaps[0][0])
        check("same bytes", ev.client.snaps[0][1] == payload)
        check("sent to the invoking chat", ev.client.calls[0][0] == -100123)
        check("sent as a document",
              ev.client.calls[0][2].get("force_document") is True)

    ev = run("ls", ".ls")
    check("ls lists it", ev.sent and "doc.txt" in str(ev.sent), str(ev.sent)[:100])
    ev = run("files", ".files")
    check(".files alias works", ev.sent and "doc.txt" in str(ev.sent))
    wipe()


@test
def test_save_dedupes_names():
    wipe()
    run("save", ".save same.txt", rep=MediaRep(b"one", "a.bin"))
    run("save", ".save same.txt", rep=MediaRep(b"two", "b.bin"))
    names = sorted(os.listdir(F.STORE))
    check("second save doesn't clobber", len(names) == 2, names)
    check("deduped name", any("(1)" in n for n in names), names)
    run("fetch", ".fetch same (1).txt")
    wipe()


@test
def test_size_cap():
    wipe()
    big = b"x" * 16
    rep = MediaRep(big, "big.bin")
    rep.document.size = F.MAX_SAVE_BYTES + 1
    ev = run("save", ".save big.bin", rep=rep)
    check("oversized download refused", ev.sent and "Too big" in str(ev.sent), ev.sent)
    check("nothing stored", os.listdir(F.STORE) == [], os.listdir(F.STORE))


# --- safety ----------------------------------------------------------------
@test
def test_resolve_cannot_escape_the_store():
    check("traversal refused", F.resolve("../etc/passwd") is None)
    check("absolute refused", F.resolve("/etc/passwd") is None)
    check("subdir refused", F.resolve("sub/x.txt") is None)
    check("backslash refused", F.resolve("sub\\x.txt") is None)
    check("nonexistent returns None", F.resolve("nope.txt") is None)
    ev = run("fetch", ".fetch ../etc/passwd")
    check(".fetch refuses traversal", ev.sent and "❌" in str(ev.sent), ev.sent)
    check("nothing sent", not ev.client.calls)
    ev = run("delfile", ".delfile ../etc/passwd force")
    check(".delfile refuses traversal", ev.sent and "❌" in str(ev.sent), ev.sent)
    check("/etc/passwd untouched", os.path.exists("/etc/passwd"))


@test
def test_get_missing_lists_alternatives():
    wipe()
    run("save", ".save here.txt", rep=MediaRep(b"x", "a.bin"))
    ev = run("fetch", ".fetch missing.txt")
    check("helpful error", ev.sent and "No stored file" in str(ev.sent), ev.sent)
    check("suggests what's available", ev.sent and "here.txt" in str(ev.sent))
    wipe()


@test
def test_delfile_requires_force():
    wipe()
    run("save", ".save bye.txt", rep=MediaRep(b"x", "a.bin"))
    ev = run("delfile", ".delfile bye.txt")
    check("refuses without force", ev.sent and "force" in str(ev.sent), ev.sent)
    check("file still there", os.path.isfile(os.path.join(F.STORE, "bye.txt")))
    ev = run("delfile", ".delfile bye.txt force")
    check("deletes with force", ev.sent and "Deleted" in str(ev.sent), ev.sent)
    check("file gone", not os.path.exists(os.path.join(F.STORE, "bye.txt")))
    ev = run("rm", ".rm bye.txt force")
    check(".rm on a missing file errors", ev.sent and "❌" in str(ev.sent), ev.sent)
    wipe()


@test
def test_store_writes_are_owner_only():
    wipe()
    for cmd, text in (("save", ".save x.txt"), ("fetch", ".fetch x.txt"),
                      ("ls", ".ls"), ("delfile", ".delfile x.txt force"),
                      ("rm", ".rm x.txt force")):
        rep = MediaRep(b"x", "a.bin") if cmd == "save" else None
        ev = run(cmd, text, rep=rep, sender_id=666)
        check(f".{cmd} refuses a non-owner",
              ev.sent and "Owner only" in str(ev.sent), ev.sent)
    check("nothing stored by a non-owner", os.listdir(F.STORE) == [])


# --- ephemeral -------------------------------------------------------------
@test
def test_ephemeral_leaves_nothing_behind():
    import glob
    before = set(glob.glob(os.path.join(F.TMP_ROOT, "*"))) if \
        os.path.isdir(F.TMP_ROOT) else set()

    run("sticker", ".sticker", rep=MediaRep(b"img", "i.jpg", "image/jpeg"))
    run("sticker", ".sticker")                    # error path

    after = set(glob.glob(os.path.join(F.TMP_ROOT, "*"))) if \
        os.path.isdir(F.TMP_ROOT) else set()
    check("no temp dirs left behind", after == before, after - before)
    check("store still empty", os.listdir(F.STORE) == [], os.listdir(F.STORE))
