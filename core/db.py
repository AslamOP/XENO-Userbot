import asyncio
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "xeno_db.json")

# Coalesce writes: many handlers mutate state in a burst (gban -> edit per chat,
# warn loops), and rewriting the whole JSON per mutation blocks the event loop.
FLUSH_DEBOUNCE = 2.0

_lock = asyncio.Lock()
_db = {}
_dirty = False
_flush_task = None


def _ensure():
    if os.path.isdir(DATA_DIR):
        return
    os.makedirs(DATA_DIR, exist_ok=True)


def load():
    global _db, _dirty
    _ensure()
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                _db = json.load(f)
        except Exception:
            _db = {}
    else:
        _db = {}
    _dirty = False


def _write():
    """Blocking write; only ever called from the (single) flush task."""
    _ensure()
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_PATH)


async def _flush_loop():
    global _flush_task, _dirty
    try:
        while True:
            await asyncio.sleep(FLUSH_DEBOUNCE)
            async with _lock:
                if not _dirty:
                    continue
                _dirty = False
                try:
                    await asyncio.to_thread(_write)
                except Exception:
                    _dirty = True
    except asyncio.CancelledError:
        pass
    finally:
        _flush_task = None


def _schedule():
    """Request a debounced flush. Caller must hold no lock; safe from handlers."""
    global _flush_task
    if _flush_task is None or _flush_task.done():
        _flush_task = asyncio.ensure_future(_flush_loop())


async def flush():
    """Force an immediate write and wait for it (used at shutdown)."""
    async with _lock:
        _dirty = False
        await asyncio.to_thread(_write)


async def get(key, default=None):
    async with _lock:
        return _db.get(key, default)


async def set_(key, value):
    global _dirty
    async with _lock:
        _db[key] = value
        _dirty = True
    _schedule()


async def update(key, fn, default=None):
    global _dirty
    async with _lock:
        cur = _db.setdefault(key, default)
        cur = fn(cur)
        _db[key] = cur
        _dirty = True
    _schedule()
    return cur


async def delete(key):
    global _dirty
    async with _lock:
        _db.pop(key, None)
        _dirty = True
    _schedule()