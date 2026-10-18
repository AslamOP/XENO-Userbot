"""Temporary vs persistent plugin lifetimes, and the addon safety scan."""
import os
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

from core import custom
from core.bot import bot
from core.db import load as db_load
from core.plugin_loader import load_plugins

db_load()
load_plugins()

TEMP = "zzz_temp"
PERS = "zzz_pers"
PREFIXES_N = len(config.PREFIXES)


def handlers(modname):
    return len([b for b in (getattr(bot, "_event_builders", []) or [])
                if getattr(b[1], "__module__", None) == modname])


def cleanup():
    for n in (TEMP, PERS):
        for d in (custom.TMP_DIR, custom.ADDONS_DIR, custom.PLUGINS_DIR):
            p = os.path.join(d, f"{n}.py")
            if os.path.exists(p):
                os.remove(p)
        for mod in (n, f"plugins.{n}", f"addons.{n}"):
            sys.modules.pop(mod, None)
        custom._temp.pop(n, None)
    custom.unload(TEMP)
    custom.unload(PERS)
    reg = custom._read()
    for n in (TEMP, PERS):
        reg.pop(n, None)
    if reg:
        custom._write(reg)
    else:
        if os.path.exists(custom.REGISTRY):
            os.remove(custom.REGISTRY)


SRC = '''"""Custom."""
from core.command import command


@command("%s")
async def cmd_%s(event):
    """Doc."""
    await event.reply("ok")
'''


# --- temporary -------------------------------------------------------------
@test
def test_temp_install_and_reload():
    cleanup()
    ok, msg = custom.temp_install(TEMP, SRC % ("ztemp", TEMP))
    check("temp install succeeds", ok, msg)
    check("live immediately", handlers(TEMP) == PREFIXES_N, handlers(TEMP))
    check("in temp_list", TEMP in custom.temp_list())
    check("NOT in the persistent registry", not custom.is_custom(TEMP))

    ok, msg = custom.temp_install(TEMP, SRC % ("ztemp2", TEMP))
    check("temp update succeeds", ok, msg)
    check("no duplicate handlers", handlers(TEMP) == PREFIXES_N, handlers(TEMP))

    ok, msg = custom.temp_remove(TEMP)
    check("temp remove succeeds", ok, msg)
    check("handlers gone", handlers(TEMP) == 0)
    cleanup()


@test
def test_temp_name_guards():
    cleanup()
    for bad, why in (("os", "stdlib"), ("json", "stdlib"),
                     ("warden", "built-in module"), ("manage", "always protected")):
        err = custom.temp_name_error(bad)
        check(f"temp refuses `{bad}` ({why})", err is not None, err)
    check("temp allows a fresh name", custom.temp_name_error("mything") is None)


@test
def test_temp_swept_on_restart():
    """A restart must delete session plugins and leave persistent ones."""
    cleanup()
    ok, _ = custom.temp_install(TEMP, SRC % ("ztemp", TEMP))
    check("temp installed", ok)
    ok, _ = custom.install(PERS, SRC % ("zpers", PERS), origin="test")
    check("persistent installed", ok)

    files = [f for f in os.listdir(custom.TMP_DIR)] if os.path.isdir(custom.TMP_DIR) else []
    check("temp file on disk", f"{TEMP}.py" in files, files)

    # simulate a fresh process
    custom.unload_top(TEMP)
    sys.modules.pop(TEMP, None)
    custom._temp.clear()
    removed = custom.sweep_tmp()

    check("sweep reported a removal", removed >= 1, removed)
    left = os.listdir(custom.TMP_DIR) if os.path.isdir(custom.TMP_DIR) else []
    check("temp dir empty after sweep", f"{TEMP}.py" not in left, left)
    check("temp not loaded on restart", handlers(TEMP) == 0, handlers(TEMP))
    check("persistent file survives the sweep",
          os.path.exists(os.path.join(custom.ADDONS_DIR, f"{PERS}.py")))
    check("persistent still registered", custom.is_custom(PERS))
    cleanup()


