"""Custom plugin lifecycle: add, list, update, delete, and restart behaviour."""
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

PLUGIN = "zzz_demo"


# @command registers once per prefix, so one command == len(PREFIXES) handlers.
EXPECTED = len(config.PREFIXES)


def count_handlers(name):
    """Handlers for a module in either namespace (plugins.* or addons.*)."""
    mods = {f"plugins.{name}", f"addons.{name}"}
    return len([b for b in (getattr(bot, "_event_builders", []) or [])
                if getattr(b[1], "__module__", None) in mods])


def write_on_disk(name, body):
    with open(os.path.join(custom.PLUGINS_DIR, f"{name}.py"), "w") as f:
        f.write(body)


SOURCE_V1 = '''"""A demo custom plugin."""
from core.command import command


@command("demov1")
async def demov1(event):
    """Version one."""
    await event.reply("v1")
'''

SOURCE_V2 = '''"""A demo custom plugin."""
from core.command import command


@command("demov2")
async def demov2(event):
    """Version two."""
    await event.reply("v2")
'''

BROKEN = "def oops(:\n    pass\n"


def cleanup():
    for p in (custom.REGISTRY,
              os.path.join(custom.PLUGINS_DIR, f"{PLUGIN}.py"),
              os.path.join(custom.ADDONS_DIR, f"{PLUGIN}.py"),
              os.path.join(custom.TMP_DIR, f"{PLUGIN}.py")):
        if os.path.exists(p):
            os.remove(p)
    custom._temp.pop(PLUGIN, None)
    custom.unload(PLUGIN)
    for mod in (PLUGIN, f"plugins.{PLUGIN}", f"addons.{PLUGIN}"):
        sys.modules.pop(mod, None)


# --- validation -------------------------------------------------------------
@test
def test_name_validation():
    check("accepts a normal name",
          custom.validate_name("mytask.py") == ("mytask", None))
    check("rejects non-.py", custom.validate_name("mytask.txt")[1] is not None)
    check("rejects underscores-prefixed",
          custom.validate_name("_hidden.py")[1] is not None)
    check("rejects dashes (not importable)",
          custom.validate_name("my-task.py")[1] is not None)
    check("rejects dots",
          custom.validate_name("a.b.py")[1] is not None)
    check("rejects leading digit",
          custom.validate_name("1task.py")[1] is not None)
    err = custom.validate_source(BROKEN, "x")
    check("detects a syntax error", err is not None, err)
    check("accepts valid source", custom.validate_source(SOURCE_V1, "x") is None)


@test
def test_builtin_modules_are_protected():
    cleanup()
    for name in ("admin", "warden", "misc", "textify"):
        check(f"`{name}` is protected", custom.is_protected(name), name)
    check("`manage` always protected",
          "manage" in custom.ALWAYS_PROTECTED)
    check("`control` always protected",
          "control" in custom.ALWAYS_PROTECTED)

    ok, msg = custom.remove("admin")
    check("cannot delete a built-in", ok is False, msg)
    check("and the file survives", os.path.exists(
        os.path.join(custom.PLUGINS_DIR, "admin.py")))
    ok, msg = custom.remove("manage")
    check("cannot delete manage", ok is False, msg)


@test
def test_install_lifecycle():
    cleanup()
    check("starts uninstalled", not custom.is_custom(PLUGIN))
    check("0 handlers before install", count_handlers(PLUGIN) == 0)

    ok, msg = custom.install(PLUGIN, SOURCE_V1, origin="test")
    check("install succeeds", ok, msg)
    check("registered as custom", custom.is_custom(PLUGIN))
    check(f"{EXPECTED} handlers live (one per prefix)",
          count_handlers(PLUGIN) == EXPECTED, count_handlers(PLUGIN))
    check("appears in list_custom", PLUGIN in custom.list_custom())

    # update in place
    ok, msg = custom.install(PLUGIN, SOURCE_V2, origin="test")
    check("update succeeds", ok, msg)
    check("reload did NOT double-register",
          count_handlers(PLUGIN) == EXPECTED, count_handlers(PLUGIN))

    # removal
    ok, msg = custom.remove(PLUGIN)
    check("remove succeeds", ok, msg)
    check("0 handlers after removal", count_handlers(PLUGIN) == 0)
    check("file deleted", not os.path.exists(
        os.path.join(custom.ADDONS_DIR, f"{PLUGIN}.py")))
    check("no longer in registry", not custom.is_custom(PLUGIN))
    check("not in list_custom", PLUGIN not in custom.list_custom())


@test
def test_restart_reverts_to_original():
    """The user's question: after deleting, does a restart bring it back?"""
    cleanup()
    ok, _ = custom.install(PLUGIN, SOURCE_V1, origin="test")
    check("installed for the restart test", ok)

    # simulate a fresh boot: wipe in-memory state, then run the loader again
    import importlib
    import sys as _s
    custom.unload(PLUGIN)
    _s.modules.pop(f"plugins.{PLUGIN}", None)
    _s.modules.pop(f"addons.{PLUGIN}", None)

    importlib.reload(custom)          # registry is read from disk on demand
    from core.plugin_loader import load_plugins
    load_plugins()
    check("survives a restart while installed",
          count_handlers(PLUGIN) == EXPECTED, count_handlers(PLUGIN))

    custom.remove(PLUGIN)
    custom.unload(PLUGIN)
    _s.modules.pop(f"plugins.{PLUGIN}", None)
    _s.modules.pop(f"addons.{PLUGIN}", None)
    load_plugins()
    check("after delete + restart it is GONE",
          count_handlers(PLUGIN) == 0, count_handlers(PLUGIN))
    check("and .plugins won't list it", PLUGIN not in custom.list_custom())
    cleanup()


