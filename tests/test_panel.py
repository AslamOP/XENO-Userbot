"""Control-panel authorization + command surface."""
import asyncio
import importlib
import re

from fakes import Cap, FakeAsstClient, check, pm, test  # noqa: F401

from core import assistant as A
from core.db import delete as db_del
from core.db import get as db_get
from core.db import load as db_load
from core.plugin_loader import load_plugins

db_load()

_client = FakeAsstClient()
A.asst = _client
Cap._default_client = _client
load_plugins()
importlib.reload(importlib.import_module("plugins.control"))  # noqa: E402

CMDS = _client.builders()


@test
def test_panel_registered():
    check("panel handlers registered", len(CMDS) >= 10, list(CMDS))
    check("every pattern uses the / prefix",
          all(src.startswith(r"^/") for _, src in CMDS.values()),
          [s for _, s in CMDS.values() if not s.startswith(r"^/")][:3])


@test
def test_every_command_is_silent_for_non_owners():
    """The critical invariant: no panel command may answer a stranger."""
    leaky = []
    for name, (fn, src) in CMDS.items():
        if name == "restart":
            continue  # would execl
        for sid in (666, 777, -100):
            arg = "blacklist on" if name == "setambient" else "PREFIXES ."
            ev = Cap(sid, f"/{name} {arg}")
            ev.pattern_match = pm(src, ev.text)
            try:
                asyncio.run(fn(ev))
            except Exception as e:
                leaky.append(f"{name} raised {type(e).__name__}: {e}")
                break
            if ev.sent is not None:
                leaky.append(f"{name} answered sender {sid}: {str(ev.sent)[:60]}")
                break
    check("every command is silent for non-owners", not leaky, leaky)


@test
def test_owner_gets_answers():
    silent = []
    for name, (fn, src) in CMDS.items():
        if name == "restart":
            continue
        arg = {"setambient": "blacklist on",
               "set": "PREFIXES .",
               "get": "PREFIXES",
               "logs": "5",
               "commands": "textify"}.get(name, "x")
        ev = Cap(111, f"/{name} {arg}".rstrip())
        ev.pattern_match = pm(src, ev.text)
        try:
            asyncio.run(fn(ev))
        except Exception as e:
            silent.append(f"{name} raised {type(e).__name__}: {e}")
            continue
        if ev.sent is None:
            silent.append(f"{name} gave the owner nothing")
    check("every command answers the owner", not silent, silent)


@test
def test_no_dangerous_commands_exposed():
    forbidden = [
        "evalx", "execx", "srestart", "logsx", "broadcast", "spamx", "digest",
        "delpfp", "setpic", "setuser", "setname", "setbio", "setemoji",
        "setcolor", "dm", "forward", "savefile", "unbanall", "gucast",
        "ggban", "gkick", "gmute", "gpromote", "kickbots", "play", "dof",
    ]
    hit = [c for c in forbidden if c in CMDS]
    check("no RCE/admin commands on the panel", not hit, hit)


@test
def test_owner_id_not_writable():
    """P0-3 regression: OWNER_ID must not be settable from the panel."""
    from plugins.control import PANEL_KEYS
    check("OWNER_ID not in PANEL_KEYS", "OWNER_ID" not in PANEL_KEYS,
          sorted(PANEL_KEYS))
    ev = Cap(111, "/set OWNER_ID 999")
    ev.pattern_match = pm(CMDS["set"][1], ev.text)
    asyncio.run(CMDS["set"][0](ev))
    check("panel refuses OWNER_ID", "isn't a panel key" in str(ev.sent), ev.sent)
    import config as cfg
    check("config.OWNER_ID unchanged", cfg.OWNER_ID == 111, cfg.OWNER_ID)


@test
def test_only_allowlisted_keys_writable():
    ev = Cap(111, "/set SUDO_USERS 999")
    ev.pattern_match = pm(CMDS["set"][1], ev.text)
    asyncio.run(CMDS["set"][0](ev))
    check("refuses non-allowlisted key", "isn't a panel key" in str(ev.sent), ev.sent)
    check("and did not write it", asyncio.run(db_get("SUDO_USERS")) is None, "wrote!")

    expected = ",".join(p for p in ". ! #".split() if p)
    ev = Cap(111, "/set PREFIXES . ! #")
    ev.pattern_match = pm(CMDS["set"][1], ev.text)
    asyncio.run(CMDS["set"][0](ev))
    check("writes an allowlisted key", "PREFIXES" in str(ev.sent), ev.sent)
    check("value persisted correctly",
          asyncio.run(db_get("PREFIXES")) == expected, asyncio.run(db_get("PREFIXES")))
    asyncio.run(db_del("PREFIXES"))


@test
def test_private_only_commands_refuse_groups():
    leaky = []
    for name in ("set", "logs", "restart"):
        if name not in CMDS:
            continue
        ev = Cap(111, f"/{name} PREFIXES .", priv=False)
        ev.pattern_match = pm(CMDS[name][1], ev.text)
        try:
            asyncio.run(CMDS[name][0](ev))
        except Exception:
            pass  # restart execls; only assert it didn't reply
        if ev.sent is not None:
            leaky.append(name)
    check("private_only commands refuse group chats", not leaky, leaky)


@test
def test_panel_commands_not_in_userbot_help():
    """Panel handlers live on the other client, so `.help` must not list them."""
    from plugins.misc import _scan_commands
    mods = _scan_commands()
    names = {c for info in mods.values() for c, _ in info["cmds"]}
    # `ambient` legitimately exists on both sides (userbot `.ambient` in warden.py,
    # panel `/ambient` here) with different prefixes on different clients, so only
    # the panel-exclusive names are checked. set/get/config/unset are
    # shared with userbot plugins/settings.py; theme is shared with the
    # userbot `.theme` chooser — same UX on both clients.
    exclusive = set(CMDS) - {"ambient", "set", "get", "config", "unset", "theme"}
    check("no panel command leaked into .help",
          not (exclusive & names), sorted(exclusive & names))
    check("control module absent from .help", "control" not in mods, list(mods))
