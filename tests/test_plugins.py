"""Plugin registry + behavioural spot-checks on local-only commands."""
import asyncio
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from fakes import check, test  # noqa: E402

import config  # noqa: E402

config.PREFIXES = [".", "!", "#", ","]
config.OWNER_ID = 111

from core.bot import bot  # noqa: E402
from core.db import load as db_load  # noqa: E402
from core.db import flush as db_flush  # noqa: E402
from core.plugin_loader import load_plugins  # noqa: E402

db_load()
load_plugins()


class Cap:
    def __init__(self, text, sender_id=111, priv=True):
        self.text = text
        self.sender_id = sender_id
        self.chat_id = 999
        self.is_private = priv
        self.is_group = not priv
        self.reply_to = None
        self.is_reply = False
        self.out = True
        self.id = 1
        self.message_id = 1
        self.pattern_match = None
        self.client = _fake_client()
        self.sent = None

    async def reply(self, *a, **k):
        self.sent = a[0] if a else None
        return self

    async def edit(self, *a, **k):
        return self

    async def respond(self, *a, **k):
        return self

    async def get_reply_message(self):
        return None

    async def get_sender(self):
        return type("U", (), {"id": self.sender_id, "first_name": "U",
                              "username": "u", "premium": False})()


def _fake_client():
    """Just enough client for get_me()/get_sender()."""
    class C:
        async def get_me(self):
            return type("Me", (), {"id": 111, "first_name": "Dev",
                                   "username": "dev", "phone": None,
                                   "about": None, "bot": False,
                                   "premium": False})()

        async def get_sender(self):
            return type("U", (), {"id": 111, "first_name": "U",
                                  "username": "u", "premium": False})()
    return C()


def userbot_commands():
    out = {}
    for ev, fn in bot._event_builders:
        pat = getattr(getattr(ev, "pattern", None), "__self__", None)
        if pat is None:
            continue
        src = pat.pattern.lstrip("^").replace("\\", "")
        for p in config.PREFIXES:
            if src.startswith(re.escape(p)):
                name = src[len(p):].split("(")[0]
                out.setdefault(name, fn)
                break
    return out


CMDS = userbot_commands()


def run(cmd, text=None):
    ev = Cap(text or f".{cmd}")
    asyncio.run(CMDS[cmd](ev))
    return str(ev.sent)


def run_as(cmd, text, sender_id):
    ev = Cap(text, sender_id=sender_id)
    asyncio.run(CMDS[cmd](ev))
    return ev.sent


# --- registry ---------------------------------------------------------------
@test
def test_registry():
    # 463 after the first prune, minus 6 dead commands removed since.
    check("450+ commands registered", len(CMDS) >= 450, len(CMDS))
    check("handler count sane", len(bot._event_builders) > 1000, len(bot._event_builders))


@test
def test_pruned_commands_gone():
    gone = [
        "savepw", "getpw", "delpw",        # plaintext credential store
        "wall",                            # retired Unsplash endpoint
        "qrcode-d", "base", "reverse",     # stubs / missing deps
        "strip", "cursed", "unicase", "smol", "tiny",   # identity no-ops
        "2dec", "2hex", "8hex", "16dec",   # redundant aliases
        "md4",                             # not in OpenSSL 3
        "celebrate", "cook",               # duplicate persona roast/compliment
        "pmpermit", "approve", "disapprove", "listapproved",  # dead feature
        "cmds", "helpx", "pingx", "alivex", "reload", "userinfo2",
        "settitle", "setabout", "setpfp", "unpinx", "muteall",
        "getid", "meid",
    ]
    left = [g for g in gone if g in CMDS]
    check("pruned commands absent", not left, left)


@test
def test_no_ungated_host_commands():
    """sysx/ip/digest must refuse non-owners."""
    leaks = []
    # `whoami` is deliberately ungated: it reports the caller's OWN id/name,
    # which discloses nothing. Everything else reports host state.
    for cmd, text in (("ip", ".ip"), ("digest", ".digest"),
                      ("sysinfo", ".sysinfo"), ("mem", ".mem"), ("uptime", ".uptime"),
                      ("cpu", ".cpu"), ("diskspace", ".diskspace")):
        if cmd not in CMDS:
            continue
        got = run_as(cmd, text, 666)
        if got is not None and "Owner only" not in str(got):
            leaks.append(f"{cmd} answered a non-owner: {str(got)[:60]}")
    check("host/diagnostic commands are owner-only", not leaks, leaks)


