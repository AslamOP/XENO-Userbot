"""Custom plugin registry: install, list, remove, and hot-reload user scripts.

Three states, matching how Ultroid splits it:

  plugins/   ships with XENO. Never overwritable or removable from chat.
  addons/    `.install` puts user plugins here. Survives restarts, and the
             directory itself is the ownership record — no bookkeeping needed.
  data/tmp_plugins/  `.addplugin` puts session-only plugins here as TOP-LEVEL
             modules. core/custom.sweep_tmp() deletes the directory at boot, so
             a restart wipes them.

`.load` / `.unload` toggle an installed addon without deleting it, so you can
disable something suspicious and keep the file for inspection.
"""
import ast
import hashlib
import importlib
import importlib.util
import json
import os
import re
import sys
import time

from core.bot import bot, log

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Two directories, exactly like Ultroid: `plugins/` ships with XENO, `addons/`
# is for user-installed plugins. The directory IS the ownership record — no
# registry needed to tell them apart.
PLUGINS_DIR = os.path.join(ROOT, "plugins")
ADDONS_DIR = os.path.join(ROOT, "addons")

DATA_DIR = os.path.join(ROOT, "data")
# Metadata only (hash, size, when installed) for `.plugins` to display.
# Ownership is decided by which directory the file is in.
REGISTRY = os.path.join(DATA_DIR, "custom_plugins.json")

# Session-only plugins live here. Deliberately NOT inside plugins/, so
# core.plugin_loader never picks them up on a restart.
TMP_DIR = os.path.join(DATA_DIR, "tmp_plugins")

MAX_PLUGIN_BYTES = 256 * 1024
MAX_FILE_BYTES = 1024 * 1024

# Must be a valid Python identifier: the loader does
# importlib.import_module(f"plugins.{name}"), so "my-plugin.py" can never work.
VALID_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

# Official modules can never be removed or overwritten by a custom install.
ALWAYS_PROTECTED = {"manage", "control"}

# Addon names the owner has switched off with `.unload`. Stored in the registry
# under this key, so the choice survives a restart.
_DISABLED_KEY = "__disabled__"


def _disabled():
    raw = _read().get(_DISABLED_KEY, [])
    return set(raw) if isinstance(raw, list) else set()


def is_disabled(name):
    """True if the owner ran `.unload <name>` and hasn't `.load`ed it since."""
    return name in _disabled()


def set_disabled(name, off):
    """Persist an addon as disabled (or enabled)."""
    reg = _read()
    cur = reg.get(_DISABLED_KEY, [])
    if not isinstance(cur, list):
        cur = []
    if off and name not in cur:
        cur.append(name)
    elif not off and name in cur:
        cur.remove(name)
    reg[_DISABLED_KEY] = cur
    _write(reg)


def _read():
    try:
        with open(REGISTRY, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, REGISTRY)


def list_custom():
    """{name: {...}} of everything in addons/, merged with stored metadata."""
    out = {}
    reg = _read()
    try:
        names = sorted(os.listdir(ADDONS_DIR))
    except OSError:
        names = []
    for f in names:
        if not f.endswith(".py") or f.startswith("_"):
            continue
        name = f[:-3]
        meta = reg.get(name, {})
        try:
            meta = {**meta, "bytes": os.path.getsize(os.path.join(ADDONS_DIR, f))}
        except OSError:
            pass
        out[name] = meta
    return out


def is_custom(name):
    """A user plugin is anything living in addons/."""
    return os.path.exists(os.path.join(ADDONS_DIR, f"{name}.py"))


def is_protected(name):
    """True if this ships with XENO and must not be replaced or removed."""
    if name in ALWAYS_PROTECTED:
        return True
    if is_custom(name):
        return False
    return os.path.exists(os.path.join(PLUGINS_DIR, f"{name}.py"))


def official_modules():
    """Every module that ships with XENO."""
    try:
        return [f[:-3] for f in sorted(os.listdir(PLUGINS_DIR))
                if f.endswith(".py") and not f.startswith("_")]
    except OSError:
        return []


def validate_name(filename):
    """Return (module_name, error)."""
    if not filename or not filename.lower().endswith(".py"):
        return None, "Attach a `.py` file."
    name = filename[:-3]
    if name.startswith("_"):
        return None, "Module names can't start with `_`."
    if not VALID_NAME.match(name):
        return None, (
            f"`{name}` isn't a valid module name. Use letters, digits and "
            "underscores only — no dashes or dots, since it has to be "
            "importable."
        )
    return name, None