# --- persistent ------------------------------------------------------------
@test
def test_persistent_install_remove():
    cleanup()
    ok, msg = custom.install(PERS, SRC % ("zpers", PERS), origin="test")
    check("persistent install ok", ok, msg)
    check("in list_custom", PERS in custom.list_custom())
    check("not in temp_list", PERS not in custom.temp_list())
    check("file in addons/", os.path.exists(
        os.path.join(custom.ADDONS_DIR, f"{PERS}.py")))
    ok, msg = custom.remove(PERS)
    check("persistent remove ok", ok, msg)
    check("file gone", not os.path.exists(
        os.path.join(custom.ADDONS_DIR, f"{PERS}.py")))
    check("registry cleaned", not custom.is_custom(PERS))
    cleanup()


@test
def test_same_name_both_lifetimes():
    """A temp and a persistent plugin can share a name — different namespaces."""
    cleanup()
    ok, _ = custom.temp_install(TEMP, SRC % ("ztemp", TEMP))
    check("temp installed", ok)
    ok, m = custom.install(PERS, SRC % ("zpers", PERS))
    check("persistent installed under a different name", ok, m)
    check("temp unaffected", handlers(TEMP) == PREFIXES_N)
    check("persistent unaffected", handlers(f"addons.{PERS}") == PREFIXES_N)
    cleanup()


# --- built-in protection ------------------------------------------------------
@test
def test_builtins_still_protected():
    for n in ("admin", "warden", "manage", "control"):
        check(f"`{n}` protected", custom.is_protected(n), n)
        ok, _ = custom.remove(n)
        check(f"`{n}` not removable", ok is False)
        ok, _ = custom.temp_remove(n)
        check(f"`{n}` not temp-removable", ok is False)


# --- the commands themselves ------------------------------------------------
import asyncio  # noqa: E402
import re  # noqa: E402

from telethon.tl.types import DocumentAttributeFilename  # noqa: E402


class Ev:
    def __init__(self, text, sender_id=111, rep=None):
        self.text = text
        self.sender_id = sender_id
        self.chat_id = 999
        self.is_private = True
        self.is_group = False
        self.reply_to = rep
        self.is_reply = rep is not None
        self.out = True
        self.id = 7
        self.message_id = 7
        self.pattern_match = None
        self.client = None
        self.sent = None
        self._rep = rep

    async def reply(self, *a, **k):
        self.sent = a[0] if a else None
        return self

    async def get_reply_message(self):
        return self._rep

    async def edit(self, *a, **k):
        return self

    async def respond(self, *a, **k):
        return self


class Doc:
    """A replied .py document."""
    def __init__(self, text, filename):
        self.raw_text = None
        self.message = None
        self.document = type("D", (), {
            "size": len(text),
            "attributes": [DocumentAttributeFilename(file_name=filename)],
        })()
        self._text = text

    async def download_media(self, file=None):
        p = os.path.join(file, "dl.py")
        with open(p, "w") as f:
            f.write(self._text)
        return p


class Txt:
    """A replied text message."""
    def __init__(self, text):
        self.raw_text = text
        self.message = text
        self.document = None


def mgr():
    """{command_name: (handler, pattern_source)} for plugins/manage.py."""
    out = {}
    for ev, fn in bot._event_builders:
        if getattr(fn, "__module__", None) != "plugins.manage":
            continue
        pat = getattr(getattr(ev, "pattern", None), "__self__", None)
        if pat is None:
            continue
        src = pat.pattern
        # Drop the caret and the escapes command() adds. Keep \s/\w/\d: a
        # blanket replace turns "\s" into "s" and mangles the pattern.
        body = re.sub(r"\\(?![swdb])", "", src).lstrip("^")
        m = re.match(r"\.([A-Za-z]+)", body)
        if m:
            out[m.group(1)] = (fn, src)
    return out


