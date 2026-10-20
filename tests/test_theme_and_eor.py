"""Theme system + edit-or-reply (eor/eod) + userbot config commands."""
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import config  # noqa: E402

config.PREFIXES = [".", "!", "#", ","]
config.OWNER_ID = 111
config.ASSISTANT_ENABLED = False
config.BOT_TOKEN = ""

from fakes import check, test  # noqa: E402

from core import sage  # noqa: E402
from core import wrappers as W  # noqa: E402
from core.db import load as db_load  # noqa: E402
from core.db import set_ as db_set  # noqa: E402

db_load()


# --- fake message for eor ---------------------------------------------------
class FakeMsg:
    def __init__(self, out=True, edit_boom=None):
        self.out = out
        self.edited = []
        self.replied = []
        self.deleted = False
        self._edit_boom = edit_boom

    async def edit(self, text=None, **k):
        if self._edit_boom:
            raise self._edit_boom
        self.edited.append(text)
        return self

    async def reply(self, text=None, **k):
        self.replied.append(text)
        return self

    async def delete(self):
        self.deleted = True


# --- eor / eod --------------------------------------------------------------
@test
def test_eor_outgoing_edits_in_place():
    m = FakeMsg(out=True)
    out = asyncio.run(W.eor(m, "hello"))
    check("outgoing eor edits (no reply)", m.edited == ["hello"] and not m.replied, (m.edited, m.replied))
    check("eor returns the message", out is m)


@test
def test_eor_incoming_replies():
    m = FakeMsg(out=False)
    asyncio.run(W.eor(m, "hi"))
    check("incoming eor replies (not edit)", m.replied == ["hi"] and not m.edited, (m.edited, m.replied))


@test
def test_eor_edit_failure_falls_back_to_reply():
    m = FakeMsg(out=True, edit_boom=RuntimeError("cannot edit"))
    asyncio.run(W.eor(m, "fallback"))
    check("edit failure → fresh reply", m.replied == ["fallback"], (m.edited, m.replied))


@test
def test_eor_file_forces_reply():
    m = FakeMsg(out=True)
    asyncio.run(W.eor(m, "pic", file=object()))
    check("file= forces a reply even when outgoing", m.replied == ["pic"] and not m.edited,
          (m.edited, m.replied))


@test
def test_eod_is_eor_with_timer():
    m = FakeMsg(out=True)
    asyncio.run(W.eod(m, "bye"))
    check("eod edits like eor", m.edited == ["bye"], m.edited)


@test
def test_message_monkeypatched():
    from telethon.tl.custom.message import Message
    check("Message.eor patched", hasattr(Message, "eor"))
    check("Message.eod patched", hasattr(Message, "eod"))


# --- theme system -----------------------------------------------------------
@test
def test_theme_catalogue():
    check("8 themes", len(sage.THEMES) == 8, list(sage.THEMES))
    check("void is plain", sage.THEMES["void"] == "", sage.THEMES["void"])
    check("neon accent present", sage.THEMES["neon"] == " ▍ ", repr(sage.THEMES["neon"]))


@test
def test_set_theme_updates_cache_and_confirmations():
    sage.set_theme("neon")
    check("cache name", sage.current_theme() == "neon", sage.current_theme())
    check("accent cached", sage.accent_now() == " ▍ ", repr(sage.accent_now()))
    check("ack is themed", sage.ack().startswith(" ▍ "), sage.ack())
    check("done is themed", sage.done().startswith(" ▍ "), sage.done())
    check("err is themed", sage.err("x").startswith(" ▍ "), sage.err("x"))


@test
def test_void_theme_has_no_accent():
    sage.set_theme("void")
    check("void → no accent", sage.accent_now() == "", repr(sage.accent_now()))
    check("void ack unprefixed", not sage.ack().startswith(" "), repr(sage.ack()))
    sage.set_theme("neon")


@test
def test_unknown_theme_falls_back():
    sage.set_theme("not-a-theme")
    check("unknown name → default", sage.current_theme() == sage.DEFAULT_THEME, sage.current_theme())
    sage.set_theme("neon")


@test
def test_load_theme_reads_db():
    asyncio.run(db_set("theme:current", "cyber"))
    got = asyncio.run(sage.load_theme())
    check("load_theme picks db value", got == "cyber", got)
    check("accent matches cyber", sage.accent_now() == sage.THEMES["cyber"], repr(sage.accent_now()))
    sage.set_theme("neon")