def validate_source(source, name):
    """Reject anything that isn't parseable Python. Returns an error or None."""
    try:
        ast.parse(source, filename=f"{name}.py")
    except SyntaxError as e:
        return f"Syntax error on line {e.lineno}: {e.msg}"
    except ValueError as e:
        return f"Could not parse: {e}"
    return None


def _modname(name):
    """Dotted name a module is imported under: `plugins.x` or `addons.x`."""
    if os.path.exists(os.path.join(PLUGINS_DIR, f"{name}.py")):
        return f"plugins.{name}"
    return f"addons.{name}"


def unload(name):
    """Strip every handler registered by a plugin or addon.

    Reloading a module re-runs its decorators, which would otherwise double up
    every command. Returns the number of handlers removed.
    """
    modname = _modname(name)
    mine = []
    for builder in list(getattr(bot, "_event_builders", []) or []):
        fn = builder[1]
        if getattr(fn, "__module__", None) in (modname, f"plugins.{name}"):
            mine.append(fn)
    for fn in mine:
        try:
            bot.remove_event_handler(fn)
        except Exception as e:
            log.debug(f"could not remove handler {fn}: {e}")
    return len(mine)


def _handler_count(modname):
    return len([b for b in (getattr(bot, "_event_builders", []) or [])
                if getattr(b[1], "__module__", None) == modname])


def load(name):
    """Import or hot-reload a module from plugins/ or addons/.

    Addons are loaded from their file path rather than as members of the
    `plugins` package — they live in a different directory, and pretending
    otherwise would make `plugins.<name>` resolve to the wrong file.

    Returns (ok, message).
    """
    path = os.path.join(PLUGINS_DIR, f"{name}.py")
    if not os.path.exists(path):
        path = os.path.join(ADDONS_DIR, f"{name}.py")
    if not os.path.exists(path):
        return False, f"`{name}.py` is in neither plugins/ nor addons/"

    modname = _modname(name)
    unload(name)

    try:
        if path.startswith(ADDONS_DIR):
            # File-path import: the module is not inside the `plugins` package.
            spec = importlib.util.spec_from_file_location(modname, path)
            if spec is None or spec.loader is None:
                return False, "could not build an import spec for that file"
            module = importlib.util.module_from_spec(spec)
            sys.modules[modname] = module
            try:
                spec.loader.exec_module(module)
            except BaseException:
                # Never leave a half-initialised module behind, or later
                # imports will hand out a broken object.
                sys.modules.pop(modname, None)
                raise
        elif modname in sys.modules:
            importlib.reload(sys.modules[modname])
        else:
            importlib.import_module(modname)
    except Exception as e:
        log.error(f"custom plugin '{name}' failed to load: {type(e).__name__}: {e}")
        return False, f"`{type(e).__name__}: {e}`"

    return True, f"{_handler_count(modname)} command(s) registered"


def install(name, source, origin=""):
    """Write source to plugins/<name>.py and record it. Returns (ok, message).

    The caller is responsible for having validated the name and syntax.
    """
    reg = _read()
    if is_protected(name):
        return False, f"`{name}` is a built-in module and can't be replaced."
    if len(source.encode("utf-8")) > MAX_PLUGIN_BYTES:
        return False, (
            f"Too big ({len(source.encode('utf-8')) // 1024}KB, "
            f"limit {MAX_PLUGIN_BYTES // 1024}KB)."
        )
    os.makedirs(ADDONS_DIR, exist_ok=True)
    path = os.path.join(ADDONS_DIR, f"{name}.py")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
    except OSError as e:
        return False, f"Could not write {path}: {e}"

    reg[name] = {
        "file": f"{name}.py",
        "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest()[:16],
        "bytes": len(source.encode("utf-8")),
        "added": time.strftime("%Y-%m-%d %H:%M:%S"),
        "origin": str(origin),
    }
    # A fresh install should be active, even if an older copy was `.unload`ed.
    if name in reg.get(_DISABLED_KEY, []):
        reg[_DISABLED_KEY].remove(name)
    _write(reg)
    ok, msg = load(name)
    if not ok:
        # Don't leave a broken file behind pretending to be installed.
        try:
            os.remove(path)
        except OSError:
            pass
        reg = _read()
        reg.pop(name, None)
        _write(reg)
        return False, f"Installed but failed to load, so it was rolled back. {msg}"
    return True, msg


