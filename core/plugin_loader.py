import importlib
import logging
import os
import pkgutil

log = logging.getLogger("plugins")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PLUGINS_DIR = os.path.join(ROOT, "plugins")
ADDONS_DIR = os.path.join(ROOT, "addons")


def _disabled():
    """Addon names the owner switched off with `.unload`."""
    try:
        from core import custom

        return custom._disabled()
    except Exception:
        return set()


def load_plugins():
    """Import every module in plugins/, then every active module in addons/.

    plugins/ comes first so a shipped module always wins a name collision with
    an addon — an installed script can't quietly replace core code.
    """
    imported = []
    skipped = []

    for _, name, _ in sorted(pkgutil.iter_modules([PLUGINS_DIR])):
        if name.startswith("_"):
            continue
        try:
            importlib.import_module(f"plugins.{name}")
            imported.append(name)
            log.info(f"Loaded plugin: {name}")
        except Exception as e:
            log.error(f"Failed to load plugin '{name}': {e}")

    # Addons import by file path; custom.load() owns that code path so the
    # sys.modules bookkeeping stays identical to a hot install.
    from core import custom

    off = _disabled()
    try:
        addon_names = sorted(n for _, n, _ in pkgutil.iter_modules([ADDONS_DIR]))
    except (FileNotFoundError, OSError):
        addon_names = []

    for name in addon_names:
        if name.startswith("_"):
            continue
        if name in imported:
            # A built-in already claimed this name — don't shadow it.
            skipped.append(f"{name} (name taken by a built-in)")
            log.warning(f"Skipped addon '{name}': a built-in plugin owns that name")
            continue
        if name in off:
            skipped.append(f"{name} (unloaded)")
            log.info(f"Skipped disabled addon: {name}")
            continue
        ok, msg = custom.load(name)
        if ok:
            imported.append(name)
        else:
            log.error(f"Failed to load addon '{name}': {msg}")

    log.info(f"Loaded {len(imported)} plugins: {', '.join(imported)}")
    if skipped:
        log.info(f"Not loaded: {', '.join(skipped)}")
    return imported