@test
def test_broken_plugin_rolls_back():
    cleanup()
    ok, msg = custom.install(PLUGIN, SOURCE_V1, origin="test")
    check("baseline install ok", ok)

    # Overwrite with syntax-valid but import-hostile code: the module raises at
    # import time. install() must roll the file and registry back.
    bad = '"""Raises on import."""\nraise RuntimeError("boom at import")\n'
    ok, msg = custom.install(PLUGIN, bad, origin="test")
    check("failed load reports failure", ok is False, msg)
    check("file rolled back", not os.path.exists(
        os.path.join(custom.PLUGINS_DIR, f"{PLUGIN}.py")))
    check("registry rolled back", not custom.is_custom(PLUGIN))
    cleanup()


@test
def test_cannot_overwrite_builtin():
    cleanup()
    ok, msg = custom.install("warden", SOURCE_V1, origin="test")
    check("refuses to overwrite a built-in", ok is False, msg)
    src = open(os.path.join(custom.PLUGINS_DIR, "warden.py")).read()
    check("warden.py untouched", "Warns" in src or len(src) > 2000, len(src))


@test
def test_size_limit():
    cleanup()
    big = '"""Big."""\nX = "' + ("a" * (custom.MAX_PLUGIN_BYTES + 100)) + '"\n'
    ok, msg = custom.install(PLUGIN, big, origin="test")
    check("rejects oversized plugin", ok is False, msg)
    check("nothing written", not os.path.exists(
        os.path.join(custom.PLUGINS_DIR, f"{PLUGIN}.py")))
    cleanup()


@test
def test_registry_persists_to_disk():
    cleanup()
    custom.install(PLUGIN, SOURCE_V1, origin="msg 42")
    reg = custom._read()
    check("registry on disk has the entry", PLUGIN in reg, list(reg))
    check("records the origin", reg[PLUGIN].get("origin") == "msg 42",
          reg.get(PLUGIN))
    check("records a hash", len(reg[PLUGIN].get("sha256", "")) == 16,
          reg.get(PLUGIN))
    cleanup()


# --- the commands themselves, through the handlers --------------------------
class Ev:
    def __init__(self, text, sender_id=111, reply=None):
        self.text = text
        self.sender_id = sender_id
        self.chat_id = 999
        self.is_private = True
        self.is_group = False
        self.reply_to = reply
        self.is_reply = reply is not None
        self.out = True
        self.id = 7
        self.message_id = 7
        self.pattern_match = None
        self.client = None
        self.sent = None

    async def reply(self, *a, **k):
        self.sent = a[0] if a else None
        return self

    async def get_reply_message(self):
        return self._rep

    async def edit(self, *a, **k):
        return self

    async def respond(self, *a, **k):
        return self


from telethon.tl.types import DocumentAttributeFilename  # noqa: E402


class FakeDoc:
    def __init__(self, text, filename):
        self._text = text
        self.document = type("D", (), {
            "size": len(text),
            "attributes": [DocumentAttributeFilename(file_name=filename)],
        })()
        self._rep = None

    async def download_media(self, file=None):
        path = os.path.join(file, "dl.py")
        with open(path, "w") as f:
            f.write(self._text)
        return path


def cmds_for(name):
    out = {}
    mod = f"plugins.{name}"
    import re
    for ev, fn in bot._event_builders:
        if getattr(fn, "__module__", None) != mod:
            continue
        pat = getattr(getattr(ev, "pattern", None), "__self__", None)
        if pat is None:
            continue
        m = re.match(r"^\\?\.?([a-z]+)", pat.pattern.replace("\\", "").lstrip("^"))
        if m:
            out[m.group(1)] = fn
    return out


@test
def test_commands_reject_non_owners():
    """Every command in manage.py must refuse a non-owner.

    All seven install code or change what the process is running, so all seven
    are owner-gated.
    """
    import asyncio
    import re as _re
    cleanup()

    c = {}
    for ev, fn in bot._event_builders:
        if getattr(fn, "__module__", None) != "plugins.manage":
            continue
        pat = getattr(getattr(ev, "pattern", None), "__self__", None)
        if pat is None:
            continue
        body = _re.sub(r"\\(?![swdb])", "", pat.pattern).lstrip("^")
        m = _re.match(r"\.([A-Za-z]+)", body)
        if m:
            c[m.group(1)] = (fn, pat.pattern)

    check("7 gated commands", len(c) == 7, sorted(c))

    class Ev:
        def __init__(self, text, sender_id=666):
            self.text = text
            self.sender_id = sender_id
            self.chat_id = 999
            self.is_private = True
            self.is_group = False
            self.reply_to = None
            self.is_reply = False
            self.out = True
            self.id = 7
            self.message_id = 7
            self.pattern_match = None
            self.client = None
            self.sent = None

        async def reply(self, *a, **k):
            self.sent = a[0] if a else None
            return self

        async def get_reply_message(self):
            return None

    for name, (fn, src) in c.items():
        ev = Ev(f".{name} zzz_demo")
        ev.pattern_match = _re.compile(src).match(ev.text)
        asyncio.run(fn(ev))
        check(f".{name} refuses a non-owner",
              ev.sent is not None and "Owner only" in str(ev.sent), ev.sent)