@test
def test_manage_commands_registered():
    """manage.py is plugins-only now; file handling moved to files.py."""
    c = mgr()
    expected = {"addplugin", "delplugin", "install", "uninstall", "plugins",
                "load", "unload"}
    for n in expected:
        check(f".{n} registered", n in c, sorted(c))
    check("manage is 7 commands", set(c) == expected, sorted(c))
    check(".mkfile stays gone", "mkfile" not in c, sorted(c))
    check(".files no longer in manage", "files" not in c, sorted(c))


@test
def test_privileged_manage_commands_reject_non_owners():
    """Every manage.py command installs code or changes the process."""
    cleanup()
    c = mgr()
    for name in ("addplugin", "delplugin", "install", "uninstall", "plugins",
                 "load", "unload"):
        fn, src = c[name]
        ev = Ev(f".{name} x", sender_id=666)
        ev.pattern_match = re.compile(src).match(ev.text)
        asyncio.run(fn(ev))
        check(f".{name} refuses a non-owner",
              ev.sent is not None and "Owner only" in str(ev.sent), ev.sent)


@test
def test_addplugin_vs_install():
    cleanup()
    c = mgr()
    add_fn, add_src = c["addplugin"]
    ins_fn, ins_src = c["install"]

    ev = Ev(".addplugin", rep=Doc(SRC % ("zcmdt", TEMP), f"{TEMP}.py"))
    asyncio.run(add_fn(ev))
    check(".addplugin installs", ev.sent and "Added" in str(ev.sent), ev.sent)
    check("says session-only", ev.sent and "restart deletes it" in str(ev.sent), ev.sent)
    check("temp is live", handlers(TEMP) == PREFIXES_N, handlers(TEMP))
    check("not persistent", not custom.is_custom(TEMP))
    check("temp file is outside plugins/",
          os.path.exists(os.path.join(custom.TMP_DIR, f"{TEMP}.py"))
          and not os.path.exists(os.path.join(custom.PLUGINS_DIR, f"{TEMP}.py")))

    ev = Ev(".install", rep=Doc(SRC % ("zcmdi", PERS), f"{PERS}.py"))
    asyncio.run(ins_fn(ev))
    check(".install installs", ev.sent and "Installed" in str(ev.sent), ev.sent)
    check("says it persists", ev.sent and "Survives restarts" in str(ev.sent), ev.sent)
    check("persistent file in addons/", os.path.exists(
        os.path.join(custom.ADDONS_DIR, f"{PERS}.py")))
    check("persistent in registry", custom.is_custom(PERS))

    # built-in protection through the commands
    ev = Ev(".install", rep=Doc(SRC % ("zzz", "x"), "warden.py"))
    asyncio.run(ins_fn(ev))
    check(".install refuses built-ins", ev.sent and "built-in" in str(ev.sent), ev.sent)
    ev = Ev(".addplugin", rep=Doc(SRC % ("zzz", "x"), "warden.py"))
    asyncio.run(add_fn(ev))
    check(".addplugin refuses built-in names",
          ev.sent and "built-in" in str(ev.sent), ev.sent)

    # removal
    ev = Ev(f".delplugin {TEMP}")
    asyncio.run(c["delplugin"][0](ev))
    check(".delplugin removes temp", ev.sent and "removed" in str(ev.sent), ev.sent)
    check("temp handlers gone", handlers(TEMP) == 0)

    ev = Ev(f".uninstall {PERS}")
    asyncio.run(c["uninstall"][0](ev))
    check(".uninstall removes persistent", ev.sent and "Removed" in str(ev.sent), ev.sent)
    check("persistent file gone", not os.path.exists(
        os.path.join(custom.PLUGINS_DIR, f"{PERS}.py")))
    cleanup()


TESTS = [v for k, v in sorted(globals().items()) if getattr(v, "_is_test", False)]