# --- local behaviour --------------------------------------------------------
@test
def test_math_guards():
    check("lcm 0 0 is handled", "0" in run("lcm", ".lcm 0 0"), run("lcm", ".lcm 0 0"))
    check("lcm 4 6 = 12", "`12`" in run("lcm", ".lcm 4 6"), run("lcm", ".lcm 4 6"))
    check("cbrt -8 is real", "-2.0" in run("cbrt", ".cbrt -8"), run("cbrt", ".cbrt -8"))
    check("sqrt -5 refused", "non-negative" in run("sqrt", ".sqrt -5"), run("sqrt", ".sqrt -5"))
    check("factorial bounded", "between" in run("factorial", ".factorial 99999"))
    check("prim bounded (P2-10)", "too large" in run("prim", ".prim 99999999999999999999"),
          run("prim", ".prim 99999999999999999999")[:90])


@test
def test_calc_python314_compat():
    """ast.Constant.n was removed in 3.14; .value is the only portable form."""
    for cmd, text in (("calc", ".calc 2+2"), ("calc2", ".calc2 2+2"),
                      ("calc", ".calc 2.5*4"), ("calc2", ".calc2 -3+1")):
        if cmd not in CMDS:
            continue
        r = run(cmd, text)
        check(f"{cmd} {text} evaluates", "Error" not in r and "Could not" not in r, r[:80])
    r = run("calc2", ".calc2 abc")
    check("calc2 rejects non-numeric", "non-numeric" in r or "Could not" in r, r[:80])


def test_calc_dos_guards():
    r = run("calc", ".calc 9**9**9")
    check("calc refuses 9**9**9", "too large" in r, r[:80])
    r = run("calc2", ".calc2 9**9**9")
    check("calc2 refuses 9**9**9", "too large" in r, r[:80])
    check("calc still works", "**14**" in run("calc", ".calc 2+3*4"), run("calc", ".calc 2+3*4"))


@test
def test_codecs():
    for enc, dec, payload in (("b32enc", "b32dec", "hello"), ("b85enc", "b85dec", "hello"),
                              ("a85enc", "a85dec", "hello"), ("urlb64", "urlb64d", "hello"),
                              ("ascii85", "a85un", "hello")):
        e = run(enc, f".{enc} {payload}")
        check(f"{enc} encodes", "error" not in e.lower(), e[:70])
        if payload in e:
            token = e.split("`")[1]
            d = run(dec, f".{dec} {token}")
            check(f"{dec} round-trips", payload in d, d[:70])


@test
def test_timezone_offline():
    r = run("timezone", ".timezone Asia/Kolkata")
    check("timezone resolves without network",
          "Asia/Kolkata" in r and "Unknown" not in r, r[:90])
    r = run("timezone", ".timezone Not/AZone")
    check("timezone rejects junk", "Unknown timezone" in r, r[:90])
    r = run("when", ".when Europe/Berlin")
    check("when resolves", "Europe/Berlin" in r, r[:90])


@test
def test_help():
    r = run("help")
    check("help renders an index", "commands" in r and "modules" in r, r[:90])
    for ghost in ("gamex", "savepw", "md4", "pmpermit"):
        check(f"help has no `{ghost}`", ghost not in r)
    r = run("help", ".help ban")
    check("help <command> works (was crashing)", "admin" in r, r[:90])
    r = run("help", ".help warden")
    check("help <module> works", "WARDEN" in r.upper(), r[:90])


@test
def test_db_roundtrip():
    async def go():
        from core.db import get, set_, delete, update
        await set_("t1", 1)
        assert await get("t1") == 1
        await update("t1", lambda v: v + 1)
        assert await get("t1") == 2
        await delete("t1")
        assert await get("t1", "gone") == "gone"
        await db_flush()

    asyncio.run(go())
    check("db set/update/delete/flush round-trips", True)


TESTS = [v for k, v in sorted(globals().items()) if getattr(v, "_is_test", False)]