# --- dangerous-pattern scan ------------------------------------------------
@test
def test_safety_scan_flags_dangerous_source():
    """The scan is the gate on `.install`; it has to actually catch things."""
    from core import safety

    cases = {
        "os.system": "import os\nos.system('rm -rf /')\n",
        "subprocess": "import subprocess\nsubprocess.run(['ls'])\n",
        "shell=True": "import subprocess\nsubprocess.run('ls', shell=True)\n",
        "eval": "def f(x):\n    return eval(x)\n",
        "exec": "exec('import os')\n",
        "__import__": "m = __import__('os')\n",
        "os.remove": "import os\nos.remove('/etc/passwd')\n",
        "rmtree": "import shutil\nshutil.rmtree('/')\n",
        "etc passwd": "f = open('/etc/passwd')\n",
        "hardcoded IP": "URL = 'http://10.0.0.5/collect'\n",
    }
    for label, src in cases.items():
        hits = safety.scan(src)
        check(f"scan flags {label}", bool(hits), hits)

    # a plugin that only uses the bot's own API must pass clean
    clean = SOURCE_V1
    check("clean source passes", safety.scan(clean) == [], safety.scan(clean))

    # imports alone are not dangerous — only the calls are
    check("bare import is fine", safety.scan("import os\nimport json\n") == [])

    rpt = safety.report([("os.system", "runs a shell command")], "evil.py")
    check("report names the rule", "os.system" in rpt)
    check("report explains force", "install f" in rpt)


@test
def test_unload_load_toggle():
    """`.unload` keeps the file and remembers; `.load` brings it back."""
    cleanup()
    ok, msg = custom.install(PLUGIN, SOURCE_V1, origin="test")
    check("install for the toggle test", ok, msg)
    check("active by default", not custom.is_disabled(PLUGIN))
    check(f"{EXPECTED} handlers active", count_handlers(PLUGIN) == EXPECTED,
          count_handlers(PLUGIN))

    n = custom.unload(PLUGIN)
    check("unload strips handlers", n == EXPECTED, n)
    check("0 handlers after unload", count_handlers(PLUGIN) == 0,
          count_handlers(PLUGIN))

    custom.set_disabled(PLUGIN, True)
    check("marked disabled", custom.is_disabled(PLUGIN))
    # survives a registry round-trip, which is what makes it stick across reboots
    check("disabled persists to disk", PLUGIN in custom._disabled())

    ok, msg = custom.load(PLUGIN)
    check("load brings it back", ok, msg)
    check(f"{EXPECTED} handlers again", count_handlers(PLUGIN) == EXPECTED,
          count_handlers(PLUGIN))

    custom.set_disabled(PLUGIN, False)
    check("re-enabled", not custom.is_disabled(PLUGIN))

    # the file itself is never touched by load/unload
    check("file still in addons/", os.path.exists(
        os.path.join(custom.ADDONS_DIR, f"{PLUGIN}.py")))
    cleanup()


@test
def test_install_clears_a_previous_disable():
    """Reinstalling something you had unloaded should switch it back on."""
    cleanup()
    custom.install(PLUGIN, SOURCE_V1, origin="test")
    custom.set_disabled(PLUGIN, True)
    check("disabled before reinstall", custom.is_disabled(PLUGIN))
    ok, _ = custom.install(PLUGIN, SOURCE_V2, origin="test")
    check("reinstall ok", ok)
    check("reinstall re-enables it", not custom.is_disabled(PLUGIN))
    cleanup()


@test
def test_unload_skipped_at_boot():
    """A disabled addon must not come back when the loader runs again."""
    cleanup()
    import importlib
    import sys as _s
    from core.plugin_loader import load_plugins

    custom.install(PLUGIN, SOURCE_V1, origin="test")
    custom.unload(PLUGIN)
    custom.set_disabled(PLUGIN, True)
    for mod in (f"plugins.{PLUGIN}", f"addons.{PLUGIN}"):
        _s.modules.pop(mod, None)

    importlib.reload(custom)
    load_plugins()
    check("disabled addon stays unloaded", count_handlers(PLUGIN) == 0,
          count_handlers(PLUGIN))

    custom.set_disabled(PLUGIN, False)
    load_plugins()
    check("re-enabled addon loads at boot", count_handlers(PLUGIN) == EXPECTED,
          count_handlers(PLUGIN))
    cleanup()



TESTS = [v for k, v in sorted(globals().items()) if getattr(v, "_is_test", False)]