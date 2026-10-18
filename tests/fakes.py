"""XENO offline test suite — no network, no Telegram session.

    python tests/run.py

Every test drives the real code paths with fakes. The point is regression
coverage for the things that actually broke: the BotFather dialogue, panel
authorization, and the "the assistant must never take the userbot down" promise.
"""
import asyncio
import os
import re
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ.setdefault("API_ID", "1234567")
os.environ.setdefault("API_HASH", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("OWNER_ID", "111")

import config  # noqa: E402

config.PREFIXES = [".", "!", "#", ","]
config.OWNER_ID = 111
config.ASSISTANT_PREFIX = "/"
config.ASSISTANT_ENABLED = True
config.ASSISTANT_NAME = "Assistant Bot"
config.ASSISTANT_USERNAME = ""
config.BOT_TOKEN = ""
config.AUTO_BOTFATHER = True

_RESULTS = []


def check(name, cond, detail=""):
    _RESULTS.append((name, bool(cond), "" if cond else str(detail)[:200]))


def test(fn):
    """Register a test function. Each gets a fresh event loop."""
    fn._is_test = True
    return fn


# ===========================================================================
# fakes
# ===========================================================================
class FakeMe:
    def __init__(self, username="thedev", first="Dev", uid=1234567890):
        self.id = uid
        self.username = username
        self.first_name = first


class FakeBotFather:
    """BotFather that replies *to* whatever is sent.

    opts: no_slots, reject_names (count), taken (count)
    """

    def __init__(self, username="thedev", boom=None, **opts):
        self.me = FakeMe(username)
        self.opts = opts
        self.boom = boom          # raise this on send_message
        self.sent = []
        self.phase = "idle"
        self.name_tries = 0
        self.username_tries = 0
        self.reply = "Send /newbot to create a bot."

    async def __call__(self, req):
        return None

    async def get_me(self):
        return self.me

    def _react(self, text):
        o = self.opts
        if text.startswith("/"):
            if text == "/newbot":
                self.reply = ("That I cannot do." if o.get("no_slots")
                              else "Alright, a new bot. How are we going to call it?")
                self.phase = "name"
                return
            self.reply = "Send /newbot to create a bot."
            return
        if self.phase == "name":
            self.name_tries += 1
            if self.name_tries <= o.get("reject_names", 0):
                self.reply = "Sorry, botname is too long."
            else:
                self.reply = "Good. Now choose a username for your bot."
                self.phase = "username"
            return
        if self.phase == "username":
            self.username_tries += 1
            if self.username_tries <= o.get("taken", 0):
                self.reply = "Sorry, that username is already taken."
            else:
                self.reply = ("Done! Use this token to access the HTTP API: "
                              "`1234567:AAHfakeTOKEN`")
            return
        self.reply = "Send /newbot to create a bot."

    async def send_message(self, chat, text, **k):
        if self.boom:
            raise self.boom
        self.sent.append(text)
        self._react(text)
        return None

    async def get_messages(self, chat, limit=1):
        return [type("M", (), {"text": self.reply})()]


class FakeAsstClient:
    """Stands in for TelegramClient so handlers can be registered offline."""
    _event_builders = []

    def __init__(self):
        self._event_builders = []
        self.disconnected = False

    def add_event_handler(self, fn, ev=None):
        self._event_builders.append((ev, fn))

    def remove_event_handler(self, *a, **k):
        return True

    async def get_me(self):
        return FakeMe("xeno_panel_bot", "Panel", 42)

    async def disconnect(self):
        self.disconnected = True

    def builders(self):
        out = {}
        for ev, fn in self._event_builders:
            pat = getattr(getattr(ev, "pattern", None), "__self__", None)
            if pat is None:
                continue
            m = re.match(r"^\^/([^(\\]+)", pat.pattern)
            if m:
                out[m.group(1)] = (fn, pat.pattern)
        return out


class Cap:
    """Minimal event object."""

    _default_client = None

    def __init__(self, sender_id, text, priv=True, client=None):
        self.text = text
        self.sender_id = sender_id
        self.chat_id = 999
        self.is_private = priv
        self.is_group = not priv
        self.reply_to = None
        self.is_reply = False
        self.out = False
        self.id = 1
        self.message_id = 1
        self.pattern_match = None
        self.client = client or Cap._default_client
        self.sent = None
        self.buttons = None

    async def reply(self, *a, **k):
        self.sent = a[0] if a else None
        self.buttons = k.get("buttons")
        return self

    async def answer(self, *a, **k):
        return self

    async def edit(self, *a, **k):
        return self

    async def get_reply_message(self):
        return None


def pm(src, text):
    """pattern_match the way Telethon builds it."""
    return re.compile(src).match(text)