def remove(name):
    """Delete a custom plugin and unload it. Returns (ok, message)."""
    if name in ALWAYS_PROTECTED:
        return False, f"`{name}` is protected."
    if not is_custom(name):
        if is_protected(name):
            return False, (
                f"`{name}` is a built-in module, not a custom plugin. "
                "Built-ins aren't removable through .delplugin."
            )
        return False, f"No custom plugin named `{name}`."

    unloaded = unload(name)
    try:
        os.remove(os.path.join(ADDONS_DIR, f"{name}.py"))
    except OSError as e:
        return False, f"Could not delete the file: {e}"

    reg = _read()
    reg.pop(name, None)
    reg[_DISABLED_KEY] = [n for n in reg.get(_DISABLED_KEY, []) if n != name]
    _write(reg)
    sys.modules.pop(f"plugins.{name}", None)
    sys.modules.pop(f"addons.{name}", None)
    return True, (
        f"Removed `{name}` — {unloaded} command(s) unloaded. "
        "A restart will not bring it back."
    )


# =====================================================================
# temporary plugins — this process only, wiped on restart
# =====================================================================

# In-memory only. Nothing here is written to custom_plugins.json.
_temp = {}


def temp_list():
    return dict(_temp)


def temp_name_error(name):
    """Extra checks for temp plugins, which import as TOP-LEVEL modules."""
    # Order matters: replacing our own temp plugin puts the name in sys.modules,
    # which is expected. Checking sys.modules first made updates impossible.
    if name in _temp:
        return None
    if name in sys.modules:
        return (
            f"`{name}` is already imported by the process (stdlib or another "
            "module). Pick a different name."
        )
    if name in ALWAYS_PROTECTED or is_protected(name):
        return f"`{name}` is a built-in module. Pick a different name."
    return None


def sweep_tmp():
    """Delete every temporary plugin. Called at boot so a restart kills them."""
    removed = 0
    try:
        for f in os.listdir(TMP_DIR):
            if f.endswith(".py"):
                try:
                    os.remove(os.path.join(TMP_DIR, f))
                    removed += 1
                except OSError:
                    pass
    except FileNotFoundError:
        return 0
    except OSError as e:
        log.warning(f"temp plugin sweep failed: {e}")
        return 0
    if removed:
        log.info(f"Swept {removed} temporary plugin(s) from the previous run")
    return removed


def _load_top_level(name):
    """Import/reload a module from TMP_DIR as a top-level module."""
    if TMP_DIR not in sys.path:
        sys.path.insert(0, TMP_DIR)
    unload_top(name)
    try:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)
    except Exception as e:
        log.error(f"temp plugin '{name}' failed to load: {type(e).__name__}: {e}")
        sys.modules.pop(name, None)
        return False, f"`{type(e).__name__}: {e}`"
    n = _top_handler_count(name)
    return True, f"{n} command(s) registered"


def _top_handler_count(name):
    return len([b for b in (getattr(bot, "_event_builders", []) or [])
                if getattr(b[1], "__module__", None) == name])


def temp_install(name, source, origin=""):
    """Install a session-only plugin. Returns (ok, message)."""
    err = temp_name_error(name)
    if err:
        return False, err
    if len(source.encode("utf-8")) > MAX_PLUGIN_BYTES:
        return False, (
            f"Too big ({len(source.encode('utf-8')) // 1024}KB, "
            f"limit {MAX_PLUGIN_BYTES // 1024}KB)."
        )
    os.makedirs(TMP_DIR, exist_ok=True)
    path = os.path.join(TMP_DIR, f"{name}.py")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
    except OSError as e:
        return False, f"Could not write {path}: {e}"

    ok, msg = _load_top_level(name)
    if not ok:
        try:
            os.remove(path)
        except OSError:
            pass
        return False, f"Failed to load, so it was rolled back. {msg}"

    _temp[name] = {
        "file": f"{name}.py",
        "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest()[:16],
        "bytes": len(source.encode("utf-8")),
        "added": time.strftime("%Y-%m-%d %H:%M:%S"),
        "origin": str(origin),
        "persistent": False,
    }
    return True, msg


def temp_remove(name):
    """Unload and forget a temporary plugin. Returns (ok, message)."""
    if name not in _temp:
        return False, f"No temporary plugin named `{name}`."
    unload_top(name)
    try:
        os.remove(os.path.join(TMP_DIR, f"{name}.py"))
    except OSError:
        pass
    _temp.pop(name, None)
    return True, f"`{name}` removed — gone for good, a restart wouldn't have kept it."


def unload_top(name):
    """Strip handlers registered by a top-level (temporary) module."""
    mine = [b[1] for b in (getattr(bot, "_event_builders", []) or [])
            if getattr(b[1], "__module__", None) == name]
    for fn in mine:
        try:
            bot.remove_event_handler(fn)
        except Exception as e:
            log.debug(f"could not remove handler {fn}: {e}")
    return len(mine)
